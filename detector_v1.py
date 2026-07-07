#!/usr/bin/env python3
"""AdShark detector v1 (shadow mode, offline) - runs against a recorded game file.

Three voting detectors per the Build Plan section 2:
  A. score-bug presence   (primary for sports: static graphic in a corner ROI)
  B. black-frame          (broadcast transition cue)
  C. loudness signature   (ads mixed louder/denser)  [stub until audio wiring is tuned]

Bias: NEVER miss a play. Switch to ads only on 2-of-3 agreement held >= HOLD_SECONDS;
switch back the instant the score bug returns.

Usage: python3 detector_v1.py recording.mkv
Output: timestamped would-have-switched log (shadow mode) + summary.
This is a v1 skeleton to tune against real recordings in Phase 3.
"""
import sys, time
import cv2
import numpy as np

ANALYZE_W, ANALYZE_H = 640, 360          # low-res analysis per build plan
SAMPLE_FPS = 10
BUG_GONE_SECONDS = 3.0                   # bug absent this long -> vote break
HOLD_SECONDS = 15.0                      # min stay in ad mode (no flapping)
BLACK_LUMA = 22                          # mean luma below this = black frame
BLACK_WINDOW = 10.0                      # black-frame cue stays "hot" this long
# score-bug ROIs to try (normalized x, y, w, h) - bottom strip + 4 corners
ROIS = {
    "bottom-strip": (0.15, 0.82, 0.70, 0.13),
    "top-left":     (0.02, 0.03, 0.28, 0.14),
    "top-right":    (0.70, 0.03, 0.28, 0.14),
    "bottom-left":  (0.02, 0.80, 0.28, 0.16),
    "bottom-right": (0.70, 0.80, 0.28, 0.16),
}

def roi_slice(frame, roi):
    h, w = frame.shape[:2]
    x, y, rw, rh = roi
    return frame[int(y*h):int((y+rh)*h), int(x*w):int((x+rw)*w)]

class BugWatcher:
    """A static graphic = region whose edges barely change frame-to-frame
    while the rest of the picture moves. Track edge-stability per ROI,
    lock onto the most stable ROI, then report bug presence."""
    def __init__(self):
        self.prev = {}
        self.stability = {k: 0.0 for k in ROIS}
        self.locked = None
        self.frames = 0
    def update(self, gray):
        self.frames += 1
        present = None
        for name, roi in ROIS.items():
            region = roi_slice(gray, roi)
            edges = cv2.Canny(region, 60, 160)
            if name in self.prev:
                prev_edges = self.prev[name]
                if prev_edges.shape == edges.shape:
                    both = cv2.countNonZero(cv2.bitwise_and(edges, prev_edges))
                    any_ = cv2.countNonZero(cv2.bitwise_or(edges, prev_edges)) or 1
                    overlap = both / any_
                    dens = cv2.countNonZero(edges) / edges.size
                    # stable graphic: high frame-to-frame edge overlap + real edge density
                    score = overlap if dens > 0.02 else 0.0
                    self.stability[name] = 0.95*self.stability[name] + 0.05*score
            self.prev[name] = edges
        if self.frames > SAMPLE_FPS * 20 and self.locked is None:
            best = max(self.stability, key=self.stability.get)
            if self.stability[best] > 0.45:
                self.locked = best
        if self.locked:
            present = self.stability[self.locked] > 0.30
        return present   # True/False once locked, None while learning

def main(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(src_fps / SAMPLE_FPS))
    bug = BugWatcher()
    bug_gone_since = None
    black_streak = 0
    last_black_t = -1e9
    mode = "GAME"
    last_switch_t = -1e9
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

        # detector B: black frames (sticky: a transition cue counts for the
        # next BLACK_WINDOW seconds, so it can overlap the slower bug vote)
        is_black = gray.mean() < BLACK_LUMA
        black_streak = black_streak + 1 if is_black else 0
        if black_streak >= 2:                   # >=0.2s of black
            last_black_t = t
        vote_black = (t - last_black_t) <= BLACK_WINDOW

        # detector A: score bug
        bug_present = bug.update(gray)
        if bug_present is False and bug_gone_since is None:
            bug_gone_since = t
        if bug_present:
            bug_gone_since = None
        vote_bug = bug_gone_since is not None and (t - bug_gone_since) >= BUG_GONE_SECONDS

        # detector C: loudness - stub (audio path lands with capture tuning)
        vote_loud = False

        votes = sum([vote_bug, vote_black, vote_loud])

        if mode == "GAME" and votes >= 2 and (t - last_switch_t) > 5:
            mode = "ADS"; last_switch_t = t
            events.append((t, "WOULD SWITCH -> HOUSE ADS", f"votes={votes} bug_gone={vote_bug} black={vote_black}"))
        elif mode == "ADS" and bug_present and (t - last_switch_t) >= HOLD_SECONDS:
            mode = "GAME"; last_switch_t = t
            events.append((t, "WOULD SWITCH -> GAME (bug back)", "instant-return rule"))
    cap.release()
    print(f"\n=== AdShark detector v1 shadow log: {path} ===")
    print(f"locked score-bug ROI: {bug.locked}")
    for t, what, why in events:
        print(f"[{int(t//60):3d}:{t%60:04.1f}] {what}   ({why})")
    print(f"=== {len(events)} events. Compare against your own notes of the real breaks. ===")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 detector_v1.py <recording.mkv>")
    main(sys.argv[1])
