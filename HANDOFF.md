# 🎲 Movie Rando — Handoff

**Read this first.** Living context for anyone (human or agent) picking this project up.
Last updated: 2026-07-16.

---

## What it is

A Flask web app that picks a **random movie or TV show** matching your filters, using
**TMDB** (catalog, ratings) + **OMDb** (Rotten Tomatoes scores). Formerly "The Movie
Zenie" — **rebranded to Movie Rando**; no Zenie/genie references remain.

| | |
|---|---|
| **Repo** | https://github.com/maxxzamani-create/movie-picker (public) |
| **Local** | `C:\Users\maxx1\OneDrive\Documents\GitHub\movie-picker` |
| **Live** | https://movie-genie-lseb.onrender.com *(URL changes after the rename — see Open Items #1)* |
| **Domain** | **movierando.com** — bought on GoDaddy, **not yet wired up** (Open Items #1) |
| **Host** | Render, **free tier** (`gunicorn server:app`), auto-deploys on push to `main` |

---

## Architecture

| File | Purpose |
|---|---|
| `server.py` | Flask server + JSON API (`/api/pick`, `/api/prefs`, `/api/actors`, `/logo.png`) |
| `tmdb.py` | TMDB/OMDb layer + **all pick logic and filters** — the brain |
| `storage.py` | Prefs load/save. **Env vars override file values** |
| `logo.py` | Logo generated at runtime, served at `/logo.png` (no static image file) |
| `templates/index.html` | UI markup |
| `static/app.js` | Frontend logic (vanilla JS, no framework) |
| `static/style.css` | Palette lives in `:root` CSS variables |
| `app.py` | **Legacy** CustomTkinter desktop app — still imports `logo.py`, keep it working |
| `.github/workflows/keep-alive.yml` | Pings the site to fight Render's sleep (unreliable — see #2) |

### API keys — important
`TMDB_API_KEY` and `OMDB_API_KEY` are set as **environment variables in the Render
dashboard**, and `storage.py` makes env vars win over file values. That's why they
survive redeploys.

**`prefs.json` is gitignored AND ephemeral on Render** — it's wiped on every deploy and
every spin-down. Never rely on it in production. (The OMDb key exists *only* in Render's
env vars — it is not recoverable from the local disk.)

---

## Hard-won gotchas — read before debugging

- **TMDB returns 5xx on individual result pages** — especially the *partial last page* of
  a result set. This is normal and intermittent, not our bug. `tmdb.py` retries other
  pages and falls back to page-1 results. Don't "simplify" that retry logic away.
- **TMDB's `popularity` is recency-biased.** Old blockbusters decay under a popularity
  cap (a *Super Mario Bros. Movie* once surfaced as a "hidden gem"). **`vote_count` is the
  reliable fame proxy** — famous titles keep high vote counts forever. Hidden Gems uses both.
- **The detail fetch is a second, separate TMDB call** and fails independently. If unchecked
  it yields a blank `title: "Unknown"` card. Always validate it.
- **`TMDBUnavailable`** distinguishes "TMDB is down" (→ honest 503) from "genuinely no
  matches" (→ 404 "relax your filters"). Keep that distinction; it saved hours of
  misdiagnosis.
- **OMDb has almost no RT data for TV** → the RT filter is **movies-only** by design.
- **Unrated ≠ unworthy** — the RT filter only rejects a movie that *has* a score below the
  bar. Titles with no RT score still qualify. This was an explicit user requirement.
- **Genres are OR, not AND** (TMDB `|` operator). Multiple genres = "any match".
- **Windows env**: use `py`, not `python`. `ast.parse(open(f, encoding='utf-8'))` — files
  contain emoji/em-dashes and cp1252 will crash. If `git fetch` errors on refs, run
  `git config windows.appendAtomically false`.
- **Every push to `main` triggers a Render redeploy** (~2–5 min). Verify live after.

---

## Current feature set

- 🎲 Random pick — movies or TV
- **Genres** (multi-select, OR), **Moods**, **★ Indie** / **⚡ Bad Ass Dad** (curated
  keyword + director filters). Moods and ★/⚡ are mutually exclusive; genres combine.
- **Actor/Director** search w/ autocomplete
- **Hidden Gems** — auto **7.0+ rating floor** + popularity cap + **vote-count cap**
  (≤5000 movies / ≤3000 TV) so faded blockbusters can't sneak in
- **Minimum Rating** (TMDB 0–10) and **Minimum Rotten Tomatoes 🍅** (movies only)
- **Never repeats a title in a session** — frontend tracks shown IDs (`state.sessionSeen`,
  separate movie/TV sets) and sends `session_seen` with each pick; server merges into
  exclusions. Cleared on page refresh.
- Watchlist, Suggested History, learned liked/disliked genres

### Theme — "Cloud & Cornflower"
Research-backed calm light palette (the user iterated through neon → rose gold+navy →
rose gold+teal → Tiffany+white before landing here):
warm cloud-white bg `#f5f3ee` → white cards → slate ink `#24303f` → **cornflower blue
`#3b82f6`** as the single accent/CTA → **muted sage `#3f7d5f`** for save/positive →
terracotta `#c4653f` for destructive only. All in `:root` in `style.css`; `logo.py`
mirrors it. **Rose gold is gone — do not reintroduce it.**

---

## 🚩 Open items

### 1. Wire up movierando.com (BLOCKED — needs the user's hands)
Requires Render + GoDaddy dashboard logins. Agent cannot do this: the GoDaddy connector
is **search-only** (no DNS record tools) and credentials must not be entered.

**Order matters:**
1. **Rename the Render service to `movierando` FIRST** → URL becomes
   `movierando.onrender.com`. Doing DNS before this breaks the CNAME.
2. Render → Settings → **Custom Domains** → add **both** `movierando.com` and
   `www.movierando.com` (required for routing + cert).
3. GoDaddy → DNS → Manage Zones:
   - **A** `@` → `216.24.57.1`
   - **CNAME** `www` → `movierando.onrender.com`
   - **Delete the parking A records** (currently `3.33.130.190` / `15.197.148.33`)
   - **Delete any AAAA records** — Render is IPv4-only
4. Wait 10 min–2 hrs; Render auto-issues SSL.

**After it's live:** update the hardcoded URL in `.github/workflows/keep-alive.yml`
(still points at `movie-genie-lseb.onrender.com`, which **dies on rename**).

### 2. Render free tier sleeps after 15 min → 30–50s cold start
The user's #1 recurring complaint. **GitHub Actions cron is NOT a reliable fix** — it
fired *once* in an hour when scheduled every 10 min (documented best-effort behavior).
The workflow was since rewritten to self-loop (each run pings ~55 min) which helps but
still isn't guaranteed. Real options, in order of recommendation:
- **cron-job.org / UptimeRobot** pinging every 5 min — free, reliable, ~2 min setup (needs a signup)
- **Render Starter $7/mo** — the only *guaranteed* fix, no migration
- **Hugging Face Spaces** — free, no card, sleeps only after **48h** idle (vs 15 min); needs a Dockerfile
- ~~Fly.io~~ — no longer has a free tier. ~~PythonAnywhere~~ — free tier's outbound whitelist can block TMDB/OMDb.

### 3. Stray commits on `main`
PRs **#3** and **#4** ("Commercial Override" demo) came from a different session — added
then removed, **net zero file changes**. Harmless, just unexpected if you read the log.

### 4. Nice-to-haves discussed, not built
"Certified Fresh 75%+" preset button; showing the RT threshold in the status line;
`lion_logo.png` in the repo root is **unused leftover** and could be deleted.

---

## Verification playbook

Live-test the API without a browser (swap the host after the domain move):

```bash
curl -sS -X POST https://movie-genie-lseb.onrender.com/api/pick \
  -H "Content-Type: application/json" \
  -d '{"media_type":"movie","genres":[28],"year_from":2000,"year_to":2026,
       "min_rating":4.0,"min_rt":0,"hidden_gem":false,"moods":[],"providers":[],
       "indie":false,"badass":false,"actor":"","actor_id":null,
       "tv_genres":[],"session_seen":[]}'
```

- Picks are **probabilistic** — always sample 5–10 times, never judge on one call.
- Check `/api/prefs` to confirm keys are present on the server.
- Render the logo locally before shipping changes: `py -c "import logo; logo.make_logo(64).save('t.png')"`
  — it must stay legible at **64px** (the served size); sprocket holes are size-gated for that reason.
- Verified good: all **18/18 movie genres** and **16/16 TV genres** return real titles.
