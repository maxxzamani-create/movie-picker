import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEAL      = "#00B5CC"
TEAL_D    = "#007a8a"
TEAL_LT   = "#40D8F0"
GREEN     = "#39FF14"
GREEN_D   = "#1a8a00"
GOLD      = "#FFD700"
GOLD_D    = "#8B6000"
BG        = "#060e0e"
DARK      = "#030808"


def _font(size):
    for path in ["C:/Windows/Fonts/impact.ttf",
                 "C:/Windows/Fonts/arialbd.ttf",
                 "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_logo(size: int = 256) -> Image.Image:
    s  = size
    cx = s / 2
    r  = s / 2 * 0.93

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # ── Teal glow ─────────────────────────────────────────────────────────
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([cx-r-6, cx-r-6, cx+r+6, cx+r+6], fill=(0, 181, 204, 150))
    glow = glow.filter(ImageFilter.GaussianBlur(max(4, s // 15)))
    img  = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # ── Background disc ───────────────────────────────────────────────────
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], fill=BG)
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], outline=TEAL, width=max(2, s//52))

    # ── Proportional anchors ──────────────────────────────────────────────
    lamp_cx  = cx
    lamp_cy  = s * 0.78
    lamp_rx  = s * 0.21
    lamp_ry  = s * 0.085

    head_cx  = cx
    head_cy  = s * 0.23
    head_r   = s * 0.105

    waist_y  = s * 0.60
    chest_y  = s * 0.46
    smoke_top = lamp_cy - lamp_ry   # smoke exits top of lamp

    # ── Magic lamp ───────────────────────────────────────────────────────
    # Shadow
    draw.ellipse([lamp_cx-lamp_rx+s*0.01, lamp_cy-lamp_ry+s*0.01,
                  lamp_cx+lamp_rx+s*0.01, lamp_cy+lamp_ry+s*0.01], fill=GOLD_D)
    # Body
    draw.ellipse([lamp_cx-lamp_rx, lamp_cy-lamp_ry,
                  lamp_cx+lamp_rx, lamp_cy+lamp_ry], fill=GOLD)
    # Spout (right side, curving up)
    spout = [
        (lamp_cx + lamp_rx*0.65, lamp_cy - lamp_ry*0.5),
        (lamp_cx + lamp_rx*1.3,  lamp_cy - lamp_ry*1.5),
        (lamp_cx + lamp_rx*1.55, lamp_cy - lamp_ry*1.1),
        (lamp_cx + lamp_rx*0.85, lamp_cy + lamp_ry*0.1),
    ]
    draw.polygon(spout, fill=GOLD)
    # Handle (left side arc)
    for i in range(18):
        a = math.radians(-20 + i * 12)
        hr = lamp_rx * 0.42
        hx = lamp_cx - lamp_rx*0.75 + hr * math.cos(a)
        hy = lamp_cy + lamp_ry*0.1  + hr * math.sin(a)
        hw = max(3, s // 48)
        draw.ellipse([hx-hw, hy-hw, hx+hw, hy+hw], fill=GOLD_D)
    # Base strip
    bw = lamp_rx * 0.85
    draw.rectangle([lamp_cx-bw, lamp_cy+lamp_ry*0.6,
                    lamp_cx+bw, lamp_cy+lamp_ry*1.0], fill=GOLD_D)
    draw.rectangle([lamp_cx-bw*1.1, lamp_cy+lamp_ry*0.9,
                    lamp_cx+bw*1.1, lamp_cy+lamp_ry*1.3], fill=GOLD)
    # Shine
    draw.ellipse([lamp_cx-lamp_rx*0.48, lamp_cy-lamp_ry*0.65,
                  lamp_cx-lamp_rx*0.05, lamp_cy-lamp_ry*0.05], fill="#FFFDE0")

    # ── Smoke / genie tail (from lamp top up to waist) ───────────────────
    for layer in range(4):
        t     = layer / 3
        alpha = int(200 - t * 80)
        col   = (0, int(100 + t*81), int(140 + t*64), alpha)
        w_bot = s * (0.03 + t * 0.01)
        w_top = s * (0.07 + t * 0.02)
        smoke = [
            (cx - w_bot, smoke_top),
            (cx - w_top, waist_y - s*0.04),
            (cx + w_top, waist_y - s*0.04),
            (cx + w_bot, smoke_top),
        ]
        layer_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(layer_img).polygon(smoke, fill=col)
        img = Image.alpha_composite(img, layer_img)
    draw = ImageDraw.Draw(img)

    # ── Genie torso ───────────────────────────────────────────────────────
    torso = [
        (cx - s*0.04, waist_y),
        (cx - s*0.13, chest_y),
        (cx - s*0.09, head_cy + head_r*0.7),
        (cx + s*0.09, head_cy + head_r*0.7),
        (cx + s*0.13, chest_y),
        (cx + s*0.04, waist_y),
    ]
    draw.polygon(torso, fill=TEAL)

    # Chest detail line
    draw.line([cx, chest_y, cx, head_cy + head_r*0.6],
              fill=TEAL_D, width=max(1, s//90))

    # ── Arms ─────────────────────────────────────────────────────────────
    arm_root_y = chest_y + s*0.02
    arm_tip_y  = chest_y - s*0.03
    for side in (-1, 1):
        arm = [
            (cx + side*s*0.10, arm_root_y),
            (cx + side*s*0.27, arm_tip_y - s*0.02),
            (cx + side*s*0.30, arm_tip_y + s*0.06),
            (cx + side*s*0.22, arm_root_y + s*0.06),
        ]
        draw.polygon(arm, fill=TEAL)
        # Hand ball
        hx = cx + side * s*0.295
        hy = arm_tip_y + s*0.04
        hr = s*0.038
        draw.ellipse([hx-hr, hy-hr, hx+hr, hy+hr], fill=TEAL_LT)

    # ── Head ─────────────────────────────────────────────────────────────
    # Shadow
    draw.ellipse([head_cx-head_r+s*0.01, head_cy-head_r+s*0.01,
                  head_cx+head_r+s*0.01, head_cy+head_r+s*0.01], fill=TEAL_D)
    draw.ellipse([head_cx-head_r, head_cy-head_r,
                  head_cx+head_r, head_cy+head_r], fill=TEAL)

    # Eyes
    ey  = head_cy - head_r*0.12
    er  = head_r * 0.16
    sep = head_r * 0.40
    for ex in (head_cx - sep, head_cx + sep):
        draw.ellipse([ex-er*1.1, ey-er*0.8, ex+er*1.1, ey+er*0.8], fill=BG)
        draw.ellipse([ex-er*0.55, ey-er*0.55, ex+er*0.55, ey+er*0.55], fill=GREEN)
        cl = max(1, int(er*0.3))
        draw.ellipse([ex-er*0.2, ey-er*0.4, ex-er*0.2+cl, ey-er*0.4+cl], fill="white")

    # Eyebrows
    brow_w = head_r * 0.30
    brow_y = ey - er*1.1
    brow_h = max(1, s//80)
    for ex in (head_cx - sep, head_cx + sep):
        draw.line([ex-brow_w, brow_y+s*0.008, ex+brow_w, brow_y],
                  fill=BG, width=brow_h*2)

    # Smile
    sm_r = head_r * 0.38
    draw.arc([head_cx-sm_r, head_cy+head_r*0.08,
              head_cx+sm_r, head_cy+head_r*0.52],
             start=10, end=170, fill=BG, width=max(1, s//70))

    # ── Turban ───────────────────────────────────────────────────────────
    turban_y  = head_cy - head_r*0.45
    turban_rx = head_r * 1.08
    turban_ry = head_r * 0.32

    # Turban band
    draw.ellipse([head_cx-turban_rx, turban_y-turban_ry,
                  head_cx+turban_rx, turban_y+turban_ry], fill=GREEN_D)
    draw.ellipse([head_cx-turban_rx*0.95, turban_y-turban_ry*0.7,
                  head_cx+turban_rx*0.95, turban_y+turban_ry*0.7], fill=GREEN)

    # Turban top (pointed)
    tip_y = head_cy - head_r * 1.75
    turban_top = [
        (head_cx - turban_rx*0.78, turban_y - turban_ry*0.2),
        (head_cx,                   tip_y),
        (head_cx + turban_rx*0.78, turban_y - turban_ry*0.2),
    ]
    draw.polygon(turban_top, fill=GREEN)
    # Turban fold lines
    for tx, ty in [(-0.3, 0.6), (0.3, 0.6)]:
        draw.line([head_cx, tip_y,
                   head_cx + tx*turban_rx, turban_y + ty*turban_ry],
                  fill=GREEN_D, width=max(1, s//100))

    # Jewel on turban
    jx, jy, jr = head_cx, turban_y, head_r*0.16
    draw.ellipse([jx-jr, jy-jr, jx+jr, jy+jr], fill=GOLD_D)
    draw.ellipse([jx-jr*0.65, jy-jr*0.65, jx+jr*0.65, jy+jr*0.65], fill=GOLD)
    draw.ellipse([jx-jr*0.25, jy-jr*0.35, jx+jr*0.25, jy+jr*0.05], fill="#FFFDE0")

    # ── Sparkles ─────────────────────────────────────────────────────────
    if s >= 80:
        for sx, sy, sr in [
            (cx - r*0.55, cx - r*0.50, s*0.030),
            (cx + r*0.60, cx - r*0.35, s*0.022),
            (cx - r*0.20, cx + r*0.55, s*0.018),
            (cx + r*0.40, cx + r*0.50, s*0.020),
        ]:
            _star(draw, sx, sy, sr, GREEN, points=4)

    return img


def _star(draw, cx, cy, r, color, points=4):
    pts = []
    for i in range(points * 2):
        angle  = math.pi * i / points - math.pi/2
        radius = r if i % 2 == 0 else r * 0.35
        pts.append((cx + radius*math.cos(angle),
                    cy + radius*math.sin(angle)))
    draw.polygon(pts, fill=color)


def save_logo(path="logo.png", size=256):
    img = make_logo(size)
    img.save(path)
    return img


if __name__ == "__main__":
    save_logo()
    print("logo.png saved.")
