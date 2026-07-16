"""
Movie Rando — logo.

A tilted white die on a cornflower-blue disc: hit the button, roll a
random movie. Rendered at runtime (server.py serves it at /logo.png),
so it always matches the app palette and scales to any size.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

# Palette (matches static/style.css — Cloud & Cornflower)
BLUE      = "#3b82f6"   # cornflower — disc
BLUE_DEEP = "#1d4ed8"   # deeper blue — die shadow
BLUE_INK  = "#1e40af"   # deep blue — pips
WHITE     = "#ffffff"


def make_logo(size: int = 256) -> Image.Image:
    s  = size
    cx = s / 2
    r  = s / 2 * 0.93

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # ── Soft blue halo ───────────────────────────────────────────────────
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [cx - r - 4, cx - r - 4, cx + r + 4, cx + r + 4],
        fill=(59, 130, 246, 130),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(max(3, s // 14)))
    img  = Image.alpha_composite(img, glow)

    draw = ImageDraw.Draw(img)

    # ── Disc + inner ring ────────────────────────────────────────────────
    draw.ellipse([cx - r, cx - r, cx + r, cx + r], fill=BLUE)
    ring_r = r - max(2, s // 26)
    draw.ellipse([cx - ring_r, cx - ring_r, cx + ring_r, cx + ring_r],
                 outline=WHITE, width=max(1, s // 64))

    # ── Film sprocket holes — only when large enough to read cleanly ─────
    if s >= 96:
        holes  = 12
        band_r = r * 0.87          # outside the die's corner reach
        hw, hh = s * 0.026, s * 0.019
        for i in range(holes):
            a  = 2 * math.pi * i / holes
            hx = cx + band_r * math.cos(a)
            hy = cx + band_r * math.sin(a)
            draw.rounded_rectangle(
                [hx - hw, hy - hh, hx + hw, hy + hh],
                radius=s * 0.008, fill=(255, 255, 255, 70),
            )

    # ── The die — drawn on its own layer so it can be tilted ─────────────
    die  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dd   = ImageDraw.Draw(die)
    half = s * 0.23          # corners clear the sprocket ring
    rad  = s * 0.06
    off  = s * 0.016

    # drop shadow, then the face
    dd.rounded_rectangle([cx - half + off, cx - half + off,
                          cx + half + off, cx + half + off],
                         radius=rad, fill=(29, 78, 216, 110))
    dd.rounded_rectangle([cx - half, cx - half, cx + half, cx + half],
                         radius=rad, fill=WHITE)

    # five pips (quincunx) — the classic "roll" face
    pr = max(1.5, s * 0.033)
    o  = half * 0.46
    for px, py in [(-o, -o), (o, -o), (0, 0), (-o, o), (o, o)]:
        dd.ellipse([cx + px - pr, cx + py - pr,
                    cx + px + pr, cx + py + pr], fill=BLUE_INK)

    die = die.rotate(-15, resample=Image.BICUBIC, center=(cx, cx))
    img = Image.alpha_composite(img, die)

    return img


def save_logo(path="logo.png", size=256):
    img = make_logo(size)
    img.save(path)
    return img


if __name__ == "__main__":
    save_logo()
    print("logo.png saved.")
