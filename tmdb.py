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

# TV genres are a different set on TMDB (some IDs differ from movie genres)
TV_GENRES = {
    10759: "Action & Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    10762: "Kids", 9648: "Mystery", 10763: "News",
    10764: "Reality", 10765: "Sci-Fi & Fantasy", 10766: "Soap",
    10767: "Talk", 10768: "War & Politics", 37: "Western",
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

# TMDB keyword IDs used by the indie/arthouse moods.
# 9826 = "independent film" (well-established TMDB keyword).
KW_INDEPENDENT = 9826

# TMDB person IDs for the ⚡ Badass genre (MOVIES) — directors whose films
# are the kind of thing the user described as "really good high rated, the
# stuff guys like." Every ID hand-verified against themoviedb.org.
BADASS_DIRECTOR_IDS = [
    # ── Auteurs & prestige action ────────────────────────────────
    138,    # Quentin Tarantino
    2710,   # James Cameron
    525,    # Christopher Nolan
    7467,   # David Fincher
    578,    # Ridley Scott
    1032,   # Martin Scorsese
    638,    # Michael Mann
    1150,   # Brian De Palma
    488,    # Steven Spielberg
    # ── Classic action / cult / 80s-90s ──────────────────────────
    11770,  # John Carpenter
    11401,  # John Woo
    1090,   # John McTiernan
    10491,  # Paul Verhoeven
    893,    # Tony Scott
    7623,   # Sam Raimi
    865,    # Michael Bay
    # ── Modern action, crime & genre ─────────────────────────────
    15218,  # James Gunn
    11090,  # Edgar Wright
    2294,   # Robert Rodriguez
    957,    # Matthew Vaughn
    956,    # Guy Ritchie
    137427, # Denis Villeneuve
    20629,  # George Miller
    40644,  # Chad Stahelski (John Wick)
    40684,  # David Leitch
    9033,   # Christopher McQuarrie
    20907,  # Antoine Fuqua
    11694,  # Doug Liman
    25598,  # Paul Greengrass
    19769,  # David Ayer
    15217,  # Zack Snyder
    # ── International heavy hitters ──────────────────────────────
    10099,  # Park Chan-wook
    21684,  # Bong Joon-ho
    142013, # Gareth Evans (The Raid)
]

# TMDB network IDs for the ⚡ Badass genre (TV). TMDB's /discover/tv
# endpoint doesn't support with_crew, so for TV we constrain by
# prestige-drama networks instead — the homes of Sopranos, Breaking
# Bad, Fargo, Yellowjackets, Severance, Power, etc. Hand-verified.
BADASS_TV_NETWORK_IDS = [
    49,     # HBO
    174,    # AMC
    88,     # FX
    67,     # Showtime
    2552,   # Apple TV+
    318,    # STARZ
]

BADASS_MIN_RATING = 7.0   # enforced floor when ⚡ Badass is checked

MOODS = {
    "none":        {"label": "None",         "movie_genres": [],              "tv_genres": []},
    # ⭐ Maxx Inspired — the user's signature mood, front and centre.
    # Combines the Bad Ass Dad director list (movies) / prestige networks
    # (TV) with a six-genre mix (Crime, Thriller, Action, Drama, Mystery,
    # Western) and a 7.0+ rating floor. For TV, "Action" translates to
    # TMDB's Action & Adventure (10759).
    "maxx":        {"label": "Maxx Inspired",
                    "movie_genres":    [80, 53, 28, 18, 9648, 37],
                    "tv_genres":       [80, 10759, 18, 9648, 37],
                    "crew_ids":        list(BADASS_DIRECTOR_IDS),
                    "tv_network_ids":  list(BADASS_TV_NETWORK_IDS),
                    "min_rating_floor": BADASS_MIN_RATING},
    # Mind-Bending repurposed to focus on twist movies (the "you can never
    # guess the twist" type — Memento, Sixth Sense, Prestige, Shutter Island
    # vibe). Pulls from Mystery/Thriller/Crime/Drama with a 7.0+ floor so
    # cheap-twist filler doesn't sneak in. Key stays "mind_bending" so any
    # existing prefs files round-trip cleanly.
    "mind_bending":{"label": "Twist",        "movie_genres": [9648, 53, 80, 18],     "tv_genres": [9648, 80, 18],
                    "min_rating_floor": 7.0},
    "feel_good":   {"label": "Feel Good",    "movie_genres": [35, 10749, 10751, 16], "tv_genres": [35, 10751, 16]},
    "dark":        {"label": "Dark",         "movie_genres": [53, 80, 27, 18],       "tv_genres": [80, 18, 9648]},
    "action":      {"label": "Action-Packed","movie_genres": [28, 12],               "tv_genres": [10759]},
    "inspiring":   {"label": "Inspiring",    "movie_genres": [18, 36, 99],           "tv_genres": [18, 99]},
    "romantic":    {"label": "Romantic",     "movie_genres": [10749, 35],            "tv_genres": [35, 18]},
    "scary":       {"label": "Scary",        "movie_genres": [27],                   "tv_genres": [9648, 80]},
    "funny":       {"label": "Funny",        "movie_genres": [35],                   "tv_genres": [35]},
    # Indie / artsy / arthouse trio — share the "independent film" keyword
    # but tilt toward different genre mixes and rating thresholds.
    "indie":       {"label": "Indie",        "movie_genres": [18, 35, 9648],         "tv_genres": [18, 35, 9648],
                    "keywords": [KW_INDEPENDENT]},
    "artsy":       {"label": "Artsy",        "movie_genres": [18, 14, 9648],         "tv_genres": [18, 9648],
                    "keywords": [KW_INDEPENDENT]},
    "arthouse":    {"label": "Arthouse",     "movie_genres": [18, 36, 10402],        "tv_genres": [18, 9648],
                    "keywords": [KW_INDEPENDENT]},
}
# Backward-compat alias for the legacy desktop app (app.py uses MOODS[k]["genres"])
# Also default the optional new fields so callers can rely on them existing.
for _m in MOODS.values():
    _m["genres"] = _m["movie_genres"]
    _m.setdefault("keywords", [])
    _m.setdefault("crew_ids", [])
    _m.setdefault("tv_network_ids", [])
    _m.setdefault("min_rating_floor", 0.0)


OMDB_URL = "http://www.omdbapi.com/"


def _movie_to_shape(detail: dict, region: str = "US") -> dict:
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
        "media_type": "movie",
    }


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
    return _movie_to_shape(detail, region)


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
                       without_genre_ids: set | None = None,
                       keyword_ids: list[int] | None = None,
                       crew_ids: list[int] | None = None) -> dict | None:
    # Indie/arthouse moods carry keywords — when present, we want
    # rarer/lower-vote results to surface (true indie titles).
    has_keywords = bool(keyword_ids)
    params = {
        "api_key": api_key,
        "sort_by": "vote_average.desc" if hidden_gem else "popularity.desc",
        "vote_average.gte": min_rating,
        "vote_count.gte": 300 if hidden_gem else (20 if has_keywords else 50),
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
    if keyword_ids:
        params["with_keywords"] = "|".join(str(k) for k in keyword_ids)
    if crew_ids:
        params["with_crew"] = "|".join(str(c) for c in crew_ids)

    r = requests.get(f"{BASE_URL}/discover/movie", params=params, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    page1_results = data.get("results", [])
    total = min(data.get("total_pages", 1), 500)
    if total == 0 or not page1_results:
        return None

    excluded_ids = excluded_ids or set()
    movie = None
    # Pull a random page for variety. TMDB intermittently returns 5xx on
    # some pages (notably the partial last page), so on a bad response we
    # try another page instead of giving up on the whole pick.
    for _ in range(12):
        params["page"] = random.randint(1, total)
        r = requests.get(f"{BASE_URL}/discover/movie", params=params, timeout=10)
        if r.status_code != 200:
            continue
        candidates = [m for m in r.json().get("results", [])
                      if m["id"] not in excluded_ids]
        if candidates:
            movie = random.choice(candidates)
            break
    # Fallback: reuse the page-1 results we already fetched, so a run of
    # TMDB page errors can't produce a spurious "No movies found".
    if not movie:
        candidates = [m for m in page1_results if m["id"] not in excluded_ids]
        if candidates:
            movie = random.choice(candidates)
    if not movie:
        return None

    detail = requests.get(
        f"{BASE_URL}/movie/{movie['id']}",
        params={"api_key": api_key, "append_to_response": "watch/providers,videos,credits"},
        timeout=10,
    ).json()

    return _movie_to_shape(detail, region)


# ── TV SHOWS ────────────────────────────────────────────────────────────────

def _tv_to_shape(detail: dict, region: str = "US") -> dict:
    """Normalize a TV detail payload to the same shape the UI uses for movies."""
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

    episode_runtimes = detail.get("episode_run_time") or []
    avg_runtime = episode_runtimes[0] if episode_runtimes else None
    seasons = detail.get("number_of_seasons") or 0
    episodes = detail.get("number_of_episodes") or 0

    creators = [c["name"] for c in detail.get("created_by", []) if c.get("name")]
    creator_str = ", ".join(creators) if creators else None

    imdb_id = detail.get("external_ids", {}).get("imdb_id") or detail.get("imdb_id")

    return {
        "id": detail.get("id"),
        "title": detail.get("name", "Unknown"),
        "overview": detail.get("overview", ""),
        "rating": round(detail.get("vote_average", 0), 1),
        "votes": detail.get("vote_count", 0),
        "year": (detail.get("first_air_date") or "")[:4],
        "runtime": avg_runtime,
        "seasons": seasons,
        "episodes": episodes,
        "genres": [g["name"] for g in detail.get("genres", [])],
        "poster": IMAGE_BASE + detail["poster_path"] if detail.get("poster_path") else None,
        "streaming": streaming,
        "tmdb_url": f"https://www.themoviedb.org/tv/{detail.get('id')}",
        "trailer_url": f"https://www.youtube.com/watch?v={trailer_key}" if trailer_key else None,
        "popularity": detail.get("popularity", 0),
        "imdb_id": imdb_id,
        "cast": [m["name"] for m in detail.get("credits", {}).get("cast", [])[:5]],
        "director": creator_str,   # repurpose "director" slot for show creators
        "media_type": "tv",
    }


def fetch_tv_by_id(api_key: str, tv_id: int, region: str = "US") -> dict | None:
    try:
        detail = requests.get(
            f"{BASE_URL}/tv/{tv_id}",
            params={"api_key": api_key,
                    "append_to_response": "watch/providers,videos,credits,external_ids"},
            timeout=10,
        ).json()
    except Exception:
        return None
    if not detail.get("id"):
        return None
    return _tv_to_shape(detail, region)


def fetch_random_tv(api_key: str, genre_ids: list[int], year_from: int,
                    year_to: int, min_rating: float, provider_ids: list[int],
                    language: str = "", hidden_gem: bool = False,
                    actor_id: int | None = None, region: str = "US",
                    excluded_ids: set | None = None,
                    without_genre_ids: set | None = None,
                    keyword_ids: list[int] | None = None,
                    crew_ids: list[int] | None = None,
                    network_ids: list[int] | None = None) -> dict | None:
    has_keywords = bool(keyword_ids)
    params = {
        "api_key": api_key,
        "sort_by": "vote_average.desc" if hidden_gem else "popularity.desc",
        "vote_average.gte": min_rating,
        "vote_count.gte": 200 if hidden_gem else (15 if has_keywords else 30),
        "first_air_date.gte": f"{year_from}-01-01",
        "first_air_date.lte": f"{year_to}-12-31",
        "language": "en-US",
        "page": 1,
    }
    if hidden_gem:
        params["popularity.lte"] = 15

    if genre_ids:
        params["with_genres"] = "|".join(str(g) for g in genre_ids)
    if without_genre_ids:
        params["without_genres"] = ",".join(str(g) for g in without_genre_ids)
    if provider_ids:
        params["with_watch_providers"] = "|".join(str(p) for p in provider_ids)
        params["watch_region"] = region
    if language:
        params["with_original_language"] = language
    if actor_id:
        params["with_cast"] = actor_id
    if keyword_ids:
        params["with_keywords"] = "|".join(str(k) for k in keyword_ids)
    if crew_ids:
        params["with_crew"] = "|".join(str(c) for c in crew_ids)
    if network_ids:
        params["with_networks"] = "|".join(str(n) for n in network_ids)

    r = requests.get(f"{BASE_URL}/discover/tv", params=params, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    page1_results = data.get("results", [])
    total = min(data.get("total_pages", 1), 500)
    if total == 0 or not page1_results:
        return None

    excluded_ids = excluded_ids or set()
    show = None
    # TMDB intermittently 5xxs on some pages; try another page rather than
    # failing the whole pick on a single bad response.
    for _ in range(12):
        params["page"] = random.randint(1, total)
        r = requests.get(f"{BASE_URL}/discover/tv", params=params, timeout=10)
        if r.status_code != 200:
            continue
        candidates = [t for t in r.json().get("results", [])
                      if t["id"] not in excluded_ids]
        if candidates:
            show = random.choice(candidates)
            break
    # Fallback: reuse the page-1 results we already fetched.
    if not show:
        candidates = [t for t in page1_results if t["id"] not in excluded_ids]
        if candidates:
            show = random.choice(candidates)
    if not show:
        return None

    detail = requests.get(
        f"{BASE_URL}/tv/{show['id']}",
        params={"api_key": api_key,
                "append_to_response": "watch/providers,videos,credits,external_ids"},
        timeout=10,
    ).json()

    return _tv_to_shape(detail, region)
