#!/usr/bin/env python3
"""AdShark scoring harness — grades a detector run against ground truth.

Answers the only question that matters before a restaurant pitch:
does the detector meet the success gate on THIS recording?

Inputs:
  1. detector JSON  (from detector_v2.py --json out.json)
  2. ground-truth breaks file: one commercial break per line, "start end" in
     seconds (mm:ss also accepted). '#' comments and blank lines ignored. e.g.

        # real breaks I noted while watching game_0712.mkv
        02:00 03:30
        08:00 08:55
        612   700

Gate (per recording):
  - >= 90% of breaks caught within CATCH_WINDOW (5s) of break start
  - return-to-game latency <= RETURN_MAX (2s), zero missed plays
  - zero false switches (switch to ads with no real break)

Usage:  python3 score.py out.json truth.txt
Exit code 0 = PASS, 1 = FAIL (so it can gate CI / a nightly run).
"""
import sys, json, re

CATCH_WINDOW = 5.0     # break "caught" if TO_ADS within this many s of break start
CATCH_EARLY  = 3.0     # allow switching this many s before the marked start
RETURN_MAX   = 2.0     # return-to-game must be within this many s of program resume
FALSE_PAD    = 2.0     # a TO_ADS this far outside any break = false switch
CATCH_RATE_GATE = 0.90

def parse_time(tok):
    tok = tok.strip()
    if ":" in tok:
        m, s = tok.split(":")
        return int(m) * 60 + float(s)
    return float(tok)

def load_truth(path):
    breaks = []
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = re.split(r"[\s,]+", line)
            if len(parts) < 2:
                continue
            breaks.append((parse_time(parts[0]), parse_time(parts[1])))
    breaks.sort()
    return breaks

def load_events(path):
    with open(path) as f:
        data = json.load(f)
    ev = data.get("events", [])
    to_ads  = sorted(e["t"] for e in ev if e["action"] == "TO_ADS")
    to_game = sorted(e["t"] for e in ev if e["action"] == "TO_GAME")
    return data, to_ads, to_game

def in_any_break(t, breaks):
    return any(bs - FALSE_PAD <= t <= be + FALSE_PAD for bs, be in breaks)

def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python3 score.py <detector.json> <truth.txt>")
    data, to_ads, to_game = load_events(sys.argv[1])
    breaks = load_truth(sys.argv[2])
    if not breaks:
        sys.exit("no breaks in ground-truth file")

    rows, caught, missed_plays = [], 0, 0
    for bs, be in breaks:
        # detection: earliest TO_ADS from just-before start through end of break
        cand = [t for t in to_ads if bs - CATCH_EARLY <= t <= be]
        det_t = min(cand) if cand else None
        det_lat = (max(0.0, det_t - bs) if det_t is not None else None)
        is_caught = det_t is not None and det_t <= bs + CATCH_WINDOW
        if is_caught:
            caught += 1
        # return: earliest TO_GAME at/after the detected switch (or after start)
        after = det_t if det_t is not None else bs
        rcand = [t for t in to_game if t >= after]
        ret_t = min(rcand) if rcand else None
        ret_lat = (ret_t - be) if ret_t is not None else None
        # missed play = still in ads > RETURN_MAX after program resumed (or never returned)
        late = (ret_lat is None) or (ret_lat > RETURN_MAX)
        if det_t is not None and late:
            missed_plays += 1
        rows.append((bs, be, det_lat, is_caught, ret_lat, late and det_t is not None))

    false_switches = [t for t in to_ads if not in_any_break(t, breaks)]
    catch_rate = caught / len(breaks)

    # ---- report ----
    print(f"\n=== AdShark score: {data.get('source','?')} "
          f"(audio={'yes' if data.get('have_audio') else 'no'}, roi={data.get('locked_roi')}) ===")
    print(f"{'break (start-end)':>20} | {'det':>6} | caught | {'return':>7} | miss")
    print("-" * 62)
    for bs, be, dl, ic, rl, mp in rows:
        b = f"{int(bs//60):02d}:{bs%60:04.1f}-{int(be//60):02d}:{be%60:04.1f}"
        dls = f"{dl:4.1f}s" if dl is not None else "  -- "
        rls = f"{rl:+5.1f}s" if rl is not None else "  --  "
        print(f"{b:>20} | {dls:>6} | {'YES' if ic else 'no ':>5}  | {rls:>7} | {'MISS' if mp else ''}")
    print("-" * 62)

    ret_lats = [rl for *_, rl, _ in rows if rl is not None]
    worst_ret = max(ret_lats) if ret_lats else None
    print(f"breaks caught within {CATCH_WINDOW:.0f}s : {caught}/{len(breaks)}  ({catch_rate*100:.0f}%)")
    print(f"return-to-game worst     : {worst_ret:+.1f}s" if worst_ret is not None else "return-to-game worst     : n/a")
    print(f"missed plays (late back) : {missed_plays}")
    print(f"false switches           : {len(false_switches)}"
          + (f"  at {[round(t,1) for t in false_switches]}" if false_switches else ""))

    # ---- gate ----
    checks = [
        (f">=90% caught within {CATCH_WINDOW:.0f}s", catch_rate >= CATCH_RATE_GATE),
        (f"return <= {RETURN_MAX:.0f}s, zero missed plays", missed_plays == 0 and (worst_ret is None or worst_ret <= RETURN_MAX)),
        ("zero false switches", len(false_switches) == 0),
    ]
    print("\ngate:")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    overall = all(ok for _, ok in checks)
    print(f"\n{'>>> PASS — meets the success gate on this recording' if overall else '>>> FAIL — tune and re-run'}\n")
    sys.exit(0 if overall else 1)

if __name__ == "__main__":
    main()
