# AD-SHARK 🦈 — the Commercial Killer

**When the commercials come on, the screen shows *your* specials instead.**

A business (sports bar, restaurant, gym) plays a live game on its TVs. When
the broadcast cuts to a commercial break, AD-SHARK detects the
break and switches the screen to the business's own promo spots — your
burger instead of McDonald's — then switches back the moment the game
returns.

**Legal by design:** the broadcaster's signal is never modified. The system
detects a break and briefly changes *what the screen displays* — the same
as flipping inputs during a commercial — then returns to the live feed.

## Try the demo

Live in your browser (nothing to install):
**https://maxxzamani-create.github.io/AD-SHARK/**

Or run it locally — double-click `run.bat` (Windows), or:

```
pip install -r requirements.txt
python server.py
```

- **`/co/`** — the virtual TV. Hit *Start the broadcast* (or *Skip to just
  before the break*). ~30 s in, the feed hits a commercial break: the
  detector sees black frames + audio silence followed by a high scene-cut
  rate, and the screen swaps to the business's promo rotation. When
  programming resumes it swaps back. Live telemetry (frame luminance,
  audio level) is measured in real time from the playing video.
- **`/co/dashboard`** — the business side: upload promo spots, toggle the
  rotation, and see impression counts / airtime per spot.

## The revenue leak (why this exists)

A customer just finished dinner and is thinking about something sweet. The
break hits and a soft-serve commercial plays on your TV — now dessert happens
on the drive home, at someone else's register. While they're your captive
audience, the screen should be selling *your* dessert menu. No more Pizza Hut
ads in a pizza restaurant.

Published research behind the pitch:

- Adults snack **~45% more** while food commercials play — the effect is
  automatic and unrelated to hunger (Harris et al., via Psychology Today).
- **14%** of people report craving the exact product they just saw advertised,
  and **8%** go on to purchase it (ecological momentary assessment studies of
  food-marketing exposure).
- **31%** of diners are already thinking about dessert before the entrée
  arrives (Restaurant-Hospitality consumer research) — the sale is sitting at
  the table waiting to be claimed.
- **78%** of consumers say they'd take a discounted add-on like dessert or a
  drink at full-service restaurants.

The dashboard includes a calculator that turns these rates into an estimated
weekly/yearly revenue leak for a specific room.

## How detection works (`co_detect.py`)

The same heuristics production systems start with, run via ffmpeg:

1. **blackdetect** — breaks are bracketed by runs of black frames
2. **silencedetect** — those black runs coincide with dead audio
3. **scene-cut rate** — ad blocks cut 20–30×/min vs 3–5×/min for programming

A boundary = black + silence overlapping; the span between boundaries is a
commercial block when its cut rate is high.

## Roadmap

- **Phase 1 (this repo):** working web demo — detection engine, virtual TV,
  business dashboard with impression tracking.
- **Phase 2:** on-premise hardware — Raspberry Pi + HDMI capture card sits
  between the cable box and the TV; the identical detection logic runs on
  the live capture feed and switches the TV's input over HDMI-CEC during
  breaks (~$150 bill of materials per TV).
- **Phase 3:** fleet management for multi-location businesses and a local
  ad-slot marketplace.

## Demo media

Promo spots are built on licensed Adobe Stock photography (free-collection assets, in `assets_src/`). `static/co/*.mp4` are rendered by `make_demo_media.py` (requires ffmpeg) —
a simulated football broadcast with a realistic break, plus three sample
promo spots. `game_feed.analysis.json` is the cached detector output so the
demo runs without ffmpeg installed.
