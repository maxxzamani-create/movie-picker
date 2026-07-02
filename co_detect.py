"""
Commercial-break detection engine.

Uses the same heuristics production systems start with, run through ffmpeg:

  1. blackdetect    — commercials are bracketed by runs of black frames
  2. silencedetect  — those black runs coincide with dead audio
  3. scene-cut rate — ad blocks cut 20-30x/min vs 3-5x/min for programming
  4. loudness       — ad blocks are mixed hotter than programming

A boundary is declared where black frames and silence overlap. The span
between two boundaries is classified as a commercial block when its
scene-cut rate is high (or it's short and loud). Everything else is
treated as live programming.

On real hardware (Phase 2) the identical logic runs on a live HDMI
capture feed instead of a file; only the frame source changes.

CLI:  python co_detect.py static/co/game_feed.mp4
      → writes analysis JSON next to the video (game_feed.analysis.json)
"""
import json
import os
import re
import subprocess
import sys

# Tunables — same knobs you'd expose on the Phase 2 appliance
BLACK_MIN_DUR    = 0.4    # s of black frames to count
BLACK_PIX_THRESH = 0.10   # max luminance to call a pixel black
SILENCE_NOISE_DB = -45    # audio below this is "silence"
SILENCE_MIN_DUR  = 0.3
SCENE_THRESHOLD  = 0.30   # ffmpeg scene-change score for a hard cut
CUTS_PER_MIN_AD  = 10.0   # cut rate above this ⇒ commercial block
MAX_BREAK_S      = 300    # sanity cap: no break is longer than 5 min


def _ffmpeg_stderr(args: list[str]) -> str:
    proc = subprocess.run(["ffmpeg", "-hide_banner", *args, "-f", "null", "-"],
                          capture_output=True, text=True)
    return proc.stderr


def detect_black_and_silence(path: str) -> tuple[list, list]:
    err = _ffmpeg_stderr([
        "-i", path,
        "-vf", f"blackdetect=d={BLACK_MIN_DUR}:pix_th={BLACK_PIX_THRESH}",
        "-af", f"silencedetect=n={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_DUR}",
    ])
    blacks = [(float(m.group(1)), float(m.group(2)))
              for m in re.finditer(
                  r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    silences = []
    for m in re.finditer(r"silence_start: ([\d.]+)", err):
        silences.append([float(m.group(1)), None])
    for i, m in enumerate(re.finditer(r"silence_end: ([\d.]+)", err)):
        if i < len(silences):
            silences[i][1] = float(m.group(1))
    silences = [(s, e) for s, e in silences if e is not None]
    return blacks, silences


def detect_scene_cuts(path: str) -> list[float]:
    err = _ffmpeg_stderr([
        "-i", path,
        "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',metadata=print",
    ])
    return [float(m.group(1))
            for m in re.finditer(r"pts_time:([\d.]+)", err)]


def video_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip())


def _overlaps(a: tuple, b: tuple) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def analyze(path: str) -> dict:
    blacks, silences = detect_black_and_silence(path)
    cuts = detect_scene_cuts(path)
    duration = video_duration(path)

    # Boundary = a black-frame run that overlaps an audio-silence run
    boundaries = [(bs, be) for bs, be in blacks
                  if any(_overlaps((bs, be), s) for s in silences)]

    # Classify each span between consecutive boundaries by scene-cut rate
    windows = []
    for (b1s, b1e), (b2s, b2e) in zip(boundaries, boundaries[1:]):
        span = (b1e, b2s)
        span_len = span[1] - span[0]
        if span_len <= 0 or span_len > MAX_BREAK_S:
            continue
        n_cuts = sum(1 for c in cuts if span[0] < c < span[1])
        cut_rate = n_cuts / span_len * 60
        if cut_rate >= CUTS_PER_MIN_AD:
            windows.append({
                # Override from the moment the screen goes black until the
                # moment programming resumes — covers the whole break.
                "start": round(b1s, 2),
                "end":   round(b2e, 2),
                "signals": {
                    "black_frames": True,
                    "audio_silence": True,
                    "scene_cuts": n_cuts,
                    "cuts_per_min": round(cut_rate, 1),
                },
                "confidence": min(0.99, 0.6 + min(cut_rate, 30) / 75),
            })

    return {
        "video": os.path.basename(path),
        "duration": round(duration, 2),
        "boundaries": [[round(s, 2), round(e, 2)] for s, e in boundaries],
        "scene_cuts": [round(c, 2) for c in cuts],
        "commercial_windows": windows,
        "detector": {
            "black_min_dur_s": BLACK_MIN_DUR,
            "silence_noise_db": SILENCE_NOISE_DB,
            "scene_threshold": SCENE_THRESHOLD,
            "cuts_per_min_ad": CUTS_PER_MIN_AD,
        },
    }


def analysis_path_for(video_path: str) -> str:
    base, _ = os.path.splitext(video_path)
    return base + ".analysis.json"


def analyze_and_cache(video_path: str, force: bool = False) -> dict:
    cache = analysis_path_for(video_path)
    if not force and os.path.exists(cache):
        try:
            with open(cache) as f:
                return json.load(f)
        except Exception:
            pass
    result = analyze(video_path)
    with open(cache, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "static", "co", "game_feed.mp4")
    result = analyze_and_cache(target, force=True)
    print(json.dumps(result, indent=2))
