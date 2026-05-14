import requests
import random

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 53: "Thriller",
    10752: "War", 37: "Western",
}

PROVIDERS = {
    8: "Netflix", 9: "Amazon Prime", 337: "Disney+", 15: "Hulu",
    384: "HBO Max", 531: "Paramount+", 386: "Peacock", 2: "Apple TV+",
}

LANGUAGES = {
    "": "Any Language",
    "en": "English Only",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "it": "Italian",
    "zh": "Chinese",
}

MOODS = {
    "none":        {"label": "None",         "genres": []},
    "feel_good":   {"label": "Feel Good",    "genres": [35, 10749, 10751, 16]},
    "dark":        {"label": "Dark",         "genres": [53, 80, 27, 18]},
    "mind_bending":{"label": "Mind-Bending", "genres": [878, 9648]},
    "action":      {"label": "Action-Packed","genres": [28, 12]},
    "inspiring":   {"label": "Inspiring",    "genres": [18, 36, 99]},
    "romantic":    {"label": "Romantic",     "genres": [10749, 35]},
    "scary":       {"label": "Scary",        "genres": [27]},
    "funny":       {"label": "Funny",        "genres": [35]},
}


OMDB_URL = "http://www.omdbapi.com/"


def fetch_movie_by_id(api_key: str, movie_id: int, region: str = "US") -> dict | None:
    """Fetch full details for a specific movie ID (used when re-loading from history)."""
    try:
        detail = requests.get(
            f"{BASE_URL}/movie/{movie_id}",
            params={"api_key": api_key, "append_to_response": "watch/providers,videos,credits"},
            timeout=10,
        ).json()
    except Exception:
        return None

    if not detail.get("id"):
        return None

    watch = detail.get("watch/providers", {}).get("results", {}).get(region, {})
    flatrate = watch.get("flatrate", [])
    streaming = [p["provider_name"] for p in flatrate] if flatrate else []

    videos = detail.get("videos", {}).get("results", [])
    trailer_key = None
    for priority in [
        lambda v: v["site"] == "YouTube" and v["type"] == "Trailer" and v.get("official"),
        lambda v: v["site"] == "YouTube" and v["type"] == "Trailer",
        lambda v: v["site"] == "YouTube" and v["type"] == "Teaser",
    ]:
        match = next((v for v in videos if priority(v)), None)
        if match:
            trailer_key = match["key"]
            break

    return {
        "id": detail.get("id"),
        "title": detail.get("title", "Unknown"),
        "overview": detail.get("overview", ""),
        "rating": round(detail.get("vote_average", 0), 1),
        "votes": detail.get("vote_count", 0),
        "year": (detail.get("release_date") or "")[:4],
        "runtime": detail.get("runtime"),
        "genres": [g["name"] for g in detail.get("genres", [])],
        "poster": IMAGE_BASE + detail["poster_path"] if detail.get("poster_path") else None,
        "streaming": streaming,
        "tmdb_url": f"https://www.themoviedb.org/movie/{detail.get('id')}",
        "trailer_url": f"https://www.youtube.com/watch?v={trailer_key}" if trailer_key else None,
        "popularity": detail.get("popularity", 0),
        "imdb_id": detail.get("imdb_id"),
        "cast": [m["name"] for m in detail.get("credits", {}).get("cast", [])[:5]],
        "director": next((m["name"] for m in detail.get("credits", {}).get("crew", [])
                          if m["job"] == "Director"), None),
    }


def fetch_rt_score(omdb_key: str, imdb_id: str) -> str | None:
    if not omdb_key or not imdb_id:
        return None
    try:
        r = requests.get(OMDB_URL, params={"apikey": omdb_key, "i": imdb_id}, timeout=6)
        if r.status_code != 200:
            return None
        data = r.json()
        for rating in data.get("Ratings", []):
            if rating.get("Source") == "Rotten Tomatoes":
                return rating["Value"]
    except Exception:
        pass
    return None


def validate_key(api_key: str) -> bool:
    r = requests.get(f"{BASE_URL}/configuration", params={"api_key": api_key}, timeout=8)
    return r.status_code == 200


def search_actor(api_key: str, name: str) -> tuple[int, str] | None:
    results = search_actors(api_key, name, limit=1)
    if not results:
        return None
    return results[0]["id"], results[0]["name"]


def search_actors(api_key: str, query: str, limit: int = 7) -> list[dict]:
    if not query.strip():
        return []
    r = requests.get(f"{BASE_URL}/search/person",
                     params={"api_key": api_key, "query": query}, timeout=6)
    if r.status_code != 200:
        return []
    results = r.json().get("results", [])[:limit]
    out = []
    for p in results:
        known = ", ".join(
            m.get("title") or m.get("name", "")
            for m in p.get("known_for", [])[:2]
            if m.get("title") or m.get("name")
        )
        out.append({"id": p["id"], "name": p["name"], "known_for": known})
    return out


def fetch_random_movie(api_key: str, genre_ids: list[int], year_from: int,
                       year_to: int, min_rating: float, provider_ids: list[int],
                       language: str = "", hidden_gem: bool = False,
                       actor_id: int | None = None, region: str = "US",
                       excluded_ids: set | None = None,
                       without_genre_ids: set | None = None) -> dict | None:
    params = {
        "api_key": api_key,
        "sort_by": "vote_average.desc" if hidden_gem else "popularity.desc",
        "vote_average.gte": min_rating,
        "vote_count.gte": 300 if hidden_gem else 50,
        "primary_release_date.gte": f"{year_from}-01-01",
        "primary_release_date.lte": f"{year_to}-12-31",
        "language": "en-US",
        "page": 1,
    }
    if hidden_gem:
        params["popularity.lte"] = 20

    if genre_ids:
        params["with_genres"] = "|".join(str(g) for g in genre_ids)  # | = OR logic
    if without_genre_ids:
        params["without_genres"] = ",".join(str(g) for g in without_genre_ids)
    if provider_ids:
        params["with_watch_providers"] = "|".join(str(p) for p in provider_ids)
        params["watch_region"] = region
    if language:
        params["with_original_language"] = language
    if actor_id:
        params["with_cast"] = actor_id

    r = requests.get(f"{BASE_URL}/discover/movie", params=params, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    total = min(data.get("total_pages", 1), 500)
    if total == 0 or not data.get("results"):
        return None

    excluded_ids = excluded_ids or set()
    # Try up to 8 random pages to find a non-watched movie
    movie = None
    for _ in range(8):
        params["page"] = random.randint(1, total)
        r = requests.get(f"{BASE_URL}/discover/movie", params=params, timeout=10)
        if r.status_code != 200:
            return None
        candidates = [m for m in r.json().get("results", [])
                      if m["id"] not in excluded_ids]
        if candidates:
            movie = random.choice(candidates)
            break
    if not movie:
        return None

    detail = requests.get(
        f"{BASE_URL}/movie/{movie['id']}",
        params={"api_key": api_key, "append_to_response": "watch/providers,videos,credits"},
        timeout=10,
    ).json()

    watch = detail.get("watch/providers", {}).get("results", {}).get(region, {})
    flatrate = watch.get("flatrate", [])
    streaming = [p["provider_name"] for p in flatrate] if flatrate else []

    # Find the best YouTube trailer
    videos = detail.get("videos", {}).get("results", [])
    trailer_key = None
    for priority in [
        lambda v: v["site"] == "YouTube" and v["type"] == "Trailer" and v.get("official"),
        lambda v: v["site"] == "YouTube" and v["type"] == "Trailer",
        lambda v: v["site"] == "YouTube" and v["type"] == "Teaser",
    ]:
        match = next((v for v in videos if priority(v)), None)
        if match:
            trailer_key = match["key"]
            break

    return {
        "id": detail.get("id"),
        "title": detail.get("title", "Unknown"),
        "overview": detail.get("overview", ""),
        "rating": round(detail.get("vote_average", 0), 1),
        "votes": detail.get("vote_count", 0),
        "year": (detail.get("release_date") or "")[:4],
        "runtime": detail.get("runtime"),
        "genres": [g["name"] for g in detail.get("genres", [])],
        "poster": IMAGE_BASE + detail["poster_path"] if detail.get("poster_path") else None,
        "streaming": streaming,
        "tmdb_url": f"https://www.themoviedb.org/movie/{detail.get('id')}",
        "trailer_url": f"https://www.youtube.com/watch?v={trailer_key}" if trailer_key else None,
        "popularity": detail.get("popularity", 0),
        "imdb_id": detail.get("imdb_id"),
        "cast": [m["name"] for m in detail.get("credits", {}).get("cast", [])[:5]],
        "director": next((m["name"] for m in detail.get("credits", {}).get("crew", [])
                          if m["job"] == "Director"), None),
    }
