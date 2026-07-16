# 🎲 Movie Rando

**[movierando.com](https://movierando.com)** — stop scrolling, roll a movie.

A web app that picks a random movie or TV show based on exactly what you're in
the mood for, powered by the TMDB database (plus Rotten Tomatoes scores via OMDb).

## Features

- **🎲 Roll a random pick** — movies or TV shows, one button
- **Genres** — check as many as you like; a title matching **any** of them qualifies
- **Moods** — curated mixes (Twist, Feel Good, Dark, Indie, Arthouse, Maxx Inspired…)
- **★ Indie / ⚡ Bad Ass Dad** — curated keyword and director filters
- **Actor / Director search** — filter by anyone, with autocomplete
- **Hidden Gems** — genuinely good but under the radar (auto 7.0+ rating floor,
  popularity *and* vote-count capped so faded blockbusters can't sneak in)
- **Minimum Rating** — TMDB score floor (0–10)
- **Minimum Rotten Tomatoes 🍅** — RT score floor (movies only). Titles with no
  RT score still qualify — unrated ≠ unworthy
- **Year range**, **language**
- **Never repeats** a title within a session
- **Watchlist** + **Suggested History**, with learning from what you like/dislike

Preferences are saved automatically between sessions.

## Running it locally

### 1. Install Python
**Python 3.10+** from https://www.python.org/downloads/ (check *"Add Python to PATH"*).

### 2. Install dependencies
```
setup.bat
```

### 3. Get API keys
- **TMDB** (required) — free at https://www.themoviedb.org/settings/api → API Key (v3 auth)
- **OMDb** (optional, for Rotten Tomatoes scores) — free at https://www.omdbapi.com/apikey.aspx

Paste them into the app on first launch, or set them as environment variables
(`TMDB_API_KEY` / `OMDB_API_KEY`) — env vars always win, which is how the
deployed site is configured.

### 4. Run
Double-click `run.bat`, or:
```
python server.py       # web app  → http://localhost:5000
python main.py         # legacy desktop app
```

## Deployment

Deployed on Render as a Flask app (`gunicorn server:app`). API keys are set as
environment variables in the Render dashboard — the filesystem is ephemeral, so
`prefs.json` should not be relied on in production.

## Project layout

| File | Purpose |
|---|---|
| `server.py` | Flask web server + API endpoints |
| `tmdb.py` | TMDB/OMDb API layer, pick logic, filters |
| `storage.py` | Preferences load/save (env vars override) |
| `logo.py` | Logo, generated at runtime and served at `/logo.png` |
| `templates/index.html` | UI markup |
| `static/app.js` | Frontend logic |
| `static/style.css` | Cloud & Cornflower palette |
| `app.py` | Legacy CustomTkinter desktop app |
