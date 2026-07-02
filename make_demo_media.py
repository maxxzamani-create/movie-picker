"""
AD-SHARK demo media renderer.

Renders every frame with PIL (proper vector art: perspective football field,
stadium crowd, animated players, broadcast score bug, art-directed national
ads and AD-SHARK promo spots), then encodes with ffmpeg.

The broadcast keeps the exact structure real detectors key on:
  game (30 s) → black+silence (1.5 s) → six loud fast-cut national ads
  (18 s) → black+silence (1.5 s) → game (24 s)

Run:  python make_demo_media.py          (~5-10 min; requires ffmpeg + Pillow)
"""
import math
import os
import random
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 960, 540, 24
OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "co")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_fonts: dict = {}


def font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT_PATH, size)
    return _fonts[size]


def run_ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


# ── drawing helpers ──────────────────────────────────────────────────────────

def vgrad(w, h, top, bottom):
    """Vertical gradient image."""
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        f = y / max(h - 1, 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3))
    return strip.resize((w, h))


def radial_glow(size, color):
    """Soft radial glow sprite with alpha."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    steps = 24
    for i in range(steps, 0, -1):
        r = c * i / steps
        a = int(160 * (1 - i / steps) ** 1.6)
        d.ellipse([c - r, c - r, c + r, c + r], fill=(*color, a))
    return img.filter(ImageFilter.GaussianBlur(size // 20))


def glow_text(base, xy, text, f, fill, glow, radius=8, anchor="la"):
    """Text with a soft glow behind it."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=f, fill=(*glow, 210), anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(layer)
    ImageDraw.Draw(base).text(xy, text, font=f, fill=fill, anchor=anchor)


def star(d, cx, cy, r, color, points=4, ratio=0.32, rot=0.0):
    pts = []
    for i in range(points * 2):
        rr = r if i % 2 == 0 else r * ratio
        a = rot + math.pi * i / points
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=color)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# ── stadium / game scene ─────────────────────────────────────────────────────

VPY = 178           # horizon (vanishing) row
SCALE_BOTTOM = 9.0  # px per world-unit at the bottom row


def _prerender_stadium():
    """Static backdrop: night sky, floodlights, packed stands."""
    img = vgrad(W, H, (7, 10, 20), (13, 20, 34)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # stands
    d.rectangle([0, 96, W, VPY + 4], fill=(20, 25, 38, 255))
    rng = random.Random(7)
    crowd_cols = [(180, 60, 60), (60, 90, 170), (200, 200, 210), (220, 180, 60),
                  (90, 160, 90), (150, 150, 160), (120, 80, 140)]
    for row in range(10):
        y = 102 + row * 8
        for x in range(0, W, 5):
            if rng.random() < 0.85:
                c = rng.choice(crowd_cols)
                dim = 0.35 + 0.4 * row / 10
                d.rectangle([x, y, x + 2, y + 3],
                            fill=tuple(int(v * dim) for v in c))
    # rails
    d.rectangle([0, VPY + 2, W, VPY + 6], fill=(200, 205, 215, 255))
    d.rectangle([0, 94, W, 97], fill=(30, 36, 52, 255))
    # floodlights
    for lx in (140, 480, 820):
        d.rectangle([lx - 2, 40, lx + 2, 96], fill=(40, 46, 60, 255))
        d.rounded_rectangle([lx - 34, 26, lx + 34, 46], 6, fill=(46, 54, 70, 255))
        for bx in range(-24, 25, 12):
            d.ellipse([lx + bx - 4, 31, lx + bx + 4, 41], fill=(235, 240, 255, 255))
        img.alpha_composite(radial_glow(240, (200, 215, 255)), (lx - 120, -60))
    return img


def _prerender_vignette():
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(90))
    black = Image.new("RGBA", (W, H), (0, 0, 12, 255))
    black.putalpha(v.point(lambda p: int((255 - p) * 0.55)))
    return black


def _prerender_noise(n=3):
    frames = []
    rng = random.Random(11)
    for _ in range(n):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = img.load()
        for _ in range(2600):
            x, y = rng.randrange(W), rng.randrange(H)
            v = rng.randrange(120, 255)
            px[x, y] = (v, v, v, 14)
        frames.append(img)
    return frames


STADIUM = _prerender_stadium()
VIGNETTE = _prerender_vignette()
NOISE = _prerender_noise()

# player squads: (team, world dx, base row, wobble amp, phase, speed)
_rng = random.Random(3)
SQUAD = [("A" if k % 2 == 0 else "B",
          _rng.uniform(-16, 16), _rng.uniform(330, 500),
          _rng.uniform(4, 14), _rng.uniform(0, 6.28), _rng.uniform(0.5, 1.4))
         for k in range(11)]


def _proj(wx, y, cam):
    s = (y - VPY) / (H - VPY)
    return W / 2 + (wx - cam) * SCALE_BOTTOM * s, s


def _draw_player(d, x, y, s, jersey, helmet, run_phase, carrier=False):
    size = 30 * s
    if size < 3:
        return
    if carrier:  # telestrator ring under the ball carrier
        d.ellipse([x - size * 1.15, y - size * 0.30, x + size * 1.15, y + size * 0.34],
                  outline=(255, 210, 60, 230), width=max(2, int(3 * s)))
    d.ellipse([x - size * 0.8, y - size * 0.16, x + size * 0.8, y + size * 0.20],
              fill=(0, 20, 0, 90))                        # shadow
    lo = math.sin(run_phase) * size * 0.35
    d.line([x - size * 0.2, y - size * 0.6, x - size * 0.32 + lo, y],
           fill=(230, 228, 224), width=max(2, int(size * 0.16)))
    d.line([x + size * 0.2, y - size * 0.6, x + size * 0.32 - lo, y],
           fill=(230, 228, 224), width=max(2, int(size * 0.16)))
    d.rounded_rectangle([x - size * 0.42, y - size * 1.5, x + size * 0.42,
                         y - size * 0.45], radius=size * 0.3, fill=jersey)
    d.line([x - size * 0.4, y - size * 1.25, x - size * 0.62 - lo * 0.5, y - size * 0.7],
           fill=jersey, width=max(2, int(size * 0.16)))
    d.line([x + size * 0.4, y - size * 1.25, x + size * 0.62 + lo * 0.5, y - size * 0.7],
           fill=jersey, width=max(2, int(size * 0.16)))
    d.ellipse([x - size * 0.30, y - size * 2.05, x + size * 0.30, y - size * 1.45],
              fill=helmet)
    d.arc([x - size * 0.30, y - size * 2.05, x + size * 0.30, y - size * 1.45],
          20, 120, fill=(235, 235, 235), width=max(1, int(size * 0.09)))


def _score_bug(img, t, score, clock_start):
    d = ImageDraw.Draw(img)
    x0, y0 = 26, H - 86
    d.rounded_rectangle([x0, y0, x0 + 372, y0 + 56], 12, fill=(8, 10, 16, 235))
    d.rounded_rectangle([x0, y0, x0 + 58, y0 + 56], 12, fill=(242, 169, 0, 255))
    d.rectangle([x0 + 30, y0, x0 + 58, y0 + 56], fill=(242, 169, 0, 255))
    d.text((x0 + 29, y0 + 28), "S1", font=font(24), fill=(12, 10, 4), anchor="mm")
    home, away = score
    d.rounded_rectangle([x0 + 66, y0 + 9, x0 + 176, y0 + 47], 8, fill=(122, 31, 31, 255))
    d.text((x0 + 76, y0 + 28), "HOM", font=font(17), fill=(255, 220, 220), anchor="lm")
    d.text((x0 + 168, y0 + 28), str(home), font=font(24), fill=(255, 255, 255), anchor="rm")
    d.rounded_rectangle([x0 + 182, y0 + 9, x0 + 292, y0 + 47], 8, fill=(31, 60, 122, 255))
    d.text((x0 + 192, y0 + 28), "AWY", font=font(17), fill=(215, 225, 255), anchor="lm")
    d.text((x0 + 284, y0 + 28), str(away), font=font(24), fill=(255, 255, 255), anchor="rm")
    secs = max(0, clock_start - int(t))
    d.text((x0 + 306, y0 + 28), f"Q3 {secs // 60}:{secs % 60:02d}",
           font=font(18), fill=(235, 238, 245), anchor="lm")
    pulse = int(150 + 100 * math.sin(t * 4))
    d.rounded_rectangle([W - 118, 20, W - 26, 52], 8, fill=(8, 10, 16, 210))
    d.ellipse([W - 106, 30, W - 94, 42], fill=(230, 40, 40, pulse))
    d.text((W - 86, 36), "LIVE", font=font(18), fill=(255, 255, 255), anchor="lm")
    d.text((W - 30, H - 26), "SPORTS ONE", font=font(15),
           fill=(255, 255, 255, 70), anchor="rm")


def game_frame(t, dur, score, clock_start, fade_out=False, fade_in=False):
    img = STADIUM.copy()
    d = ImageDraw.Draw(img)

    carrier_wx = -34 + t * 2.1 + 4.5 * math.sin(t * 1.1)
    cam = carrier_wx * 0.75
    # field stripes (perspective quads)
    for i in range(-14, 14):
        xt0, _ = _proj(i * 10, VPY + 7, cam)
        xt1, _ = _proj(i * 10 + 10, VPY + 7, cam)
        xb0, _ = _proj(i * 10, H, cam)
        xb1, _ = _proj(i * 10 + 10, H, cam)
        col = (26, 122, 54, 255) if i % 2 == 0 else (21, 105, 45, 255)
        d.polygon([(xt0, VPY + 7), (xt1, VPY + 7), (xb1, H), (xb0, H)], fill=col)
    # yard lines + numbers
    for i in range(-14, 15):
        xt, _ = _proj(i * 10, VPY + 7, cam)
        xb, _ = _proj(i * 10, H, cam)
        d.line([(xt, VPY + 7), (xb, H)], fill=(240, 244, 240, 190), width=2)
        num = 50 - abs(((i + 100) % 10) - 5) * 10
        xnum, s = _proj(i * 10 + 1.2, 470, cam)
        if 20 < xnum < W - 20:
            d.text((xnum, 470), str(num), font=font(int(34 * s + 6)),
                   fill=(235, 240, 235, 120), anchor="mm")
    # hash marks
    for row in (338, 452):
        for i in range(-28, 29):
            x, s = _proj(i * 5, row, cam)
            if 0 < x < W:
                d.line([(x, row - 4 * s - 1), (x, row + 4 * s + 1)],
                       fill=(240, 244, 240, 120), width=2)

    # players, far to near
    players = []
    for team, dx, row, amp, ph, spd in SQUAD:
        wy = row + amp * math.sin(t * spd + ph)
        wx = carrier_wx + dx + 2.5 * math.sin(t * spd * 0.8 + ph * 2)
        players.append((wy, wx, team, ph))
    players.sort()
    for wy, wx, team, ph in players:
        x, s = _proj(wx, wy, cam)
        jersey = (196, 57, 43) if team == "A" else (36, 80, 160)
        helmet = (240, 240, 240) if team == "A" else (255, 200, 60)
        _draw_player(d, x, wy, s, jersey, helmet, t * 9 + ph)
    cy = 415 + 26 * math.sin(t * 0.8)
    cx, cs = _proj(carrier_wx, cy, cam)
    _draw_player(d, cx, cy, cs, (196, 57, 43), (240, 240, 240), t * 11, carrier=True)

    img.alpha_composite(VIGNETTE)
    img.alpha_composite(NOISE[int(t * FPS) % len(NOISE)])
    _score_bug(img, t, score, clock_start)

    if fade_out and t > dur - 0.35:
        a = int(255 * (t - (dur - 0.35)) / 0.35)
        ImageDraw.Draw(img).rectangle([0, 0, W, H], fill=(0, 0, 0, a))
    if fade_in and t < 0.35:
        a = int(255 * (1 - t / 0.35))
        ImageDraw.Draw(img).rectangle([0, 0, W, H], fill=(0, 0, 0, a))
    return img


# ── national commercials (loud, fast-cut, alternating bright/dark) ───────────

def ad_frame_car(t, dur):
    img = vgrad(W, H, (12, 14, 34), (28, 20, 50)).convert("RGBA")
    d = ImageDraw.Draw(img)
    star(d, W / 2, 240, 300, (255, 205, 40, 60), points=12, ratio=0.62, rot=t * 0.5)
    star(d, W / 2, 240, 220, (255, 220, 70, 90), points=12, ratio=0.62, rot=-t * 0.4)
    cx, cy = W / 2, 320
    d.rounded_rectangle([cx - 190, cy - 46, cx + 190, cy + 26], 26, fill=(200, 30, 40))
    d.rounded_rectangle([cx - 110, cy - 96, cx + 96, cy - 26], 22, fill=(160, 20, 30))
    d.polygon([(cx - 96, cy - 88), (cx - 20, cy - 88), (cx - 20, cy - 40),
               (cx - 108, cy - 40)], fill=(150, 200, 235))
    d.polygon([(cx - 6, cy - 88), (cx + 82, cy - 88), (cx + 92, cy - 40),
               (cx - 6, cy - 40)], fill=(150, 200, 235))
    for wx in (cx - 118, cx + 118):
        d.ellipse([wx - 42, cy - 2, wx + 42, cy + 82], fill=(20, 20, 24))
        d.ellipse([wx - 20, cy + 20, wx + 20, cy + 60], fill=(180, 185, 195))
    d.rounded_rectangle([cx + 168, cy - 30, cx + 196, cy - 6], 6, fill=(255, 240, 170))
    sc = 1 + 0.05 * math.sin(t * 7)
    glow_text(img, (W / 2, 108), "MEGA CAR SALE!", font(int(72 * sc)),
              (255, 230, 90), (255, 160, 0), 14, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2, 452), "0% APR — THIS WEEKEND ONLY", font=font(30),
           fill=(255, 255, 255), anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(255, 255, 255, 150))
    return img


def ad_frame_cola(t, dur):
    img = vgrad(W, H, (200, 235, 250), (150, 205, 235)).convert("RGBA")
    d = ImageDraw.Draw(img)
    rng = random.Random(5)
    for _ in range(36):
        bx = rng.uniform(0, W)
        r = rng.uniform(4, 16)
        by = (rng.uniform(0, H) - t * (30 + r * 6)) % (H + 40) - 20
        d.ellipse([bx - r, by - r, bx + r, by + r], outline=(255, 255, 255, 150),
                  width=2)
    can = Image.new("RGBA", (220, 320), (0, 0, 0, 0))
    cd = ImageDraw.Draw(can)
    cd.rounded_rectangle([30, 16, 190, 304], 28, fill=(190, 24, 34))
    cd.ellipse([30, 4, 190, 40], fill=(205, 210, 218))
    cd.ellipse([46, 10, 174, 32], fill=(160, 166, 176))
    cd.ellipse([44, 80, 176, 260], fill=(255, 255, 255, 50))
    cd.text((110, 165), "FIZZY", font=font(44), fill=(255, 255, 255), anchor="mm")
    can = can.rotate(math.sin(t * 2) * 6, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(can, (int(W / 2 - can.width / 2), int(300 - can.height / 2)))
    glow_text(img, (W / 2, 88), "FIZZY COLA", font(74), (190, 24, 34),
              (255, 255, 255), 12, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2, 486), "TASTE THE FIZZ", font=font(32), fill=(20, 40, 70),
           anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(30, 50, 80, 170))
    return img


def ad_frame_burger(t, dur):
    img = vgrad(W, H, (40, 20, 8), (66, 32, 12)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for k in range(16):
        a = t * 0.6 + k * math.pi / 8
        d.polygon([(W / 2, 300),
                   (W / 2 + 700 * math.cos(a), 300 + 700 * math.sin(a)),
                   (W / 2 + 700 * math.cos(a + 0.12), 300 + 700 * math.sin(a + 0.12))],
                  fill=(255, 160, 40, 26))
    cx, cy = W / 2, 330
    bob = math.sin(t * 3) * 6
    d.ellipse([cx - 170, cy + 64 + bob, cx + 170, cy + 118 + bob], fill=(30, 10, 4, 120))
    d.rounded_rectangle([cx - 160, cy + 28 + bob, cx + 160, cy + 74 + bob], 20,
                        fill=(222, 160, 74))
    for k in range(7):
        lx = cx - 150 + k * 50
        d.ellipse([lx - 30, cy + 8 + bob, lx + 30, cy + 42 + bob], fill=(90, 170, 60))
    d.rounded_rectangle([cx - 150, cy - 14 + bob, cx + 150, cy + 22 + bob], 14,
                        fill=(96, 52, 26))
    d.rectangle([cx - 150, cy - 22 + bob, cx + 150, cy - 8 + bob], fill=(250, 190, 50))
    for k in range(5):
        chx = cx - 120 + k * 60
        d.polygon([(chx - 24, cy - 12 + bob), (chx + 24, cy - 12 + bob),
                   (chx, cy + 26 + bob)], fill=(250, 190, 50))
    d.ellipse([cx - 160, cy - 92 + bob, cx + 160, cy + 6 + bob], fill=(235, 172, 82))
    rng = random.Random(9)
    for _ in range(16):
        sx = cx + rng.uniform(-120, 120)
        sy = cy - 72 + bob + rng.uniform(0, 44) - abs(sx - cx) * 0.12
        d.ellipse([sx - 5, sy - 3, sx + 5, sy + 3], fill=(250, 236, 200))
    glow_text(img, (W / 2, 92), "BURGER BARN", font(70), (255, 220, 120),
              (255, 120, 20), 14, anchor="mm")
    d = ImageDraw.Draw(img)
    badge = 1 + 0.08 * math.sin(t * 8)
    d.ellipse([764 - 78 * badge, 380 - 78 * badge, 764 + 78 * badge, 380 + 78 * badge],
              fill=(200, 30, 30))
    d.text((764, 362), "2 FOR", font=font(26), fill=(255, 255, 255), anchor="mm")
    d.text((764, 398), "$6", font=font(44), fill=(255, 230, 90), anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(255, 255, 255, 150))
    return img


def ad_frame_phone(t, dur):
    img = vgrad(W, H, (225, 218, 248), (190, 176, 240)).convert("RGBA")
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, 300
    ph = Image.new("RGBA", (240, 420), (0, 0, 0, 0))
    pd = ImageDraw.Draw(ph)
    pd.rounded_rectangle([20, 10, 220, 410], 36, fill=(24, 26, 34))
    ph.paste(vgrad(176, 376, (80, 60, 220), (240, 90, 160)), (32, 22))
    pd.rounded_rectangle([32, 22, 208, 398], 26, outline=(24, 26, 34), width=8)
    pd.ellipse([112, 26, 128, 42], fill=(10, 10, 14))
    pd.text((120, 210), "9000", font=font(44), fill=(255, 255, 255), anchor="mm")
    ph = ph.rotate(math.sin(t * 1.6) * 5, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(ph, (int(cx - ph.width / 2), int(cy - ph.height / 2)))
    for k in range(6):
        a = t * 2 + k * math.pi / 3
        star(d, cx + 210 * math.cos(a), cy + 130 * math.sin(a),
             12 + 4 * math.sin(t * 5 + k), (255, 255, 255, 230), rot=t * 3)
    glow_text(img, (W / 2, 80), "PHONE 9000", font(70), (40, 20, 90),
              (255, 255, 255), 10, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2, 496), "PRE-ORDER NOW", font=font(32), fill=(50, 30, 100),
           anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(50, 30, 100, 170))
    return img


def ad_frame_insurance(t, dur):
    img = vgrad(W, H, (6, 42, 40), (10, 70, 62)).convert("RGBA")
    d = ImageDraw.Draw(img)
    ring = (t * 90) % 260
    d.ellipse([W / 2 - ring, 290 - ring, W / 2 + ring, 290 + ring],
              outline=(120, 220, 200, max(0, 160 - int(ring * 0.6))), width=4)
    cx, cy = W / 2, 290
    d.polygon([(cx - 110, cy - 100), (cx + 110, cy - 100), (cx + 110, cy + 10),
               (cx, cy + 110), (cx - 110, cy + 10)], fill=(16, 120, 104))
    d.polygon([(cx - 90, cy - 82), (cx + 90, cy - 82), (cx + 90, cy + 2),
               (cx, cy + 88), (cx - 90, cy + 2)], fill=(232, 240, 238))
    d.line([(cx - 44, cy - 6), (cx - 8, cy + 34), (cx + 56, cy - 52)],
           fill=(16, 120, 104), width=18, joint="curve")
    d.pieslice([cx - 70, cy - 190, cx + 70, cy - 50], 180, 360, fill=(242, 169, 0))
    d.line([(cx, cy - 120), (cx, cy - 84)], fill=(242, 169, 0), width=6)
    glow_text(img, (W / 2, 74), "SAFECO INSURANCE", font(56), (235, 245, 242),
              (60, 200, 170), 10, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2, 486), "SWITCH & SAVE 15%", font=font(34), fill=(190, 235, 225),
           anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(255, 255, 255, 140))
    return img


def ad_frame_detergent(t, dur):
    img = vgrad(W, H, (250, 214, 235), (242, 170, 210)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for k in range(14):
        a = -t * 0.8 + k * math.pi / 7
        d.polygon([(W / 2, 290),
                   (W / 2 + 720 * math.cos(a), 290 + 720 * math.sin(a)),
                   (W / 2 + 720 * math.cos(a + 0.10), 290 + 720 * math.sin(a + 0.10))],
                  fill=(255, 255, 255, 42))
    cx, cy = W / 2, 310
    d.rounded_rectangle([cx - 90, cy - 130, cx + 90, cy + 130], 30, fill=(160, 30, 110))
    d.rounded_rectangle([cx - 46, cy - 176, cx + 46, cy - 118], 12, fill=(240, 200, 40))
    d.rounded_rectangle([cx - 66, cy - 60, cx + 66, cy + 84], 16, fill=(255, 255, 255))
    d.text((cx, cy - 20), "SHINE", font=font(36), fill=(160, 30, 110), anchor="mm")
    d.text((cx, cy + 30), "ultra", font=font(24), fill=(90, 90, 100), anchor="mm")
    for k in range(7):
        a = t * 4 + k * 1.7
        star(d, cx + 170 * math.cos(a * 0.7 + k),
             cy - 40 + 130 * math.sin(a * 0.5 + k * 2),
             14 + 5 * math.sin(t * 6 + k), (255, 255, 255, 240), rot=a)
    glow_text(img, (W / 2, 80), "SHINE DETERGENT", font(62), (120, 20, 80),
              (255, 255, 255), 10, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2, 496), "50% BRIGHTER WHITES", font=font(32), fill=(110, 25, 75),
           anchor="mm")
    d.text((30, 26), "AD", font=font(18), fill=(120, 20, 80, 170))
    return img


# ── AD-SHARK promo spots (Maxx's Bar & Grill) ────────────────────────────────

def _promo_chrome(img, t, headline, sub, cta, accent):
    """Shared lockup: brand top, eased headline slide-in, CTA bar."""
    d = ImageDraw.Draw(img)
    d.text((W / 2, 54), "M A X X ' S   B A R   &   G R I L L", font=font(24),
           fill=(238, 232, 220), anchor="mm")
    lw = 150 + 40 * ease_out(t / 0.8)
    d.line([(W / 2 - lw, 82), (W / 2 + lw, 82)], fill=(*accent, 220), width=2)
    slide = (1 - ease_out(t / 0.9)) * -420
    glow_text(img, (W / 2 + slide, 150), headline, font(64), (255, 255, 255),
              accent, 16, anchor="mm")
    d = ImageDraw.Draw(img)
    d.text((W / 2 + slide * 0.6, 208), sub, font=font(28), fill=(*accent, 255),
           anchor="mm")
    a = int(255 * ease_out((t - 0.6) / 0.8))
    d.rounded_rectangle([W / 2 - 330, H - 74, W / 2 + 330, H - 26], 24,
                        fill=(*accent, min(a, 235)))
    d.text((W / 2, H - 50), cta, font=font(22), fill=(14, 10, 4, a), anchor="mm")


def promo_frame_burger(t, dur):
    img = vgrad(W, H, (16, 12, 8), (34, 22, 12)).convert("RGBA")
    img.alpha_composite(radial_glow(760, (242, 169, 0)), (W // 2 - 380, -110))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, 368
    bob = math.sin(t * 2) * 5
    for k in range(3):  # steam wisps
        phase = t * 0.7 + k * 2.1
        pts = [(cx - 60 + k * 60 + 18 * math.sin(phase + y / 30.0),
                cy - 130 + bob - y) for y in range(0, 110, 8)]
        a = int(90 + 50 * math.sin(phase))
        d.line(pts, fill=(255, 245, 225, max(30, a)), width=5, joint="curve")
    d.ellipse([cx - 190, cy + 66 + bob, cx + 190, cy + 122 + bob], fill=(0, 0, 0, 130))
    d.rounded_rectangle([cx - 175, cy + 30 + bob, cx + 175, cy + 78 + bob], 22,
                        fill=(224, 162, 76))
    for k in range(8):
        lx = cx - 165 + k * 48
        d.ellipse([lx - 30, cy + 6 + bob, lx + 30, cy + 44 + bob], fill=(94, 172, 62))
    d.rounded_rectangle([cx - 165, cy - 16 + bob, cx + 165, cy + 20 + bob], 14,
                        fill=(92, 50, 24))
    d.rectangle([cx - 165, cy - 26 + bob, cx + 165, cy - 10 + bob], fill=(250, 190, 50))
    for k in range(6):
        chx = cx - 138 + k * 55
        d.polygon([(chx - 26, cy - 12 + bob), (chx + 26, cy - 12 + bob),
                   (chx, cy + 28 + bob)], fill=(250, 190, 50))
    d.rounded_rectangle([cx - 158, cy - 52 + bob, cx + 158, cy - 20 + bob], 12,
                        fill=(92, 50, 24))
    d.ellipse([cx - 175, cy - 128 + bob, cx + 175, cy - 22 + bob], fill=(238, 176, 86))
    rng = random.Random(4)
    for _ in range(18):
        sx = cx + rng.uniform(-130, 130)
        sy = cy - 100 + bob + rng.uniform(0, 48) - abs(sx - cx) * 0.14
        d.ellipse([sx - 6, sy - 3, sx + 6, sy + 3], fill=(252, 240, 205))
    rock = math.sin(t * 3) * 0.12
    bx, by = cx + 268, cy - 60
    d.ellipse([bx - 84, by - 84, bx + 84, by + 84], fill=(242, 169, 0))
    d.ellipse([bx - 74, by - 74, bx + 74, by + 74], outline=(20, 14, 6), width=3)
    d.text((bx, by - 22 + rock * 40), "½ PRICE", font=font(30), fill=(20, 14, 6),
           anchor="mm")
    d.text((bx, by + 20 + rock * 40), "game time", font=font(20), fill=(60, 40, 10),
           anchor="mm")
    _promo_chrome(img, t, "THE ZENIE BURGER", "half price during every game",
                  "ORDER AT THE BAR — TONIGHT ONLY", (242, 169, 0))
    return img


def promo_frame_wings(t, dur):
    img = vgrad(W, H, (22, 8, 6), (52, 14, 8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for layer, (col, amp, yb) in enumerate([((200, 60, 10, 160), 46, 40),
                                            ((245, 120, 20, 170), 34, 22),
                                            ((255, 200, 60, 180), 22, 6)]):
        pts = [(0, H)]
        for x in range(0, W + 1, 24):
            y = H - yb - amp * (0.6 + 0.4 * math.sin(x * 0.045 + t * (3 + layer)))
            pts.append((x, y))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    rng = random.Random(6)
    for _ in range(26):
        ex = rng.uniform(0, W)
        ey = (rng.uniform(0, H) - t * rng.uniform(50, 130)) % H
        r = rng.uniform(2, 5)
        d.ellipse([ex - r, ey - r, ex + r, ey + r],
                  fill=(255, 170, 60, int(rng.uniform(70, 190))))
    cx, cy = W / 2, 350
    d.rounded_rectangle([cx - 180, cy + 10, cx + 180, cy + 96], 18, fill=(150, 34, 26))
    d.rounded_rectangle([cx - 196, cy - 6, cx + 196, cy + 26], 12, fill=(180, 44, 32))
    wing_rng = random.Random(2)
    for k in range(7):
        wx = cx - 140 + k * 47 + wing_rng.uniform(-8, 8)
        wy = cy - 24 + (k % 2) * 14
        wing = Image.new("RGBA", (110, 80), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wing)
        wd.ellipse([10, 20, 86, 66], fill=(176, 84, 30))
        wd.ellipse([60, 12, 102, 46], fill=(150, 66, 22))
        wd.ellipse([16, 30, 52, 58], fill=(198, 104, 40))
        wing = wing.rotate(wing_rng.uniform(-30, 30), resample=Image.BICUBIC,
                           expand=True)
        img.alpha_composite(wing, (int(wx - wing.width / 2), int(wy - wing.height / 2)))
    price = 1 + 0.06 * math.sin(t * 6)
    glow_text(img, (cx + 286, 300), "50¢", font(int(84 * price)), (255, 220, 80),
              (255, 120, 20), 16, anchor="mm")
    _promo_chrome(img, t, "WING NIGHT", "every wednesday — all flavors",
                  "DINE-IN ONLY — ASK YOUR SERVER", (226, 88, 34))
    return img


def promo_frame_happyhour(t, dur):
    img = vgrad(W, H, (6, 14, 26), (12, 28, 48)).convert("RGBA")
    d = ImageDraw.Draw(img)
    rng = random.Random(8)
    for _ in range(30):
        bx = rng.uniform(0, W)
        r = rng.uniform(2, 7)
        by = (rng.uniform(0, H) - t * (18 + r * 8)) % (H + 20) - 10
        d.ellipse([bx - r, by - r, bx + r, by + r], outline=(120, 180, 220, 90),
                  width=1)
    clink = math.sin(t * 1.6)
    for side in (-1, 1):
        ang = side * (8 - 6 * max(0, clink))
        mug = Image.new("RGBA", (240, 300), (0, 0, 0, 0))
        md = ImageDraw.Draw(mug)
        md.rounded_rectangle([40, 60, 180, 280], 18, fill=(244, 170, 40, 235))
        for gx in (62, 96, 130):
            md.rounded_rectangle([gx, 76, gx + 16, 264], 8, fill=(255, 220, 120, 130))
        md.rounded_rectangle([40, 60, 180, 280], 18, outline=(255, 245, 220, 200),
                             width=5)
        md.rounded_rectangle([176, 110, 226, 230], 22, outline=(255, 245, 220, 200),
                             width=12)
        md.ellipse([30, 30, 110, 86], fill=(252, 248, 238))
        md.ellipse([80, 20, 160, 80], fill=(252, 248, 238))
        md.ellipse([130, 32, 196, 86], fill=(252, 248, 238))
        for _ in range(9):
            fx, fy = rng.uniform(46, 180), rng.uniform(90, 250)
            md.ellipse([fx - 3, fy - 3, fx + 3, fy + 3], fill=(255, 235, 170, 150))
        mug = mug.rotate(ang, resample=Image.BICUBIC, expand=True)
        x = int(W / 2 + side * 150 - mug.width / 2 + side * -30 * max(0, clink))
        img.alpha_composite(mug, (x, 250 - mug.height // 2 + 60))
    if clink > 0.93:
        star(d, W / 2, 300, 44, (255, 255, 220, 240), rot=t * 2)
    _promo_chrome(img, t, "HAPPY HOUR 4–7", "$3 drafts • $5 apps • mon–fri",
                  "BRING A FRIEND — WE'LL KEEP THE GAME ON", (58, 160, 216))
    return img


# ── encoding ─────────────────────────────────────────────────────────────────

V_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
          "-pix_fmt", "yuv420p"]
A_ARGS = ["-c:a", "aac", "-b:a", "112k", "-ar", "44100", "-ac", "2"]


def render_segment(path, dur, frame_fn, audio_lavfi):
    tmp = tempfile.mkdtemp(prefix="adshark_f_")
    try:
        for i in range(int(dur * FPS)):
            img = frame_fn(i / FPS, dur)
            img.convert("RGB").save(os.path.join(tmp, f"{i:05d}.jpg"), quality=88)
        run_ffmpeg(["-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg"),
                    "-f", "lavfi", "-i", audio_lavfi,
                    "-t", str(dur), *V_ARGS, *A_ARGS, "-shortest", path])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def black_segment(path, dur=1.5):
    run_ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur}",
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur}",
                "-map", "0:v", "-map", "1:a", *V_ARGS, *A_ARGS, "-t", str(dur), path])


def concat(paths, out):
    lst = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    for p in paths:
        lst.write(f"file '{p}'\n")
    lst.close()
    try:
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", lst.name,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                    "-pix_fmt", "yuv420p", *A_ARGS, out])
    finally:
        os.unlink(lst.name)


CROWD = ("anoisesrc=color=brown:amplitude=0.30:d={d},lowpass=f=850,"
         "tremolo=f=0.3:d=0.4,volume=1.5")
AD_AUDIO = ("aevalsrc=sin(2*PI*{f}*t)*0.32+sin(2*PI*{f15}*t)*0.22"
            "+sin(2*PI*{f2}*t)*0.16*gt(mod(t\\,0.5)\\,0.25):s=44100:d={d},"
            "aformat=channel_layouts=stereo,volume=1.9")
PROMO_AUDIO = ("aevalsrc=(sin(2*PI*{f}*t)*0.16+sin(2*PI*{f5}*t)*0.12"
               "+sin(2*PI*{f3}*t)*0.10)*(0.7+0.3*sin(2*PI*0.5*t)):s=44100:d={d},"
               "aformat=channel_layouts=stereo,volume=0.9")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="adshark_seg_")
    seg = lambda n: os.path.join(tmp, n)

    print("Rendering game segments (PIL frames)…")
    render_segment(seg("g1.mp4"), 30,
                   lambda t, d: game_frame(t, d, (21, 17), 462, fade_out=True),
                   CROWD.format(d=30))
    black_segment(seg("b1.mp4"))
    print("Rendering national ad block…")
    ads = [(ad_frame_car, 520), (ad_frame_cola, 660), (ad_frame_burger, 440),
           (ad_frame_phone, 780), (ad_frame_insurance, 350),
           (ad_frame_detergent, 590)]
    for i, (fn, f) in enumerate(ads):
        render_segment(seg(f"c{i}.mp4"), 3, fn,
                       AD_AUDIO.format(f=f, f15=int(f * 1.5), f2=f * 2, d=3))
    black_segment(seg("b2.mp4"))
    render_segment(seg("g2.mp4"), 24,
                   lambda t, d: game_frame(t, d, (24, 17), 311, fade_in=True),
                   CROWD.format(d=24))

    print("Concatenating broadcast…")
    concat([seg("g1.mp4"), seg("b1.mp4"),
            *[seg(f"c{i}.mp4") for i in range(len(ads))],
            seg("b2.mp4"), seg("g2.mp4")],
           os.path.join(OUT_DIR, "game_feed.mp4"))

    print("Rendering AD-SHARK promo spots…")
    promos = [("ad_burger.mp4", promo_frame_burger, 392),
              ("ad_wings.mp4", promo_frame_wings, 440),
              ("ad_happyhour.mp4", promo_frame_happyhour, 494)]
    for name, fn, f in promos:
        render_segment(os.path.join(OUT_DIR, name), 10, fn,
                       PROMO_AUDIO.format(f=f, f5=int(f * 1.25), f3=int(f * 1.5),
                                          d=10))

    print("Transcoding WebM fallbacks…")
    for fname in sorted(os.listdir(OUT_DIR)):
        if fname.endswith(".mp4"):
            src = os.path.join(OUT_DIR, fname)
            run_ffmpeg(["-i", src, "-c:v", "libvpx-vp9", "-crf", "37", "-b:v", "0",
                        "-cpu-used", "5", "-row-mt", "1",
                        "-c:a", "libopus", "-b:a", "84k",
                        os.path.join(OUT_DIR, fname[:-4] + ".webm")])

    shutil.rmtree(tmp, ignore_errors=True)
    for f in sorted(os.listdir(OUT_DIR)):
        p = os.path.join(OUT_DIR, f)
        print(f"  {f:24s} {os.path.getsize(p) / 1024:8.0f} KB")
    print("Done.")


if __name__ == "__main__":
    main()
