#!/usr/bin/env python3
"""Procedural 2D renderer for 'A Loira do Banheiro' (LENDAS DO BRASIL #1).

Reads the 72-beat manifest (storyboard_72.py) and draws every beat as a
flat-2D cartoon shot: backgrounds, props, characters with lip-sync, camera
moves, SFX bubbles, banners, and bold captions.

Usage:
  python render_engine.py sheet <out.png> <out.jpg>   # 72-frame storyboard sheet
  python render_engine.py video <out.mp4>             # full 85s 9:16 animation
"""
import math
import os
import random
import subprocess
import sys
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from storyboard_72 import STORYBOARD_BEATS as BEATS  # noqa: E402

W, H = 720, 1280
SS = 2  # supersampling factor
FPS = 30
FONT_DIR = os.environ.get(
    "LOIRA_FONTS",
    "/home/user/stickman-video-director/skills/directing-stickman-videos/assets/fonts",
)
AUDIO = os.environ.get("LOIRA_AUDIO", "/tmp/loira_v2/master_audio.wav")

BLACK = (18, 14, 16, 255)
WHITE = (255, 255, 255, 255)
YEL = (255, 207, 40, 255)
RED = (216, 34, 44, 255)
SKIN = (246, 204, 168, 255)
LSKIN = (226, 230, 242, 255)
HAIR_DARK = (40, 26, 20, 255)
PAL = {
    "lucas": dict(hair=HAIR_DARK, shirt=RED, pants=(34, 52, 112, 255), skin=SKIN),
    "bia": dict(hair=(28, 18, 16, 255), shirt=YEL, pants=(64, 64, 86, 255), skin=SKIN),
    "maria": dict(hair=(232, 196, 110, 255), shirt=(246, 236, 214, 255), pants=(246, 236, 214, 255), skin=(246, 214, 186, 255)),
    "loira": dict(hair=(12, 10, 14, 255), shirt=(242, 242, 238, 255), pants=(242, 242, 238, 255), skin=LSKIN),
}

_font_cache = {}


def font(size, name="Anton.ttf"):
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), int(size * SS))
    return _font_cache[key]


def sc(v):
    return v * SS


def pts(lst):
    return [(x * SS, y * SS) for x, y in lst]


_CANVAS = [None]


def _comp_inplace(base, ov):
    base.paste(Image.alpha_composite(base, ov))


def _tr(fill):
    return fill is not None and len(fill) == 4 and 0 < fill[3] < 255


def _canvas_draw(fn):
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    c = _CANVAS[0]
    c.paste(Image.alpha_composite(c, layer))


def ell(d, cx, cy, rx, ry, fill, outline=BLACK, w=4):
    box = [(sc(cx - rx), sc(cy - ry)), (sc(cx + rx), sc(cy + ry))]
    wd = max(1, int(w * SS)) if outline else 0
    if _tr(fill):
        _canvas_draw(lambda dd: dd.ellipse(box, fill=fill, outline=outline, width=wd))
        return
    d.ellipse(box, fill=fill, outline=outline, width=wd)


def poly(d, p, fill, outline=BLACK, w=4):
    if _tr(fill):
        _canvas_draw(lambda dd: dd.polygon(pts(p), fill=fill))
    else:
        d.polygon(pts(p), fill=fill)
    if outline and w > 0:
        d.line(pts(p + [p[0]]), fill=outline, width=max(1, int(w * SS)), joint="curve")


def rect(d, x0, y0, x1, y1, fill, outline=None, w=3):
    box = [sc(x0), sc(y0), sc(x1), sc(y1)]
    wd = max(1, int(w * SS)) if outline else 0
    if _tr(fill):
        _canvas_draw(lambda dd: dd.rectangle(box, fill=fill, outline=outline, width=wd))
        return
    d.rectangle(box, fill=fill, outline=outline, width=wd)


def line(d, p, fill, w):
    d.line(pts(p), fill=fill, width=max(1, int(w * SS)), joint="curve")


def text(d, x, y, s, size, fill=WHITE, stroke=0, name="Anton.ttf", anchor="mm"):
    d.text((sc(x), sc(y)), s, font=font(size, name), fill=fill,
           stroke_width=int(stroke * SS), stroke_fill=BLACK, anchor=anchor)


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def grad(top, bot, h=H):
    arr = np.zeros((h * SS, 1, 3), dtype=np.float32)
    for i in range(3):
        arr[:, 0, i] = np.linspace(top[i], bot[i], h * SS)
    return Image.fromarray(np.repeat(arr, W * SS, axis=1).astype(np.uint8), "RGB").convert("RGBA")


# ---------------------------------------------------------------- props
def moon(d, x, y, r, t=0):
    ell(d, x, y, r * 1.12, r * 1.12, (255, 240, 190, 60), outline=None)
    ell(d, x, y, r, r, (250, 236, 186, 255), outline=(200, 180, 120, 255), w=3)
    for cx, cy, cr in [(-0.3, -0.2, 0.18), (0.25, 0.1, 0.13), (-0.1, 0.35, 0.1)]:
        ell(d, x + cx * r, y + cy * r, cr * r, cr * r, (220, 205, 160, 255), outline=None)


def house(d, x, y, w, h, wall, roof=(190, 60, 40, 255), win=(250, 230, 130, 255)):
    rect(d, x, y, x + w, y + h, wall, BLACK, 3)
    poly(d, [(x - 10, y), (x + w / 2, y - h * 0.45), (x + w + 10, y)], roof, BLACK, 3)
    rect(d, x + w * 0.15, y + h * 0.25, x + w * 0.4, y + h * 0.55, win, BLACK, 2)
    rect(d, x + w * 0.6, y + h * 0.25, x + w * 0.85, y + h * 0.55, win, BLACK, 2)
    rect(d, x + w * 0.42, y + h * 0.6, x + w * 0.58, y + h, (120, 70, 40, 255), BLACK, 2)


def lamp(d, x, y, h, glow=True):
    rect(d, x - 4, y - h, x + 4, y, (40, 36, 40, 255))
    if glow:
        ell(d, x, y - h, 60, 60, (255, 210, 110, 70), outline=None)
    ell(d, x, y - h, 12, 12, (255, 220, 120, 255), outline=BLACK, w=2)


def clock_face(d, x, y, r, hour=3, minute=0, face=(250, 248, 236, 255)):
    ell(d, x, y, r, r, face, BLACK, 8)
    for k in range(12):
        a = math.radians(k * 30 - 90)
        d.line(pts([(x + math.cos(a) * r * 0.82, y + math.sin(a) * r * 0.82),
                    (x + math.cos(a) * r * 0.95, y + math.sin(a) * r * 0.95)]), fill=BLACK, width=3 * SS)
    ah = math.radians(hour * 30 + minute * 0.5 - 90)
    am = math.radians(minute * 6 - 90)
    line(d, [(x, y), (x + math.cos(ah) * r * 0.5, y + math.sin(ah) * r * 0.5)], BLACK, 8)
    line(d, [(x, y), (x + math.cos(am) * r * 0.78, y + math.sin(am) * r * 0.78)], BLACK, 5)
    ell(d, x, y, 6, 6, RED, None)


def stall_door(d, x, y, w, h, open_amt=0.0):
    door_w = w * (1 - 0.55 * open_amt)
    rect(d, x, y, x + door_w, y + h, (150, 118, 88, 255), BLACK, 4)
    for k in range(1, 4):
        line(d, [(x + 8, y + h * k / 4), (x + door_w - 8, y + h * k / 4)], (110, 84, 60, 255), 4)
    ell(d, x + door_w - 14, y + h * 0.5, 5, 5, (200, 190, 120, 255), BLACK, 2)


def toilet(d, x, y, s=1.0, swirl=0.0):
    poly(d, [(x - 60 * s, y - 60 * s), (x + 60 * s, y - 60 * s), (x + 56 * s, y + 10 * s), (x - 56 * s, y + 10 * s)],
         (245, 245, 245, 255))
    ell(d, x, y + 40 * s, 92 * s, 52 * s, (250, 250, 250, 255), BLACK, 5)
    ell(d, x, y + 40 * s, 70 * s, 36 * s, (90, 170, 230, 255), BLACK, 3)
    if swirl:
        for k in range(3):
            rr = (1 - k * 0.25) * 60 * s
            a0 = swirl * 720 + k * 120
            for j in range(40):
                a = math.radians(a0 + j * 9)
                px = x + math.cos(a) * rr * 0.9
                py = y + 40 * s + math.sin(a) * rr * 0.5
                ell(d, px, py, 3 * s, 3 * s, (230, 250, 255, 255), outline=None)


def sink(d, x, y, s=1.0, faucet_on=0.0):
    rect(d, x - 110 * s, y, x + 110 * s, y + 60 * s, (240, 242, 245, 255), BLACK, 4)
    ell(d, x, y + 10 * s, 80 * s, 26 * s, (210, 220, 228, 255), BLACK, 4)
    rect(d, x - 10 * s, y - 80 * s, x + 10 * s, y - 20 * s, (200, 205, 210, 255), BLACK, 3)
    poly(d, [(x, y - 80 * s), (x + 40 * s, y - 80 * s), (x + 40 * s, y - 60 * s), (x + 10 * s, y - 60 * s)],
         (200, 205, 210, 255), BLACK, 3)
    if faucet_on:
        for k in range(int(9 * faucet_on) + 3):
            yy = y - 20 * s + (k * 16 + (faucet_on * 100) % 16) * s
            line(d, [(x + 6 * s, yy), (x + 6 * s, yy + 10 * s)], (120, 200, 255, 255), 4 * s)


def mirror(d, x0, y0, x1, y1, fog=0.5, crack=True, shade=0.0):
    base = (int(lerp(120, 60, shade)), int(lerp(150, 80, shade)), int(lerp(160, 96, shade)), 255)
    rect(d, x0 - 14, y0 - 14, x1 + 14, y1 + 14, (120, 92, 60, 255), BLACK, 6)
    rect(d, x0, y0, x1, y1, base, BLACK, 3)
    for k in range(6):
        xx = x0 + (x1 - x0) * (k / 6)
        line(d, [(xx, y0), (xx + 60, y1)], (base[0] + 30, base[1] + 30, base[2] + 30, 255), 6)
    rect(d, x0, y0, x1, y1, (230, 240, 245, int(255 * fog * 0.35)), None)
    if crack:
        line(d, [(x0 + (x1 - x0) * 0.6, y0), (x0 + (x1 - x0) * 0.52, y0 + 120), (x0 + (x1 - x0) * 0.66, y0 + 230)], (250, 250, 250, 255), 3)
        line(d, [(x0 + (x1 - x0) * 0.52, y0 + 120), (x0 + (x1 - x0) * 0.3, y0 + 180)], (250, 250, 250, 255), 2)


def chandelier(d, x, y, s=1.0):
    line(d, [(x, 0), (x, y)], BLACK, 4)
    ell(d, x, y, 90 * s, 22 * s, (210, 170, 70, 255), BLACK, 4)
    for k in range(-2, 3):
        ell(d, x + k * 36 * s, y - 30 * s, 9 * s, 14 * s, (255, 230, 150, 255), BLACK, 2)
        ell(d, x + k * 36 * s, y - 52 * s, 4 * s, 4 * s, (255, 250, 220, 255), outline=None)


def portrait(d, x, y, w, h):
    rect(d, x - 12, y - 12, x + w + 12, y + h + 12, (210, 170, 60, 255), BLACK, 5)
    rect(d, x, y, x + w, y + h, (90, 70, 60, 255), BLACK, 3)
    ell(d, x + w / 2, y + h * 0.42, w * 0.22, h * 0.26, (230, 190, 160, 255), BLACK, 3)
    poly(d, [(x + w * 0.2, y + h), (x + w * 0.3, y + h * 0.7), (x + w * 0.7, y + h * 0.7), (x + w * 0.8, y + h)],
         (40, 30, 40, 255), BLACK, 3)


def candle(d, x, y, h=90, flick=0.0):
    rect(d, x - 9, y - h, x + 9, y, (250, 244, 220, 255), BLACK, 2)
    fx_ = x + math.sin(flick * 3.0) * 2
    ell(d, x, y - h - 28, 60, 60, (255, 170, 60, 60), outline=None)
    poly(d, [(fx_ - 9, y - h), (fx_, y - h - 34), (fx_ + 9, y - h)], (255, 210, 90, 255), (240, 120, 30, 255), 2)


def bell_jar(d, x, y, w, h, shade=0.0):
    rect(d, x - w * 0.6, y, x + w * 0.6, y + 40, (120, 90, 60, 255), BLACK, 4)
    ell(d, x, y - h * 0.3, w / 2, h * 0.55, (150, 200, 230, 110), (90, 150, 190, 255), 6)
    ell(d, x - w * 0.22, y - h * 0.5, w * 0.1, h * 0.12, (255, 255, 255, 120), outline=None)


def ship(d, x, y, s=1.0):
    poly(d, [(x - 170 * s, y), (x + 170 * s, y), (x + 120 * s, y + 50 * s), (x - 120 * s, y + 50 * s)],
         (35, 30, 40, 255), BLACK, 3)
    rect(d, x - 60 * s, y - 60 * s, x + 80 * s, y, (240, 230, 210, 255), BLACK, 3)
    rect(d, x - 20 * s, y - 110 * s, x - 8 * s, y - 60 * s, (60, 50, 50, 255))
    rect(d, x + 30 * s, y - 100 * s, x + 42 * s, y - 60 * s, (60, 50, 50, 255))
    for k in range(4):
        rect(d, x - 40 * s + k * 35 * s, y - 35 * s, x - 22 * s + k * 35 * s, y - 15 * s, (80, 150, 210, 255), None)


def eiffel(d, x, y, s=1.0):
    col = (60, 50, 70, 255)
    poly(d, [(x - 60 * s, y), (x - 10 * s, y - 260 * s), (x + 10 * s, y - 260 * s), (x + 60 * s, y)], col, None, 0)
    rect(d, x - 25 * s, y - 150 * s, x + 25 * s, y - 130 * s, col, None)
    line(d, [(x - 80 * s, y - 60 * s), (x, y - 180 * s), (x + 80 * s, y - 60 * s)], col, 6 * s)


def lightning(d, x, y, seed=0):
    rnd = random.Random(seed)
    p = [(x, y)]
    for _ in range(9):
        p.append((p[-1][0] + rnd.uniform(-40, 40), p[-1][1] + rnd.uniform(60, 110)))
    line(d, p, (255, 255, 240, 255), 10)
    line(d, p, (160, 200, 255, 255), 4)


def fire_block(d, x, y, w, h, t):
    rect(d, x, y, x + w, y + h, (90, 40, 40, 255), BLACK, 4)
    if w >= 150:
        for k in range(6):
            xx = x + k * w / 6
            rect(d, xx + 10, y + 30, xx + w / 6 - 14, y + 80, (255, 180, 80, 255), BLACK, 2)
    for k in range(9):
        fx_ = x + (k + 0.5) * w / 9
        hgt = 90 + 60 * math.sin(t * 9 + k)
        poly(d, [(fx_ - 26, y), (fx_ + 2 + math.sin(t * 7 + k) * 8, y - hgt), (fx_ + 26, y)],
             (255, 140, 40, 255), (200, 40, 20, 255), 2)


def smoke(d, x, y, r, a=110):
    ell(d, x, y, r, r * 0.8, (60, 50, 60, a), outline=None)


def note_paper(d, x, y, rot_deg=0.0, lines=None, w=260, h=340, color=(250, 246, 228, 255)):
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    rect(ld, x, y, x + w, y + h, color, BLACK, 4)
    for k in range(10):
        line(ld, [(x + 18, y + 40 + k * 28), (x + w - 18, y + 40 + k * 28)], (150, 180, 210, 255), 2)
    if lines:
        for k, s_ in enumerate(lines):
            text(ld, x + 20, y + 40 + k * 56, s_, 34, (30, 30, 50, 255), 0, "ArchivoBlack.ttf", "lm")
    return layer.rotate(rot_deg, center=(sc(x + w / 2), sc(y + h / 2)), resample=Image.BICUBIC)


def starburst(d, cx, cy, r, color, label, label_size=60, rot=0.0):
    pp = []
    for k in range(24):
        a = math.radians(k * 15 + rot)
        rr = r if k % 2 == 0 else r * 0.72
        pp.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    poly(d, pp, color, BLACK, 5)
    text(d, cx, cy, label, label_size, BLACK, 0, "Anton.ttf", "mm")


def speech_bubble(d, cx, cy, label, label_size=44, fill=(255, 255, 255, 255)):
    w = max(120, len(label) * label_size * 0.62 + 40)
    rect(d, cx - w / 2, cy - 36, cx + w / 2, cy + 36, fill, BLACK, 5)
    text(d, cx, cy, label, label_size, BLACK, 0, "Anton.ttf", "mm")


# ---------------------------------------------------------------- characters
def draw_char(layer, c, t):
    """Draw a flat-2D character on an RGBA layer. Coordinates are logical."""
    d = ImageDraw.Draw(layer)
    kind = c["kind"]
    pal = PAL[kind]
    s = c.get("s", 1.0)
    r = 58 * s
    fl = -1 if c.get("flip") else 1
    x0, y0 = c["x"], c["y"]
    expr = c.get("expr", "neutral")
    mouth = c.get("mouth", 0.0)
    blink = c.get("blink", 0.0)
    gaze = c.get("gaze", (0.0, 0.0))
    ow = max(2.0, 0.07 * r)

    def P(dx, dy):
        return (x0 + fl * dx * r, y0 + dy * r)

    def E(dx, dy, rx, ry, fill, outline=BLACK, w=None):
        cx, cy = P(dx, dy)
        ell(d, cx, cy, rx * r, ry * r, fill, outline, ow if w is None else w)

    def L(p, col, wd):
        line(d, [P(*q) for q in p], col, wd * r)

    # --- back hair / long hair (Loira)
    if kind == "loira":
        poly(d, [P(-1.0, -0.6), P(-1.25, 0.6), P(-1.15, 2.2), P(-1.4, 3.2), P(-0.6, 3.4), P(-0.2, 2.6),
                 P(0.3, 3.5), P(0.9, 2.4), P(1.25, 1.2), P(1.0, -0.6), P(0.0, -1.5)], pal["hair"], BLACK, ow)
    elif kind == "maria":
        E(0, -0.2, 1.15, 1.2, pal["hair"], BLACK, ow)
        E(0, -1.3, 0.38, 0.38, pal["hair"], BLACK, ow)
    elif kind == "bia":
        poly(d, [P(-1.1, -0.9), P(-1.2, 0.6), P(-0.9, 1.2), P(0.9, 1.2), P(1.2, 0.6), P(1.1, -0.9),
                 P(0, -1.5)], pal["hair"], BLACK, ow)
    else:  # lucas
        E(0, -0.2, 1.05, 1.0, pal["hair"], BLACK, ow)

    # --- legs / gown
    if kind == "loira":
        poly(d, [P(-0.9, 2.8), P(0.9, 2.8), P(1.2, 4.6), P(0.6, 4.2), P(0.3, 5.0), P(-0.1, 4.4), P(-0.5, 5.0),
                 P(-0.8, 4.3), P(-1.1, 4.7)], pal["shirt"], BLACK, ow)
        d.polygon(pts([P(-0.6, 3.6), P(-0.2, 4.2), P(0.5, 3.8)]), fill=(90, 80, 90, 255))
    elif kind == "maria":
        poly(d, [P(-0.85, 1.15), P(0.85, 1.15), P(1.55, 5.3), P(-1.55, 5.3)], pal["shirt"], BLACK, ow)
        for k in range(-4, 5):
            E(k * 0.33, 5.2, 0.16, 0.12, (255, 255, 255, 255), BLACK, 2)
        L([(-0.75, 1.9), (0.75, 1.9)], (200, 180, 150, 255), 0.05)
    else:
        if c.get("kick"):
            L([(0.35, 3.1), (1.9, 3.5)], BLACK, 0.5)
            L([(0.4, 3.1), (1.8, 3.5)], pal["pants"], 0.36)
            E(1.95, 3.55, 0.3, 0.18, BLACK, None)
        else:
            L([(-0.4, 3.1), (-0.45, 5.1)], BLACK, 0.5)
            L([(-0.4, 3.1), (-0.45, 5.1)], pal["pants"], 0.36)
            E(-0.55, 5.2, 0.34, 0.16, BLACK, None)
        L([(0.4, 3.1), (0.45, 5.1)], BLACK, 0.5)
        L([(0.4, 3.1), (0.45, 5.1)], pal["pants"], 0.36)
        E(0.55, 5.2, 0.34, 0.16, BLACK, None)
        poly(d, [P(-0.85, 1.15), P(0.85, 1.15), P(0.8, 3.2), P(-0.8, 3.2)], pal["shirt"], BLACK, ow)
        if kind == "bia":
            L([(-0.6, 1.4), (0.6, 1.4)], (255, 255, 255, 255), 0.05)

    # --- arms (back arm drawn under torso edge)
    hands = c.get("hands") or [(-1.45, 3.0), (1.45, 3.0)]
    for (hx, hy), sx in zip(hands, (-0.92, 0.92)):
        sh = (sx, 1.4)
        mid = (sh[0] + (hx - sh[0]) * 0.5, sh[1] + (hy - sh[1]) * 0.5)
        # elbow bend
        L([sh, mid], BLACK, 0.5)
        L([sh, mid], pal["shirt"] if kind != "loira" else pal["shirt"], 0.38)
        L([mid, (hx, hy)], BLACK, 0.42)
        L([mid, (hx, hy)], pal["skin"], 0.3)
        E(hx, hy, 0.2, 0.2, pal["skin"], BLACK, ow * 0.8)

    # --- neck & head
    E(0, 1.05, 0.24, 0.3, pal["skin"], None)
    E(-0.97, 0.05, 0.2, 0.22, pal["skin"], BLACK, ow * 0.8)
    E(0.97, 0.05, 0.2, 0.22, pal["skin"], BLACK, ow * 0.8)
    E(0, 0, 0.95, 1.0, pal["skin"], BLACK, ow)

    # --- face: eyes
    eye_x = 0.38
    eyes_open = blink < 0.5
    for sx in (-1, 1):
        ex, ey = eye_x * sx, -0.1
        if kind == "loira":
            E(ex, ey, 0.28, 0.24, (24, 22, 34, 255), None)
            if expr in ("scream", "gaping"):
                E(ex, ey, 0.22, 0.22, (14, 12, 20, 255), None)
            ecx, ecy = P(ex + gaze[0] * 0.08, ey + gaze[1] * 0.08)
            ell(d, ecx, ecy, 0.09 * r, 0.09 * r, (170, 240, 255, 255), None)
        elif eyes_open:
            E(ex, ey, 0.27, 0.32, WHITE, BLACK, ow * 0.7)
            px, py = P(ex + gaze[0] * 0.09, ey + 0.02 + gaze[1] * 0.09)
            pr = (0.1 if expr in ("scared", "shock") else 0.14) * r
            ell(d, px, py, pr, pr, BLACK, None)
            ell(d, px - pr * 0.3, py - pr * 0.3, pr * 0.3, pr * 0.3, WHITE, None)
        else:
            L([(ex - 0.2, ey), (ex + 0.2, ey + 0.02)], BLACK, 0.07)
        if kind == "bia":
            E(ex, ey, 0.36, 0.38, None, BLACK, ow * 0.9)
    if kind == "bia":
        L([(-0.73, -0.1), (-0.04, -0.1)], BLACK, 0.05)
        L([(0.04, -0.1), (0.73, -0.1)], BLACK, 0.05)
    if kind == "loira":
        for sx in (-1, 1):
            L([(sx * 0.1, 0.15), (sx * 0.14, 0.3)], (120, 40, 40, 255), 0.07)
            E(sx * 0.12, 0.28, 0.12, 0.12, WHITE, None)  # cotton tuft
        for sx in (-1, 1):
            L([(sx * 0.5, 0.05), (sx * 0.56, 0.35)], (60, 60, 80, 255), 0.05)

    # --- brows
    bt = {
        "neutral": ((-0.6, -0.5), (-0.2, -0.5)),
        "worried": ((-0.6, -0.36), (-0.2, -0.62)),
        "angry": ((-0.6, -0.72), (-0.2, -0.44)),
        "shock": ((-0.6, -0.76), (-0.2, -0.76)),
        "smirk": ((-0.6, -0.5), (-0.2, -0.56)),
        "scared": ((-0.6, -0.7), (-0.2, -0.7)),
        "scream": ((-0.6, -0.76), (-0.2, -0.76)),
        "gaping": ((-0.6, -0.6), (-0.2, -0.66)),
        "happy": ((-0.6, -0.52), (-0.2, -0.6)),
        "proud": ((-0.6, -0.58), (-0.2, -0.5)),
        "skeptic": ((-0.6, -0.42), (-0.2, -0.56)),
    }.get(expr, ((-0.6, -0.5), (-0.2, -0.5)))
    if kind != "loira":
        L([(bt[0][0], bt[0][1]), (bt[1][0], bt[1][1])], BLACK, 0.08)
        L([(-bt[0][0], bt[0][1]), (-bt[1][0], bt[1][1])], BLACK, 0.08)
    else:
        L([(bt[0][0], bt[0][1] - 0.1), (bt[1][0], bt[1][1])], (30, 30, 40, 255), 0.07)
        L([(-bt[0][0], bt[0][1] - 0.1), (-bt[1][0], bt[1][1])], (30, 30, 40, 255), 0.07)

    # --- mouth
    my = 0.52
    if expr == "scream" or expr == "gaping":
        mouth = max(mouth, 0.8)
    if mouth < 0.07:
        if expr == "smirk" or expr == "skeptic":
            L([(-0.12, my + 0.04), (0.14, my - 0.03), (0.28, my - 0.08)], BLACK, 0.07)
        elif expr == "happy" or expr == "proud":
            L([(-0.22, my - 0.04), (0.0, my + 0.07), (0.22, my - 0.04)], BLACK, 0.07)
        else:
            L([(-0.2, my), (0.2, my)], BLACK, 0.07)
    else:
        rx = 0.2 + 0.1 * mouth if expr != "scream" else 0.22
        ry = 0.05 + 0.3 * mouth
        E(0, my + 0.02, rx, ry, (70, 12, 24, 255), BLACK, ow * 0.7)
        E(0, my + 0.06 + ry * 0.3, rx * 0.5, ry * 0.4, (230, 90, 100, 255), None)

    # --- front hair
    if kind == "lucas":
        poly(d, [P(-0.98, -0.2), P(-0.92, -0.9), P(-0.2, -1.05), P(0.5, -0.92), P(0.98, -0.45),
                 P(0.82, -0.62), P(0.22, -0.62), P(-0.28, -0.46), P(-0.72, -0.1)], pal["hair"], BLACK, ow * 0.8)
    elif kind == "bia":
        poly(d, [P(-1.0, -0.4), P(-0.85, -0.9), P(0.0, -1.02), P(0.85, -0.9), P(1.0, -0.4), P(0.7, -0.62),
                 P(0.0, -0.58), P(-0.7, -0.62)], pal["hair"], BLACK, ow * 0.8)
        for sx in (-1, 1):
            cx_, cy_ = P(sx * 0.38, -0.1)
            ell(d, cx_, cy_, 0.36 * r, 0.38 * r, None, BLACK, ow * 0.9)
    elif kind == "maria":
        poly(d, [P(-0.98, -0.3), P(-0.75, -0.9), P(-0.1, -1.0), P(0.6, -0.92), P(0.98, -0.5), P(0.7, -0.6),
                 P(0.2, -0.7), P(-0.5, -0.66), P(-0.9, -0.2)], pal["hair"], BLACK, ow * 0.8)
        E(-0.98, 0.3, 0.12, 0.12, (255, 255, 255, 255), BLACK, ow * 0.6)
        E(0.98, 0.3, 0.12, 0.12, (255, 255, 255, 255), BLACK, ow * 0.6)
    elif kind == "loira":
        poly(d, [P(-0.98, -0.2), P(-0.9, -0.95), P(0.0, -1.1), P(0.9, -0.95), P(0.98, -0.2), P(0.5, -0.45),
                 P(0.0, -0.6), P(-0.5, -0.45)], pal["hair"], BLACK, ow * 0.6)
        L([(-0.45, -0.1), (-0.28, 0.2)], (60, 40, 60, 255), 0.06)


# ---------------------------------------------------------------- beat plans
def C(kind, x, y, s=1.0, expr="neutral", hands=None, talk=False, gaze=(0.0, 0.0),
      alpha=1.0, flip=False, blink=None, kick=False):
    return dict(kind=kind, x=x, y=y, s=s, expr=expr, hands=hands, talk=talk, gaze=gaze,
                alpha=alpha, flip=flip, blink=blink, kick=kick)


def bg_draw(d, key, lt, seed):
    if key == "bath_dark":
        d.rectangle([0, 0, W * SS, H * SS], fill=(26, 30, 38, 255))
        for k in range(0, 720, 60):
            line(d, [(k, 0), (k, 960)], (44, 50, 60, 255), 2)
        for k in range(0, 960, 60):
            line(d, [(0, k), (720, k)], (44, 50, 60, 255), 2)
        rect(d, 0, 960, 720, 1280, (58, 62, 70, 255))
        flick = 0.6 + 0.4 * (1 if (int(lt * 12) % 7) else 0.2)
        ell(d, 360, 40, 340, 60, (230, 240, 255, int(60 * flick)), None)
        rect(d, 300, 20, 420, 36, (250, 250, 240, 255), BLACK, 2)
    elif key == "bath_blue":
        d.rectangle([0, 0, W * SS, H * SS], fill=(120, 170, 200, 255))
        for k in range(0, 720, 80):
            line(d, [(k, 0), (k, 960)], (150, 200, 225, 255), 3)
        rect(d, 0, 960, 720, 1280, (110, 150, 170, 255))
    elif key == "bath_day":
        d.rectangle([0, 0, W * SS, H * SS], fill=(204, 236, 240, 255))
        for k in range(0, 720, 80):
            line(d, [(k, 0), (k, 960)], (170, 214, 226, 255), 3)
        for k in range(0, 960, 80):
            line(d, [(0, k), (720, k)], (170, 214, 226, 255), 3)
        rect(d, 0, 960, 720, 1280, (200, 180, 150, 255))
        rect(d, 0, 0, 720, 60, (255, 255, 240, 255), None)
    elif key == "stalls":
        d.rectangle([0, 0, W * SS, H * SS], fill=(118, 140, 128, 255))
        rect(d, 0, 900, 720, 1280, (84, 98, 90, 255))
        for k in range(0, 720, 120):
            rect(d, k + 40, 280, k + 46, 1000, (210, 220, 210, 255), BLACK, 2)
        for k, x in enumerate((70, 260, 450)):
            rect(d, x - 16, 160, x + 220, 200, (210, 214, 206, 255), BLACK, 2)
    elif key == "school":
        d.rectangle([0, 0, W * SS, H * SS], fill=(120, 200, 240, 255))
        rect(d, 0, 900, 720, 1280, (110, 180, 90, 255))
        rect(d, 40, 320, 680, 930, (250, 210, 84, 255), BLACK, 5)
        for k in range(3):
            rect(d, 80 + k * 200, 380, 230 + k * 200, 520, (110, 170, 220, 255), BLACK, 4)
            rect(d, 80 + k * 200, 560, 230 + k * 200, 680, (110, 170, 220, 255), BLACK, 4)
        rect(d, 300, 760, 420, 930, (200, 60, 50, 255), BLACK, 4)
        line(d, [(640, 960), (640, 500)], BLACK, 5)
        rect(d, 645, 500, 690, 540, (40, 150, 60, 255), BLACK, 2)
    elif key == "hall":
        d.rectangle([0, 0, W * SS, H * SS], fill=(252, 216, 110, 255))
        rect(d, 0, 880, 720, 1280, (206, 170, 120, 255))
        for k in range(4):
            rect(d, 40 + k * 170, 360, 190 + k * 170, 640, (80, 130, 200, 255), BLACK, 4)
        rect(d, 0, 640, 720, 680, (160, 120, 80, 255))
        rect(d, 280, 620, 440, 880, (110, 90, 70, 255), BLACK, 4)
    elif key == "street":
        _CANVAS[0].paste(grad((30, 26, 70), (120, 80, 110)).convert("RGB"), (0, 0))
        d.rectangle([0, 0, W * SS, 0], fill=None)
        moon(d, 360, 220, 120, lt)
        for k, x in enumerate((30, 220, 430)):
            house(d, x, 560 + (k % 2) * 20, 180, 210, [(246, 220, 170, 255), (230, 180, 150, 255), (200, 230, 210, 255)][k])
        rect(d, 0, 900, 720, 1280, (96, 70, 60, 255))
        lamp(d, 110, 800, 230)
        lamp(d, 610, 800, 230)
    elif key == "mansion":
        _CANVAS[0].paste(grad((120, 80, 150), (250, 170, 150)).convert("RGB"), (0, 0))
        rect(d, 0, 900, 720, 1280, (110, 150, 80, 255))
        rect(d, 80, 360, 640, 900, (240, 160, 180, 255), BLACK, 5)
        rect(d, 230, 240, 490, 360, (240, 170, 190, 255), BLACK, 5)
        for k in range(4):
            for j in range(2):
                x = 120 + k * 130
                ell(d, x + 30, 430 + j * 180, 30, 40, (250, 240, 230, 255), BLACK, 3)
        rect(d, 310, 720, 410, 900, (120, 70, 50, 255), BLACK, 4)
        for x in (20, 660):
            line(d, [(x, 900), (x, 560)], (80, 60, 40, 255), 10)
            ell(d, x, 540, 60, 40, (60, 130, 60, 255), BLACK, 3)
    elif key == "parlor":
        d.rectangle([0, 0, W * SS, H * SS], fill=(84, 34, 46, 255))
        rect(d, 0, 900, 720, 1280, (110, 60, 36, 255))
        rect(d, 0, 0, 720, 900, (96, 40, 50, 255))
        for k in range(0, 720, 90):
            line(d, [(k, 0), (k, 900)], (110, 56, 66, 255), 3)
    elif key == "parlor_dark":
        d.rectangle([0, 0, W * SS, H * SS], fill=(18, 12, 20, 255))
        rect(d, 0, 900, 720, 1280, (40, 24, 20, 255))
    elif key == "ocean":
        _CANVAS[0].paste(grad((18, 22, 50), (40, 70, 110)).convert("RGB"), (0, 0))
        rect(d, 0, 780, 720, 1280, (26, 60, 110, 255))
        for k in range(8):
            y = 800 + k * 60
            line(d, [(0, y), (180, y - 12), (360, y), (540, y - 12), (720, y)], (200, 230, 255, 255), 6)
    elif key == "ship":
        _CANVAS[0].paste(grad((16, 20, 46), (60, 80, 130)).convert("RGB"), (0, 0))
        moon(d, 560, 240, 80, lt)
        rect(d, 0, 820, 720, 1280, (22, 46, 92, 255))
        for k in range(6):
            y = 860 + k * 60
            line(d, [(0, y), (180, y - 12), (360, y), (540, y - 12), (720, y)], (120, 170, 220, 255), 4)
    elif key == "shrine":
        d.rectangle([0, 0, W * SS, H * SS], fill=(16, 10, 18, 255))
        ell(d, 360, 640, 420, 420, (120, 70, 30, 60), None)
        rect(d, 0, 920, 720, 1280, (40, 28, 26, 255))
    elif key == "fire":
        _CANVAS[0].paste(grad((230, 90, 30), (40, 14, 20)).convert("RGB"), (0, 0))
        rect(d, 0, 900, 720, 1280, (50, 30, 30, 255))
    elif key == "fire_inside":
        d.rectangle([0, 0, W * SS, H * SS], fill=(90, 36, 26, 255))
        for k in range(10):
            fire_block(d, -20 + k * 80, 20 + (k % 3) * 40, 70, 300, lt + k * 0.2)
    elif key == "dusk":
        _CANVAS[0].paste(grad((250, 170, 90), (130, 190, 240)).convert("RGB"), (0, 0))
        rect(d, 0, 900, 720, 1280, (100, 160, 80, 255))
    elif key == "sunrise":
        _CANVAS[0].paste(grad((255, 200, 130), (120, 190, 240)).convert("RGB"), (0, 0))
        ell(d, 360, 880 - min(lt, 1) * 300, 120, 120, (255, 226, 120, 255), BLACK, 4)
        rect(d, 0, 900, 720, 1280, (110, 150, 80, 255))
    elif key == "map":
        d.rectangle([0, 0, W * SS, H * SS], fill=(186, 220, 240, 255))
        poly(d, [(120, 380), (620, 330), (640, 620), (560, 840), (400, 980), (180, 880), (110, 640)],
             (240, 232, 190, 255), BLACK, 5)
        text(d, 360, 280, "SÃO PAULO", 46, BLACK, 0)
    elif key == "fog":
        _CANVAS[0].paste(grad((20, 14, 36), (70, 52, 90)).convert("RGB"), (0, 0))
    elif key == "clock":
        _CANVAS[0].paste(grad((40, 36, 56), (110, 80, 60)).convert("RGB"), (0, 0))
    elif key == "paper":
        d.rectangle([0, 0, W * SS, H * SS], fill=(236, 230, 210, 255))
    elif key == "dark_mirror":
        d.rectangle([0, 0, W * SS, H * SS], fill=(20, 22, 28, 255))
    elif key == "shadow":
        d.rectangle([0, 0, W * SS, H * SS], fill=(40, 32, 44, 255))
    else:
        d.rectangle([0, 0, W * SS, H * SS], fill=(40, 40, 50, 255))


def plan_for(b):
    """Return the visual plan (bg, props, cast, fx, sfx, focus) for a beat."""
    i = b["id"]
    P_ = dict(bg="bath_dark", props=[], cast=[], fx=[], sfx=[], focus=(360, 640))

    # -- hook: mirror & Lucas
    if i == 1:
        P_.update(bg="dark_mirror", props=[("mirror", (150, 150, 640, 860), 0.7, True, 0.3)],
                  cast=[C("loira", 360, 560, 1.4, "neutral", alpha=0.35, gaze=(0, 0))],
                  fx=["flicker"], focus=(360, 600))
    elif i == 2:
        P_.update(bg="bath_dark", props=[("mirror", (120, 120, 600, 880), 0.7, True, 0.2)],
                  cast=[C("lucas", 330, 560, 2.2, "worried", talk=True, hands=[(-1.7, 3.0), (1.7, 3.0)], gaze=(-1, 0))],
                  focus=(330, 520))
    elif i == 3:
        P_.update(bg="stalls", props=[("stall", (70, 620, 180, 620), 0.7), ("stall", (270, 620, 180, 620), 0.0),
                                       ("stall", (470, 620, 180, 620), 0.0)], fx=["dust"])
    elif i == 4:
        P_.update(bg="school", props=[("clock", (360, 360, 110, 3, 0))], fx=["dust"], focus=(360, 400))
    elif i == 5:
        P_.update(bg="school", cast=[C("lucas", 230, 800, 1.1, "neutral", talk=True),
                                    C("bia", 490, 800, 1.1, "happy")], fx=["dust"])
    elif i == 6:
        P_.update(bg="hall", cast=[C("lucas", 240, 640, 1.2, "neutral", talk=True, hands=[(-1.6, 2.6), (-0.4, 2.4)]),
                                  C("bia", 480, 640, 1.2, "smirk", talk=True, hands=[(1.6, 2.6), (0.6, 2.2)])])
    elif i == 7:
        P_.update(bg="hall", props=[("note", (210, 330, -6, ["SEGREDO", "DO BANHEIRO", "4 REGRAS"]))],
                  cast=[C("bia", 500, 620, 1.4, "smirk", talk=True, hands=[(-1.2, 0.2), (1.8, 2.8)]),
                        C("lucas", 180, 680, 1.0, "worried", hands=[(-1.5, 3.0), (1.4, 3.0)])], focus=(380, 560))
    elif i == 8:
        P_.update(bg="hall", cast=[C("bia", 400, 560, 2.5, "smirk", talk=True, hands=[(-1.0, 0.3), (0.5, 0.2)], gaze=(-1, 0))],
                  fx=["vignette"], focus=(400, 520))
    elif i == 9:
        P_.update(bg="hall", cast=[C("lucas", 360, 560, 2.7, "shock", talk=False, gaze=(0, -1))],
                  fx=["sweat", "flash"], focus=(360, 520))
    elif i == 10:
        P_.update(bg="hall", cast=[C("lucas", 230, 720, 1.0, "shock", hands=[(-1.8, 1.4), (-1.2, 2.6)]),
                                  C("bia", 490, 720, 1.0, "shock", hands=[(1.8, 1.4), (1.2, 2.6)])],
                  fx=["dust", "speed"])
    elif i == 11:
        P_.update(bg="hall", props=[("stall", (500, 560, 150, 360), 0.8), ("note", (300, 880, 8, ["BILHETE"]))],
                  fx=["dust"])
    elif i == 12:
        P_.update(bg="bath_dark", props=[("stall", (500, 560, 150, 360), 0.8)],
                  cast=[C("loira", 340, 600, 1.7, "scream", talk=True, gaze=(0, 0))],
                  fx=["flash", "glow"], focus=(340, 580))
    elif i == 13:
        P_.update(bg="paper", props=[("checklist", ["1. CHUTE A PORTA", "2. DÊ A DESCARGA", "3. ABRA A TORNEIRA", "4. XINGUE O ESPELHO"])],
                  fx=["paper_tilt"], focus=(360, 640))
    elif i == 14:
        P_.update(bg="stalls", props=[("stall", (70, 620, 180, 620), 0.0), ("stall", (270, 620, 180, 620), 0.0),
                                       ("stall", (470, 620, 180, 620), 0.0)],
                  cast=[C("lucas", 200, 720, 1.2, "worried", talk=True, hands=[(-1.4, 3.0), (1.4, 3.0)])], fx=["dust"])
    elif i == 15:
        P_.update(bg="stalls", props=[("stall", (240, 500, 240, 620), 0.0)],
                  cast=[C("lucas", 360, 760, 1.5, "worried", talk=True, hands=[(-1.6, 3.0), (1.6, 3.0)])])
    elif i in (16, 17, 18):
        P_.update(bg="stalls", props=[("stall", (240, 500, 240, 620), 0.0)],
                  cast=[C("lucas", 360, 760, 1.5, "angry", kick=True, hands=[(-1.7, 1.2), (1.6, 2.3)])],
                  fx=["impact%d" % (i - 15), "shake"], sfx=[("TUM!", 200, 430, YEL, -10), ("TUM!", 530, 500, WHITE, 8)] if i == 16 else
                  ([("TUM! TUM!", 300, 450, YEL, -6)] if i == 17 else [("1 · 2 · 3!", 360, 430, RED, 0)]))
    elif i == 19:
        P_.update(bg="bath_dark", props=[("toilet", (360, 760, 1.6, 0.0)), ("cord", (520, 540))],
                  cast=[], fx=["hand_pull"], focus=(380, 640))
    elif i == 20:
        P_.update(bg="bath_dark", props=[("toilet", (360, 780, 2.0, 1.0))], fx=["swirl", "flash"], focus=(360, 740),
                  sfx=[("SHHH!", 360, 440, WHITE, -4)])
    elif i == 21:
        P_.update(bg="bath_day", props=[("sink", (360, 760, 2.4, 1.0))], fx=["water"], focus=(360, 560))
    elif i == 22:
        P_.update(bg="bath_dark", props=[("mirror", (140, 180, 580, 840), 0.4, False, 0.0)],
                  cast=[C("lucas", 360, 620, 1.7, "angry", talk=True, hands=[(-1.7, 1.6), (1.8, 1.6)])],
                  sfx=[("#@!&!", 180, 420, RED, -8), ("#@!&*!", 520, 470, YEL, 6), ("#@!&!", 330, 300, WHITE, -2)],
                  fx=["shake"], focus=(360, 600))
    elif i == 23:
        P_.update(bg="dark_mirror", cast=[C("lucas", 360, 760, 3.6, "scared", gaze=(0, 0), blink=0.0)],
                  fx=["stare"], focus=(360, 500))
    elif i == 24:
        P_.update(bg="dark_mirror", props=[("mirror", (120, 150, 600, 860), 0.15, False, 0.6)],
                  cast=[C("loira", 540, 560, 1.1, "neutral", alpha=0.95, gaze=(-1, 0)),
                        C("lucas", 280, 690, 1.4, "shock")], fx=["darken"], focus=(360, 620))
    elif i == 25:
        P_.update(bg="fog", cast=[C("loira", 360, 620, 1.6, "neutral", alpha=0.65, gaze=(0, 0))],
                  fx=["questions", "spin"], focus=(360, 600))
    elif i == 26:
        P_.update(bg="clock", props=[("clock_big", (360, 580, 220, 1890))], fx=["rewind"], focus=(360, 580))
    elif i == 27:
        P_.update(bg="street", fx=["lantern_glow", "fog"], focus=(360, 640))
    elif i == 28:
        P_.update(bg="mansion", fx=["lantern_glow"], focus=(360, 600))
    elif i == 29:
        P_.update(bg="map", props=[("pin", (360, 420))], fx=["stamp"], focus=(360, 420))
    elif i == 30:
        P_.update(bg="mansion", props=[], fx=["lantern_swing"], focus=(360, 500))
    elif i == 31:
        P_.update(bg="parlor", props=[("portrait", (250, 240, 220, 300)), ("chandelier", (360, 100))], focus=(360, 500))
    elif i == 32:
        P_.update(bg="parlor", props=[("calendar", (260, 230, "1890")), ("candelabra", (520, 800))], fx=["flicker"],
                  focus=(360, 500))
    elif i == 33:
        P_.update(bg="parlor", props=[("doors", (250, 380, 460, 900))],
                  cast=[C("maria", 360, 640, 1.1, "proud", talk=True, alpha=1.0)], fx=["flash"], focus=(360, 560))
    elif i == 34:
        P_.update(bg="parlor", props=[("chandelier", (360, 100))],
                  cast=[C("maria", 360, 600, 1.7, "proud", talk=True, hands=[(-1.2, 2.4), (1.2, 2.4)])], focus=(360, 560))
    elif i == 35:
        P_.update(bg="parlor", cast=[C("maria", 360, 560, 2.4, "proud", talk=True, hands=[(-2.2, 1.8), (2.2, 1.8)])],
                  fx=["earring_glint"], focus=(360, 480))
    elif i == 36:
        P_.update(bg="parlor", props=[("chest", (520, 820)), ("portrait", (420, 180, 180, 220))],
                  cast=[C("maria", 260, 640, 1.2, "proud", talk=True, hands=[(-1.7, 2.6), (1.0, 2.2)])], fx=["coins"],
                  focus=(320, 600))
    elif i == 37:
        P_.update(bg="parlor", props=[("suitcase", (560, 820))],
                  cast=[C("maria", 360, 680, 1.1, "worried", kick=False, hands=[(-1.0, 1.6), (-0.6, 3.0)], flip=True)],
                  fx=["speed"], focus=(360, 640))
    elif i == 38:
        P_.update(bg="shadow", props=[("ring", (360, 760)), ("table", (360, 780))],
                  cast=[C("loira", 580, 520, 1.6, "neutral", alpha=0.3, gaze=(0, 0))], focus=(360, 700))
    elif i == 39:
        P_.update(bg="parlor", cast=[C("maria", 360, 560, 2.3, "angry", talk=True, hands=[(-1.6, 1.4), (1.6, 1.4)])],
                  sfx=[("NÃO!", 580, 400, RED, 8)], fx=["shake"], focus=(360, 500))
    elif i == 40:
        P_.update(bg="dusk", props=[("eiffel", (560, 880, 1.0)), ("ticket", (200, 760))], fx=["sea_glint"], focus=(360, 640))
    elif i == 41:
        P_.update(bg="ocean", props=[("lightning", (360, 0, 3))], fx=["flash_lightning"], focus=(360, 500))
    elif i == 42:
        P_.update(bg="ocean", props=[("porthole", (360, 560, 220))], fx=["flicker", "shake_soft"], focus=(360, 560))
    elif i == 43:
        P_.update(bg="ship", props=[("ship", (360, 760, 1.0))], fx=["sea_glint"], focus=(360, 640))
    elif i == 44:
        P_.update(bg="shrine", props=[("candles", None), ("altar", (360, 880))], fx=["flicker", "glow"], focus=(360, 620))
    elif i == 45:
        P_.update(bg="shrine", props=[("bell_jar", (360, 860, 380, 540))], fx=["glow", "flicker"], focus=(360, 600))
    elif i == 46:
        P_.update(bg="parlor_dark", props=[("bell_jar", (360, 900, 280, 400))], fx=["flicker"], focus=(360, 600))
    elif i == 47:
        P_.update(bg="sunrise", props=[("house_big", (360, 640))], fx=["sun_rise"], focus=(360, 640))
    elif i == 48:
        P_.update(bg="mansion", props=[("gate", (260, 880)), ("desks", None)], fx=[], focus=(360, 640))
    elif i == 49:
        P_.update(bg="school", props=[("sign", (360, 300, "ESCOLA ESTADUAL"))], focus=(360, 380))
    elif i == 50:
        P_.update(bg="hall", props=[("desks", None), ("board", (360, 330))], cast=[C("lucas", 210, 780, 0.7, "neutral"), C("bia", 500, 780, 0.7, "neutral")], focus=(360, 600))
    elif i in (51, 53):
        P_.update(bg="fire", props=[("fire_block", (60, 430, 600, 420))], fx=["fire", "shake_soft"], focus=(360, 640))
    elif i == 52:
        P_.update(bg="fire_inside", fx=["smoke", "sparks", "shake"], focus=(360, 640))
    elif i == 54:
        P_.update(bg="fire", props=[("fire_block", (60, 430, 600, 420))], fx=["fire", "stamp_year"], focus=(360, 360))
    elif i == 55:
        P_.update(bg="smoke", cast=[C("loira", 360, 700, 2.0, "neutral", alpha=1.0, gaze=(0, 0))],
                  fx=["fire", "rise"], focus=(360, 620))
    elif i == 56:
        P_.update(bg="bath_blue", props=[("sink", (460, 760, 1.2, 0.0))],
                  cast=[C("bia", 240, 680, 1.1, "worried", talk=False, hands=[(-1.5, 3.0), (1.4, 3.0)])], focus=(300, 600))
    elif i == 57:
        P_.update(bg="bath_blue", cast=[C("bia", 360, 580, 2.3, "scared", talk=True, hands=[(-0.4, 0.9), (1.0, 0.7)])],
                  fx=["shake_soft"], focus=(360, 520))
    elif i == 58:
        P_.update(bg="bath_blue", props=[("sink", (460, 760, 1.2, 1.0))],
                  cast=[C("loira", 500, 640, 1.5, "neutral", talk=True, hands=[(-2.0, 1.4), (-1.5, 2.8)])],
                  fx=["drip"], focus=(440, 600))
    elif i == 59:
        P_.update(bg="bath_blue", props=[("sink", (500, 760, 1.2, 0.0))],
                  cast=[C("loira", 510, 660, 1.2, "neutral", talk=True, hands=[(-1.2, 2.0), (-1.2, 3.0)]),
                        C("bia", 200, 680, 1.0, "scared", flip=False, hands=[(-1.6, 1.0), (1.2, 1.4)])], focus=(360, 640))
    elif i == 60:
        P_.update(bg="bath_blue", cast=[C("loira", 360, 560, 2.9, "gaping", talk=True, gaze=(0, 0))],
                  fx=["flash", "cotton"], focus=(360, 500))
    elif i == 61:
        P_.update(bg="bath_dark", cast=[C("loira", 360, 620, 1.9, "scream", talk=True, gaze=(0, 0))],
                  fx=["glow", "flash"], focus=(360, 560))
    elif i == 62:
        P_.update(bg="bath_day", props=[("sink", (360, 760, 1.6, 0.0))],
                  cast=[C("lucas", 360, 760, 1.4, "neutral", talk=True, hands=[(-1.5, 3.0), (1.5, 3.0)])], fx=["lights_on"],
                  focus=(360, 640))
    elif i == 63:
        P_.update(bg="bath_day", cast=[C("lucas", 360, 680, 1.6, "skeptic", talk=True,
                                         hands=[(-1.9, 2.0), (1.9, 2.0)])], focus=(360, 560))
    elif i == 64:
        P_.update(bg="bath_day", cast=[C("loira", 540, 620, 1.1, "neutral", alpha=0.22),
                                      C("lucas", 300, 700, 1.4, "smirk", talk=True, hands=[(-1.6, 2.6), (1.4, 3.0)])],
                  fx=["questions"], focus=(360, 600))
    elif i == 65:
        P_.update(bg="bath_day", cast=[C("lucas", 360, 560, 2.5, "smirk", talk=True, hands=[(-1.9, 1.4), (1.9, 1.4)])],
                  focus=(360, 480))
    elif i == 66:
        P_.update(bg="bath_day", props=[("sink", (520, 760, 1.2, 0.0))],
                  cast=[C("lucas", 300, 700, 1.4, "neutral", talk=True, hands=[(-1.6, 3.0), (1.5, 3.0)])], fx=["walk"],
                  focus=(360, 640))
    elif i == 67:
        P_.update(bg="bath_day", props=[("sink", (360, 760, 2.4, 1.0))],
                  cast=[C("lucas", 340, 560, 2.2, "shock", hands=[(-1.6, 2.0), (1.0, 1.7)], gaze=(0, 1))],
                  fx=["splash"], focus=(360, 580))
    elif i == 68:
        P_.update(bg="bath_day", props=[("mirror", (150, 150, 570, 840), 0.0, False, 0.0)],
                  cast=[C("lucas", 360, 780, 0.9, "neutral", hands=[(-1.6, 3.0), (1.6, 3.0)])], focus=(360, 700))
    elif i == 69:
        P_.update(bg="bath_day", props=[("mirror", (150, 150, 570, 840), 0.0, False, 0.0)],
                  cast=[C("lucas", 360, 600, 1.8, "neutral", talk=True, hands=[(-1.7, 3.0), (1.7, 3.0)])],
                  fx=["wet"], focus=(360, 560))
    elif i == 70:
        P_.update(bg="bath_day", props=[("mirror", (150, 150, 570, 840), 0.0, False, 0.0)],
                  cast=[C("lucas", 360, 620, 3.2, "neutral", gaze=(1, 0), blink=0.0)], focus=(360, 580))
    elif i == 71:
        P_.update(bg="bath_day", cast=[C("lucas", 360, 620, 2.1, "worried", talk=True, gaze=(1, 0))],
                  fx=["sweat"], sfx=[("SERÁ?!", 560, 400, YEL, 6)], focus=(360, 560))
    elif i == 72:
        P_.update(bg="dark_mirror", props=[("mirror", (120, 120, 600, 880), 0.3, False, 0.0)],
                  cast=[C("lucas", 260, 700, 1.3, "worried", talk=True, hands=[(-1.6, 3.0), (1.6, 3.0)]),
                        C("loira", 510, 600, 1.1, "neutral", alpha=0.0, gaze=(0, 0))],
                  fx=["flash_ghost"], focus=(360, 640))
    return P_


def camera(cam, lt, dur):
    table = {
        "push_in": (1.0, 1.22), "slow_push": (1.0, 1.12), "push_mirror": (1.0, 1.2), "push_ghost": (1.05, 1.3),
        "zoom_in": (1.0, 1.25), "zoom_pin": (1.1, 1.0), "zoom_sign": (1.2, 1.0), "close_up": (1.35, 1.45),
        "medium_hero": (1.1, 1.15), "medium_front": (1.0, 1.08), "medium_pan": (1.0, 1.05),
        "medium_profile": (1.0, 1.1), "medium_two": (1.05, 1.15), "medium_left": (1.0, 1.08),
        "wide_pan": (1.0, 1.0), "wide_establish": (1.1, 1.0), "wide_drift": (1.0, 1.05), "wide_hold": (1.05, 1.05),
        "wide_shake": (1.0, 1.0), "wide_chill": (1.05, 1.0), "pan_right": (1.0, 1.0), "pan_left": (1.0, 1.0),
        "track_right": (1.0, 1.1), "track_fast": (1.0, 1.2), "spin_zoom": (0.9, 1.35), "snap_zoom": (1.0, 1.6),
        "dramatic_zoom": (1.0, 1.5), "reveal_zoom": (1.4, 1.0), "impact_zoom": (1.1, 1.5),
        "extreme_close": (2.0, 2.3), "extreme_eyes": (2.4, 2.6), "extreme_zoom": (2.2, 2.6),
        "close_tense": (1.6, 1.8), "close_hand": (1.5, 1.7), "close_sink": (1.6, 1.9), "close_insert": (1.4, 1.6),
        "close_splash": (1.5, 1.7), "close_shake": (1.5, 1.6), "shake_close": (1.5, 1.7), "shake_wide": (1.0, 1.0),
        "shake_heavy": (1.05, 1.1), "push_door": (1.0, 1.15), "pull_wide": (1.3, 1.0), "pull_back": (1.4, 1.0),
        "pull_out": (1.2, 1.0), "tilt_up": (1.0, 1.1), "top_down": (1.0, 1.05), "zoom_out": (1.4, 1.0),
        "final_punch": (1.0, 1.4), "lights_on": (1.0, 1.0), "wipe_pan": (1.0, 1.0), "wide_postcard": (1.0, 1.05),
        "flash_shake": (1.0, 1.05), "impact_shake_1": (1.1, 1.1), "impact_shake_2": (1.1, 1.1),
        "impact_shake_3": (1.15, 1.15), "zoom_bowl": (1.2, 1.4), "close_sink_": (1.6, 1.9),
        "lights_": (1.0, 1.0), "medium_": (1.0, 1.08), "wide_": (1.0, 1.0),
    }
    z0, z1 = table.get(cam, (1.0, 1.06))
    e = ease(lt / max(dur, 0.01))
    z = z0 + (z1 - z0) * e
    z *= 1.0 + 0.008 * math.sin(lt * 3.1)
    dx = dy = 0.0
    if "pan_right" in cam or "track_right" in cam or "pan_right" == cam:
        dx = -70 * e
    if "pan_left" in cam:
        dx = 70 * e
    if "shake" in cam or "impact" in cam or cam in ("flash_shake", "wide_shake", "close_tense"):
        amp = 18 * math.exp(-lt * 5.0)
        dx += random.uniform(-amp, amp)
        dy += random.uniform(-amp, amp)
    return z, dx, dy


def compose_world(beat, lt, frame_idx, env_val, flip_seed=0):
    rnd = random.Random(beat["id"] * 1000 + int(lt * 30))
    plan = plan_for(beat)
    dur = beat["end"] - beat["start"]
    base = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 255))
    _CANVAS[0] = base
    d = ImageDraw.Draw(base)
    bg_draw(d, plan["bg"], lt, beat["id"])

    # props: drawn on bg layer
    for pr in plan["props"]:
        name = pr[0]
        if name == "mirror":
            x0, y0, x1, y1 = pr[1]
            mirror(d, x0, y0, x1, y1, fog=pr[2], crack=pr[3], shade=pr[4])
        elif name == "stall":
            x, y, w, h = pr[1]
            stall_door(d, x, y, w, h, open_amt=pr[2])
        elif name == "clock":
            x, y, r_, hh, mm = pr[1]
            clock_face(d, x, y, r_, hh, mm + int(lt * 4) % 60)
        elif name == "note":
            x, y, rot, lines_ = pr[1]
            base = Image.alpha_composite(base, note_paper(d, x, y, rot, lines_))
            _CANVAS[0] = base
            d = ImageDraw.Draw(base)
        elif name == "checklist":
            y = 230
            for k, s_ in enumerate(pr[1]):
                text(d, 360, y + k * 180, s_, 60, (30, 30, 50, 255), 0, "ArchivoBlack.ttf", "mm")
                text(d, 360, y + k * 180 + 70, "✓" if k < int(lt * 2) else "", 46, RED, 0, "ArchivoBlack.ttf")
        elif name == "toilet":
            x, y, s_, sw = pr[1]
            toilet(d, x, y, s_, swirl=lt * 2 if sw else 0)
        elif name == "cord":
            x, y = pr[1]
            line(d, [(x, y), (x + 30, y + 200 + 20 * math.sin(lt * 8))], BLACK, 6)
            ell(d, x + 30, y + 200 + 20 * math.sin(lt * 8), 18, 18, (240, 220, 80, 255), BLACK, 3)
        elif name == "sink":
            x, y, s_, on = pr[1]
            sink(d, x, y, s_, faucet_on=on * (0.5 + 0.5 * math.sin(lt * 9)))
        elif name == "pin":
            x, y = pr[1]
            ell(d, x, y, 18, 18, RED, BLACK, 4)
            poly(d, [(x - 14, y + 4), (x + 14, y + 4), (x, y + 40)], RED, BLACK, 3)
            text(d, x, y + 90, "GUARATINGUETÁ", 48, WHITE, 6)
        elif name == "portrait":
            x, y, w, h = pr[1]
            portrait(d, x, y, w, h)
        elif name == "chandelier":
            x, y = pr[1]
            chandelier(d, x, y, 1.0)
        elif name == "calendar":
            x, y, yr = pr[1]
            rect(d, x, y, x + 180, y + 140, (250, 240, 220, 255), BLACK, 5)
            text(d, x + 90, y + 70, yr, 70, BLACK, 0)
        elif name == "candelabra":
            x, y = pr[1]
            for k in range(-1, 2):
                candle(d, x + k * 60, y, 120, flick=lt + k)
        elif name == "doors":
            x0, y0, x1, y1 = pr[1]
            open_ = min(1.0, lt * 3)
            rect(d, x0, y0, x0 + (x1 - x0) / 2 * (1 - 0.8 * open_), y1, (120, 60, 40, 255), BLACK, 5)
            rect(d, x1 - (x1 - x0) / 2 * (1 - 0.8 * open_), y0, x1, y1, (120, 60, 40, 255), BLACK, 5)
        elif name == "chest":
            x, y = pr[1]
            rect(d, x - 110, y - 60, x + 110, y + 40, (150, 90, 40, 255), BLACK, 5)
            for k in range(6):
                ell(d, x - 90 + k * 36, y - 80 + (k % 2) * 20, 12, 12, YEL, BLACK, 2)
        elif name == "suitcase":
            x, y = pr[1]
            rect(d, x - 80, y - 40, x + 80, y + 40, (120, 60, 30, 255), BLACK, 5)
        elif name == "ring":
            x, y = pr[1]
            ell(d, x, y, 46, 46, None, (235, 190, 60, 255), 14)
            ell(d, x - 30, y - 40, 14, 14, (255, 255, 255, 255), outline=None)
        elif name == "table":
            x, y = pr[1]
            rect(d, 80, y, 640, y + 60, (120, 70, 40, 255), BLACK, 5)
        elif name == "eiffel":
            x, y, s_ = pr[1]
            eiffel(d, x, y, s_)
        elif name == "ticket":
            x, y = pr[1]
            rect(d, x, y, x + 220, y + 130, (250, 240, 200, 255), BLACK, 4)
            text(d, x + 110, y + 66, "PARIS", 50, RED, 0)
        elif name == "lightning":
            x, y, seed_ = pr[1]
            if int(lt * 30) % 9 < 2:
                lightning(d, 360, 40, seed=seed_ + int(lt * 10))
        elif name == "porthole":
            x, y, r_ = pr[1]
            ell(d, x, y, r_, r_, (120, 170, 210, 255), BLACK, 14)
        elif name == "ship":
            x, y, s_ = pr[1]
            ship(d, x, y, s_)
        elif name == "candles":
            for k in range(-3, 4):
                candle(d, 360 + k * 90, 900 - abs(k) * 20, 150, flick=lt * 3 + k)
        elif name == "altar":
            x, y = pr[1]
            rect(d, x - 200, y - 90, x + 200, y, (60, 40, 40, 255), BLACK, 4)
        elif name == "bell_jar":
            x, y, w, h = pr[1]
            bell_jar(d, x, y, w, h)
            ell(d, x, y - h * 0.3, w * 0.25, h * 0.45, (250, 240, 230, 255), outline=None)
        elif name == "house_big":
            x, y = pr[1]
            house(d, 200, 640, 320, 260, (240, 190, 170, 255))
        elif name == "gate":
            x, y = pr[1]
            rect(d, x - 80, y - 180, x + 80, y, (60, 60, 60, 255), BLACK, 4)
        elif name == "desks":
            for k in range(4):
                for j in range(2):
                    rect(d, 90 + k * 150, 760 + j * 110, 200 + k * 150, 790 + j * 110, (150, 100, 60, 255), BLACK, 3)
        elif name == "board":
            x, y = pr[1]
            rect(d, x - 240, y - 110, x + 240, y + 110, (40, 80, 60, 255), BLACK, 8)
        elif name == "sign":
            x, y, s_ = pr[1]
            rect(d, x - 240, y - 40, x + 240, y + 40, (40, 90, 170, 255), BLACK, 5)
            text(d, x, y, s_, 46, WHITE, 0)
        elif name == "fire_block":
            x, y, w, h = pr[1]
            fire_block(d, x, y, w, h, lt)

    # characters
    char_layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    for c in plan["cast"]:
        c = dict(c)
        if c.get("talk"):
            c["mouth"] = min(1.0, env_val * (0.85 + 0.25 * rnd.random()))
        if c.get("blink") is None:
            bp = (lt + beat["id"] * 0.37) % 3.4
            c["blink"] = 1.0 if bp < 0.12 else 0.0
        if c.get("kick") and "impact1" in plan["fx"] or c.get("kick") and "impact2" in plan["fx"]:
            c["hands"] = c.get("hands")
        if plan["fx"] and "walk" in plan["fx"]:
            c["x"] = c["x"] + 90 * math.sin(lt * 4.0)
        if c.get("kind") == "loira" and "glow" in plan["fx"]:
            c["gaze"] = (0.0, 0.0)
        layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        draw_char(layer, c, lt)
        a = c.get("alpha", 1.0)
        if "flash_ghost" in plan["fx"]:
            a = c["alpha"] if lt > 0.5 else 0.0
        if a < 1.0:
            arr = np.asarray(layer).copy()
            arr[..., 3] = (arr[..., 3].astype(np.float32) * a).astype(np.uint8)
            layer = Image.fromarray(arr, "RGBA")
        char_layer = Image.alpha_composite(char_layer, layer)
    base = Image.alpha_composite(base, char_layer)
    _CANVAS[0] = base
    d = ImageDraw.Draw(base)
    # fx overlays inside the world
    fxs = plan["fx"]
    if "flash" in fxs and lt < 0.12:
        ov = Image.new("RGBA", base.size, (255, 255, 255, int(220 * (1 - lt / 0.12))))
        _comp_inplace(base, ov)
    if "flash_lightning" in fxs and int(lt * 30) % 9 < 2:
        ov = Image.new("RGBA", base.size, (255, 255, 240, 170))
        _comp_inplace(base, ov)
    if "flash_ghost" in fxs and lt > 0.5:
        ov = Image.new("RGBA", base.size, (255, 255, 255, 120 if int(lt * 12) % 2 else 0))
        _comp_inplace(base, ov)
    if "darken" in fxs:
        ov = Image.new("RGBA", base.size, (0, 0, 0, int(min(1, lt * 2) * 150)))
        _comp_inplace(base, ov)
    if "flicker" in fxs and int(lt * 24) % 11 == 0:
        ov = Image.new("RGBA", base.size, (0, 0, 0, 90))
        _comp_inplace(base, ov)
    if "glow" in fxs:
        ov = Image.new("RGBA", base.size, (160, 220, 255, 0))
        arr = np.asarray(ov).copy()
        base_ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(base_ov)
        ell(dd, 360, 500, 360, 320, (150, 220, 255, 30 + int(20 * math.sin(lt * 6)) + 20), None)
        _comp_inplace(base, base_ov)
    if "vignette" in fxs:
        base_ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(base_ov)
        ell(dd, 360, 640, 760, 800, None, (0, 0, 0, 200), 180)
        _comp_inplace(base, base_ov)
    if "dust" in fxs or "speed" in fxs or "walk" in fxs:
        for k in range(30):
            px = (rnd.random() * 720 + lt * 180 * (1 if k % 2 else -1)) % 720
            py = rnd.random() * 1280
            ell(d, px, py, 3, 3, (230, 220, 200, 120), None)
    if "speed" in fxs:
        for k in range(10):
            y = 300 + k * 90
            line(d, [(0, y), (rnd.random() * 200, y)], (255, 255, 255, 160), 4)
    if "water" in fxs or "splash" in fxs or "drip" in fxs or "wet" in fxs:
        n = 24 if "splash" in fxs else 12
        for k in range(n):
            px = rnd.random() * 720
            py = ((rnd.random() + lt * 1.5) % 1.0) * 900 + 200
            ell(d, px, py, 4, 6, (150, 210, 255, 220), BLACK, 1)
    if "smoke" in fxs or "rise" in fxs:
        for k in range(10):
            px = rnd.random() * 720
            py = 1280 - ((rnd.random() + lt * 0.4) % 1.0) * 1000
            ell(d, px, py, 50 + rnd.random() * 40, 40, (70, 60, 70, 110), None)
    if "sparks" in fxs:
        for k in range(20):
            px = rnd.random() * 720
            py = rnd.random() * 1000
            ell(d, px, py, 4, 4, (255, 210, 80, 240), None)
    if "fire" in fxs:
        for k in range(10):
            px = rnd.random() * 720
            ell(d, px, 1100 - rnd.random() * 200, 14, 22, (255, 170, 60, 180), None)
    if "swirl" in fxs:
        for k in range(12):
            a = lt * 10 + k * 0.5
            ell(d, 360 + math.cos(a) * 200, 560 + math.sin(a) * 90, 14, 10, (240, 250, 255, 200), BLACK, 2)
    if "sea_glint" in fxs:
        for k in range(6):
            ell(d, rnd.random() * 720, 840 + rnd.random() * 380, 4, 2, (255, 255, 230, 200), None)
    if "questions" in fxs or "spin" in fxs:
        for k in range(6):
            ang = lt * 2 + k * 1.05
            text(d, 360 + math.cos(ang) * 240, 620 + math.sin(ang) * 260, "?", 110, YEL, 6)
    if "sweat" in fxs:
        ell(d, 330, 470 + 30 * ((lt * 2) % 1), 14, 20, (150, 220, 255, 230), BLACK, 3)
    if "stare" in fxs:
        for k in range(3):
            pass
    if "stamp_year" in fxs:
        text(d, 360, 880, "1916", 140, YEL, 8)
    if "lantern_swing" in fxs:
        pass

    # SFX stars/bubbles
    for label, x, y, col, rot in plan["sfx"]:
        pop = min(1.0, lt / 0.12)
        r_ = 150 * (0.3 + 0.7 * ease(pop))
        if len(label) <= 6:
            starburst(d, x, y, r_, col, label, label_size=int(64 * (0.3 + 0.7 * ease(pop))), rot=rot)
        else:
            speech_bubble(d, x, y, label, int(44 * (0.3 + 0.7 * ease(pop))))
    return base, plan


def camera_warp(world_img, cam, lt, dur, focus):
    z, dx, dy = camera(cam, lt, dur)
    fx_, fy_ = focus
    M = np.float32([[z, 0, (fx_ * (1 - z) + dx) * SS], [0, z, (fy_ * (1 - z) + dy) * SS]])
    arr = np.asarray(world_img.convert("RGB"))
    out = cv2.warpAffine(arr, M, (W * SS, H * SS), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out


def overlays(beat, lt, dur, t):
    """Header, banner, caption (returns RGBA at SS scale)."""
    ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    _CANVAS[0] = ov
    d = ImageDraw.Draw(ov)
    # header band
    rect(d, 0, 0, 720, 66, (10, 10, 14, 210), None)
    text(d, 360, 33, "LENDAS DO BRASIL #1", 40, YEL, 4)
    # banner
    if beat.get("banner"):
        appear = ease(lt / 0.25)
        bcol = {"red": RED, "yellow": YEL, "white": WHITE}.get(beat.get("banner_color") or "red", RED)
        tcol = WHITE if bcol == RED else BLACK
        seed = random.Random(beat["id"] * 7).uniform(-4, 4)
        label = beat["banner"]
        fsz = 58
        while fsz > 30 and font(fsz).getlength(label) / SS > 620:
            fsz -= 2
        bw = min(680, font(fsz).getlength(label) / SS + 70)
        bh = fsz * 1.5
        bl = Image.new("RGBA", (int(bw * SS), int(bh * SS)), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bl)
        bd.rounded_rectangle([0, 0, bw * SS - 1, bh * SS - 1], radius=10 * SS, fill=bcol, outline=BLACK, width=6 * SS)
        bd.text((bw * SS / 2, bh * SS / 2), label, font=font(fsz), fill=tcol, anchor="mm",
                stroke_width=2 * SS, stroke_fill=BLACK)
        bl = bl.rotate(seed, resample=Image.BICUBIC, expand=True)
        sc_ = 0.6 + 0.4 * appear
        if sc_ != 1.0:
            bl = bl.resize((max(1, int(bl.width * sc_)), max(1, int(bl.height * sc_))), Image.BICUBIC)
        ov.alpha_composite(bl, (int(360 * SS - bl.width / 2), int(170 * SS - bl.height / 2)))
    # caption
    cap = beat["text"].upper()
    hl = (beat.get("highlight") or "").upper()
    if t <= beat["end"] + 0.05:
        f = font(74)
        words = cap.split()
        lines, cur = [], ""
        for w_ in words:
            trial = (cur + " " + w_).strip()
            if f.getlength(trial) / SS > 640 and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = trial
        if cur:
            lines.append(cur)
        y0 = 1130 - (len(lines) - 1) * 84
        for li, ln in enumerate(lines):
            tw = f.getlength(ln) / SS
            x = 360 - tw / 2
            yy = y0 + li * 84
            if hl and hl in ln:
                # draw segment by segment
                pre, _, post = ln.partition(hl)
                xx = x
                for seg, col in ((pre, WHITE), (hl, YEL), (post, WHITE)):
                    if not seg:
                        continue
                    d.text((sc(xx), sc(yy)), seg, font=f, fill=col, anchor="lm",
                           stroke_width=8 * SS, stroke_fill=BLACK)
                    xx += f.getlength(seg) / SS
            else:
                d.text((sc(x), sc(yy)), ln, font=f, fill=WHITE, anchor="lm",
                       stroke_width=8 * SS, stroke_fill=BLACK)
    return ov


def render_frame(beat, t, env_val, frame_idx):
    lt = t - beat["start"]
    dur = beat["end"] - beat["start"]
    world, plan = compose_world(beat, max(0.0, lt), frame_idx, env_val)
    warped = camera_warp(world, beat["camera"], max(0.0, lt), dur, plan["focus"])
    base = Image.fromarray(warped).convert("RGBA")
    # global film look: slight vignette
    ov = overlays(beat, max(0.0, lt), dur, t)
    comp = Image.alpha_composite(base, ov).convert("RGB")
    return comp.resize((W, H), Image.LANCZOS)


def beat_at(t):
    cur = BEATS[0]
    for b in BEATS:
        if b["start"] <= t:
            cur = b
        else:
            break
    return cur


def load_env():
    w = wave.open(AUDIO)
    sr = w.getframerate()
    n = w.getnframes()
    raw = np.frombuffer(w.readframes(n), dtype=np.int16).reshape(-1, w.getnchannels()).astype(np.float32)
    mono = raw.mean(axis=1) / 32768.0
    hop = sr // FPS
    nfr = int(math.ceil(n / hop))
    env = np.zeros(nfr, dtype=np.float32)
    for i in range(nfr):
        seg = mono[i * hop:(i + 1) * hop]
        env[i] = float(np.sqrt(np.mean(seg * seg))) if seg.size else 0.0
    p = np.percentile(env, 98)
    env = np.clip(env / (p + 1e-6), 0, 1.0) ** 0.7
    return env


def cmd_sheet(out_png, out_jpg):
    cols, rows = 6, 12
    tw, th = 200, 356
    gap = 10
    head = 110
    sheet = Image.new("RGB", (cols * (tw + gap) + gap, head + rows * (th + gap + 24) + gap), (14, 12, 18))
    dr = ImageDraw.Draw(sheet)
    dr.text((sheet.width // 2, 40), "LENDAS DO BRASIL #1 · A LOIRA DO BANHEIRO — STORYBOARD (72 FRAMES)",
            font=ImageFont.truetype(os.path.join(FONT_DIR, "Anton.ttf"), 40), fill=(255, 207, 40), anchor="mm")
    dr.text((sheet.width // 2, 84), "9:16 · 72 beats · 0.28s–84.35s · pt-BR",
            font=ImageFont.truetype(os.path.join(FONT_DIR, "ArchivoBlack.ttf"), 22), fill=(240, 240, 240), anchor="mm")
    env = load_env()
    for k, b in enumerate(BEATS):
        mid = (b["start"] + b["end"]) / 2
        fi = int(mid * FPS)
        img = render_frame(b, mid, float(env[min(fi, len(env) - 1)]), fi)
        thumb = img.resize((tw, th), Image.LANCZOS)
        c, r = k % cols, k // cols
        x = gap + c * (tw + gap)
        y = head + r * (th + gap + 24)
        sheet.paste(thumb, (x, y))
        dr.rectangle([x, y, x + tw, y + th], outline=(255, 207, 40), width=2)
        dr.text((x + 6, y + th + 12), f"#{b['id']:02d}  {b['start']:.2f}s  {b['shot'][:26]}",
                font=ImageFont.truetype(os.path.join(FONT_DIR, "ArchivoBlack.ttf"), 11), fill=(230, 230, 230), anchor="lm")
        print("frame", b["id"], flush=True)
    sheet.save(out_png, optimize=True)
    sheet.convert("RGB").save(out_jpg, quality=92)
    print("saved", out_png, out_jpg, sheet.size)


def cmd_video(out_mp4, limit=None):
    env = load_env()
    total = int(round(85.0 * FPS))
    if limit:
        total = min(total, limit)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", AUDIO, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-t", f"{total / FPS:.3f}", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    random.seed(7)
    for f in range(total):
        t = f / FPS
        b = beat_at(t)
        ei = min(f, len(env) - 1)
        img = render_frame(b, t, float(env[ei]), f)
        proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
        if f % 150 == 0:
            print("frame", f, "/", total, flush=True)
    proc.stdin.close()
    proc.wait()
    print("done", out_mp4, proc.returncode, flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "sheet":
        cmd_sheet(sys.argv[2], sys.argv[3])
    elif mode == "video":
        lim = int(os.environ.get("LOIRA_LIMIT", "0")) or None
        cmd_video(sys.argv[2], lim)
    elif mode == "frame":
        b = beat_at(float(sys.argv[2]))
        env = load_env()
        t = float(sys.argv[2])
        render_frame(b, t, float(env[int(t * FPS)]), int(t * FPS)).save(sys.argv[3])
        print("ok")
