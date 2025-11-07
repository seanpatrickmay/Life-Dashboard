"""Generate Monet-inspired pixel PNG assets (light/dark variants) without external deps.

Outputs to: frontend/src/assets/pixels/

Generates PNGs for:
  - lilies/blossoms + clusters
  - water bases, reflections, clouds, ripples
  - reeds, willow fronds, speckles
  - microgrids, dithers, stroke tiles
  - vignette overlays, bridge/koi/boat silhouettes

All images use RGBA and are rendered from simple shapes.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
import zlib
from binascii import crc32
import math
import random

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "src" / "assets" / "pixels"
SEED = int(os.environ.get("PIXEL_SEED", "1337"))
rng = random.Random(SEED)


def _chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(
        ">I", len(data)
    ) + typ + data + struct.pack(
        ">I", crc32(typ + data) & 0xFFFFFFFF
    )


def write_png_rgba(path: Path, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        for x in range(w):
            r, g, b, a = pixels[y][x]
            raw += bytes([r & 255, g & 255, b & 255, a & 255])
    comp = zlib.compress(bytes(raw), level=9)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(
        b"IHDR",
        struct.pack(
            ">IIBBBBB",
            w,
            h,
            8,  # bit depth
            6,  # color type RGBA
            0,
            0,
            0,
        ),
    )
    idat = _chunk(b"IDAT", comp)
    iend = _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)


# --- Pixel helper utilities -------------------------------------------------

BAYER_4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]

BAYER_8 = [
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
]

_blue_values = list(range(256))
random.Random(42).shuffle(_blue_values)
BLUE_NOISE_16 = [
    _blue_values[i * 16 : (i + 1) * 16] for i in range(16)
]

PREVIEWS: list[tuple[str, list[list[tuple[int, int, int, int]]], bool]] = []


def save_asset(filename: str, px: list[list[tuple[int, int, int, int]]], tile_preview: bool = False) -> None:
    write_png_rgba(OUT / filename, px)
    PREVIEWS.append((filename, px, tile_preview))


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def mix(c1: tuple[int, int, int, int], c2: tuple[int, int, int, int], alpha: float) -> tuple[int, int, int, int]:
    """Linear interpolate RGBA colors."""
    a = clamp(alpha, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * a),
        int(c1[1] + (c2[1] - c1[1]) * a),
        int(c1[2] + (c2[2] - c1[2]) * a),
        int(c1[3] + (c2[3] - c1[3]) * a),
    )


def blank(w: int, h: int, rgba=(0, 0, 0, 0)) -> list[list[tuple[int, int, int, int]]]:
    return [[rgba for _ in range(w)] for _ in range(h)]


def wrap_put(px, x, y, c):
    h = len(px)
    w = len(px[0])
    px[y % h][x % w] = c


def put(px, x, y, c):
    h = len(px)
    w = len(px[0])
    if 0 <= x < w and 0 <= y < h:
        px[y][x] = c


def add_blue_noise(px, color, coverage: float):
    """Place color using blue-noise threshold for coverage (0-1)."""
    w = len(px[0])
    h = len(px)
    threshold = int(clamp(coverage, 0.0, 1.0) * 256)
    for y in range(h):
        for x in range(w):
            if BLUE_NOISE_16[y % 16][x % 16] < threshold:
                wrap_put(px, x, y, color)


def ordered_mask(mask, x, y):
    n = len(mask)
    return mask[y % n][x % n] / (n * n)


def ordered_dither_fill(px, base_color, highlight_color, strength: float, mask=BAYER_8):
    """Fill with base_color and add highlight pixels based on ordered mask."""
    strength = clamp(strength, 0.0, 1.0)
    h = len(px)
    w = len(px[0])
    for y in range(h):
        for x in range(w):
            px[y][x] = base_color
            if ordered_mask(mask, x, y) < strength:
                px[y][x] = highlight_color


def blit(src, dst, ox, oy, alpha=True):
    sh = len(src)
    sw = len(src[0])
    dh = len(dst)
    dw = len(dst[0])
    for y in range(sh):
        for x in range(sw):
            if not (0 <= ox + x < dw and 0 <= oy + y < dh):
                continue
            c = src[y][x]
            if not alpha or c[3] > 0:
                dst[oy + y][ox + x] = c


def draw_line(px, x0, y0, x1, y1, color, wrap=False):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        if wrap:
            wrap_put(px, x, y, color)
        else:
            put(px, x, y, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy



# Palette (light/dark)
LIGHT = {
    "water": (233, 241, 255, 255),
    "pond": (126, 215, 196, 255),
    "pond_deep": (63, 155, 138, 255),
    "leaf": (137, 222, 201, 255),
    "leaf_deep": (79, 181, 111, 255),
    "bloom": (246, 214, 237, 255),
    "bloom_core": (215, 127, 179, 255),
    "sun": (255, 192, 117, 255),
    "grid": (111, 139, 203, 48),
    "ink": (30, 31, 46, 255),
}

DARK = {
    "water": (15, 20, 36, 255),
    "pond": (47, 122, 109, 255),
    "pond_deep": (30, 90, 79, 255),
    "leaf": (31, 102, 92, 255),
    "leaf_deep": (26, 77, 68, 255),
    "bloom": (185, 83, 137, 255),
    "bloom_core": (217, 120, 173, 255),
    "sun": (240, 166, 90, 255),
    "grid": (194, 213, 255, 28),
    "ink": (246, 240, 232, 255),
}


def circle(px, cx, cy, r, c):
    # Midpoint circle
    x = r
    y = 0
    d = 1 - r
    while x >= y:
        for dx, dy in (
            (x, y), (y, x), (-y, x), (-x, y), (-x, -y), (-y, -x), (y, -x), (x, -y)
        ):
            put(px, cx + dx, cy + dy, c)
        y += 1
        if d < 0:
            d += 2 * y + 1
        else:
            x -= 1
            d += 2 * (y - x) + 1


def filled_circle(px, cx, cy, r, c):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r * r:
                put(px, xx, yy, c)


def notch(px, cx, cy, r, angle_deg=315, width=5, c=(0, 0, 0, 0)):
    # Carve a notch into the lily pad (simple triangular wedge)
    import math

    ang = math.radians(angle_deg)
    for rr in range(0, r + 1):
        xx = int(cx + rr * math.cos(ang))
        yy = int(cy + rr * math.sin(ang))
        for w in range(-width // 2, width // 2 + 1):
            put(px, xx + w, yy + w, c)


def draw_lily_light(name: str, base=LIGHT) -> None:
    w = h = 24
    px = blank(w, h, base["water"][0:3] + (0,))
    # Base leaf
    filled_circle(px, 12, 12, 9, base["leaf"])
    # Shading
    filled_circle(px, 9, 10, 7, base["leaf_deep"])
    # Notch
    notch(px, 12, 12, 9, 300, 4)
    # Occasional blossom
    filled_circle(px, 16, 9, 3, base["bloom"])
    filled_circle(px, 16, 9, 1, base["bloom_core"])
    save_asset(f"{name}.png", px)


def draw_lily_dark(name: str, base=DARK) -> None:
    w = h = 24
    px = blank(w, h, base["water"][0:3] + (0,))
    filled_circle(px, 12, 12, 9, base["leaf"])
    filled_circle(px, 9, 10, 7, base["leaf_deep"])
    notch(px, 12, 12, 9, 300, 4)
    filled_circle(px, 16, 9, 3, base["bloom"])  # darker bloom
    filled_circle(px, 16, 9, 1, base["bloom_core"])
    save_asset(f"{name}.png", px)


def draw_pad_small(name: str, base, radius: int, notch_angle=315) -> None:
    size = radius * 2 + 6
    px = blank(size, size, (0, 0, 0, 0))
    cx = cy = size // 2
    filled_circle(px, cx, cy, radius, base["leaf"])
    filled_circle(px, cx - 2, cy - 2, radius - 2, base["leaf_deep"])
    notch(px, cx, cy, radius, notch_angle, 3)
    save_asset(f"{name}.png", px)


def draw_pad_ring(name: str, base, outer: int, inner: int) -> None:
    size = outer * 2 + 6
    px = blank(size, size, (0, 0, 0, 0))
    cx = cy = size // 2
    filled_circle(px, cx, cy, outer, base["leaf_deep"])
    # carve center
    for yy in range(size):
        for xx in range(size):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= inner ** 2:
                px[yy][xx] = (0, 0, 0, 0)
    notch(px, cx, cy, outer, 300, 4)
    save_asset(f"{name}.png", px)


def draw_blossom_small(name: str, base, radius: int) -> None:
    size = radius * 2 + 6
    px = blank(size, size, (0, 0, 0, 0))
    cx = cy = size // 2
    filled_circle(px, cx, cy, radius, base["bloom"])
    filled_circle(px, cx, cy, max(1, radius - 2), base["bloom_core"])
    save_asset(f"{name}.png", px)


def draw_blossom_glow(name: str, color: tuple[int, int, int, int]) -> None:
    w = h = 48
    px = blank(w, h)
    cx = cy = w // 2
    max_r = w // 2 - 2
    for y in range(h):
        for x in range(w):
            dist = math.hypot(x - cx, y - cy)
            t = clamp(1 - dist / max_r, 0.0, 1.0)
            if t <= 0:
                continue
            alpha = int(color[3] * (t ** 2))
            if alpha > 0:
                px[y][x] = (color[0], color[1], color[2], alpha)
    save_asset(f"{name}.png", px)


def build_blossom_pixels(base) -> list[list[tuple[int, int, int, int]]]:
    w = h = 16
    px = blank(w, h)
    filled_circle(px, 8, 8, 5, base["bloom"])  # petal
    filled_circle(px, 8, 8, 2, base["bloom_core"])  # core
    return px


def draw_blossom(name: str, base) -> None:
    px = build_blossom_pixels(base)
    save_asset(f"{name}.png", px)


def draw_ripple(name: str, base) -> None:
    w = h = 16
    px = blank(w, h)
    c1 = (126, 171, 239, 64) if base is LIGHT else (120, 170, 213, 64)
    for y in (6, 10):
        for x in range(0, w, 1):
            put(px, x, y, c1)
    for y in (3, 13):
        for x in range(0, w, 2):
            put(px, x, y, c1)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_microgrid(name: str, base) -> None:
    w = h = 8
    px = blank(w, h)
    g = base["grid"]
    # vertical
    for x in (0, 4):
        for y in range(h):
            put(px, x, y, g)
    # horizontal
    for y in (0, 4):
        for x in range(w):
            put(px, x, y, g)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_dither(name: str, base) -> None:
    w = h = 8
    px = blank(w, h)
    a = 42 if base is LIGHT else 32
    c = (255, 255, 255, a)
    for y in range(h):
        for x in range(w):
            if (x + y) % 4 == 0:
                put(px, x, y, c)
    save_asset(f"{name}.png", px)


def draw_frame_corners(name: str, base) -> None:
    w = h = 12
    px = blank(w, h)
    gold = base["sun"]
    # top-left
    for y in range(0, 3):
        for x in range(0, 3):
            put(px, x, y, gold)
    # top-right
    for y in range(0, 3):
        for x in range(w - 3, w):
            put(px, x, y, gold)
    # bottom-left
    for y in range(h - 3, h):
        for x in range(0, 3):
            put(px, x, y, gold)
    # bottom-right
    for y in range(h - 3, h):
        for x in range(w - 3, w):
            put(px, x, y, gold)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_speckles(name: str, base) -> None:
    w = h = 12
    px = blank(w, h)
    star = (246, 240, 232, 160) if base is DARK else (239, 233, 225, 140)
    coords = [(1, 2), (6, 1), (10, 3), (3, 8), (8, 10)]
    for (x, y) in coords:
        put(px, x, y, star)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_speckles_light(name: str) -> None:
    w = h = 16
    px = blank(w, h)
    star = (255, 255, 255, 72)
    coords = [(2, 1), (7, 2), (13, 4), (4, 11), (10, 13)]
    for (x, y) in coords:
        put(px, x, y, star)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_water_base(name: str, base, tint: tuple[int, int, int, int]) -> None:
    w = h = 16
    px = blank(w, h, base["water"])
    # Add subtle dither glints
    coords = [(1, 3), (6, 2), (12, 4), (3, 10), (9, 12), (14, 8)]
    for (x, y) in coords:
        put(px, x, y, tint)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_water_reflection(name: str, colors: list[tuple[int, int, int, int]]) -> None:
    w, h = 32, 16
    px = blank(w, h)
    bands = len(colors)
    for idx, color in enumerate(colors):
        base_y = int((idx + 1) * (h / (bands + 1)))
        phase = rng.uniform(0, math.pi * 2)
        amp = rng.uniform(0.8, 1.6)
        thickness = 1 if color[3] < 70 else 2
        for x in range(w):
            offset = math.sin((x + phase) / 4.2) * amp
            y = int(base_y + offset)
            for t in range(-thickness, thickness + 1):
                wrap_put(px, x, y + t, color)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_water_stroke(name: str, base_color: tuple[int, int, int, int], highlight: tuple[int, int, int, int], size=(128, 64)) -> None:
    w, h = size
    px = blank(w, h)
    for band in range(6):
        offset_y = rng.randint(0, h - 1)
        amplitude = rng.uniform(1.0, 3.0)
        thickness = rng.randint(1, 2)
        for x in range(w):
            y = int(offset_y + math.sin((x + band * 13) / 8.0) * amplitude)
            for t in range(thickness):
                put(px, x, (y + t) % h, base_color)
            if x % 9 == 0:
                put(px, x, (y + thickness) % h, highlight)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_caustic_ripple(name: str, tint: tuple[int, int, int, int]) -> None:
    w = h = 24
    px = blank(w, h)
    for ring in range(3, 10, 3):
        circle(px, w // 2, h // 2, ring, tint)
    add_blue_noise(px, tint, 0.2)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_sun_glow(name: str, inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> None:
    w = h = 96
    px = blank(w, h)
    cx = cy = w // 2
    max_r = w // 2 - 2
    for y in range(h):
        for x in range(w):
            dist = math.hypot(x - cx, y - cy)
            t = clamp(1 - dist / max_r, 0.0, 1.0)
            if t <= 0:
                continue
            if t > 0.7:
                color = inner
                strength = (t - 0.7) / 0.3
            else:
                color = outer
                strength = t
            alpha = int(color[3] * strength)
            if alpha > 0:
                px[y][x] = (color[0], color[1], color[2], alpha)
    save_asset(f"{name}.png", px)


def draw_cloud_reflection(name: str, highlight: tuple[int, int, int, int], accent: tuple[int, int, int, int]) -> None:
    w, h = 32, 16
    px = blank(w, h)
    clusters = 3
    for _ in range(clusters):
        radius = rng.randint(3, 5)
        cx = rng.randint(4, w - 5)
        cy = rng.randint(2, h - 3)
        for yy in range(cy - radius, cy + radius + 1):
            for xx in range(cx - radius, cx + radius + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2:
                    put(px, xx, yy, highlight)
    add_blue_noise(px, accent, 0.12)
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_reeds(name: str, palette) -> None:
    w = h = 24
    px = blank(w, h)
    stems = 3
    for idx in range(stems):
        base_x = rng.randint(3 + idx * 6, 6 + idx * 6)
        height = rng.randint(10, 17)
        for step in range(height):
            y = h - 1 - step
            x = base_x + rng.randint(-1, 1)
            put(px, x, y, palette["leaf_deep"])
            if step > height * 0.3 and rng.random() < 0.3:
                put(px, x + rng.choice([-1, 1]), y - rng.randint(0, 1), mix(palette["leaf"], palette["leaf_deep"], 0.4))
    save_asset(f"{name}.png", px, tile_preview=True)


def draw_reeds_edge(name: str, palette) -> None:
    w, h = 256, 120
    px = blank(w, h)
    for x in range(0, w, 6):
        height = rng.randint(40, 110)
        color = mix(palette["leaf_deep"], palette["leaf"], rng.random() * 0.3)
        for y in range(h - 1, h - height, -1):
            put(px, x + rng.randint(-1, 1), y, color)
            if rng.random() < 0.2:
                put(px, x + rng.choice([-1, 1]), y - 1, mix(color, palette["leaf"], 0.5))
    save_asset(f"{name}.png", px)


def draw_willow_frond(name: str, palette) -> None:
    w, h = 48, 96
    px = blank(w, h)
    branches = rng.randint(6, 8)
    for _ in range(branches):
        x = rng.randint(8, w - 8)
        max_len = rng.randint(60, h - 6)
        drift = rng.uniform(-0.4, 0.4)
        for y in range(max_len):
            put(px, int(round(x)), y, palette["leaf"])
            if rng.random() < 0.2:
                put(px, int(round(x + rng.choice([-1, 1]))), y, palette["leaf_deep"])
            x += drift + rng.uniform(-0.12, 0.12)
    save_asset(f"{name}.png", px)


def draw_willow_strands(name: str, palette, side: str) -> None:
    w, h = 140, 520
    px = blank(w, h)
    strand_count = 12
    for idx in range(strand_count):
        start_x = 18 + idx * 8 + rng.randint(-4, 4)
        drift = rng.uniform(-0.25, 0.35)
        thickness = rng.randint(2, 3)
        for y in range(h):
            x = int(start_x + math.sin((y / 36.0) + idx) * 3 + drift * y / 32)
            if side == "right":
                x = w - x
            for t in range(-thickness, thickness + 1):
                x0 = max(0, min(w - 1, x + t))
                put(px, x0, y, palette["leaf"])
                if rng.random() < 0.18:
                    x1 = max(0, min(w - 1, x0 + rng.choice([-1, 1])))
                    put(px, x1, y, palette["leaf_deep"])
            if rng.random() < 0.1:
                tip_x = max(0, min(w - 1, x + rng.choice([-1, 0, 1])))
                put(px, tip_x, y, mix(palette["leaf"], palette["leaf_deep"], 0.3))
    save_asset(f"{name}.png", px)


def draw_blossom_cluster(name: str, base, count: int) -> None:
    w = h = 48
    px = blank(w, h)
    for _ in range(count):
        sprite = build_blossom_pixels(base)
        ox = rng.randint(4, w - 20)
        oy = rng.randint(4, h - 20)
        blit(sprite, px, ox, oy)
    save_asset(f"{name}.png", px)


def draw_vignette(name: str, color: tuple[int, int, int, int], radius_inner: float, radius_outer: float) -> None:
    w = h = 256
    px = blank(w, h)
    cx = (w - 1) / 2
    cy = (h - 1) / 2
    max_dist = math.sqrt(cx * cx + cy * cy)
    inner = radius_inner * max_dist
    outer = radius_outer * max_dist
    for y in range(h):
        for x in range(w):
            dist = math.hypot(x - cx, y - cy)
            t = clamp((dist - inner) / (outer - inner), 0.0, 1.0)
            if t <= 0:
                continue
            alpha = int(color[3] * clamp(t, 0.0, 1.0))
            if alpha > 0:
                px[y][x] = (color[0], color[1], color[2], alpha)
    save_asset(f"{name}.png", px)


def draw_vignette_haze(name: str, color: tuple[int, int, int, int]) -> None:
    w = h = 512
    px = blank(w, h)
    cx = int(w * 0.5)
    cy = int(h * 0.55)
    max_r = min(cx, cy)
    for y in range(h):
        for x in range(w):
            dist = math.hypot(x - cx, y - cy)
            t = clamp(1 - dist / max_r, 0.0, 1.0)
            if t <= 0:
                continue
            alpha = int(color[3] * (t ** 1.6))
            if alpha > 0:
                px[y][x] = (color[0], color[1], color[2], alpha)
    save_asset(f"{name}.png", px)


def build_bridge_arc(main: tuple[int, int, int, int], highlight: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
    w, h = 220, 80
    px = blank(w, h)
    mid = w / 2
    base_y = int(h * 0.65)
    curvature = 620.0
    thickness = 2
    for x in range(w):
        offset = ((x - mid) ** 2) / curvature
        y = int(base_y - offset)
        for t in range(thickness):
            put(px, x, y - t, main)
        if x % 5 == 0:
            put(px, x, y - thickness, highlight)
    return px


def draw_bridge_arc(name: str, main: tuple[int, int, int, int], highlight: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
    px = build_bridge_arc(main, highlight)
    save_asset(f"{name}.png", px)
    return px


def draw_bridge_reflection(name: str, arc_px: list[list[tuple[int, int, int, int]]], tint: tuple[int, int, int, int]) -> None:
    w = len(arc_px[0])
    h = len(arc_px)
    target_h = 60
    px = blank(w, target_h)
    for y in range(h):
        for x in range(w):
            c = arc_px[y][x]
            if c[3] == 0:
                continue
            ry = int((y / h) * target_h)
            jitter = rng.randint(-1, 1)
            ny = int(clamp(ry + jitter, 0, target_h - 1))
            alpha = int(tint[3] * (1 - ry / target_h))
            px[ny][x] = (tint[0], tint[1], tint[2], alpha)
    save_asset(f"{name}.png", px)


def draw_koi(name: str, body: tuple[int, int, int, int], patch: tuple[int, int, int, int]) -> None:
    w, h = 24, 12
    px = blank(w, h)
    cx, cy = w / 2, h / 2
    rx, ry = w / 2.2, h / 2.3
    for y in range(h):
        for x in range(w):
            if ((x - cx) ** 2) / (rx ** 2) + ((y - cy) ** 2) / (ry ** 2) <= 1:
                px[y][x] = body
    for y in range(h):
        for x in range(w):
            if px[y][x][3] > 0 and (x + y) % 7 == 0:
                px[y][x] = patch
    save_asset(f"{name}.png", px)


def draw_boat(name: str, color: tuple[int, int, int, int]) -> None:
    w, h = 48, 16
    px = blank(w, h)
    hull_y = h // 2
    for x in range(6, w - 6):
        put(px, x, hull_y, color)
        put(px, x, hull_y + 1, color)
    for i in range(6):
        put(px, 6 + i, hull_y - i // 2, color)
        put(px, w - 7 - i, hull_y - i // 2, color)
    save_asset(f"{name}.png", px)


def draw_stroke_pattern(name: str, coords: list[tuple[int, int]]) -> None:
    w = h = 8
    px = blank(w, h)
    color = (255, 255, 255, 170)
    for (x, y) in coords:
        put(px, x % w, y % h, color)
    save_asset(f"{name}.png", px, tile_preview=True)


def generate_previews() -> None:
    if not PREVIEWS:
        return
    preview_dir = OUT / "_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for name, px, is_tile in PREVIEWS:
        if not is_tile:
            continue
        reps = 3
        tile_h = len(px)
        tile_w = len(px[0])
        canvas = blank(tile_w * reps, tile_h * reps, (0, 0, 0, 0))
        for y in range(tile_h * reps):
            for x in range(tile_w * reps):
                canvas[y][x] = px[y % tile_h][x % tile_w]
        write_png_rgba(preview_dir / f"{name}_preview.png", canvas)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    # Light lilies/blossoms (8 occurrences target)
    for i in range(1, 5):
        draw_lily_light(f"lily_light_{i}")
    for i in range(1, 5):
        draw_blossom(f"blossom_light_{i}", LIGHT)
    # Dark lilies/blossoms
    for i in range(1, 5):
        draw_lily_dark(f"lily_dark_{i}")
    for i in range(1, 5):
        draw_blossom(f"blossom_dark_{i}", DARK)
    # Sparse pads + blossoms (new small sprites)
    for i, radius in enumerate((10, 8, 12), start=1):
        draw_pad_small(f"pad_small_light_{i}", LIGHT, radius)
    for i, radius in enumerate((10, 8, 12), start=1):
        draw_pad_small(f"pad_small_dark_{i}", DARK, radius)
    draw_pad_ring("pad_ring_light", LIGHT, 18, 9)
    draw_pad_ring("pad_ring_dark", DARK, 18, 9)
    for i, radius in enumerate((6, 5, 7), start=1):
        draw_blossom_small(f"blossom_small_light_{i}", LIGHT, radius)
    for i, radius in enumerate((6, 5, 7), start=1):
        draw_blossom_small(f"blossom_small_dark_{i}", DARK, radius)
    draw_blossom_glow("blossom_glow_light", (247, 194, 217, 110))
    draw_blossom_glow("blossom_glow_dark", (233, 150, 198, 130))
    # Ripples, grids, dithers, frames, speckles
    draw_ripple("ripple_light", LIGHT)
    draw_ripple("ripple_dark", DARK)
    draw_microgrid("microgrid_light", LIGHT)
    draw_microgrid("microgrid_dark", DARK)
    draw_dither("dither_light", LIGHT)
    draw_dither("dither_dark", DARK)
    draw_frame_corners("frame_corners_light", LIGHT)
    draw_frame_corners("frame_corners_dark", DARK)
    draw_speckles("speckles_dark", DARK)
    draw_speckles_light("speckles_light")
    draw_water_base("water_base_light", {"water": (233, 241, 255, 255)}, (111, 139, 203, 28))
    draw_water_base("water_base_dark", {"water": (15, 20, 36, 255)}, (120, 170, 213, 32))
    draw_water_reflection(
        "water_reflection_light",
        [(194, 212, 255, 70), (246, 214, 237, 60)],
    )
    draw_water_reflection(
        "water_reflection_dark",
        [(120, 170, 213, 60), (111, 139, 203, 55), (215, 127, 179, 50)],
    )
    draw_cloud_reflection(
        "cloud_reflect_light",
        (246, 214, 237, 55),
        (255, 225, 179, 45),
    )
    draw_cloud_reflection(
        "cloud_reflect_dark",
        (215, 127, 179, 50),
        (120, 170, 213, 45),
    )
    draw_water_stroke(
        "water_stroke_large_light",
        (165, 190, 255, 90),
        (255, 214, 210, 80),
        size=(256, 128),
    )
    draw_water_stroke(
        "water_stroke_medium_light",
        (150, 180, 245, 80),
        (255, 203, 180, 70),
        size=(192, 96),
    )
    draw_water_stroke(
        "water_stroke_small_light",
        (140, 172, 230, 70),
        (244, 195, 200, 60),
        size=(128, 64),
    )
    draw_water_stroke(
        "water_stroke_large_dark",
        (58, 102, 173, 90),
        (210, 140, 190, 70),
        size=(256, 128),
    )
    draw_water_stroke(
        "water_stroke_medium_dark",
        (52, 94, 160, 80),
        (195, 120, 170, 65),
        size=(192, 96),
    )
    draw_water_stroke(
        "water_stroke_small_dark",
        (44, 80, 140, 70),
        (180, 110, 160, 60),
        size=(128, 64),
    )
    draw_caustic_ripple("caustic_ripple_fine_light", (255, 255, 255, 60))
    draw_caustic_ripple("caustic_ripple_fine_dark", (180, 210, 255, 50))
    draw_sun_glow("sun_glow_light", (255, 225, 179, 200), (247, 194, 217, 140))
    draw_sun_glow("sun_glow_dark", (240, 166, 90, 190), (215, 127, 179, 120))
    draw_reeds("reeds_light", LIGHT)
    draw_reeds("reeds_dark", DARK)
    draw_reeds_edge("reeds_edge_light", LIGHT)
    draw_reeds_edge("reeds_edge_dark", DARK)
    draw_willow_frond("willow_frond_light", LIGHT)
    draw_willow_frond("willow_frond_dark", DARK)
    draw_willow_strands("willow_strands_left_light", LIGHT, "left")
    draw_willow_strands("willow_strands_right_light", LIGHT, "right")
    draw_willow_strands("willow_strands_left_dark", DARK, "left")
    draw_willow_strands("willow_strands_right_dark", DARK, "right")
    draw_blossom_cluster("blossom_cluster_light_1", LIGHT, 4)
    draw_blossom_cluster("blossom_cluster_light_2", LIGHT, 3)
    draw_blossom_cluster("blossom_cluster_light_3", LIGHT, 5)
    draw_blossom_cluster("blossom_cluster_dark_1", DARK, 3)
    draw_blossom_cluster("blossom_cluster_dark_2", DARK, 2)
    draw_vignette("vignette_radial_light", (225, 214, 200, 70), 0.5, 1.0)
    draw_vignette("vignette_radial_dark", (20, 20, 32, 90), 0.4, 1.0)
    draw_vignette_haze("vignette_haze_light", (255, 240, 220, 65))
    draw_vignette_haze("vignette_haze_dark", (20, 30, 55, 110))
    light_arc = draw_bridge_arc(
        "bridge_arc_light",
        (126, 215, 196, 255),
        (194, 212, 255, 220),
    )
    draw_bridge_reflection(
        "bridge_arc_reflection_light",
        light_arc,
        (184, 240, 223, 140),
    )
    dark_arc = draw_bridge_arc(
        "bridge_arc_dark",
        (120, 170, 213, 255),
        (230, 169, 211, 220),
    )
    draw_bridge_reflection(
        "bridge_arc_reflection_dark",
        dark_arc,
        (120, 170, 213, 140),
    )
    draw_koi("koi_silhouette", (242, 140, 60, 255), (255, 255, 255, 255))
    draw_boat("boat_silhouette", (43, 42, 53, 255))
    draw_stroke_pattern("stroke_stipple", [(0, 0), (4, 4)])
    draw_stroke_pattern("stroke_crosshatch", [(0, 0), (7, 7), (0, 7), (7, 0)])
    draw_stroke_pattern("stroke_zigzag", [(0, 0), (1, 1), (2, 0), (3, 1), (4, 0), (5, 1), (6, 0), (7, 1)])
    generate_previews()


if __name__ == "__main__":
    main()
