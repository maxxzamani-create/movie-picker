"""
The Movie Genie — Flask web server
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
app.secret_key = os.environ.get("SECRET_KEY", "movie-genie-secret")


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


# ── Movie picking ─────────────────────────────────────────────────────────────

@app.route("/api/pick", methods=["POST"])
def pick_movie():
    prefs = storage.load()
    data  = request.json or {}
    api_key = prefs.get("api_key", "")
    if not api_key:
        return jsonify({"error": "No API key configured"}), 400

    # Mood overrides genre checkboxes
    mood_key = data.get("mood", "none")
    if mood_key and mood_key != "none":
        genre_ids = tmdb.MOODS[mood_key]["genres"]
    else:
        genre_ids = [int(g) for g in data.get("genres", [])]

    # Actor resolution
    actor_id   = data.get("actor_id")
    actor_name = data.get("actor", "").strip()
    if actor_name and not actor_id:
        result = tmdb.search_actor(api_key, actor_name)
        if result:
            actor_id = result[0]

    # Exclusions
    watched_ids   = {w["id"] for w in prefs.get("watched",  [])}
    disliked_ids  = {d["id"] for d in prefs.get("disliked", [])}
    excluded_ids  = watched_ids | disliked_ids

    disliked_genres = prefs.get("disliked_genres", {})
    avoided_genres  = {int(gid) for gid, cnt in disliked_genres.items()
                       if cnt >= 2 and int(gid) not in genre_ids}

    movie = tmdb.fetch_random_movie(
        api_key        = api_key,
        genre_ids      = genre_ids,
        year_from      = int(data.get("year_from", 1980)),
        year_to        = int(data.get("year_to",   2026)),
        min_rating     = float(data.get("min_rating", 6.0)),
        provider_ids   = [int(p) for p in data.get("providers", [])],
        language       = data.get("language", ""),
        hidden_gem     = bool(data.get("hidden_gem", False)),
        actor_id       = actor_id,
        excluded_ids   = excluded_ids,
        without_genre_ids = avoided_genres,
    )

    if not movie:
        return jsonify({"error": "No movies found — try relaxing your filters"}), 404

    # RT score
    omdb_key = prefs.get("omdb_api_key", "")
    if omdb_key and movie.get("imdb_id"):
        movie["rt_score"] = tmdb.fetch_rt_score(omdb_key, movie["imdb_id"])

    _log_history(prefs, movie, "Suggested")
    storage.save(prefs)
    return jsonify(movie)


@app.route("/api/movie/<int:movie_id>")
def get_movie(movie_id):
    prefs   = storage.load()
    api_key = prefs.get("api_key", "")
    if not api_key:
        return jsonify({"error": "No API key"}), 400
    movie = tmdb.fetch_movie_by_id(api_key, movie_id)
    if not movie:
        return jsonify({"error": "Not found"}), 404
    omdb_key = prefs.get("omdb_api_key", "")
    if omdb_key and movie.get("imdb_id"):
        movie["rt_score"] = tmdb.fetch_rt_score(omdb_key, movie["imdb_id"])
    return jsonify(movie)


@app.route("/api/actors")
def search_actors():
    prefs = storage.load()
    q     = request.args.get("q", "")
    return jsonify(tmdb.search_actors(prefs.get("api_key", ""), q))


# ── Actions ───────────────────────────────────────────────────────────────────

@app.route("/api/watchlist/add", methods=["POST"])
def add_watchlist():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(w["id"] == mid for w in prefs["watchlist"]):
        prefs["watchlist"].append({"id": mid, "title": data["title"], "year": data["year"]})
        _log_history(prefs, data, "Watchlist")
        storage.save(prefs)
    return jsonify({"watchlist": prefs["watchlist"]})


@app.route("/api/watched/add", methods=["POST"])
def add_watched():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(w["id"] == mid for w in prefs["watched"]):
        prefs["watched"].append({"id": mid, "title": data["title"], "year": data["year"]})
        _log_history(prefs, data, "Watched")
        storage.save(prefs)
    return jsonify({"watched_count": len(prefs["watched"])})


@app.route("/api/disliked/add", methods=["POST"])
def add_disliked():
    prefs = storage.load()
    data  = request.json or {}
    mid   = data.get("id")
    if not any(d["id"] == mid for d in prefs["disliked"]):
        prefs["disliked"].append({
            "id": mid, "title": data["title"],
            "year": data["year"], "genres": data.get("genres", []),
        })
    genre_map = {v: k for k, v in tmdb.GENRES.items()}
    dg = prefs.setdefault("disliked_genres", {})
    for gname in data.get("genres", []):
        gid = genre_map.get(gname)
        if gid:
            dg[str(gid)] = dg.get(str(gid), 0) + 1
    _log_history(prefs, data, "Disliked")
    storage.save(prefs)
    avoided = [tmdb.GENRES[int(gid)] for gid, cnt in dg.items()
               if cnt >= 2 and int(gid) in tmdb.GENRES]
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

def _log_history(prefs: dict, movie: dict, action: str):
    history = prefs.setdefault("history", [])
    for entry in history:
        if entry["id"] == movie["id"]:
            if action not in entry["actions"]:
                entry["actions"].append(action)
            return
    history.insert(0, {
        "id":      movie["id"],
        "title":   movie["title"],
        "year":    movie.get("year", ""),
        "rating":  movie.get("rating", 0),
        "actions": [action],
    })
    if len(history) > 60:
        history.pop()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_local = (port == 5000)
    print("=" * 50)
    print("  The Movie Genie — Web Edition")
    print(f"  Open: http://localhost:{port}")
    print("=" * 50)
    if is_local:
        webbrowser.open(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
