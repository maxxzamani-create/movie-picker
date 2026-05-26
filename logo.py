"""
The Movie Zenie — logo.

A stylized 'Z' rising out of a magic lamp on a dark midnight disc.
Color palette matches the Indigo Night UI theme.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Palette (matches static/style.css — California Neon)
MAGENTA    = "#ff6ec7"   # flamingo pink — primary
MAGENTA_D  = "#d94a9c"   # deeper flamingo
MAGENTA_LT = "#ffb3df"   # pale pink highlight
CYAN       = "#4dd0e1"   # turquoise — secondary
CYAN_D     = "#26a69a"   # deeper teal
CYAN_LT    = "#80deea"   # pale teal highlight
LIME       = "#ffd54f"   # sun gold sparkle (semantic var name kept)
LIME_D     = "#ffa726"
PURPLE     = "#4a3a7a"   # lavender haze border
CORAL      = "#ff8a65"   # sunset coral
BG         = "#1a1338"   # deep midnight purple
BG_DEEP    = "#0d0820"
WHITE      = "#ffffff"
# Brushed-chrome tones for the magic lamp — still cool/silvery for the
# vapor-tech feel, but slightly warmer than the Tokyo cyberpunk version.
GOLD       = "#a8a3c0"   # brushed chrome body (var name kept for downstream code)
GOLD_D     = "#5a546d"   # deep chrome shadow


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

    # ── Flamingo-pink halo (sunset bleeding into dusk) ───────────────────
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([cx-r-6, cx-r-6, cx+r+6, cx+r+6], fill=(255, 110, 199, 160))
    glow = glow.filter(ImageFilter.GaussianBlur(max(4, s // 12)))
    img  = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # ── Background disc with two-tone ring (pink outer, turquoise inner) ─
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], fill=BG)
    # Outer flamingo ring
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], outline=MAGENTA, width=max(2, s//50))
    # Inner turquoise ring (the second tube)
    inner_r = r - max(3, s//38)
    draw.ellipse([cx-inner_r, cx-inner_r, cx+inner_r, cx+inner_r],
                 outline=CYAN, width=max(1, s//95))

    # ── Proportional anchors ─────────────────────────────────────────────
    lamp_cx   = cx
    lamp_cy   = s * 0.80
    lamp_rx   = s * 0.22
    lamp_ry   = s * 0.085
    smoke_top = lamp_cy - lamp_ry        # smoke exits top of lamp body

    # Z bounding box (where the 'Z' floats above the lamp)
    z_top    = s * 0.20
    z_bot    = s * 0.58
    z_half_w = s * 0.20
    z_thick  = s * 0.085

    # ── Magic lamp ───────────────────────────────────────────────────────
    # Shadow
    draw.ellipse([lamp_cx-lamp_rx+s*0.012, lamp_cy-lamp_ry+s*0.012,
                  lamp_cx+lamp_rx+s*0.012, lamp_cy+lamp_ry+s*0.012], fill=GOLD_D)
    # Body
    draw.ellipse([lamp_cx-lamp_rx, lamp_cy-lamp_ry,
                  lamp_cx+lamp_rx, lamp_cy+lamp_ry], fill=GOLD)
    # Spout (right side, curving up)
    spout = [
        (lamp_cx + lamp_rx*0.65, lamp_cy - lamp_ry*0.5),
        (lamp_cx + lamp_rx*1.30, lamp_cy - lamp_ry*1.5),
        (lamp_cx + lamp_rx*1.55, lamp_cy - lamp_ry*1.1),
        (lamp_cx + lamp_rx*0.85, lamp_cy + lamp_ry*0.1),
    ]
    draw.polygon(spout, fill=GOLD)
    # Handle (left side arc, drawn as a string of small circles)
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
    # Highlight
    draw.ellipse([lamp_cx-lamp_rx*0.48, lamp_cy-lamp_ry*0.65,
                  lamp_cx-lamp_rx*0.05, lamp_cy-lamp_ry*0.05], fill=WHITE)

    # ── Smoke rising from the spout, curling to under the Z ──────────────
    # Sunset gradient: turquoise at the lamp, coral mid-air, flamingo near
    # the Z. Reads like sky colors fading into each other at dusk.
    smoke_x_bottom = lamp_cx + lamp_rx*1.15
    smoke_x_top    = cx
    for layer in range(5):
        t     = layer / 4
        alpha = int(195 - t * 120)
        # Bottom: turquoise (#4dd0e1)  Top: flamingo (#ff6ec7)
        col   = (
            int(77  + t * 178),   # R: 77 -> 255
            int(208 - t * 98),    # G: 208 -> 110
            int(225 - t * 26),    # B: 225 -> 199
            alpha,
        )
        w_bot = s * (0.025 + t * 0.012)
        w_top = s * (0.08  + t * 0.030)
        # The smoke S-curves slightly: start at spout, curl to center
        x_mid_bottom = smoke_x_bottom - (smoke_x_bottom - smoke_x_top) * 0.35
        x_mid_top    = smoke_x_bottom - (smoke_x_bottom - smoke_x_top) * 0.85
        y_mid        = (smoke_top + z_bot) / 2
        smoke = [
            (x_mid_bottom - w_bot, smoke_top + s*0.005),
            (x_mid_top    - w_top, z_bot - s*0.01),
            (x_mid_top    + w_top, z_bot - s*0.01),
            (x_mid_bottom + w_bot, smoke_top + s*0.005),
        ]
        layer_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(layer_img).polygon(smoke, fill=col)
        layer_img = layer_img.filter(ImageFilter.GaussianBlur(max(1, s // 90)))
        img = Image.alpha_composite(img, layer_img)
    draw = ImageDraw.Draw(img)

    # ── Flamingo glow behind the Z — soft sunset bloom ───────────────────
    z_glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    zd = ImageDraw.Draw(z_glow)
    glow_pad = s * 0.07
    zd.ellipse([cx - z_half_w - glow_pad, z_top - glow_pad,
                cx + z_half_w + glow_pad, z_bot + glow_pad],
               fill=(255, 110, 199, 175))
    z_glow = z_glow.filter(ImageFilter.GaussianBlur(max(3, s // 11)))
    img = Image.alpha_composite(img, z_glow)
    draw = ImageDraw.Draw(img)

    # ── The Z — flamingo pink fill with turquoise outline ────────────────
    _draw_z(draw, cx, z_top, z_bot, z_half_w, z_thick,
            fill=MAGENTA, edge=CYAN, edge_width=max(2, s // 56))

    # Inner shine — pale pink highlight along the diagonal
    if s >= 80:
        sh_top    = (cx + z_half_w * 0.55, z_top + z_thick + s*0.012)
        sh_bot    = (cx - z_half_w * 0.30, z_bot - z_thick - s*0.012)
        sh_w      = max(2, s // 110)
        draw.line([sh_top, sh_bot], fill=MAGENTA_LT, width=sh_w)

        # Tiny gold shine on the top bar (sun catching the edge)
        draw.line(
            [(cx - z_half_w + s*0.025, z_top + s*0.014),
             (cx + z_half_w - s*0.025, z_top + s*0.014)],
            fill=LIME, width=max(1, s // 120)
        )

    # ── Sparkles (sunset specks — flamingo, turquoise, sun gold, coral) ──
    if s >= 80:
        sparkles = [
            (cx - r*0.62, cx - r*0.45, s*0.028, MAGENTA_LT),
            (cx + r*0.60, cx - r*0.30, s*0.022, LIME),
            (cx - r*0.18, cx + r*0.55, s*0.017, CYAN),
            (cx + r*0.42, cx + r*0.48, s*0.020, CORAL),
            (cx + r*0.55, cx + r*0.10, s*0.014, MAGENTA),
        ]
        for sx, sy, sr, scol in sparkles:
            _star(draw, sx, sy, sr, scol, points=4)

    return img


def _draw_z(draw, cx, top, bot, half_w, thick, fill, edge=None, edge_width=0):
    """Bold stylized Z made of 3 polygons: top bar, diagonal stripe, bottom bar."""
    left  = cx - half_w
    right = cx + half_w

    top_bar = [
        (left,  top),
        (right, top),
        (right, top + thick),
        (left,  top + thick),
    ]
    bot_bar = [
        (left,  bot - thick),
        (right, bot - thick),
        (right, bot),
        (left,  bot),
    ]
    # Diagonal stripe (parallelogram from top-right to bottom-left)
    diag = [
        (right,         top + thick),
        (left  + thick, bot - thick),
        (left,          bot - thick),
        (right - thick, top + thick),
    ]

    draw.polygon(top_bar, fill=fill)
    draw.polygon(diag,    fill=fill)
    draw.polygon(bot_bar, fill=fill)

    # Optional edge stroke for definition
    if edge and edge_width > 0:
        def outline(pts):
            n = len(pts)
            for i in range(n):
                draw.line([pts[i], pts[(i+1) % n]], fill=edge, width=edge_width)
        outline(top_bar)
        outline(diag)
        outline(bot_bar)


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
