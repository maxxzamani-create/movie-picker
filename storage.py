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
    "mood": "none",
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
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(prefs: dict) -> None:
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)
