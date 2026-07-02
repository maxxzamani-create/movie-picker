"""
Commercial Override — Flask blueprint.

A virtual proof-of-concept of the Phase-1 product: detect commercial breaks
in a (simulated) live broadcast and switch the screen to the business's own
promo spots, then switch back when programming resumes.

Pages
  /co/            the "TV" — live feed + detection telemetry + auto-override
  /co/dashboard   business dashboard — ad library, settings, impression stats

Data lives in co_data.json (gitignored, seeded on first run). Uploaded ads
go to static/co/uploads/.
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request
from werkzeug.utils import secure_filename

import co_detect

co_bp = Blueprint("co", __name__, url_prefix="/co")

BASE_DIR   = os.path.dirname(__file__)
DATA_FILE  = os.path.join(BASE_DIR, "co_data.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "co", "uploads")
FEED_PATH  = os.path.join(BASE_DIR, "static", "co", "game_feed.mp4")

MAX_UPLOAD_BYTES = 60 * 1024 * 1024
ALLOWED_EXT = {".mp4", ".webm", ".mov", ".m4v"}

_lock = threading.Lock()

DEFAULTS = {
    "business_name": "Maxx's Bar & Grill",
    "override_enabled": True,
    "ads": [
        {"id": "burger", "name": "Zenie Burger — ½ Price",
         "url": "/static/co/ad_burger.mp4",
         "url_webm": "/static/co/ad_burger.webm", "enabled": True, "builtin": True},
        {"id": "wings", "name": "50¢ Wing Night",
         "url": "/static/co/ad_wings.mp4",
         "url_webm": "/static/co/ad_wings.webm", "enabled": True, "builtin": True},
        {"id": "happyhour", "name": "Happy Hour 4–7",
         "url": "/static/co/ad_happyhour.mp4",
         "url_webm": "/static/co/ad_happyhour.webm", "enabled": True, "builtin": True},
    ],
    "impressions": [],
}


def _load() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                data = json.load(f)
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULTS))


def _save(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Pages ────────────────────────────────────────────────────────────────────

@co_bp.route("/")
def tv():
    return render_template("co_tv.html")


@co_bp.route("/dashboard")
def dashboard():
    return render_template("co_dashboard.html")


# ── State / settings ─────────────────────────────────────────────────────────

@co_bp.route("/api/state")
def state():
    with _lock:
        data = _load()
    try:
        analysis = co_detect.analyze_and_cache(FEED_PATH)
    except Exception as e:
        analysis = {"error": f"analysis unavailable: {e}",
                    "commercial_windows": [], "duration": 0}
    return jsonify({
        "business_name": data["business_name"],
        "override_enabled": data["override_enabled"],
        "ads": data["ads"],
        "feed_url": "/static/co/game_feed.mp4",
        "feed_url_webm": "/static/co/game_feed.webm",
        "analysis": analysis,
    })


@co_bp.route("/api/settings", methods=["POST"])
def settings():
    body = request.json or {}
    with _lock:
        data = _load()
        if "business_name" in body:
            name = str(body["business_name"]).strip()[:80]
            if name:
                data["business_name"] = name
        if "override_enabled" in body:
            data["override_enabled"] = bool(body["override_enabled"])
        _save(data)
    return jsonify({"ok": True,
                    "business_name": data["business_name"],
                    "override_enabled": data["override_enabled"]})


# ── Ad library ───────────────────────────────────────────────────────────────

@co_bp.route("/api/ads", methods=["POST"])
def upload_ad():
    file = request.files.get("file")
    name = (request.form.get("name") or "").strip()[:80]
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Unsupported type {ext} — use mp4/webm/mov"}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ad_id = uuid.uuid4().hex[:10]
    fname = f"{ad_id}_{secure_filename(file.filename)}"
    path = os.path.join(UPLOAD_DIR, fname)
    file.save(path)
    if os.path.getsize(path) > MAX_UPLOAD_BYTES:
        os.unlink(path)
        return jsonify({"error": "File too large (60 MB max)"}), 400

    ad = {"id": ad_id, "name": name or file.filename,
          "url": f"/static/co/uploads/{fname}", "enabled": True,
          "builtin": False}
    with _lock:
        data = _load()
        data["ads"].append(ad)
        _save(data)
    return jsonify({"ok": True, "ad": ad})


@co_bp.route("/api/ads/<ad_id>/toggle", methods=["POST"])
def toggle_ad(ad_id):
    with _lock:
        data = _load()
        for ad in data["ads"]:
            if ad["id"] == ad_id:
                ad["enabled"] = not ad["enabled"]
                _save(data)
                return jsonify({"ok": True, "enabled": ad["enabled"]})
    return jsonify({"error": "Not found"}), 404


@co_bp.route("/api/ads/<ad_id>", methods=["DELETE"])
def delete_ad(ad_id):
    with _lock:
        data = _load()
        ad = next((a for a in data["ads"] if a["id"] == ad_id), None)
        if not ad:
            return jsonify({"error": "Not found"}), 404
        if ad.get("builtin"):
            return jsonify({"error": "Built-in demo ads can only be disabled"}), 400
        data["ads"] = [a for a in data["ads"] if a["id"] != ad_id]
        _save(data)
    # Remove the file only after the record is gone
    fpath = os.path.join(BASE_DIR, ad["url"].lstrip("/"))
    if fpath.startswith(UPLOAD_DIR) and os.path.exists(fpath):
        try:
            os.unlink(fpath)
        except OSError:
            pass
    return jsonify({"ok": True})


# ── Impressions ──────────────────────────────────────────────────────────────

@co_bp.route("/api/impressions", methods=["POST"])
def log_impression():
    body = request.json or {}
    ad_id = body.get("ad_id")
    seconds = float(body.get("seconds") or 0)
    with _lock:
        data = _load()
        ad = next((a for a in data["ads"] if a["id"] == ad_id), None)
        if not ad:
            return jsonify({"error": "Unknown ad"}), 404
        data["impressions"].insert(0, {
            "ad_id": ad_id,
            "ad_name": ad["name"],
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(seconds, 1),
        })
        del data["impressions"][500:]   # keep the log bounded
        _save(data)
    return jsonify({"ok": True})


@co_bp.route("/api/impressions")
def impressions():
    with _lock:
        data = _load()
    log = data["impressions"]
    per_ad: dict = {}
    for imp in log:
        s = per_ad.setdefault(imp["ad_id"],
                              {"ad_name": imp["ad_name"], "plays": 0,
                               "seconds": 0.0, "last": imp["at"]})
        s["plays"] += 1
        s["seconds"] = round(s["seconds"] + imp["seconds"], 1)
    return jsonify({
        "total_plays": len(log),
        "total_seconds": round(sum(i["seconds"] for i in log), 1),
        "per_ad": per_ad,
        "recent": log[:25],
    })


@co_bp.route("/api/impressions/clear", methods=["POST"])
def clear_impressions():
    with _lock:
        data = _load()
        data["impressions"] = []
        _save(data)
    return jsonify({"ok": True})


# ── Analysis ─────────────────────────────────────────────────────────────────

@co_bp.route("/api/analyze", methods=["POST"])
def reanalyze():
    try:
        analysis = co_detect.analyze_and_cache(FEED_PATH, force=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(analysis)
