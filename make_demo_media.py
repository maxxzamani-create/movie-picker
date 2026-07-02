"""
Demo media generator for the Commercial Override module.

Synthesizes with ffmpeg:
  static/co/game_feed.mp4   — simulated live football broadcast containing a
                              commercial break (game → black+silence → loud
                              rapid-cut national ads → black+silence → game)
  static/co/ad_*.mp4        — the business's own promo spots that get shown
                              instead of the national ads

The break boundaries are marked exactly the way real broadcasts mark them
(black frames + audio silence, then a burst of scene cuts and louder audio),
so the detection engine in co_detect.py finds them with the same heuristics
a real capture device would use.

Run:  python make_demo_media.py
"""
import os
import shutil
import subprocess
import tempfile

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT_DIR   = os.path.join(os.path.dirname(__file__), "static", "co")

W, H, FPS = 640, 360, 30
V_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
          "-pix_fmt", "yuv420p", "-r", str(FPS)]
A_ARGS = ["-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "2"]


def run(args: list[str]):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def esc(text: str) -> str:
    """Escape drawtext special characters."""
    return (text.replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "’").replace("%", "\\%"))


def dtext(text, size, color, x, y, font=FONT_BOLD, extra=""):
    return (f"drawtext=fontfile={font}:text='{esc(text)}':fontsize={size}"
            f":fontcolor={color}:x={x}:y={y}:expansion=none{extra}")


# ── Segment builders ─────────────────────────────────────────────────────────

def game_segment(path, dur, quarter_clock, score):
    """Green-field 'live game' look: steady scene, crowd noise, scoreboard."""
    vf = ",".join([
        # subtle vertical pitch stripes so the frame isn't flat
        "drawbox=x=0:y=0:w=64:h=ih:color=0x156b28@0.5:t=fill",
        "drawbox=x=128:y=0:w=64:h=ih:color=0x156b28@0.5:t=fill",
        "drawbox=x=256:y=0:w=64:h=ih:color=0x156b28@0.5:t=fill",
        "drawbox=x=384:y=0:w=64:h=ih:color=0x156b28@0.5:t=fill",
        "drawbox=x=512:y=0:w=64:h=ih:color=0x156b28@0.5:t=fill",
        # yard line that drifts to give the frame motion
        "drawbox=x='mod(t*40\\,640)':y=0:w=6:h=ih:color=white@0.35:t=fill",
        # 'players' — two moving dots
        "drawbox=x='320+150*sin(t*1.2)':y='200+40*cos(t*0.9)':w=14:h=14:color=0xcc2222:t=fill",
        "drawbox=x='300+170*cos(t*0.8)':y='220+30*sin(t*1.4)':w=14:h=14:color=0x2244cc:t=fill",
        # broadcast chrome
        "drawbox=x=12:y=12:w=250:h=44:color=black@0.65:t=fill",
        dtext("LIVE", 20, "red", 24, 24),
        dtext(score, 18, "white", 88, 26),
        "drawbox=x=12:y=308:w=330:h=36:color=black@0.65:t=fill",
        dtext(f"Q3  {quarter_clock}  •  THE BIG GAME", 17, "white", 24, 318),
    ])
    run(["-f", "lavfi", "-i", f"color=c=0x1a7a2e:s={W}x{H}:r={FPS}:d={dur}",
         "-f", "lavfi", "-i",
         f"anoisesrc=color=brown:amplitude=0.28:d={dur}",
         "-filter_complex",
         f"[0:v]{vf}[v];[1:a]lowpass=f=900,volume=1.4[a]",
         "-map", "[v]", "-map", "[a]", *V_ARGS, *A_ARGS, "-t", str(dur), path])


def black_segment(path, dur=1.5):
    """Break boundary: black frames + dead silence (what detectors look for)."""
    run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur}",
         "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur}",
         "-map", "0:v", "-map", "1:a", *V_ARGS, *A_ARGS, "-t", str(dur), path])


def commercial_clip(path, dur, bg, fg, line1, line2, freq, bright=False):
    """One loud, garish national ad clip. Concatenating several of these
    produces the high scene-cut rate (and louder audio) typical of ad blocks.
    Alternating `bright` swaps the luminance layout clip-to-clip so hard cuts
    register strongly, the way real ads cut between pack shots and scenes."""
    layout = ("drawbox=x=0:y=180:w=iw:h=180:color=white@0.92:t=fill"
              if bright else
              "drawbox=x=0:y=0:w=iw:h=90:color=black@0.55:t=fill")
    text_color = "black" if bright else "white"
    vf = ",".join([
        layout,
        f"drawbox=x='mod(t*220\\,740)-100':y=0:w=100:h=ih:color=white@0.18:t=fill",
        dtext(line1, 40, fg, "(w-text_w)/2", 60 if bright else 120),
        dtext(line2, 24, text_color, "(w-text_w)/2", 230 if bright else 190),
        dtext("AD", 16, f"{text_color}@0.7", 20, 20),
    ])
    audio = (f"sin(2*PI*{freq}*t)*0.35+sin(2*PI*{freq * 1.5}*t)*0.25"
             f"+sin(2*PI*{freq * 2}*t)*0.15*gt(mod(t\\,0.5)\\,0.25)")
    run(["-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={FPS}:d={dur}",
         "-f", "lavfi", "-i", f"aevalsrc={audio}:s=44100:d={dur}",
         "-filter_complex", f"[0:v]{vf}[v];[1:a]volume=1.8,aformat=channel_layouts=stereo[a]",
         "-map", "[v]", "-map", "[a]", *V_ARGS, *A_ARGS, "-t", str(dur), path])


def business_ad(path, dur, bg, accent, headline, sub, cta, freq):
    """The business's own promo spot — clean, on-brand, pleasant audio."""
    vf = ",".join([
        f"drawbox=x=0:y=0:w=iw:h=70:color={accent}@0.9:t=fill",
        f"drawbox=x=0:y=290:w=iw:h=70:color={accent}@0.9:t=fill",
        dtext("MAXX’S BAR & GRILL", 26, "white", "(w-text_w)/2", 22),
        dtext(headline, 42, accent, "(w-text_w)/2", "118+4*sin(2*t)"),
        dtext(sub, 22, "white", "(w-text_w)/2", 195),
        dtext(cta, 20, "white", "(w-text_w)/2", 312),
    ])
    audio = (f"sin(2*PI*{freq}*t)*0.15+sin(2*PI*{freq * 1.25}*t)*0.12"
             f"+sin(2*PI*{freq * 1.5}*t)*0.10")
    run(["-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:r={FPS}:d={dur}",
         "-f", "lavfi", "-i", f"aevalsrc={audio}:s=44100:d={dur}",
         "-filter_complex",
         f"[0:v]{vf}[v];[1:a]aformat=channel_layouts=stereo,volume=0.9[a]",
         "-map", "[v]", "-map", "[a]", *V_ARGS, *A_ARGS, "-t", str(dur), path])


def concat(paths, out):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in paths:
            f.write(f"file '{p}'\n")
        lst = f.name
    try:
        run(["-f", "concat", "-safe", "0", "-i", lst,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
             "-pix_fmt", "yuv420p", *A_ARGS, out])
    finally:
        os.unlink(lst)


# ── Build everything ─────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="co_media_")
    seg = lambda n: os.path.join(tmp, n)

    print("Building game feed segments…")
    game_segment(seg("g1.mp4"), 30, "07:42", "HOME 21 - AWAY 17")
    black_segment(seg("b1.mp4"))
    # National commercial block: 6 clips x 3 s → 5 hard cuts in 18 s
    ads = [
        ("0xcc2200", "yellow", "MEGA CAR SALE!!!",   "0% APR — THIS WEEKEND ONLY", 520),
        ("0x0033cc", "yellow", "FIZZY COLA",          "TASTE THE FIZZ",                660),
        ("0xdd7700", "white",  "BURGER BARN",         "2 FOR $6 MEGA DEAL",            440),
        ("0x551a8b", "yellow", "PHONE 9000",          "PRE-ORDER NOW",                 780),
        ("0x006644", "white",  "SAFECO INSURANCE",    "SWITCH & SAVE 15%",             350),
        ("0xaa0055", "white",  "SHINE DETERGENT",     "50% BRIGHTER WHITES",           590),
    ]
    for i, (bg, fg, l1, l2, fq) in enumerate(ads):
        commercial_clip(seg(f"c{i}.mp4"), 3, bg, fg, l1, l2, fq, bright=i % 2 == 1)
    black_segment(seg("b2.mp4"))
    game_segment(seg("g2.mp4"), 24, "05:11", "HOME 24 - AWAY 17")

    print("Concatenating broadcast…")
    concat([seg("g1.mp4"), seg("b1.mp4"),
            *[seg(f"c{i}.mp4") for i in range(len(ads))],
            seg("b2.mp4"), seg("g2.mp4")],
           os.path.join(OUT_DIR, "game_feed.mp4"))

    print("Building business promo spots…")
    business_ad(os.path.join(OUT_DIR, "ad_burger.mp4"), 10,
                "0x1a0d05", "0xf2a900", "THE ZENIE BURGER",
                "1/2 PRICE DURING EVERY GAME", "ORDER AT THE BAR — TONIGHT ONLY", 392)
    business_ad(os.path.join(OUT_DIR, "ad_wings.mp4"), 10,
                "0x140a02", "0xe25822", "50c WING NIGHT",
                "EVERY WEDNESDAY — ALL FLAVORS", "DINE-IN ONLY — ASK YOUR SERVER", 440)
    business_ad(os.path.join(OUT_DIR, "ad_happyhour.mp4"), 10,
                "0x050d14", "0x3aa0d8", "HAPPY HOUR 4–7",
                "$3 DRAFTS • $5 APPS", "MON–FRI — BRING A FRIEND", 494)

    print("Transcoding WebM fallbacks (for browsers without H.264)…")
    for f in list(sorted(os.listdir(OUT_DIR))):
        if f.endswith(".mp4"):
            src = os.path.join(OUT_DIR, f)
            dst = os.path.join(OUT_DIR, f[:-4] + ".webm")
            run(["-i", src, "-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0",
                 "-cpu-used", "4", "-row-mt", "1",
                 "-c:a", "libopus", "-b:a", "80k", dst])

    shutil.rmtree(tmp, ignore_errors=True)
    for f in sorted(os.listdir(OUT_DIR)):
        p = os.path.join(OUT_DIR, f)
        print(f"  {f:22s} {os.path.getsize(p) / 1024:8.0f} KB")
    print("Done.")


if __name__ == "__main__":
    main()
