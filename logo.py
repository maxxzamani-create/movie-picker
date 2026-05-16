"""
The Movie Zenie — logo.

A stylized 'Z' rising out of a magic lamp on a dark midnight disc.
Color palette matches the Indigo Night UI theme.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Palette (matches static/style.css — Forest Green & Gold)
FOREST     = "#228B22"   # CSS forest green — heritage classic
FOREST_D   = "#176617"   # darker pine
FOREST_LT  = "#4caf50"   # brighter leaf for accents
PINE       = "#0d3a1a"   # deepest pine
GOLD       = "#FFD700"   # true gold — primary accent
GOLD_D     = "#b8860b"   # dark goldenrod for gradient end
GOLD_LT    = "#ffe566"   # pale gold highlight
GOLD_DEEP  = "#DAA520"   # goldenrod for borders
BG         = "#0d1a12"   # deep forest night
BG_DEEP    = "#060e08"
WHITE      = "#FFFDE0"


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

    # ── Gold-tinted glow halo ────────────────────────────────────────────
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([cx-r-6, cx-r-6, cx+r+6, cx+r+6], fill=(218, 165, 32, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(max(4, s // 14)))
    img  = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # ── Background disc with gold ring on green inner edge ───────────────
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], fill=BG)
    # Outer gold ring
    draw.ellipse([cx-r, cx-r, cx+r, cx+r], outline=GOLD_DEEP, width=max(2, s//52))
    # Inner forest-green stroke for the two-tone heritage look
    inner_r = r - max(3, s//40)
    draw.ellipse([cx-inner_r, cx-inner_r, cx+inner_r, cx+inner_r],
                 outline=FOREST, width=max(1, s//110))

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

    # ── Magical smoke rising from the spout, curling to under the Z ──────
    # We paint several semi-transparent layers, widest near the Z.
    smoke_x_bottom = lamp_cx + lamp_rx*1.15   # exit point near the spout tip
    smoke_x_top    = cx                       # converges to center, under Z
    for layer in range(5):
        t     = layer / 4
        alpha = int(190 - t * 130)
        # Forest-green smoke shifting to gold mist as it rises
        col   = (
            int(34  + t * 180),  # R: 34 -> 214
            int(139 + t * 35),   # G: 139 -> 174 (stays greenish then warm)
            int(34  + t * 20),   # B: 34 -> 54 (stays low — warm hue)
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

    # ── Soft gold glow behind the Z ──────────────────────────────────────
    z_glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    zd = ImageDraw.Draw(z_glow)
    glow_pad = s * 0.05
    zd.ellipse([cx - z_half_w - glow_pad, z_top - glow_pad,
                cx + z_half_w + glow_pad, z_bot + glow_pad],
               fill=(255, 215, 0, 110))
    z_glow = z_glow.filter(ImageFilter.GaussianBlur(max(3, s // 16)))
    img = Image.alpha_composite(img, z_glow)
    draw = ImageDraw.Draw(img)

    # ── The Z (3 bars: top, diagonal, bottom) ────────────────────────────
    _draw_z(draw, cx, z_top, z_bot, z_half_w, z_thick,
            fill=GOLD, edge=GOLD_D, edge_width=max(1, s // 60))

    # Inner shine line along the diagonal of the Z (pale gold highlight)
    if s >= 80:
        sh_top    = (cx + z_half_w * 0.55, z_top + z_thick + s*0.012)
        sh_bot    = (cx - z_half_w * 0.30, z_bot - z_thick - s*0.012)
        sh_w      = max(2, s // 110)
        draw.line([sh_top, sh_bot], fill=GOLD_LT, width=sh_w)

        # Tiny shine on the top bar
        draw.line(
            [(cx - z_half_w + s*0.025, z_top + s*0.014),
             (cx + z_half_w - s*0.025, z_top + s*0.014)],
            fill=WHITE, width=max(1, s // 120)
        )

    # ── Sparkles (fireflies — green and gold) ────────────────────────────
    if s >= 80:
        sparkles = [
            (cx - r*0.62, cx - r*0.45, s*0.028, GOLD_LT),
            (cx + r*0.60, cx - r*0.30, s*0.022, FOREST_LT),
            (cx - r*0.18, cx + r*0.55, s*0.017, GOLD),
            (cx + r*0.42, cx + r*0.48, s*0.020, GOLD_LT),
            (cx + r*0.55, cx + r*0.10, s*0.014, FOREST_LT),
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
