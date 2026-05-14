import json
import os

PREFS_FILE = os.path.join(os.path.dirname(__file__), "prefs.json")

DEFAULTS = {
    "api_key": "",
    "omdb_api_key": "",
    "genres": [],
    "year_from": 1980,
    "year_to": 2026,
    "min_rating": 6.0,
    "providers": [],
    "language": "",
    "hidden_gem": False,
    "moods": [],
    "actor": "",
    "watchlist": [],
    "watched": [],
    "disliked": [],
    "disliked_genres": {},
    "history": [],
}


def load() -> dict:
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE) as f:
                data = json.load(f)
            prefs = {**DEFAULTS, **data}
        except Exception:
            prefs = dict(DEFAULTS)
    else:
        prefs = dict(DEFAULTS)

    # Environment variables always win — lets the deployed app work without
    # anyone having to paste API keys into the UI.
    env_tmdb = os.environ.get("TMDB_API_KEY", "")
    env_omdb = os.environ.get("OMDB_API_KEY", "")
    if env_tmdb:
        prefs["api_key"] = env_tmdb
    if env_omdb:
        prefs["omdb_api_key"] = env_omdb

    return prefs


def save(prefs: dict) -> None:
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)
