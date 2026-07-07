#!/usr/bin/env python3
"""AdShark detector v2 (shadow mode, offline) — grades a recorded game file.

Upgrades over v1:
  - Detector C (loudness) is REAL now: a one-pass audio loudness envelope
    (ffmpeg -> raw PCM -> per-window dBFS). Ads run louder + denser than play.
  - Detector D (scene-cut rate): ads cut fast; sustained high cut-rate votes break.
  - Audio-silence pairs with black frames for a strong transition cue.
  - Weighted voting (not flat 2-of-3) with a never-miss-a-play bias:
    score-bug is the ace, but bug-gone ALONE never switches — it needs a
    corroborating cue. Return-to-game is instant the moment the bug is back.
  - Machine-readable output: writes an events .json (for score.py) and a
    SQLite event log (the seed of the customer "reclaimed value" dashboard).

The eight detector *types* in the patent spec are the north star; v2 ships the
four that need no extra hardware: score-bug(302), black/silence(304), loudness(306),
scene-cut(308). The rest (logo/ACR/caption/SCTE-35) slot into the same vote bus later.

Usage:
    python3 detector_v2.py recording.mkv [--json out.json] [--db events.db] [--quiet]

Output: timestamped shadow log + a summary. Feed the .json to score.py with a
ground-truth breaks file to grade against the success gate.
"""
import sys, os, time, json, argparse, sqlite3, subprocess
import cv2
import numpy as np

# ----------------------------- CONFIG (tune here) -----------------------------
ANALYZE_W, ANALYZE_H = 640, 360     # low-res analysis (plenty for detection)
SAMPLE_FPS   = 10                   # frames analysed per second

# Detector A — score bug
BUG_LEARN_SECONDS = 20.0            # observe this long before locking an ROI
BUG_LOCK_MIN      = 0.45            # min stability to trust an ROI as "the bug"
BUG_PRESENT_MIN   = 0.30            # locked-ROI stability above this = bug present
BUG_GONE_SECONDS  = 3.0            # bug absent this long -> bug-gone cue

# Detector B — black frame + audio silence
BLACK_LUMA    = 22                  # mean luma below this = black frame
BLACK_MINRUN  = 2                   # frames of black to count a transition
BLACK_WINDOW  = 10.0                # transition cue stays "hot" this long (s)
SILENCE_DBFS  = -45.0               # below this = audio silence
SILENCE_WINDOW= 8.0                 # silence cue hot window (s)

# Detector C — loudness
AUD_SR        = 8000                # audio pre-pass sample rate
AUD_WIN_S     = 0.25               # loudness window (s)
LOUD_BASE_S   = 90.0               # rolling baseline window (s)
LOUD_MARGIN_DB= 4.0                # sustained dB above baseline = loud cue
LOUD_SUSTAIN_S= 2.0                # loudness must hold this long

# Detector D — scene-cut rate
CUT_DIFF      = 28.0               # mean abs frame delta above this = a cut
CUT_RATE_WIN  = 6.0               # window to measure cuts/sec (s)
CUT_RATE_HOT  = 0.55              # cuts/sec above this = fast-cut (ad) cue

# Voting — weighted, never-miss-a-play biased
W = {"bug_gone": 2.0, "black": 1.0, "silence": 0.9, "loud": 0.9, "cut": 0.8}
SWITCH_THRESHOLD = 2.6            # >= this vote-sum -> switch to house ads
# 2.6 means bug-gone(2.0)+ANY one corroborator, OR a strong no-bug combo
# (black+silence+loud+cut = 3.6). Bug-gone alone (2.0) never switches.
MIN_HOLD_S    = 12.0             # min stay in ad mode (anti-flap)
RESTORE_CLEAR_S = 3.0           # if bug never locked: break cues quiet this long -> restore
SWITCH_COOLDOWN = 4.0          # min seconds between switches

# score-bug ROIs to try (normalized x, y, w, h): bottom strip + 4 corners
ROIS = {
    "bottom-strip": (0.15, 0.82, 0.70, 0.13),
    "top-left":     (0.02, 0.03, 0.28, 0.14),
    "top-right":    (0.70, 0.03, 0.28, 0.14),
    "bottom-left":  (0.02, 0.80, 0.28, 0.16),
    "bottom-right": (0.70, 0.80, 0.28, 0.16),
}

# ----------------------------- audio pre-pass --------------------------------
def audio_loudness(path):
    """Return (times[], dbfs[]) at AUD_WIN_S resolution, or None if no audio.
    One ffmpeg pass -> mono s16le PCM -> per-window RMS dBFS."""
    cmd = ["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(AUD_SR),
           "-f", "s16le", "-"]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return None
    raw = p.stdout
    if not raw or len(raw) < AUD_SR:            # < ~0.5s of audio -> treat as none
        return None
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    win = max(1, int(AUD_SR * AUD_WIN_S))
    n = len(x) // win
    if n < 2:
        return None
    x = x[: n * win].reshape(n, win)
    rms = np.sqrt(np.mean(x * x, axis=1) + 1e-9)
    dbfs = 20.0 * np.log10(rms + 1e-9)
    times = np.arange(n) * AUD_WIN_S
    return times, dbfs

class LoudnessWatcher:
    """Adaptive baseline (rolling median of recent loudness). Vote 'loud' when
    short-term loudness sustains LOUD_MARGIN_DB above baseline; 'silence' when
    it drops below SILENCE_DBFS."""
    def __init__(self, times, dbfs):
        self.times = times
        self.dbfs = dbfs
        self.base_n = max(3, int(LOUD_BASE_S / AUD_WIN_S))
        self.sustain_n = max(1, int(LOUD_SUSTAIN_S / AUD_WIN_S))
        self.i = 0
    def at(self, t):
        """Return (loud_bool, silence_bool) for time t."""
        if self.times is None:
            return False, False
        while self.i + 1 < len(self.times) and self.times[self.i + 1] <= t:
            self.i += 1
        i = self.i
        cur = self.dbfs[i]
        lo = max(0, i - self.base_n)
        base = np.median(self.dbfs[lo:i + 1])
        s0 = max(0, i - self.sustain_n + 1)
        loud = bool(np.all(self.dbfs[s0:i + 1] >= base + LOUD_MARGIN_DB))
        silence = bool(cur < SILENCE_DBFS)
        return loud, silence

# ----------------------------- video detectors -------------------------------
def roi_slice(frame, roi):
    h, w = frame.shape[:2]
    x, y, rw, rh = roi
    return frame[int(y * h):int((y + rh) * h), int(x * w):int((x + rw) * w)]

class BugWatcher:
    """A static graphic = a region whose edges barely change frame-to-frame
    while the rest of the picture moves. Track edge-stability per ROI, lock the
    most stable one, then report bug presence."""
    def __init__(self):
        self.prev = {}
        self.stability = {k: 0.0 for k in ROIS}
        self.locked = None
        self.frames = 0
    def update(self, gray):
        self.frames += 1
        for name, roi in ROIS.items():
            region = roi_slice(gray, roi)
            edges = cv2.Canny(region, 60, 160)
            if name in self.prev and self.prev[name].shape == edges.shape:
                pe = self.prev[name]
                both = cv2.countNonZero(cv2.bitwise_and(edges, pe))
                any_ = cv2.countNonZero(cv2.bitwise_or(edges, pe)) or 1
                overlap = both / any_
                dens = cv2.countNonZero(edges) / edges.size
                score = overlap if dens > 0.02 else 0.0
                self.stability[name] = 0.95 * self.stability[name] + 0.05 * score
            self.prev[name] = edges
        if self.frames > SAMPLE_FPS * BUG_LEARN_SECONDS and self.locked is None:
            best = max(self.stability, key=self.stability.get)
            if self.stability[best] > BUG_LOCK_MIN:
                self.locked = best
        if self.locked:
            return self.stability[self.locked] > BUG_PRESENT_MIN
        return None   # None while still learning

class SceneCutWatcher:
    """Fast cuts are an ad signature. Track cuts/sec over a rolling window."""
    def __init__(self):
        self.prev = None
        self.cuts = []   # timestamps of recent cuts
    def update(self, gray, t):
        if self.prev is not None and self.prev.shape == gray.shape:
            d = float(np.mean(cv2.absdiff(gray, self.prev)))
            if d > CUT_DIFF:
                self.cuts.append(t)
        self.prev = gray
        self.cuts = [c for c in self.cuts if c >= t - CUT_RATE_WIN]
        rate = len(self.cuts) / CUT_RATE_WIN
        return rate >= CUT_RATE_HOT

# ----------------------------- SQLite log ------------------------------------
def open_db(path):
    if not path:
        return None
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY, source TEXT, t_sec REAL, action TEXT,
        mode TEXT, vote REAL, detail TEXT, wall TEXT)""")
    db.commit()
    return db

def log_event(db, source, t, action, mode, vote, detail):
    if db is None:
        return
    db.execute("INSERT INTO events(source,t_sec,action,mode,vote,detail,wall) "
               "VALUES(?,?,?,?,?,?,?)",
               (source, round(t, 2), action, mode, round(vote, 2), detail,
                time.strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()

# ----------------------------- main ------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json", default=None, help="write switch events as JSON")
    ap.add_argument("--db", default=None, help="append events to a SQLite db")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    path = args.path

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(src_fps / SAMPLE_FPS))

    aud = audio_loudness(path)
    loud_watch = LoudnessWatcher(*aud) if aud else LoudnessWatcher(None, None)
    have_audio = aud is not None

    bug = BugWatcher()
    cutw = SceneCutWatcher()
    db = open_db(args.db)
    source = os.path.basename(path)

    bug_gone_since = None
    last_black_t = -1e9
    last_silence_t = -1e9
    black_streak = 0
    mode = "GAME"
    last_switch_t = -1e9
    clear_since = None
    events = []
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        if n % step:
            continue
        t = n / src_fps
        small = cv2.resize(frame, (ANALYZE_W, ANALYZE_H))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # B: black frame (sticky window)
        is_black = gray.mean() < BLACK_LUMA
        black_streak = black_streak + 1 if is_black else 0
        if black_streak >= BLACK_MINRUN:
            last_black_t = t
        vote_black = (t - last_black_t) <= BLACK_WINDOW

        # C: loudness + silence
        loud, silence = loud_watch.at(t)
        if silence:
            last_silence_t = t
        vote_silence = (t - last_silence_t) <= SILENCE_WINDOW
        vote_loud = bool(loud)

        # D: scene-cut rate
        vote_cut = cutw.update(gray, t)

        # A: score bug
        bug_present = bug.update(gray)
        if bug_present is False and bug_gone_since is None:
            bug_gone_since = t
        if bug_present:
            bug_gone_since = None
        vote_bug_gone = bug_gone_since is not None and (t - bug_gone_since) >= BUG_GONE_SECONDS

        vote = (W["bug_gone"] * vote_bug_gone + W["black"] * vote_black +
                W["silence"] * vote_silence + W["loud"] * vote_loud +
                W["cut"] * vote_cut)

        any_break_cue = vote_black or vote_silence or vote_loud or vote_cut or vote_bug_gone
        if not any_break_cue:
            clear_since = clear_since or t
        else:
            clear_since = None

        detail = (f"bug_gone={int(vote_bug_gone)} black={int(vote_black)} "
                  f"silence={int(vote_silence)} loud={int(vote_loud)} cut={int(vote_cut)}")

        if mode == "GAME" and vote >= SWITCH_THRESHOLD and (t - last_switch_t) > SWITCH_COOLDOWN:
            mode = "ADS"; last_switch_t = t
            events.append({"t": round(t, 2), "action": "TO_ADS", "vote": round(vote, 2), "detail": detail})
            log_event(db, source, t, "TO_ADS", mode, vote, detail)
        elif mode == "ADS" and (t - last_switch_t) >= MIN_HOLD_S:
            restore = False; why = ""
            if bug_present:                       # ace: program is back
                restore = True; why = "bug-back"
            elif bug.locked is None and clear_since and (t - clear_since) >= RESTORE_CLEAR_S:
                restore = True; why = "cues-clear"   # no bug lock -> fall back to cue-quiet
            if restore:
                mode = "GAME"; last_switch_t = t
                events.append({"t": round(t, 2), "action": "TO_GAME", "vote": round(vote, 2), "detail": why})
                log_event(db, source, t, "TO_GAME", mode, vote, why)
    cap.release()
    if db is not None:
        db.close()

    result = {
        "source": source, "have_audio": have_audio,
        "locked_roi": bug.locked, "events": events,
        "config": {"threshold": SWITCH_THRESHOLD, "weights": W},
    }
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)

    if not args.quiet:
        print(f"\n=== AdShark detector v2 shadow log: {source} ===")
        print(f"audio: {'yes' if have_audio else 'NO (video-only)'}   locked score-bug ROI: {bug.locked}")
        for e in events:
            m, s = int(e['t'] // 60), e['t'] % 60
            print(f"[{m:3d}:{s:04.1f}] {e['action']:<8} vote={e['vote']:<4} ({e['detail']})")
        print(f"=== {len(events)} switch events. Grade with:  python3 score.py {args.json or 'out.json'} truth.txt ===")

if __name__ == "__main__":
    main()
