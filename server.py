"""
The Movie Zenie — Flask web server
Run locally:  python server.py  → opens http://localhost:5000
Deployed:     gunicorn server:app  (Render uses PORT env var automatically)
"""
import os
import webbrowser
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file

import storage
import tmdb

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "movie-zenie-secret")


# ── Static assets ────────────────────────────────────────────────────────────

@app.route("/logo.png")
def serve_logo():
    from logo import make_logo
    img = make_logo(64)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           genres=tmdb.GENRES,
                           tv_genres=tmdb.TV_GENRES,
                           providers=tmdb.PROVIDERS,
                           languages=tmdb.LANGUAGES,
                           moods=tmdb.MOODS)


# ── Preferences ───────────────────────────────────────────────────────────────

@app.route("/api/prefs")
def get_prefs():
    return jsonify(storage.load())


@app.route("/api/prefs", methods=["POST"])
def save_prefs():
    prefs = storage.load()
    prefs.update(request.json or {})
    storage.save(prefs)
    return jsonify({"ok": True})


@app.route("/api/validate-key", methods=["POST"])
def validate_key():
    key = (request.json or {}).get("api_key", "")
    return jsonify({"valid": tmdb.validate_key(key)})


# ── Pick (movie or TV) ────────────────────────────────────────────────────────

@app.route("/api/pick", methods=["POST"])
def pick():
    prefs = storage.load()
    data  = request.json or {}
    api_key = prefs.get("api_key", "")
    if not api_key:
        return jsonify({"error": "No API key configured"}), 400

    media_type = data.get("media_type") or prefs.get("media_type", "movie")
    is_tv = (media_type == "tv")
    genre_map = tmdb.TV_GENRES if is_tv else tmdb.GENRES

    # Moods combine with OR logic; multiple moods pool their genres and keywords
    mood_keys = data.get("moods", [])
    mood_field = "tv_genres" if is_tv else "movie_genres"
    keyword_ids: list[int] = []
    if mood_keys:
        genre_set = set()
        keyword_set = set()
        for mk in mood_keys:
            if mk in tmdb.MOODS:
                genre_set.update(tmdb.MOODS[mk].get(mood_field, []))
                keyword_set.update(tmdb.MOODS[mk].get("keywords", []))
        genre_ids = list(genre_set)
        keyword_ids = list(keyword_set)
    else:
        ui_genres = data.get("tv_genres" if is_tv else "genres", [])
        genre_ids = [int(g) for g in ui_genres]

    # ★ Indie genre checkbox — adds the independent-film keyword on top of
    # whatever the user picked (moods or genres). Works in both media modes.
    if data.get("indie") and tmdb.KW_INDEPENDENT not in keyword_ids:
        keyword_ids.append(tmdb.KW_INDEPENDENT)

    # ⚡ Badass genre checkbox — restricts crew to a curated list of
    # action/genre directors and enforces a high rating floor so picks
    # are "really good high rated" by design.
    crew_ids: list[int] = []
    min_rating = float(data.get("min_rating", 6.0))
    if data.get("badass"):
        crew_ids = list(tmdb.BADASS_DIRECTOR_IDS)
        min_rating = max(min_rating, tmdb.BADASS_MIN_RATING)

    # If user picked nothing explicit, bias toward learned LIKED genres
    # (Only counts where the user has shown a pattern: count >= 2)
    if not genre_ids:
        liked = prefs.get("liked_genres", {})
        liked_relevant = [int(gid) for gid, cnt in liked.items()
                          if cnt >= 2 and int(gid) in genre_map]
        # Take top 4 by count to keep results varied
        liked_relevant.sort(key=lambda g: -liked.get(str(g), 0))
        genre_ids = liked_relevant[:4]

    # Actor resolution
    actor_id   = data.get("actor_id")
    actor_name = data.get("actor", "").strip()
    if actor_name and not actor_id:
        result = tmdb.search_actor(api_key, actor_name)
        if result:
            actor_id = result[0]

    # Exclusions — never re-suggest watched/disliked items
    watched_ids   = {w["id"] for w in prefs.get("watched",  [])}
    disliked_ids  = {d["id"] for d in prefs.get("disliked", [])}
    excluded_ids  = watched_ids | disliked_ids

    disliked_genres = prefs.get("disliked_genres", {})
    avoided_genres  = {int(gid) for gid, cnt in disliked_genres.items()
                       if cnt >= 2 and int(gid) not in genre_ids
                       and int(gid) in genre_map}

    fetch_fn = tmdb.fetch_random_tv if is_tv else tmdb.fetch_random_movie
    item = fetch_fn(
        api_key        = api_key,
        genre_ids      = genre_ids,
        year_from      = int(data.get("year_from", 1980)),
        year_to        = int(data.get("year_to",   2026)),
        min_rating     = min_rating,
        provider_ids   = [int(p) for p in data.get("providers", [])],
        language       = data.get("language", ""),
        hidden_gem     = bool(data.get("hidden_gem", False)),
        actor_id       = actor_id,
        excluded_ids   = excluded_ids,
        without_genre_ids = avoided_genres,
        keyword_ids    = keyword_ids,
        crew_ids       = crew_ids,
    )

    if not item:
        kind = "shows" if is_tv else "movies"
        return jsonify({"error": f"No {kind} found — try relaxing your filters"}), 404

    # RT score (works for both via IMDb ID)
    omdb_key = prefs.get("omdb_api_key", "")
    if omdb_key and item.get("imdb_id"):
        item["rt_score"] = tmdb.fetch_rt_score(omdb_key, item["imdb_id"])

    _log_history(prefs, item, "Suggested")
    storage.save(prefs)
    return jsonify(item)


@app.route("/api/movie/<int:movie_id>")
def get_movie(movie_id):
    prefs   = storage.load()
    api_key = prefs.get("api_key", "")
    if not api_key:
        return jsonify({"error": "No API key"}), 400
    # Try movie first, fall back to TV
    item = tmdb.fetch_movie_by_id(api_key, movie_id) or tmdb.fetch_tv_by_id(api_key, movie_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    omdb_key = prefs.get("omdb_api_key", "")
    if omdb_key and item.get("imdb_id"):
        item["rt_score"] = tmdb.fetch_rt_score(omdb_key, item["imdb_id"])
    return jsonify(item)


@app.route("/api/actors")
def search_actors():
    prefs = storage.load()
    q     = request.args.get("q", "")
    return jsonify(tmdb.search_actors(prefs.get("api_key", ""), q))


# ── Helpers for preference learning ──────────────────────────────────────────

def _bump_liked_genres(prefs: dict, item: dict) -> list[str]:
    """Increment liked_genres for each genre on a positively-engaged title."""
    is_tv = (item.get("media_type") == "tv")
    name_to_id = {v: k for k, v in (tmdb.TV_GENRES if is_tv else tmdb.GENRES).items()}
    lg = prefs.setdefault("liked_genres", {})
    boosted = []
    for gname in item.get("genres", []):
        gid = name_to_id.get(gname)
        if gid:
            lg[str(gid)] = lg.get(str(gid), 0) + 1
            if lg[str(gid)] >= 2:
                boosted.append(gname)
    return boosted


# ── Actions ───────────────────────────────────────────────────────────────────

@app.route("/api/watchlist/add", methods=["POST"])
def add_watchlist():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(w["id"] == mid for w in prefs["watchlist"]):
        prefs["watchlist"].append({
            "id": mid, "title": data["title"], "year": data["year"],
            "media_type": data.get("media_type", "movie"),
        })
        _log_history(prefs, data, "Watchlist")
    boosted = _bump_liked_genres(prefs, data)
    storage.save(prefs)
    return jsonify({"watchlist": prefs["watchlist"], "preferred_genres": boosted})


@app.route("/api/watched/add", methods=["POST"])
def add_watched():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(w["id"] == mid for w in prefs["watched"]):
        prefs["watched"].append({
            "id": mid, "title": data["title"], "year": data["year"],
            "media_type": data.get("media_type", "movie"),
        })
        _log_history(prefs, data, "Watched")
    boosted = _bump_liked_genres(prefs, data)
    storage.save(prefs)
    return jsonify({"watched_count": len(prefs["watched"]), "preferred_genres": boosted})


@app.route("/api/disliked/add", methods=["POST"])
def add_disliked():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(d["id"] == mid for d in prefs["disliked"]):
        prefs["disliked"].append({
            "id": mid, "title": data["title"],
            "year": data["year"], "genres": data.get("genres", []),
            "media_type": data.get("media_type", "movie"),
        })
    is_tv = (data.get("media_type") == "tv")
    name_to_id = {v: k for k, v in (tmdb.TV_GENRES if is_tv else tmdb.GENRES).items()}
    dg = prefs.setdefault("disliked_genres", {})
    for gname in data.get("genres", []):
        gid = name_to_id.get(gname)
        if gid:
            dg[str(gid)] = dg.get(str(gid), 0) + 1
    _log_history(prefs, data, "Disliked")
    storage.save(prefs)
    active_map = tmdb.TV_GENRES if is_tv else tmdb.GENRES
    avoided = [active_map[int(gid)] for gid, cnt in dg.items()
               if cnt >= 2 and int(gid) in active_map]
    return jsonify({"avoided_genres": avoided})


@app.route("/api/clear-watched",   methods=["POST"])
def clear_watched():
    prefs = storage.load(); prefs["watched"] = []; storage.save(prefs)
    return jsonify({"ok": True})

@app.route("/api/clear-watchlist", methods=["POST"])
def clear_watchlist():
    prefs = storage.load(); prefs["watchlist"] = []; storage.save(prefs)
    return jsonify({"ok": True})

@app.route("/api/clear-history",   methods=["POST"])
def clear_history():
    prefs = storage.load(); prefs["history"] = []; storage.save(prefs)
    return jsonify({"ok": True})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_history(prefs: dict, item: dict, action: str):
    history = prefs.setdefault("history", [])
    for entry in history:
        if entry["id"] == item["id"]:
            if action not in entry["actions"]:
                entry["actions"].append(action)
            return
    history.insert(0, {
        "id":      item["id"],
        "title":   item["title"],
        "year":    item.get("year", ""),
        "rating":  item.get("rating", 0),
        "actions": [action],
        "media_type": item.get("media_type", "movie"),
    })
    if len(history) > 60:
        history.pop()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_local = (port == 5000)
    print("=" * 50)
    print("  The Movie Zenie — Web Edition")
    print(f"  Open: http://localhost:{port}")
    print("=" * 50)
    if is_local:
        webbrowser.open(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
