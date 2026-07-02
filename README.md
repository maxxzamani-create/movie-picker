# Movie Picker

A desktop app that picks random movies based on your preferences using the TMDB database.

## Setup (one time)

### 1. Install Python
Download and install **Python 3.10+** from https://www.python.org/downloads/

> During install, check **"Add Python to PATH"**

### 2. Install dependencies
Double-click `setup.bat` (or run in terminal):
```
setup.bat
```

### 3. Get a free TMDB API key
1. Create a free account at https://www.themoviedb.org/
2. Go to Settings → API → Request an API key (v3 auth)
3. Copy the key — you'll paste it into the app on first launch

## Running the app

Double-click `run.bat`, or:
```
python main.py
```

## Features

- **Genre filters** — pick one or more genres (or none for anything)
- **Year range** — e.g. 1980–2000 for classics
- **Minimum rating** — slider from 0–10
- **Streaming providers** — filter by Netflix, Disney+, Hulu, etc. (US)
- **Watchlist** — save movies you want to watch
- **Pick Again** — keep rolling until you find something good
- **View on TMDB** — opens the movie's TMDB page in your browser

Preferences are saved automatically between sessions.

---

# Commercial Override (demo) — `/co/`

A working proof-of-concept of a system that detects commercial breaks in a
live TV broadcast and switches the screen to the business's own promo spots
(your burger instead of McDonald's), then switches back when the game resumes.

**Legal note:** the design never modifies the broadcaster's signal. It detects
a break and briefly changes *what the screen displays* — the same as flipping
inputs during a commercial — then returns to the live feed.

## Try it

```
pip install -r requirements.txt
python server.py
```

- **`/co/`** — the virtual TV. Hit *Start the broadcast* (or *Skip to just
  before the break*). ~30 s in, the feed hits a commercial break: the detector
  sees black frames + audio silence followed by a high scene-cut rate, and the
  screen swaps to the business's promo rotation. When programming resumes it
  swaps back. Live telemetry (frame luminance, audio level) is measured in
  real time from the playing video.
- **`/co/dashboard`** — the business side: upload promo spots, toggle the
  rotation, and see impression counts / airtime per spot.

## How detection works (`co_detect.py`)

Same heuristics production systems start with, run via ffmpeg:

1. **blackdetect** — breaks are bracketed by runs of black frames
2. **silencedetect** — those black runs coincide with dead audio
3. **scene-cut rate** — ad blocks cut 20–30×/min vs 3–5×/min for programming

A boundary = black + silence overlapping; the span between boundaries is a
commercial block when its cut rate is high. On real hardware (Phase 2:
Raspberry Pi + HDMI capture between the cable box and TV, HDMI-CEC to switch
inputs) the identical logic runs on the live capture feed.

## Demo media

`static/co/*.mp4` are synthesized by `make_demo_media.py` (requires ffmpeg) —
a simulated football broadcast with a realistic break, plus three sample
promo spots. `game_feed.analysis.json` is the cached detector output so the
demo runs without ffmpeg installed.
