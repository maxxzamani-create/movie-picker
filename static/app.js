/* ── State ─────────────────────────────────────────────────────────────── */
let state = {
  prefs:         {},
  currentMoods:  new Set(),   // multi-select — any of these moods
  resolvedActor: null,        // { id, name }
  currentMovie:  null,
  fetching:      false,
  mediaType:     "movie",     // "movie" | "tv"
};

/* ── API helpers ───────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  return res.json();
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

const noun = () => state.mediaType === "tv" ? "show" : "movie";
const nounCap = () => state.mediaType === "tv" ? "Show" : "Movie";

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  state.prefs = await api("/api/prefs");
  state.mediaType = state.prefs.media_type || "movie";
  applyMediaType(state.mediaType, { silent: true });
  loadPrefsIntoUI();
  refreshHistory();
  refreshWatchlist();

  if (!state.prefs.api_key) {
    openApiModal();
  }
});

/* ── Preferences ───────────────────────────────────────────────────────── */
function loadPrefsIntoUI() {
  const p = state.prefs;

  // Language
  const langSel = document.getElementById("language");
  langSel.value = p.language || "";

  // Discovery mode
  document.querySelector(`input[name="discovery"][value="${p.hidden_gem ? "1" : "0"}"]`).checked = true;

  // Moods (multi-select)
  state.currentMoods = new Set(p.moods || []);
  document.querySelectorAll(".mood-btn").forEach(btn => {
    btn.classList.toggle("active", state.currentMoods.has(btn.dataset.mood));
  });

  // Actor
  if (p.actor) {
    document.getElementById("actor-input").value = p.actor;
    document.getElementById("actor-status").textContent = `Filtering by: ${p.actor}`;
  }

  // Movie Genres
  (p.genres || []).forEach(gid => {
    const cb = document.getElementById(`genre-${gid}`);
    if (cb) cb.checked = true;
  });

  // TV Genres
  (p.tv_genres || []).forEach(gid => {
    const cb = document.getElementById(`tv-genre-${gid}`);
    if (cb) cb.checked = true;
  });

  // Year
  document.getElementById("year-from").value = p.year_from || 1980;
  document.getElementById("year-to").value   = p.year_to   || 2026;

  // Rating
  const slider = document.getElementById("rating-slider");
  slider.value = p.min_rating ?? 6.0;
  document.getElementById("rating-val").textContent = `${parseFloat(slider.value).toFixed(1)} / 10`;
}

function collectPrefs() {
  const movieGenres = [...document.querySelectorAll(".genre-cb:checked")].map(el => parseInt(el.value));
  const tvGenres    = [...document.querySelectorAll(".tv-genre-cb:checked")].map(el => parseInt(el.value));
  const langEl      = document.getElementById("language");
  const yearFrom    = parseInt(document.getElementById("year-from").value) || 1980;
  const yearTo      = parseInt(document.getElementById("year-to").value)   || 2026;
  const rating      = parseFloat(document.getElementById("rating-slider").value) || 6.0;
  const hidden      = document.querySelector('input[name="discovery"]:checked').value === "1";
  const actor       = document.getElementById("actor-input").value.trim();

  return {
    ...state.prefs,
    media_type:  state.mediaType,
    genres:      movieGenres,
    tv_genres:   tvGenres,
    providers:   [],
    language:    langEl.value,
    year_from:   yearFrom,
    year_to:     yearTo,
    min_rating:  rating,
    hidden_gem:  hidden,
    moods:       [...state.currentMoods],
    actor,
    actor_id:    state.resolvedActor?.name === actor ? state.resolvedActor.id : null,
  };
}

document.getElementById("btn-save").addEventListener("click", async () => {
  const p = collectPrefs();
  await post("/api/prefs", p);
  state.prefs = p;
  setStatus("Preferences saved.");
});

/* ── Media type toggle (Movies / TV) ───────────────────────────────────── */
function applyMediaType(type, { silent = false } = {}) {
  state.mediaType = type;
  document.querySelectorAll(".media-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.media === type);
  });
  document.querySelectorAll(".media-section").forEach(s => {
    s.classList.toggle("hidden", s.dataset.mediaSection !== type);
  });
  // Update button label and status
  document.getElementById("btn-pick").innerHTML = `🎲  Pick a ${nounCap()}`;
  if (!silent) {
    setStatus(`Switched to ${type === "tv" ? "TV Shows" : "Movies"}.`);
  }
}

document.querySelectorAll(".media-btn").forEach(btn => {
  btn.addEventListener("click", () => applyMediaType(btn.dataset.media));
});

/* ── Mood (multi-select toggle) ────────────────────────────────────────── */
function selectMood(key) {
  if (key === "none") {
    state.currentMoods.clear();
  } else if (state.currentMoods.has(key)) {
    state.currentMoods.delete(key);   // tap again to deselect
  } else {
    state.currentMoods.add(key);
  }
  document.querySelectorAll(".mood-btn").forEach(btn => {
    btn.classList.toggle("active", state.currentMoods.has(btn.dataset.mood));
  });
}

document.querySelectorAll(".mood-btn").forEach(btn => {
  btn.addEventListener("click", () => selectMood(btn.dataset.mood));
});

/* ── Actor autocomplete ────────────────────────────────────────────────── */
const actorInput    = document.getElementById("actor-input");
const actorDropdown = document.getElementById("actor-dropdown");
const actorStatus   = document.getElementById("actor-status");
let actorDebounce   = null;

actorInput.addEventListener("input", () => {
  clearTimeout(actorDebounce);
  const q = actorInput.value.trim();
  if (q.length < 2) { closeActorDropdown(); return; }
  actorDebounce = setTimeout(() => fetchActors(q), 350);
});

actorInput.addEventListener("blur", () => setTimeout(closeActorDropdown, 200));

async function fetchActors(q) {
  const results = await api(`/api/actors?q=${encodeURIComponent(q)}`);
  renderActorDropdown(results);
}

function renderActorDropdown(results) {
  actorDropdown.innerHTML = "";
  if (!results || !results.length) { closeActorDropdown(); return; }
  results.slice(0, 7).forEach(person => {
    const div = document.createElement("div");
    div.className = "actor-option";
    div.innerHTML = `<div class="name">${esc(person.name)}</div>
                     ${person.known_for ? `<div class="known">${esc(person.known_for)}</div>` : ""}`;
    div.addEventListener("mousedown", () => selectActor(person));
    actorDropdown.appendChild(div);
  });
  actorDropdown.classList.add("open");
}

function selectActor(person) {
  state.resolvedActor = { id: person.id, name: person.name };
  actorInput.value = person.name;
  actorStatus.textContent = `Selected: ${person.name}`;
  closeActorDropdown();
}

function closeActorDropdown() {
  actorDropdown.classList.remove("open");
}

document.getElementById("btn-clear-actor").addEventListener("click", () => {
  actorInput.value = "";
  actorStatus.textContent = "";
  state.resolvedActor = null;
  closeActorDropdown();
});

/* ── Rating slider ─────────────────────────────────────────────────────── */
document.getElementById("rating-slider").addEventListener("input", e => {
  document.getElementById("rating-val").textContent = `${parseFloat(e.target.value).toFixed(1)} / 10`;
});

/* ── Pick movie/show ───────────────────────────────────────────────────── */
document.getElementById("btn-pick").addEventListener("click", pickMovie);
document.getElementById("btn-pick-again").addEventListener("click", pickMovie);

async function pickMovie() {
  if (state.fetching) return;
  if (!state.prefs.api_key) { openApiModal(); return; }

  state.fetching = true;
  setStatus(`Finding a ${noun()}…`);
  clearMovieCard();
  setBtnsDisabled(true);
  const pickBtn = document.getElementById("btn-pick");
  pickBtn.disabled    = true;
  pickBtn.textContent = "Searching…";
  document.getElementById("btn-pick-again").disabled = true;

  const prefs = collectPrefs();
  try {
    const result = await post("/api/pick", prefs);
    if (result.error) {
      setStatus(result.error);
    } else {
      displayMovie(result);
      state.currentMovie = result;
      setStatus(`Here's your pick!${result.popularity < 15 ? "  ✨ Hidden Gem" : ""}`);
    }
  } catch (e) {
    setStatus("Network error — check your connection.");
  }

  state.fetching = false;
  pickBtn.disabled    = false;
  pickBtn.innerHTML   = `🎲  Pick a ${nounCap()}`;
  setBtnsDisabled(!state.currentMovie);
  if (state.currentMovie) {
    document.getElementById("btn-pick-again").disabled = false;
    document.getElementById("btn-trailer").disabled    = !state.currentMovie.trailer_url;
    document.getElementById("btn-trailer").textContent =
      state.currentMovie.trailer_url ? "▶  Watch Trailer" : "No Trailer";
  }
  refreshHistory();
}

/* ── Display movie/show ───────────────────────────────────────────────── */
function displayMovie(m) {
  document.getElementById("movie-title").textContent = m.title || "";

  // Build meta line — movies show runtime, shows show seasons/episodes
  let meta = m.year || "";
  if (m.media_type === "tv") {
    if (m.seasons)  meta += `  •  ${m.seasons} season${m.seasons !== 1 ? "s" : ""}`;
    if (m.episodes) meta += `  •  ${m.episodes} episode${m.episodes !== 1 ? "s" : ""}`;
    if (m.runtime)  meta += `  •  ~${m.runtime} min/ep`;
  } else if (m.runtime) {
    meta += `  •  ${m.runtime} min`;
  }
  document.getElementById("movie-meta").textContent = meta;

  // Rating badge
  const stars = "★".repeat(Math.round(m.rating / 2)) + "☆".repeat(5 - Math.round(m.rating / 2));
  document.getElementById("rating-badge").textContent =
    `${stars}  ${m.rating}/10  (${(m.votes || 0).toLocaleString()} votes)`;

  // RT badge
  const rtBadge = document.getElementById("rt-badge");
  if (m.rt_score) {
    const pct = parseInt(m.rt_score);
    rtBadge.textContent = `Rotten Tomatoes  ${m.rt_score}`;
    rtBadge.className   = `badge ${pct >= 75 ? "rt-fresh" : pct >= 60 ? "rt-ok" : "rt-rotten"}`;
    rtBadge.style.display = "";
  } else if (state.prefs.omdb_api_key && m.media_type !== "tv") {
    // TV Rotten Tomatoes data is rare in OMDb, so hide N/A for shows
    rtBadge.textContent   = "Rotten Tomatoes: N/A";
    rtBadge.className     = "badge";
    rtBadge.style.display = "";
  } else {
    rtBadge.style.display = "none";
  }

  document.getElementById("movie-overview").textContent = m.overview || "No overview available.";
  const directorLabel = m.media_type === "tv" ? "Created by" : "Directed by";
  document.getElementById("movie-director").textContent = m.director ? `🎬  ${directorLabel} ${m.director}` : "";
  document.getElementById("movie-cast").textContent     = m.cast?.length ? `🎭  ${m.cast.join(" • ")}` : "";
  document.getElementById("movie-genres").textContent   = m.genres?.join("  ") || "";
  document.getElementById("movie-streaming").textContent =
    m.streaming?.length ? `Streaming: ${m.streaming.join(" • ")}` : "Not on your selected streaming services";

  // Poster
  const posterWrap = document.getElementById("poster-wrap");
  if (m.poster) {
    posterWrap.innerHTML = `<img src="${esc(m.poster)}" alt="Poster" loading="lazy">`;
  } else {
    posterWrap.innerHTML = `<div class="poster-placeholder">No poster</div>`;
  }
}

function clearMovieCard() {
  ["movie-title","movie-meta","movie-overview","movie-director",
   "movie-cast","movie-genres","movie-streaming"].forEach(id => {
    document.getElementById(id).textContent = "";
  });
  document.getElementById("rating-badge").textContent = "";
  document.getElementById("rt-badge").style.display   = "none";
  document.getElementById("poster-wrap").innerHTML    = `<div class="poster-placeholder"></div>`;
}

/* ── Action buttons ────────────────────────────────────────────────────── */
document.getElementById("btn-trailer").addEventListener("click", () => {
  if (state.currentMovie?.trailer_url) {
    window.open(state.currentMovie.trailer_url, "_blank");
  }
});

document.getElementById("btn-tmdb").addEventListener("click", () => {
  if (state.currentMovie?.tmdb_url) window.open(state.currentMovie.tmdb_url, "_blank");
});

document.getElementById("btn-watchlist").addEventListener("click", async () => {
  if (!state.currentMovie) return;
  const r = await post("/api/watchlist/add", state.currentMovie);
  if (r.watchlist) {
    state.prefs.watchlist = r.watchlist;
    refreshWatchlist();
    const more = r.preferred_genres?.length
      ? `  Will show more ${noun()}s like this (${r.preferred_genres.join(", ")}).`
      : "";
    setStatus(`Added "${state.currentMovie.title}" to watchlist.${more}`);
    refreshHistory();
  }
});

document.getElementById("btn-watched").addEventListener("click", async () => {
  if (!state.currentMovie) return;
  const r = await post("/api/watched/add", state.currentMovie);
  document.getElementById("watched-count").textContent =
    `${r.watched_count} ${noun()}${r.watched_count !== 1 ? "s" : ""} marked as watched`;
  const more = r.preferred_genres?.length
    ? `  Showing more like this (${r.preferred_genres.join(", ")}).`
    : "  Finding something else…";
  setStatus(`Marked "${state.currentMovie.title}" as watched.${more}`);
  refreshHistory();
  pickMovie();
});

document.getElementById("btn-dislike").addEventListener("click", async () => {
  if (!state.currentMovie) return;
  const r = await post("/api/disliked/add", state.currentMovie);
  const note = r.avoided_genres?.length ? `  Showing fewer like this (${r.avoided_genres.join(", ")}).` : "";
  setStatus(`Noted! Skipping "${state.currentMovie.title}" and similar.${note}`);
  refreshHistory();
  pickMovie();
});

function setBtnsDisabled(disabled) {
  ["btn-trailer","btn-tmdb","btn-watchlist","btn-watched","btn-dislike"].forEach(id => {
    document.getElementById(id).disabled = disabled;
  });
}

/* ── Reset search filters ──────────────────────────────────────────────── */
document.getElementById("btn-reset-filters").addEventListener("click", () => {
  document.getElementById("language").value = "";
  document.querySelector('input[name="discovery"][value="0"]').checked = true;

  state.currentMoods.clear();
  document.querySelectorAll(".mood-btn").forEach(btn => btn.classList.remove("active"));

  document.getElementById("actor-input").value = "";
  document.getElementById("actor-status").textContent = "";
  state.resolvedActor = null;
  closeActorDropdown();

  document.querySelectorAll(".genre-cb").forEach(cb => cb.checked = false);
  document.querySelectorAll(".tv-genre-cb").forEach(cb => cb.checked = false);

  document.getElementById("year-from").value = 1980;
  document.getElementById("year-to").value   = 2026;

  document.getElementById("rating-slider").value = 6.0;
  document.getElementById("rating-val").textContent = "6.0 / 10";

  setStatus("Filters reset to defaults.");
});

/* ── Refresh / reset ───────────────────────────────────────────────────── */
document.getElementById("btn-refresh").addEventListener("click", () => {
  state.fetching = false;
  document.getElementById("btn-pick").disabled  = false;
  document.getElementById("btn-pick").innerHTML = `🎲  Pick a ${nounCap()}`;
  setBtnsDisabled(!state.currentMovie);
  if (state.currentMovie) {
    document.getElementById("btn-pick-again").disabled = false;
  }
  setStatus(state.currentMovie
    ? `Ready — showing ${state.currentMovie.title}`
    : `Set your preferences and click Pick a ${nounCap()}`);
});

/* ── History ───────────────────────────────────────────────────────────── */
async function refreshHistory() {
  const prefs = await api("/api/prefs");
  state.prefs = { ...state.prefs, history: prefs.history };
  renderHistory(prefs.history || []);
}

function renderHistory(history) {
  const list = document.getElementById("history-list");
  if (!history.length) {
    list.innerHTML = `<div class="history-empty">No history yet.<br>Pick something to start!</div>`;
    return;
  }
  list.innerHTML = history.map(entry => {
    const title = entry.title.length > 20 ? entry.title.slice(0, 19) + "…" : entry.title;
    const chips = (entry.actions || []).map(a =>
      `<span class="chip chip-${a}">${a}</span>`).join("");
    const tvBadge = entry.media_type === "tv" ? `<span class="hist-type">TV</span>` : "";
    return `<div class="hist-card" onclick="loadMovieById(${entry.id})">
      <div class="hist-title-row">
        <span class="hist-title">${esc(title)}</span>
        ${tvBadge}
        <button class="hist-play" onclick="event.stopPropagation();loadMovieById(${entry.id})">▶</button>
      </div>
      <div class="hist-meta">${esc(entry.year)}  ★ ${entry.rating}</div>
      <div class="hist-chips">${chips}</div>
    </div>`;
  }).join("");
}

document.getElementById("btn-clear-history").addEventListener("click", async () => {
  await post("/api/clear-history", {});
  renderHistory([]);
});

/* ── Load by ID from history ───────────────────────────────────────────── */
async function loadMovieById(itemId) {
  if (state.fetching) return;
  if (!state.prefs.api_key) return;

  state.fetching = true;
  setStatus("Loading details…");
  clearMovieCard();
  setBtnsDisabled(true);
  document.getElementById("btn-pick-again").disabled = true;

  try {
    const movie = await api(`/api/movie/${itemId}`);
    if (movie.error) {
      setStatus("Could not load details.");
    } else {
      state.currentMovie = movie;
      displayMovie(movie);
      setStatus(`Re-loaded from history: ${movie.title}`);
      setBtnsDisabled(false);
      document.getElementById("btn-pick-again").disabled = false;
      document.getElementById("btn-trailer").disabled    = !movie.trailer_url;
      document.getElementById("btn-trailer").textContent =
        movie.trailer_url ? "▶  Watch Trailer" : "No Trailer";
    }
  } catch (e) {
    setStatus("Network error.");
  }
  state.fetching = false;
}

/* ── Watchlist ─────────────────────────────────────────────────────────── */
function refreshWatchlist() {
  const items = state.prefs.watchlist || [];
  const el    = document.getElementById("watchlist-items");
  if (!items.length) {
    el.innerHTML = `<span class="watchlist-empty">Your watchlist is empty</span>`;
  } else {
    el.innerHTML = items.map(i => {
      const badge = i.media_type === "tv" ? ` <span class="chip-tv-sm">TV</span>` : "";
      return `<span class="watchlist-chip">${esc(i.title)} (${esc(i.year)})${badge}</span>`;
    }).join("");
  }
  const cnt = state.prefs.watched?.length || 0;
  document.getElementById("watched-count").textContent =
    `${cnt} ${noun()}${cnt !== 1 ? "s" : ""} marked as watched`;
}

document.getElementById("btn-clear-watchlist").addEventListener("click", async () => {
  await post("/api/clear-watchlist", {});
  state.prefs.watchlist = [];
  refreshWatchlist();
});

document.getElementById("btn-clear-watched").addEventListener("click", async () => {
  await post("/api/clear-watched", {});
  state.prefs.watched = [];
  refreshWatchlist();
});

/* ── API key modal ─────────────────────────────────────────────────────── */
function openApiModal() {
  const modal = document.getElementById("api-modal");
  modal.classList.remove("hidden");
  document.getElementById("tmdb-key-input").value = state.prefs.api_key  || "";
  document.getElementById("omdb-key-input").value = state.prefs.omdb_api_key || "";
  document.getElementById("modal-status").textContent = "";
}

document.getElementById("btn-open-api").addEventListener("click", openApiModal);
document.getElementById("btn-modal-cancel").addEventListener("click", () => {
  document.getElementById("api-modal").classList.add("hidden");
});

document.getElementById("btn-modal-save").addEventListener("click", async () => {
  const tmdbKey = document.getElementById("tmdb-key-input").value.trim();
  const omdbKey = document.getElementById("omdb-key-input").value.trim();
  const statusEl = document.getElementById("modal-status");
  statusEl.textContent = "Validating…";
  statusEl.style.color = "var(--primary)";

  const r = await post("/api/validate-key", { api_key: tmdbKey });
  if (r.valid) {
    await post("/api/prefs", { api_key: tmdbKey, omdb_api_key: omdbKey });
    state.prefs.api_key      = tmdbKey;
    state.prefs.omdb_api_key = omdbKey;
    document.getElementById("api-modal").classList.add("hidden");
    setStatus("API keys saved. Ready to pick!");
  } else {
    statusEl.textContent = "Invalid TMDB key. Try again.";
    statusEl.style.color = "var(--rose)";
  }
});

/* ── Status ────────────────────────────────────────────────────────────── */
function setStatus(msg) {
  document.getElementById("status-text").textContent = msg;
}

/* ── Mobile filters toggle ─────────────────────────────────────────────── */
(function () {
  const sidebar = document.querySelector(".sidebar");
  const toggleBtn = document.getElementById("btn-filters-toggle");
  const MOBILE = 768;

  let wasMobile = window.innerWidth <= MOBILE;

  if (wasMobile) {
    toggleBtn.textContent = "✕";
  }

  window.addEventListener("resize", () => {
    const isMobile = window.innerWidth <= MOBILE;
    if (isMobile === wasMobile) return;
    wasMobile = isMobile;
    if (isMobile) {
      sidebar.classList.add("collapsed");
      toggleBtn.textContent = "☰";
    } else {
      sidebar.classList.remove("collapsed");
    }
  });

  toggleBtn.addEventListener("click", () => {
    const isCollapsed = sidebar.classList.toggle("collapsed");
    toggleBtn.textContent = isCollapsed ? "☰" : "✕";
  });
})();

/* ── Escape HTML ───────────────────────────────────────────────────────── */
function esc(str) {
  return String(str ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
