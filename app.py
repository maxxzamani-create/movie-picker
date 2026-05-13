import threading
import webbrowser
from io import BytesIO

import customtkinter as ctk
import requests
from PIL import Image, ImageTk

import logo as logo_mod
import storage
import tmdb

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT   = "#00B5CC"   # Rick's portal teal
GREEN    = "#39FF14"   # portal green
DARK_BG  = "#060e0e"   # near-black with teal tint
SURFACE  = "#0d1a1a"   # dark teal surface
SURFACE2 = "#0d2626"   # slightly lighter teal surface


class MoviePickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.prefs = storage.load()
        self._current_movie = None
        self._poster_image = None
        self._resolved_actor: tuple[int, str] | None = None

        self.title("The Movie Genie")
        self.geometry("1340x760")
        self.minsize(1100, 660)

        # Window icon
        logo_img = logo_mod.make_logo(64)
        self._icon_photo = ImageTk.PhotoImage(logo_img)
        self.iconphoto(True, self._icon_photo)

        self._genre_vars: dict[int, ctk.BooleanVar] = {}
        self._provider_vars: dict[int, ctk.BooleanVar] = {}
        self._mood_buttons: dict[str, ctk.CTkButton] = {}
        self._actor_debounce_id = None
        self._actor_dropdown: ctk.CTkToplevel | None = None
        self._current_mood = "none"          # safe default before UI loads
        self._wrap_resize_id = None          # debounce handle for wraplength updates
        self._fetching = False               # guard against stacked fetch threads

        self._build_ui()
        self._load_prefs_into_ui()
        self._update_watched_count()

        if not self.prefs["api_key"]:
            self.after(200, self._show_api_dialog)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=290)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=230)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self._build_history_panel()
        # Single window-level resize listener — fires only on window resize, not child layout
        self.bind("<Configure>", self._on_window_resize)
        self.after(300, self._apply_wraplength)   # set correct wraplength after first render

    def _build_sidebar(self):
        sidebar = ctk.CTkScrollableFrame(self, width=280, corner_radius=0,
                                         fg_color=(DARK_BG, DARK_BG))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        row = 0

        # Header — logo + name
        hdr = ctk.CTkFrame(sidebar, fg_color="transparent")
        hdr.grid(row=row, column=0, sticky="ew", padx=10, pady=(12, 4)); row += 1
        hdr.grid_columnconfigure(1, weight=1)

        logo_img = logo_mod.make_logo(56)
        self._sidebar_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img,
                                           size=(56, 56))
        ctk.CTkLabel(hdr, image=self._sidebar_logo, text="").grid(
            row=0, column=0, rowspan=2, padx=(0, 8))

        ctk.CTkLabel(hdr, text="THE MOVIE",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=GREEN).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(hdr, text="GENIE",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=ACCENT).grid(row=1, column=1, sticky="nw")

        ctk.CTkButton(hdr, text="API Key", width=72, height=26, fg_color="#0d2626",
                      hover_color="#1a3a3a", command=self._show_api_dialog).grid(
            row=0, column=2, rowspan=2)

        row = self._sep(sidebar, row)

        # Language
        ctk.CTkLabel(sidebar, text="Language", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        self._language_var = ctk.StringVar(value=self.prefs.get("language", ""))
        lang_menu = ctk.CTkOptionMenu(sidebar, variable=self._language_var,
                                       values=list(tmdb.LANGUAGES.values()),
                                       command=self._on_language_change)
        lang_menu.grid(row=row, column=0, sticky="ew", padx=14, pady=(0, 6)); row += 1

        row = self._sep(sidebar, row)

        # Discovery mode
        ctk.CTkLabel(sidebar, text="Discovery Mode", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        disc_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        disc_frame.grid(row=row, column=0, sticky="ew", padx=14); row += 1
        disc_frame.grid_columnconfigure((0, 1), weight=1)
        self._hidden_gem_var = ctk.BooleanVar(value=self.prefs.get("hidden_gem", False))
        ctk.CTkRadioButton(disc_frame, text="Popular", variable=self._hidden_gem_var,
                           value=False).grid(row=0, column=0, sticky="w", pady=2)
        ctk.CTkRadioButton(disc_frame, text="Hidden Gems", variable=self._hidden_gem_var,
                           value=True).grid(row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(sidebar, text="Hidden Gems = high rated, low popularity",
                     font=ctk.CTkFont(size=10), text_color="#2a6a6a").grid(
            row=row, column=0, sticky="w", padx=14); row += 1

        row = self._sep(sidebar, row)

        # Mood
        ctk.CTkLabel(sidebar, text="Mood", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        ctk.CTkLabel(sidebar, text="Overrides genre checkboxes when active",
                     font=ctk.CTkFont(size=10), text_color="#2a6a6a").grid(
            row=row, column=0, sticky="w", padx=14); row += 1
        mood_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        mood_frame.grid(row=row, column=0, sticky="ew", padx=14, pady=(4, 4)); row += 1
        mood_frame.grid_columnconfigure((0, 1, 2), weight=1)
        moods = list(tmdb.MOODS.items())
        for i, (key, info) in enumerate(moods):
            btn = ctk.CTkButton(mood_frame, text=info["label"], height=28,
                                font=ctk.CTkFont(size=11),
                                fg_color=SURFACE2, hover_color="#0a3a3a",
                                command=lambda k=key: self._select_mood(k))
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
            self._mood_buttons[key] = btn

        row = self._sep(sidebar, row)

        # Actor search
        ctk.CTkLabel(sidebar, text="Actor / Director", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        actor_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        actor_frame.grid(row=row, column=0, sticky="ew", padx=14); row += 1
        actor_frame.grid_columnconfigure(0, weight=1)
        self._actor_entry = ctk.CTkEntry(actor_frame, placeholder_text="McLovin",
                                          fg_color=SURFACE, border_color=ACCENT,
                                          text_color="white", placeholder_text_color="#2a6a6a")
        self._actor_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._actor_entry.bind("<KeyRelease>", self._on_actor_type)
        self._actor_entry.bind("<FocusOut>", lambda e: self.after(150, self._hide_actor_dropdown))
        self._actor_entry.bind("<Escape>", lambda e: self._hide_actor_dropdown())
        ctk.CTkButton(actor_frame, text="X", width=28, height=28, fg_color="#0d2626",
                      hover_color="#1a3a3a",
                      command=self._clear_actor).grid(row=0, column=1)
        self._actor_status = ctk.CTkLabel(sidebar, text="", font=ctk.CTkFont(size=11),
                                           text_color=GREEN)
        self._actor_status.grid(row=row, column=0, sticky="w", padx=14); row += 1

        row = self._sep(sidebar, row)

        # Genres
        ctk.CTkLabel(sidebar, text="Genres", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        genre_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        genre_frame.grid(row=row, column=0, sticky="ew", padx=14); row += 1
        genre_frame.grid_columnconfigure((0, 1), weight=1)
        for i, (gid, gname) in enumerate(tmdb.GENRES.items()):
            var = ctk.BooleanVar()
            self._genre_vars[gid] = var
            ctk.CTkCheckBox(genre_frame, text=gname, variable=var,
                            font=ctk.CTkFont(size=12),
                            checkbox_width=16, checkbox_height=16).grid(
                row=i // 2, column=i % 2, sticky="w", padx=4, pady=2)

        row = self._sep(sidebar, row)

        # Year range
        ctk.CTkLabel(sidebar, text="Release Year", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        yr = ctk.CTkFrame(sidebar, fg_color="transparent")
        yr.grid(row=row, column=0, sticky="ew", padx=14); row += 1
        yr.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(yr, text="From").grid(row=0, column=0)
        self._year_from = ctk.CTkEntry(yr, width=60, placeholder_text="1980",
                                        fg_color=SURFACE, border_color=ACCENT,
                                        text_color="white", placeholder_text_color="#2a6a6a")
        self._year_from.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(yr, text="To").grid(row=0, column=2)
        self._year_to = ctk.CTkEntry(yr, width=60, placeholder_text="2026",
                                      fg_color=SURFACE, border_color=ACCENT,
                                      text_color="white", placeholder_text_color="#2a6a6a")
        self._year_to.grid(row=0, column=3, padx=4)

        row = self._sep(sidebar, row)

        # Min rating
        ctk.CTkLabel(sidebar, text="Minimum Rating", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        self._rating_label = ctk.CTkLabel(sidebar, text="6.0 / 10")
        self._rating_label.grid(row=row, column=0, sticky="w", padx=14); row += 1
        self._rating_slider = ctk.CTkSlider(sidebar, from_=0, to=10, number_of_steps=20,
                                             command=self._on_rating_change)
        self._rating_slider.grid(row=row, column=0, sticky="ew", padx=14, pady=(0, 4)); row += 1

        row = self._sep(sidebar, row)

        # Streaming
        ctk.CTkLabel(sidebar, text="Streaming (US)", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=row, column=0, sticky="w", padx=14, pady=(4, 2))
        row += 1
        prov_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        prov_frame.grid(row=row, column=0, sticky="ew", padx=14); row += 1
        prov_frame.grid_columnconfigure((0, 1), weight=1)
        for i, (pid, pname) in enumerate(tmdb.PROVIDERS.items()):
            var = ctk.BooleanVar()
            self._provider_vars[pid] = var
            ctk.CTkCheckBox(prov_frame, text=pname, variable=var,
                            font=ctk.CTkFont(size=12),
                            checkbox_width=16, checkbox_height=16).grid(
                row=i // 2, column=i % 2, sticky="w", padx=4, pady=2)

        row = self._sep(sidebar, row)

        # Buttons
        self._pick_btn = ctk.CTkButton(sidebar, text="Pick a Movie", height=44,
                                        font=ctk.CTkFont(size=15, weight="bold"),
                                        fg_color=ACCENT, hover_color="#b0070f",
                                        command=self._pick_movie)
        self._pick_btn.grid(row=row, column=0, sticky="ew", padx=14, pady=(0, 6)); row += 1
        ctk.CTkButton(sidebar, text="Save Preferences", height=34, fg_color="#0d2626",
                      hover_color="#1a3a3a",
                      command=self._save_prefs).grid(row=row, column=0, sticky="ew",
                                                     padx=14, pady=(0, 14))

    def _sep(self, parent, row):
        ctk.CTkFrame(parent, height=1, fg_color="#0d2626").grid(
            row=row, column=0, sticky="ew", padx=14, pady=6)
        return row + 1

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color=("#080d0d", "#080d0d"), corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        status_row = ctk.CTkFrame(main, fg_color="transparent")
        status_row.grid(row=0, column=0, pady=(16, 0), padx=20, sticky="ew")
        status_row.grid_columnconfigure(0, weight=1)

        self._status = ctk.CTkLabel(status_row, text="Set your preferences and click Pick a Movie",
                                    font=ctk.CTkFont(size=13), text_color="#888")
        self._status.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(status_row, text="↺  Refresh", width=90, height=26,
                      font=ctk.CTkFont(size=12),
                      fg_color="#0d2626", hover_color="#1a3a3a",
                      command=self._reset_ui).grid(row=0, column=1, padx=(8, 0))

        card = ctk.CTkFrame(main, fg_color="transparent")
        card.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self._poster_label = ctk.CTkLabel(card, text="", width=220)
        self._poster_label.grid(row=0, column=0, sticky="n", padx=(0, 20))

        info = ctk.CTkFrame(card, fg_color=(SURFACE, SURFACE), corner_radius=12)
        info.grid(row=0, column=1, sticky="nsew")
        info.grid_columnconfigure(0, weight=1)
        info.grid_rowconfigure(0, weight=1)

        # ── Scrollable text area (left column) ───────────────────────────────
        info_scroll = ctk.CTkScrollableFrame(info, fg_color="transparent",
                                              corner_radius=0)
        info_scroll.grid(row=0, column=0, sticky="nsew")
        info_scroll.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(info_scroll, text="", wraplength=320,
                                          font=ctk.CTkFont(size=26, weight="bold"),
                                          justify="left", anchor="w")
        self._title_label.pack(fill="x", padx=20, pady=(20, 4))

        self._meta_label = ctk.CTkLabel(info_scroll, text="", text_color="#4dcfcf",
                                         font=ctk.CTkFont(size=13), justify="left",
                                         anchor="w")
        self._meta_label.pack(fill="x", padx=20, pady=(0, 8))

        scores_row = ctk.CTkFrame(info_scroll, fg_color="transparent")
        scores_row.pack(fill="x", padx=20, pady=(0, 12))
        self._rating_badge = ctk.CTkLabel(scores_row, text="",
                                           font=ctk.CTkFont(size=14, weight="bold"),
                                           fg_color=SURFACE2, corner_radius=8, padx=10, pady=4)
        self._rating_badge.grid(row=0, column=0, padx=(0, 8))
        self._rt_badge = ctk.CTkLabel(scores_row, text="",
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color=SURFACE2, corner_radius=8, padx=10, pady=4)
        self._rt_badge.grid(row=0, column=1)

        self._overview_label = ctk.CTkLabel(info_scroll, text="", wraplength=320,
                                             font=ctk.CTkFont(size=13), justify="left",
                                             text_color="#ddd", anchor="w")
        self._overview_label.pack(fill="x", padx=20, pady=(0, 12))

        self._director_label = ctk.CTkLabel(info_scroll, text="", wraplength=320,
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             justify="left", text_color=ACCENT, anchor="w")
        self._director_label.pack(fill="x", padx=20, pady=(0, 4))

        self._cast_label = ctk.CTkLabel(info_scroll, text="", wraplength=320,
                                         font=ctk.CTkFont(size=12), justify="left",
                                         text_color="#ccc", anchor="w")
        self._cast_label.pack(fill="x", padx=20, pady=(0, 10))

        self._genres_label = ctk.CTkLabel(info_scroll, text="", text_color=ACCENT,
                                           font=ctk.CTkFont(size=12), justify="left",
                                           anchor="w")
        self._genres_label.pack(fill="x", padx=20, pady=(0, 6))

        self._streaming_label = ctk.CTkLabel(info_scroll, text="", text_color=GREEN,
                                              font=ctk.CTkFont(size=12), justify="left",
                                              anchor="w")
        self._streaming_label.pack(fill="x", padx=20, pady=(0, 12))

        # ── Action buttons — 3-column grid below the details ─────────────────
        btn_grid = ctk.CTkFrame(info_scroll, fg_color="transparent")
        btn_grid.pack(fill="x", padx=16, pady=(4, 20))
        btn_grid.grid_columnconfigure((0, 1, 2), weight=1)

        self._again_btn = ctk.CTkButton(btn_grid, text="🎲  Pick Again", height=40,
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         fg_color="#FF2020", hover_color="#CC0000",
                                         command=self._pick_movie, state="disabled")
        self._again_btn.grid(row=0, column=0, padx=4, pady=(0, 6), sticky="ew")

        self._trailer_btn = ctk.CTkButton(btn_grid, text="▶  Watch Trailer", height=40,
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           fg_color="#FF7700", hover_color="#CC5500",
                                           command=self._open_trailer, state="disabled")
        self._trailer_btn.grid(row=0, column=1, padx=4, pady=(0, 6), sticky="ew")

        self._tmdb_btn = ctk.CTkButton(btn_grid, text="🔗  View on TMDB", height=40,
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        fg_color="#E8D000", hover_color="#B8A400",
                                        text_color="#000000",
                                        command=self._open_tmdb, state="disabled")
        self._tmdb_btn.grid(row=0, column=2, padx=4, pady=(0, 6), sticky="ew")

        self._watchlist_btn = ctk.CTkButton(btn_grid, text="➕  Add to Watchlist", height=40,
                                             font=ctk.CTkFont(size=13, weight="bold"),
                                             fg_color="#00CC44", hover_color="#009933",
                                             command=self._add_watchlist, state="disabled")
        self._watchlist_btn.grid(row=1, column=0, padx=4, sticky="ew")

        self._watched_btn = ctk.CTkButton(btn_grid, text="✓  Already Watched", height=40,
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           fg_color="#1177FF", hover_color="#0055CC",
                                           command=self._mark_watched, state="disabled")
        self._watched_btn.grid(row=1, column=1, padx=4, sticky="ew")

        self._dislike_btn = ctk.CTkButton(btn_grid, text="👎  Don't Like That", height=40,
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           fg_color="#9900FF", hover_color="#7700CC",
                                           command=self._mark_disliked, state="disabled")
        self._dislike_btn.grid(row=1, column=2, padx=4, sticky="ew")

        # Keep a reference to the wrappable labels for dynamic resizing
        self._wrap_labels = (
            self._title_label, self._overview_label, self._director_label,
            self._cast_label, self._genres_label, self._streaming_label,
        )

        wl_frame = ctk.CTkFrame(main, fg_color=("#060e0e", "#060e0e"),
                                 corner_radius=0, height=120)
        wl_frame.grid(row=2, column=0, sticky="ew")
        wl_frame.grid_columnconfigure(0, weight=1)
        wl_frame.grid_propagate(False)

        wl_hdr = ctk.CTkFrame(wl_frame, fg_color="transparent")
        wl_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 2))
        wl_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wl_hdr, text="Watchlist", font=ctk.CTkFont(weight="bold"),
                     text_color="#4dcfcf").grid(row=0, column=0, sticky="w")
        self._watched_count_label = ctk.CTkLabel(wl_hdr, text="0 movies marked as watched",
                                                  font=ctk.CTkFont(size=11), text_color="#2a5a5a")
        self._watched_count_label.grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(wl_hdr, text="Clear Watched", width=100, height=22, fg_color="#3a2a2a",
                      hover_color="#5a3a3a",
                      command=self._clear_watched).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(wl_hdr, text="Clear Watchlist", width=110, height=22, fg_color="#0d2626",
                      hover_color="#1a3a3a", command=self._clear_watchlist).grid(row=0, column=3)

        self._watchlist_scroll = ctk.CTkScrollableFrame(wl_frame, orientation="horizontal",
                                                         height=72, fg_color="transparent")
        self._watchlist_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self._refresh_watchlist_ui()

    # ── Preferences ──────────────────────────────────────────────────────────

    def _load_prefs_into_ui(self):
        for gid, var in self._genre_vars.items():
            var.set(gid in self.prefs["genres"])
        for pid, var in self._provider_vars.items():
            var.set(pid in self.prefs["providers"])
        self._year_from.delete(0, "end")
        self._year_from.insert(0, str(self.prefs["year_from"]))
        self._year_to.delete(0, "end")
        self._year_to.insert(0, str(self.prefs["year_to"]))
        self._rating_slider.set(self.prefs["min_rating"])
        self._rating_label.configure(text=f"{self.prefs['min_rating']:.1f} / 10")
        self._hidden_gem_var.set(self.prefs.get("hidden_gem", False))
        # Language
        lang_label = tmdb.LANGUAGES.get(self.prefs.get("language", ""), "Any Language")
        self._language_var.set(lang_label)
        # Mood
        self._select_mood(self.prefs.get("mood", "none"))
        # Actor
        if self.prefs.get("actor"):
            self._actor_entry.insert(0, self.prefs["actor"])
            self._actor_status.configure(text=f"Filtering by: {self.prefs['actor']}")

    def _collect_prefs(self) -> dict:
        try:
            yf = int(self._year_from.get())
            yt = int(self._year_to.get())
        except ValueError:
            yf, yt = 1980, 2026
        lang_label = self._language_var.get()
        lang_code = next((k for k, v in tmdb.LANGUAGES.items() if v == lang_label), "")
        return {
            **self.prefs,
            "genres": [g for g, v in self._genre_vars.items() if v.get()],
            "providers": [p for p, v in self._provider_vars.items() if v.get()],
            "year_from": yf,
            "year_to": yt,
            "min_rating": round(self._rating_slider.get(), 1),
            "language": lang_code,
            "hidden_gem": self._hidden_gem_var.get(),
            "mood": self._current_mood,
            "actor": self._actor_entry.get().strip(),
        }

    def _save_prefs(self):
        self.prefs = self._collect_prefs()
        storage.save(self.prefs)
        self._status.configure(text="Preferences saved.")

    def _on_rating_change(self, val):
        self._rating_label.configure(text=f"{float(val):.1f} / 10")

    def _on_language_change(self, _val):
        pass

    def _on_window_resize(self, event):
        """Fires on window resize. Filter to root window only to avoid child noise."""
        if event.widget is not self:
            return
        if self._wrap_resize_id:
            self.after_cancel(self._wrap_resize_id)
        self._wrap_resize_id = self.after(120, self._apply_wraplength)

    def _apply_wraplength(self):
        """Set wraplength from current window width. Called once at startup and on resize."""
        self._wrap_resize_id = None
        # window - sidebar(290) - history(230) - poster+gap(240) - scrollbar(20) - padding(40)
        w = max(200, self.winfo_width() - 820)
        for lbl in getattr(self, "_wrap_labels", ()):
            try:
                lbl.configure(wraplength=w)
            except Exception:
                pass

    # ── Mood ─────────────────────────────────────────────────────────────────

    def _select_mood(self, key: str):
        self._current_mood = key
        for k, btn in self._mood_buttons.items():
            if k == key and key != "none":
                btn.configure(fg_color=ACCENT, hover_color="#b0070f")
            else:
                btn.configure(fg_color=SURFACE2, hover_color="#0a3a3a")

    # ── Actor ─────────────────────────────────────────────────────────────────

    def _clear_actor(self):
        self._actor_entry.delete(0, "end")
        self._actor_status.configure(text="")
        self._resolved_actor = None
        self._hide_actor_dropdown()

    def _on_actor_type(self, _event=None):
        if self._actor_debounce_id:
            self.after_cancel(self._actor_debounce_id)
        query = self._actor_entry.get().strip()
        if len(query) < 2:
            self._hide_actor_dropdown()
            return
        self._actor_debounce_id = self.after(350, self._fetch_actor_suggestions, query)

    def _fetch_actor_suggestions(self, query: str):
        api_key = self.prefs.get("api_key", "")
        if not api_key:
            return
        threading.Thread(target=self._actor_search_thread,
                         args=(query, api_key), daemon=True).start()

    def _actor_search_thread(self, query: str, api_key: str):
        results = tmdb.search_actors(api_key, query)
        self.after(0, self._show_actor_dropdown, results)

    def _show_actor_dropdown(self, results: list[dict]):
        self._hide_actor_dropdown()
        if not results:
            return
        # Position dropdown below the entry widget
        entry = self._actor_entry
        x = entry.winfo_rootx()
        y = entry.winfo_rooty() + entry.winfo_height() + 2
        w = entry.winfo_width() + 36  # match entry + X button width

        drop = ctk.CTkToplevel(self)
        drop.overrideredirect(True)
        drop.geometry(f"{w}x{min(len(results), 7) * 46}+{x}+{y}")
        drop.attributes("-topmost", True)
        drop.configure(fg_color=SURFACE)
        drop.grid_columnconfigure(0, weight=1)
        self._actor_dropdown = drop

        for i, person in enumerate(results):
            name = person["name"]
            known = person["known_for"]
            label = f"{name}\n{known}" if known else name
            font_size = 11

            btn = ctk.CTkButton(
                drop, text=label, anchor="w", height=42,
                font=ctk.CTkFont(size=font_size),
                fg_color=SURFACE, hover_color="#0a2e2e",
                corner_radius=0, border_width=0,
                command=lambda p=person: self._select_actor(p),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=2, pady=1)

    def _hide_actor_dropdown(self):
        if self._actor_dropdown:
            try:
                self._actor_dropdown.destroy()
            except Exception:
                pass
            self._actor_dropdown = None

    def _select_actor(self, person: dict):
        self._hide_actor_dropdown()
        self._resolved_actor = (person["id"], person["name"])
        self._actor_entry.delete(0, "end")
        self._actor_entry.insert(0, person["name"])
        self._actor_status.configure(text=f"Selected: {person['name']}", text_color=GREEN)

    # ── API key dialog ────────────────────────────────────────────────────────

    def _show_api_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("The Movie Genie — API Keys")
        dlg.geometry("440x220")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.geometry("460x340")
        ctk.CTkLabel(dlg, text="API Keys",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 2))

        # TMDB
        ctk.CTkLabel(dlg, text="TMDB Key  —  themoviedb.org/settings/api",
                     text_color="#4dcfcf", font=ctk.CTkFont(size=12)).pack()
        tmdb_entry = ctk.CTkEntry(dlg, width=380, placeholder_text="Paste TMDB API key")
        tmdb_entry.pack(pady=(6, 12))
        if self.prefs["api_key"]:
            tmdb_entry.insert(0, self.prefs["api_key"])

        # OMDb
        ctk.CTkLabel(dlg, text="OMDb Key (optional, for Rotten Tomatoes scores)",
                     text_color="#4dcfcf", font=ctk.CTkFont(size=12)).pack()
        ctk.CTkLabel(dlg, text="Free key at omdbapi.com/apikey.aspx",
                     text_color="#2a6a6a", font=ctk.CTkFont(size=11)).pack()
        omdb_entry = ctk.CTkEntry(dlg, width=380, placeholder_text="Paste OMDb API key")
        omdb_entry.pack(pady=(6, 12))
        if self.prefs.get("omdb_api_key"):
            omdb_entry.insert(0, self.prefs["omdb_api_key"])

        status = ctk.CTkLabel(dlg, text="", text_color="#f77")
        status.pack()

        def save_key():
            key = tmdb_entry.get().strip()
            status.configure(text="Validating…", text_color="#4dcfcf")
            dlg.update()
            if tmdb.validate_key(key):
                self.prefs["api_key"] = key
                self.prefs["omdb_api_key"] = omdb_entry.get().strip()
                storage.save(self.prefs)
                dlg.destroy()
                self._status.configure(text="API keys saved. Ready to pick!")
            else:
                status.configure(text="Invalid TMDB key. Try again.", text_color="#f77")

        ctk.CTkButton(dlg, text="Save Keys", fg_color=ACCENT, hover_color="#b0070f",
                      command=save_key).pack(pady=8)

    # ── Movie picking ─────────────────────────────────────────────────────────

    def _pick_movie(self):
        if not self.prefs.get("api_key"):
            self._show_api_dialog()
            return
        if self._fetching:
            return                          # don't stack threads
        self._fetching = True
        prefs = self._collect_prefs()
        self._pick_btn.configure(state="disabled", text="Searching…")
        self._again_btn.configure(state="disabled")
        self._trailer_btn.configure(state="disabled")
        self._tmdb_btn.configure(state="disabled")
        self._watchlist_btn.configure(state="disabled")
        self._watched_btn.configure(state="disabled")
        self._dislike_btn.configure(state="disabled")
        self._status.configure(text="Finding a movie…")
        self._clear_card()
        threading.Thread(target=self._fetch_thread, args=(prefs,), daemon=True).start()

    def _fetch_thread(self, prefs: dict):
        try:
            # Use pre-resolved actor ID if available, otherwise look it up
            actor_id = None
            actor_name = prefs.get("actor", "").strip()
            if actor_name:
                if self._resolved_actor and self._resolved_actor[1] == actor_name:
                    actor_id = self._resolved_actor[0]
                else:
                    result = tmdb.search_actor(prefs["api_key"], actor_name)
                    if result:
                        actor_id, resolved = result
                        self.after(0, lambda n=resolved: self._actor_status.configure(
                            text=f"Selected: {n}", text_color=GREEN))
                    else:
                        self.after(0, lambda: self._actor_status.configure(
                            text="Actor not found", text_color="#f77"))

            # Determine genre IDs: mood overrides checkboxes
            mood_key = prefs.get("mood", "none")
            if mood_key and mood_key != "none":
                genre_ids = tmdb.MOODS[mood_key]["genres"]
            else:
                genre_ids = prefs["genres"]

            watched_ids = {w["id"] for w in prefs.get("watched", [])}
            disliked_ids = {d["id"] for d in prefs.get("disliked", [])}
            excluded_ids = watched_ids | disliked_ids

            # Avoid genres disliked 2+ times (unless user explicitly selected them)
            disliked_genres = prefs.get("disliked_genres", {})
            avoided_genres = {int(gid) for gid, count in disliked_genres.items()
                             if count >= 2 and int(gid) not in genre_ids}

            movie = tmdb.fetch_random_movie(
                api_key=prefs["api_key"],
                genre_ids=genre_ids,
                year_from=prefs["year_from"],
                year_to=prefs["year_to"],
                min_rating=prefs["min_rating"],
                provider_ids=prefs["providers"],
                language=prefs.get("language", ""),
                hidden_gem=prefs.get("hidden_gem", False),
                actor_id=actor_id,
                excluded_ids=excluded_ids,
                without_genre_ids=avoided_genres,
            )
            self.after(0, self._on_movie_fetched, movie)
        except Exception as exc:
            self.after(0, self._on_fetch_error, str(exc))

    def _on_fetch_error(self, msg: str):
        self._fetching = False
        self._pick_btn.configure(state="normal", text="Pick a Movie")
        self._status.configure(text=f"Error — check your connection. ({msg})")

    def _on_movie_fetched(self, movie):
        self._fetching = False
        self._pick_btn.configure(state="normal", text="Pick a Movie")
        if not movie:
            self._status.configure(
                text="No movies found. Try relaxing your filters.")
            return
        self._current_movie = movie
        self._display_movie(movie)
        self._log_history(movie, "Suggested")
        self._again_btn.configure(state="normal")
        self._trailer_btn.configure(
            state="normal" if movie.get("trailer_url") else "disabled",
            text="▶  Watch Trailer" if movie.get("trailer_url") else "No Trailer Found",
        )
        self._tmdb_btn.configure(state="normal")
        self._watchlist_btn.configure(state="normal")
        self._watched_btn.configure(state="normal")
        self._dislike_btn.configure(state="normal")
        gem = "  Hidden Gem" if movie.get("popularity", 99) < 15 else ""
        self._status.configure(text=f"Here's your pick!{gem}")

    def _display_movie(self, m: dict):
        self._title_label.configure(text=m["title"])
        runtime = f"  •  {m['runtime']} min" if m.get("runtime") else ""
        self._meta_label.configure(text=f"{m['year']}{runtime}")
        stars = "★" * round(m["rating"] / 2) + "☆" * (5 - round(m["rating"] / 2))
        self._rating_badge.configure(
            text=f"{stars}  {m['rating']}/10  ({m['votes']:,} votes)")

        # Full overview — no truncation
        self._overview_label.configure(text=m["overview"] or "No overview available.")

        # Director
        if m.get("director"):
            self._director_label.configure(text=f"🎬  Directed by {m['director']}")
        else:
            self._director_label.configure(text="")

        # Cast
        if m.get("cast"):
            cast_str = "🎭  " + " • ".join(m["cast"])
            self._cast_label.configure(text=cast_str)
        else:
            self._cast_label.configure(text="")

        self._genres_label.configure(text="  ".join(m["genres"]) if m["genres"] else "")
        if m["streaming"]:
            self._streaming_label.configure(text="Streaming: " + " • ".join(m["streaming"]))
        else:
            self._streaming_label.configure(text="Not on your selected streaming services")
        self._rt_badge.configure(text="RT: …" if self.prefs.get("omdb_api_key") else "")
        if m.get("poster"):
            threading.Thread(target=self._load_poster, args=(m["poster"],), daemon=True).start()
        else:
            self._poster_label.configure(image=None, text="No poster")
        if self.prefs.get("omdb_api_key") and m.get("imdb_id"):
            threading.Thread(target=self._load_rt_score,
                             args=(m["imdb_id"],), daemon=True).start()

    def _load_rt_score(self, imdb_id: str):
        score = tmdb.fetch_rt_score(self.prefs.get("omdb_api_key", ""), imdb_id)
        def update():
            if score:
                pct = int(score.replace("%", ""))
                color = "#ff4444" if pct < 60 else "#f5a623" if pct < 75 else "#21c55d"
                self._rt_badge.configure(text=f"RT  {score}", text_color=color)
            else:
                self._rt_badge.configure(text="RT: N/A", text_color="#2a6a6a")
        self.after(0, update)

    def _load_poster(self, url: str):
        try:
            data = requests.get(url, timeout=10).content
            img = Image.open(BytesIO(data)).resize((220, 330), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 330))
            self.after(0, lambda: self._poster_label.configure(image=ctk_img, text=""))
            self._poster_image = ctk_img
        except Exception:
            pass

    def _reset_ui(self):
        """Unstick the UI — clear fetch lock, re-enable all buttons, reset status."""
        self._fetching = False
        self._pick_btn.configure(state="normal", text="Pick a Movie")
        has_movie = self._current_movie is not None
        for btn in (self._again_btn, self._tmdb_btn, self._watchlist_btn,
                    self._watched_btn, self._dislike_btn):
            btn.configure(state="normal" if has_movie else "disabled")
        self._trailer_btn.configure(
            state="normal" if (has_movie and self._current_movie.get("trailer_url")) else "disabled",
            text="▶  Watch Trailer" if (has_movie and self._current_movie.get("trailer_url"))
                 else ("No Trailer Found" if has_movie else "▶  Watch Trailer"),
        )
        self._status.configure(
            text=f"Ready — showing {self._current_movie['title']}" if has_movie
            else "Set your preferences and click Pick a Movie",
            text_color="#888",
        )

    def _clear_card(self):
        for lbl in (self._title_label, self._meta_label, self._rating_badge,
                    self._rt_badge, self._overview_label, self._director_label,
                    self._cast_label, self._genres_label, self._streaming_label):
            lbl.configure(text="")
        self._poster_label.configure(image=None, text="")

    # ── Actions ───────────────────────────────────────────────────────────────

    # ── History panel ────────────────────────────────────────────────────────

    def _build_history_panel(self):
        panel = ctk.CTkFrame(self, width=230, corner_radius=0,
                             fg_color=(DARK_BG, DARK_BG))
        panel.grid(row=0, column=2, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="SUGGESTED HISTORY",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=ACCENT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="Clear", width=48, height=22,
                      fg_color="#0d2626", hover_color="#1a3a3a",
                      font=ctk.CTkFont(size=11),
                      command=self._clear_history).grid(row=0, column=1)

        # Scrollable list
        self._history_scroll = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", corner_radius=0)
        self._history_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._history_scroll.grid_columnconfigure(0, weight=1)

        self._refresh_history_ui()

    def _log_history(self, movie: dict, action: str):
        """Add action to history. If movie already in history, append action."""
        history = self.prefs.setdefault("history", [])

        # Find existing entry for this movie
        for entry in history:
            if entry["id"] == movie["id"]:
                if action not in entry["actions"]:
                    entry["actions"].append(action)
                storage.save(self.prefs)
                self._refresh_history_ui()
                return

        # New entry
        entry = {
            "id":      movie["id"],
            "title":   movie["title"],
            "year":    movie["year"],
            "rating":  movie["rating"],
            "actions": [action],
        }
        history.insert(0, entry)          # newest first
        if len(history) > 60:             # cap at 60
            history.pop()
        storage.save(self.prefs)
        self._refresh_history_ui()

    def _refresh_history_ui(self):
        for w in self._history_scroll.winfo_children():
            w.destroy()

        history = self.prefs.get("history", [])
        if not history:
            ctk.CTkLabel(self._history_scroll,
                         text="No history yet.\nPick a movie to start!",
                         text_color="#2a6a6a",
                         font=ctk.CTkFont(size=12),
                         justify="center").pack(pady=20)
            return

        ACTION_COLORS = {
            "Suggested":  ("#0d2626", "#4dcfcf"),
            "Trailer":    ("#1a3a00", "#39FF14"),
            "Watchlist":  ("#004a3a", "#00d4a0"),
            "Watched":    ("#0d2a2a", "#4dcfcf"),
            "Disliked":   ("#3a1a00", "#ff8c00"),
            "Skip":       ("#1a1a1a", "#555555"),
        }

        for entry in history:
            mid = entry["id"]

            card = ctk.CTkFrame(self._history_scroll,
                                fg_color=SURFACE, corner_radius=8)
            card.pack(fill="x", padx=2, pady=3)
            card.grid_columnconfigure(0, weight=1)

            # Title row with a small reload button
            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=(8, 6), pady=(6, 0))
            title_row.grid_columnconfigure(0, weight=1)

            title = entry["title"]
            if len(title) > 20:
                title = title[:19] + "…"
            ctk.CTkLabel(title_row, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w", text_color="white").grid(row=0, column=0, sticky="w")

            ctk.CTkButton(title_row, text="▶", width=26, height=22,
                          font=ctk.CTkFont(size=11),
                          fg_color="#0d3030", hover_color=ACCENT,
                          command=lambda m=mid: self._load_movie_by_id(m)).grid(
                row=0, column=1, padx=(4, 0))

            # Year + rating
            ctk.CTkLabel(card,
                         text=f"{entry['year']}  ★ {entry['rating']}",
                         font=ctk.CTkFont(size=11),
                         text_color="#4dcfcf", anchor="w").pack(
                fill="x", padx=8, pady=(2, 4))

            # Action chips
            chips = ctk.CTkFrame(card, fg_color="transparent")
            chips.pack(fill="x", padx=6, pady=(0, 6))
            for action in entry["actions"]:
                bg, fg = ACTION_COLORS.get(action, ("#0d2626", "#4dcfcf"))
                ctk.CTkLabel(chips, text=action,
                             font=ctk.CTkFont(size=10),
                             fg_color=bg, text_color=fg,
                             corner_radius=6, padx=6, pady=2).pack(
                    side="left", padx=2)

            # Entire card is also clickable (click anywhere to reload)
            self._make_clickable(card, lambda m=mid: self._load_movie_by_id(m))

    def _clear_history(self):
        self.prefs["history"] = []
        storage.save(self.prefs)
        self._refresh_history_ui()

    # ── History card click — reload a previous movie ─────────────────────────

    def _make_clickable(self, widget, callback):
        """Bind a click callback to a widget and its CTk-level children only.
        Stops at CTkButton (has its own command) and never recurses into raw
        tk.Canvas / tk.Scrollbar internals which would break scrolling."""
        import tkinter as _tk
        safe_types = (ctk.CTkFrame, ctk.CTkLabel)
        try:
            widget.bind("<Button-1>", lambda e: callback())
            widget.configure(cursor="hand2")
        except Exception:
            pass
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                continue          # keep its own command, don't override
            if isinstance(child, (_tk.Canvas, _tk.Scrollbar)):
                continue          # never touch internal tk primitives
            if isinstance(child, safe_types):
                self._make_clickable(child, callback)

    def _load_movie_by_id(self, movie_id: int):
        """Re-fetch and display a movie from its TMDB ID (called from history panel)."""
        if not self.prefs.get("api_key"):
            return
        self._status.configure(text="Loading movie details…")
        self._pick_btn.configure(state="disabled", text="Loading…")
        self._again_btn.configure(state="disabled")
        self._trailer_btn.configure(state="disabled")
        self._tmdb_btn.configure(state="disabled")
        self._watchlist_btn.configure(state="disabled")
        self._watched_btn.configure(state="disabled")
        self._dislike_btn.configure(state="disabled")
        self._clear_card()
        threading.Thread(target=self._fetch_by_id_thread,
                         args=(movie_id,), daemon=True).start()

    def _fetch_by_id_thread(self, movie_id: int):
        try:
            movie = tmdb.fetch_movie_by_id(self.prefs["api_key"], movie_id)
            self.after(0, self._on_movie_reloaded, movie)
        except Exception as exc:
            self.after(0, self._on_fetch_error, str(exc))

    def _on_movie_reloaded(self, movie):
        """Display a re-fetched movie without adding a new history entry."""
        self._fetching = False
        self._pick_btn.configure(state="normal", text="Pick a Movie")
        if not movie:
            self._status.configure(text="Could not load movie details.")
            return
        self._current_movie = movie
        self._display_movie(movie)
        self._again_btn.configure(state="normal")
        self._trailer_btn.configure(
            state="normal" if movie.get("trailer_url") else "disabled",
            text="▶  Watch Trailer" if movie.get("trailer_url") else "No Trailer Found",
        )
        self._tmdb_btn.configure(state="normal")
        self._watchlist_btn.configure(state="normal")
        self._watched_btn.configure(state="normal")
        self._dislike_btn.configure(state="normal")
        gem = "  Hidden Gem" if movie.get("popularity", 99) < 15 else ""
        self._status.configure(text=f"Re-loaded from history: {movie['title']}{gem}")

    def _open_trailer(self):
        if self._current_movie and self._current_movie.get("trailer_url"):
            self._log_history(self._current_movie, "Trailer")
            webbrowser.open(self._current_movie["trailer_url"])

    def _open_tmdb(self):
        if self._current_movie:
            webbrowser.open(self._current_movie["tmdb_url"])

    def _add_watchlist(self):
        m = self._current_movie
        if not m:
            return
        if any(w["id"] == m["id"] for w in self.prefs["watchlist"]):
            self._status.configure(text=f'"{m["title"]}" is already in your watchlist.')
            return
        self.prefs["watchlist"].append({"id": m["id"], "title": m["title"], "year": m["year"]})
        storage.save(self.prefs)
        self._refresh_watchlist_ui()
        self._log_history(m, "Watchlist")
        self._status.configure(text=f'Added "{m["title"]}" to watchlist.')

    def _mark_disliked(self):
        m = self._current_movie
        if not m:
            return
        # Add to disliked list
        if not any(d["id"] == m["id"] for d in self.prefs["disliked"]):
            self.prefs["disliked"].append({"id": m["id"], "title": m["title"],
                                           "year": m["year"], "genres": m["genres"]})
        # Tally genre dislikes using TMDB genre IDs
        genre_map = {v: k for k, v in tmdb.GENRES.items()}
        dg = self.prefs.setdefault("disliked_genres", {})
        for genre_name in m.get("genres", []):
            gid = genre_map.get(genre_name)
            if gid:
                dg[str(gid)] = dg.get(str(gid), 0) + 1

        storage.save(self.prefs)
        self._log_history(m, "Disliked")

        # Build a human-readable note about avoided genres
        avoided = [tmdb.GENRES[int(gid)] for gid, cnt in dg.items()
                   if cnt >= 2 and int(gid) in tmdb.GENRES]
        note = f"  Avoiding: {', '.join(avoided)}" if avoided else ""
        self._status.configure(
            text=f'Noted! Skipping "{m["title"]}" and similar.{note}')
        self._pick_movie()

    def _mark_watched(self):
        m = self._current_movie
        if not m:
            return
        if any(w["id"] == m["id"] for w in self.prefs["watched"]):
            self._pick_movie()
            return
        self.prefs["watched"].append({"id": m["id"], "title": m["title"], "year": m["year"]})
        storage.save(self.prefs)
        self._update_watched_count()
        self._log_history(m, "Watched")
        self._status.configure(text=f'Marked "{m["title"]}" as watched — finding something else…')
        self._pick_movie()

    def _clear_watched(self):
        self.prefs["watched"] = []
        storage.save(self.prefs)
        self._update_watched_count()

    def _update_watched_count(self):
        count = len(self.prefs.get("watched", []))
        self._watched_count_label.configure(
            text=f"{count} movie{'s' if count != 1 else ''} marked as watched"
        )

    def _clear_watchlist(self):
        self.prefs["watchlist"] = []
        storage.save(self.prefs)
        self._refresh_watchlist_ui()

    def _refresh_watchlist_ui(self):
        for w in self._watchlist_scroll.winfo_children():
            w.destroy()
        if not self.prefs["watchlist"]:
            ctk.CTkLabel(self._watchlist_scroll, text="Your watchlist is empty",
                         text_color="#2a5a5a").pack(side="left", padx=8)
            return
        for item in self.prefs["watchlist"]:
            ctk.CTkLabel(self._watchlist_scroll,
                         text=f"{item['title']} ({item['year']})",
                         fg_color=SURFACE2, corner_radius=8,
                         padx=10, pady=4,
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=4)


def run():
    app = MoviePickerApp()
    app.mainloop()


if __name__ == "__main__":
    run()
