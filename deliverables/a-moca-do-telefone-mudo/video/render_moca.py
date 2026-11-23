#!/usr/bin/env python3
"""A Moça do Telefone Mudo — stickman renderer (one part, 9:16, 720x1280, 30 fps).

Builds: procedural 2D scenes per beat (camera push/pan, lamp flicker, ringing phone),
captions from captions.json, synthesized sound effects mixed with the narration master,
then encodes with ffmpeg. Usage:
  python3 render_moca.py sfx          -> writes video/sfx-mix.wav
  python3 render_moca.py frame T OUT  -> one still at time T
  python3 render_moca.py video OUT    -> full film
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H, FPS = 720, 1280, 30
FONT = os.path.join(HERE, "ArchivoBlack.ttf")
NARR = os.path.join(ROOT, "audio-master", "master-narration.wav")
MIX = os.path.join(HERE, "sfx-mix.wav")
FFMPEG = os.environ.get("FFMPEG", "/home/user/.local/bin/ffmpeg")
CAPS = json.load(open(os.path.join(ROOT, "b6-plan", "captions.json"), encoding="utf-8"))
TIMING = json.load(open(os.path.join(ROOT, "audio-master", "timing.json")))
TOTAL = TIMING["total"]
SR = 24000

BLACK = (18, 14, 16)
WHITE = (255, 255, 255)
YEL = (255, 207, 40)
RED = (216, 34, 44)
BROWN = (92, 56, 34)
BLUE = (70, 110, 170)
GREY = (150, 150, 158)
CREAM = (238, 226, 196)

BEATS = [(0.0, 9.86), (9.86, 15.34), (15.34, 25.34), (25.34, 35.34), (35.34, 42.82),
         (42.82, 53.14), (53.14, 61.02), (61.02, 70.82), (70.82, TOTAL)]

_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT, size)
    return _fonts[size]


# ---------------------------------------------------------------- primitives
def vgrad(top, bot):
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / (H - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def glow(img, x, y, r, color, alpha=150, blur=40):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([x - r, y - r, x + r, y + r], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base = img.convert("RGBA")
    base.alpha_composite(layer)
    return base.convert("RGB")


def limb(d, p, q, s, w=14):
    width = max(2, int(w * s))
    d.line([p, q], fill=BLACK, width=width)
    r = width / 2
    for x, y in (p, q):
        d.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)


def person(d, cx, base, s, expr="neutral", arms="down", hair=BROWN, shirt=BLUE,
           skirt=None, bun=False, hold_phone=False, phase=0.0):
    """Round white head, dot eyes, stick limbs. base = feet y, s = scale."""
    bob = math.sin(phase) * 3 * s
    hip = (cx, base - 150 * s + bob)
    sh_y = base - 300 * s + bob
    head_c = (cx, base - 340 * s + bob)
    hr = 70 * s
    # legs
    limb(d, hip, (cx - 40 * s, base), s)
    limb(d, hip, (cx + 40 * s, base), s)
    d.ellipse([cx - 60 * s, base - 8 * s, cx - 14 * s, base + 6 * s], fill=BLACK)
    d.ellipse([cx + 14 * s, base - 8 * s, cx + 60 * s, base + 6 * s], fill=BLACK)
    # torso (shirt or cardigan)
    body = [(cx - 60 * s, sh_y), (cx + 60 * s, sh_y), (cx + 52 * s, hip[1] + 10 * s), (cx - 52 * s, hip[1] + 10 * s)]
    if skirt:
        d.polygon([(cx - 60 * s, hip[1]), (cx + 60 * s, hip[1]), (cx + 110 * s, base), (cx - 110 * s, base)],
                  fill=skirt, outline=BLACK)
    d.polygon(body, fill=shirt, outline=BLACK)
    # neck
    d.line([(cx, sh_y), (cx, head_c[1] + hr - 4)], fill=BLACK, width=max(2, int(12 * s)))
    # arms
    ls, rs = (cx - 58 * s, sh_y + 8 * s), (cx + 58 * s, sh_y + 8 * s)
    if arms == "down":
        l_hand, r_hand = (cx - 92 * s, base - 170 * s), (cx + 92 * s, base - 170 * s)
    elif arms == "crossed":
        l_hand, r_hand = (cx + 30 * s, sh_y + 110 * s), (cx - 30 * s, sh_y + 110 * s)
    elif arms == "point":
        l_hand, r_hand = (cx - 92 * s, base - 170 * s), (cx + 170 * s, sh_y + 30 * s)
    else:  # reach up to a held phone near the head
        l_hand, r_hand = (cx - 92 * s, base - 170 * s), (cx + 40 * s, head_c[1] + 20 * s)
    if hold_phone:
        r_hand = (cx + 52 * s, head_c[1] + 10 * s)
    limb(d, ls, l_hand, s)
    limb(d, rs, r_hand, s)
    # head
    d.ellipse([head_c[0] - hr, head_c[1] - hr, head_c[0] + hr, head_c[1] + hr], fill=WHITE, outline=BLACK, width=max(3, int(6 * s)))
    if bun:
        d.ellipse([head_c[0] - 30 * s, head_c[1] - hr - 26 * s, head_c[0] + 30 * s, head_c[1] - hr + 16 * s], fill=hair, outline=BLACK, width=3)
        d.chord([head_c[0] - hr - 4, head_c[1] - hr - 4, head_c[0] + hr + 4, head_c[1] + 6 * s], 180, 360, fill=hair, outline=BLACK, width=3)
    else:
        d.chord([head_c[0] - hr - 4, head_c[1] - hr - 6, head_c[0] + hr + 4, head_c[1] + 4 * s], 180, 360, fill=hair, outline=BLACK, width=3)
    ex, ey = 26 * s, -6 * s
    er = 7 * s
    if expr == "scared":
        er = 12 * s
    for sx in (-1, 1):
        ecx, ecy = head_c[0] + sx * ex, head_c[1] + ey
        d.ellipse([ecx - er, ecy - er, ecx + er, ecy + er], fill=BLACK)
    # brows and mouth
    bw = max(3, int(6 * s))
    if expr == "skeptical":
        d.line([(head_c[0] - 44 * s, head_c[1] - 26 * s), (head_c[0] - 10 * s, head_c[1] - 24 * s)], fill=BLACK, width=bw)
        d.line([(head_c[0] + 10 * s, head_c[1] - 36 * s), (head_c[0] + 44 * s, head_c[1] - 30 * s)], fill=BLACK, width=bw)
        d.line([(head_c[0] - 22 * s, head_c[1] + 34 * s), (head_c[0] + 22 * s, head_c[1] + 30 * s)], fill=BLACK, width=bw)
    elif expr == "smirk":
        d.arc([head_c[0] - 26 * s, head_c[1] + 18 * s, head_c[0] + 26 * s, head_c[1] + 44 * s], 20, 160, fill=BLACK, width=bw)
    elif expr in ("scared", "shock"):
        d.ellipse([head_c[0] - 12 * s, head_c[1] + 28 * s, head_c[0] + 12 * s, head_c[1] + 50 * s], fill=BLACK)
    elif expr == "worried":
        d.arc([head_c[0] - 22 * s, head_c[1] + 36 * s, head_c[0] + 22 * s, head_c[1] + 56 * s], 200, 340, fill=BLACK, width=bw)
    else:
        d.line([(head_c[0] - 18 * s, head_c[1] + 36 * s), (head_c[0] + 18 * s, head_c[1] + 36 * s)], fill=BLACK, width=bw)


def phone(d, x, y, s=1.0, shake=0.0, color=BLACK):
    """Bakelite telephone; shake in px."""
    x = x + shake
    d.rounded_rectangle([x - 70 * s, y, x + 70 * s, y + 46 * s], radius=10 * s, fill=color, outline=BLACK, width=4)
    d.rounded_rectangle([x - 60 * s, y - 34 * s, x + 60 * s, y + 4 * s], radius=14 * s, fill=color, outline=BLACK, width=4)
    d.ellipse([x - 36 * s, y + 6 * s, x + 36 * s, y + 46 * s], outline=(120, 120, 120), width=3)


def ring_marks(d, x, y, t):
    for k in range(3):
        r = 40 + 26 * ((t * 3 + k) % 1.0) * 3
        d.arc([x - r, y - r, x + r, y + r], 200, 320, fill=WHITE, width=4)


def ring_active(t, a, b):
    return a <= t < b and (int((t - a) / 0.6) % 2 == 0)


def lamp(img, x, y, t, flicker=0.0):
    k = 0.85 + flicker * (0.5 * math.sin(t * 37) + 0.5 * math.sin(t * 13))
    img = glow(img, x, y, int(170 * k), YEL, alpha=int(130 * k), blur=50)
    return img


def caption_at(t):
    for c in CAPS:
        if c["start"] <= t < c["end"]:
            return c["text"]
    return None


# ---------------------------------------------------------------- scenes
def bg_living():
    img = vgrad((40, 36, 58), (78, 56, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 180, 660, 760], fill=(92, 68, 50), outline=BLACK, width=6)  # wall panel
    d.rectangle([420, 260, 620, 560], fill=(30, 40, 70), outline=BLACK, width=8)  # window
    d.line([(520, 260), (520, 560)], fill=BLACK, width=6)
    d.line([(420, 410), (620, 410)], fill=BLACK, width=6)
    img = glow(img, 520, 330, 120, (120, 150, 200), alpha=90, blur=40)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 960, W, H], fill=(60, 42, 30))  # floor
    d.rounded_rectangle([60, 900, 330, 1000], radius=18, fill=(120, 74, 40), outline=BLACK, width=6)  # couch
    d.rectangle([40, 780, 200, 900], fill=(96, 60, 34), outline=BLACK, width=6)  # table
    d.rectangle([40, 880, 200, 900], fill=(70, 44, 26), outline=BLACK, width=4)
    return img


def bg_house():
    img = vgrad((18, 24, 52), (44, 52, 82))
    d = ImageDraw.Draw(img)
    img = glow(img, 560, 240, 90, (230, 230, 210), alpha=200, blur=20)
    d = ImageDraw.Draw(img)
    d.ellipse([520, 200, 600, 280], fill=(240, 238, 220))
    d.rectangle([150, 640, 610, 1100], fill=(74, 90, 130), outline=BLACK, width=8)  # wall
    d.polygon([(120, 660), (380, 470), (640, 660)], fill=(160, 70, 50), outline=BLACK)  # roof
    d.rectangle([330, 860, 420, 1100], fill=(40, 30, 28), outline=BLACK, width=6)  # door
    d.rectangle([190, 730, 290, 830], fill=(20, 24, 40), outline=BLACK, width=6)  # broken window
    d.line([(200, 740), (260, 800)], fill=(180, 200, 230), width=3)
    d.rectangle([0, 1100, W, H], fill=(30, 46, 34))  # grass
    d.line([(60, 1200), (360, 1100)], fill=(70, 60, 50), width=18)  # path
    d.rectangle([520, 1000, 690, 1100], fill=(70, 70, 80), outline=BLACK, width=5)  # old car
    return img


def bg_hall():
    img = vgrad((30, 22, 20), (70, 46, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 0, 640, 960], fill=(110, 80, 56), outline=BLACK, width=6)
    d.rectangle([250, 480, 470, 960], fill=(60, 36, 24), outline=BLACK, width=8)  # bedroom door
    d.line([(250, 720), (470, 720)], fill=(252, 220, 140), width=6)  # light under door
    d.rectangle([0, 960, W, H], fill=(54, 36, 24))
    d.rectangle([520, 780, 620, 860], fill=(90, 60, 40), outline=BLACK, width=4)  # small table
    img = glow(img, 170, 430, 150, YEL, alpha=120, blur=50)
    d = ImageDraw.Draw(img)
    d.rectangle([150, 380, 190, 470], fill=(250, 230, 150), outline=BLACK, width=4)  # wall lamp
    return img


def bg_notebook():
    img = Image.new("RGB", (W, H), (90, 60, 38))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 90):
        d.line([(0, y), (W, y)], fill=(78, 50, 30), width=4)
    d.rectangle([110, 360, 610, 900], fill=(246, 240, 220), outline=BLACK, width=8)
    for y in range(420, 880, 46):
        d.line([(140, y), (580, y)], fill=(170, 190, 210), width=2)
    d.line([(160, 380), (160, 880)], fill=(220, 90, 90), width=3)
    d.text((170, 430), "Dona Eunice", font=font(38), fill=(60, 60, 70))
    d.text((170, 480), "555 - 3214 - 9876", font=font(34), fill=(70, 70, 80))
    d.line([(170, 508), (560, 508)], fill=BLACK, width=5)  # crossed out
    return img


def bg_bedroom(dark=False):
    img = vgrad((18, 22, 40), (40, 50, 80)) if dark else vgrad((28, 30, 56), (62, 58, 80))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 180, 660, 960], fill=(54, 58, 92), outline=BLACK, width=6)
    d.rectangle([80, 240, 240, 420], fill=(120, 150, 190), outline=BLACK, width=6)  # window
    d.rectangle([250, 180, 300, 380], fill=(110, 84, 60), outline=BLACK, width=4)
    d.rectangle([120, 740, 600, 860], fill=(210, 210, 224), outline=BLACK, width=6)  # bed
    d.rectangle([0, 960, W, H], fill=(44, 40, 52))
    d.rectangle([520, 620, 620, 740], fill=(80, 60, 50), outline=BLACK, width=4)  # nightstand
    if dark:
        img = glow(img, 260, 250, 110, (120, 150, 220), alpha=60, blur=40)
    return img


def bg_map():
    img = Image.new("RGB", (W, H), (120, 84, 56))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 200, 660, 1040], fill=(228, 214, 180), outline=BLACK, width=8)
    for gx in range(90, 640, 90):
        d.line([(gx, 220), (gx, 1020)], fill=(200, 184, 150), width=2)
    for gy in range(240, 1020, 90):
        d.line([(80, gy), (640, gy)], fill=(200, 184, 150), width=2)
    for gx in range(120, 620, 90):
        for gy in range(260, 1000, 90):
            d.rectangle([gx, gy, gx + 40, gy + 40], fill=(160, 120, 90), outline=BLACK, width=2)
    return img


def bg_stage_dark():
    img = vgrad((12, 14, 26), (26, 30, 50))
    d = ImageDraw.Draw(img)
    d.rectangle([250, 300, 470, 520], fill=(200, 220, 240), outline=BLACK, width=6)  # mirror
    d.rectangle([0, 960, W, H], fill=(20, 18, 28))
    d.rectangle([160, 860, 580, 960], fill=(210, 210, 226), outline=BLACK, width=6)  # bed
    return img


# ---------------------------------------------------------------- beats
def draw_beat(i, t, lt):
    """Return an RGB frame for beat i at global time t (lt = local 0..1)."""
    cam = 1.0 + 0.07 * lt  # slow push-in
    if i == 0:
        img = bg_living()
        img = lamp(img, 220, 800, t, flicker=0.0)
        d = ImageDraw.Draw(img)
        shake = 4 * math.sin(t * 70) if ring_active(t, 0.3, 4.3) else 0
        phone(d, 130, 760, shake=shake)
        if ring_active(t, 0.3, 4.3):
            ring_marks(d, 130, 760, t)
        person(d, 430, 1010, 1.25, expr="worried", arms="down", phase=t * 2)
    elif i == 1:
        img = bg_living()
        img = lamp(img, 220, 800, t)
        d = ImageDraw.Draw(img)
        phone(d, 130, 760)
        person(d, 360, 1010, 1.25, expr="smirk", arms="crossed", phase=t * 2)
    elif i == 2:
        img = bg_house()
        d = ImageDraw.Draw(img)
        sway = 10 * math.sin(t * 2.0)
        d.line([(290, 740), (340 + sway, 900), (300, 1000)], fill=BLACK, width=5)  # cord hanging out
        phone(d, 320, 1020, s=0.6, shake=sway * 0.3)
    elif i == 3:
        img = bg_hall()
        img = lamp(img, 170, 430, t, flicker=0.25)
        d = ImageDraw.Draw(img)
        phone(d, 560, 820, s=0.7)
        pulse = 1.0 + 0.04 * math.sin(t * 2 * math.pi * 1.3)
        person(d, 380, 1010, 1.3 * pulse, expr="scared", arms="reach", skirt=(60, 50, 60),
               bun=True, hair=GREY, shirt=BROWN, hold_phone=True, phase=t * 1.5)
    elif i == 4:
        img = bg_notebook()
        d = ImageDraw.Draw(img)
        prog = min(1.0, lt * 1.8)
        d.arc([300 - 150 * prog, 470 - 60 * prog, 300 + 150 * prog, 530 + 60 * prog], 0, 360, fill=RED, width=10)
        d.line([(420, 490), (520, 490)], fill=RED, width=8) if prog > 0.6 else None
    elif i == 5:
        img = bg_bedroom(dark=False)
        img = lamp(img, 260, 700, t, flicker=0.35)
        d = ImageDraw.Draw(img)
        phone(d, 580, 680, s=0.6)
        person(d, 360, 1010, 1.25, expr="shock", arms="reach", skirt=(228, 228, 236),
               bun=True, hair=GREY, shirt=(232, 232, 240), hold_phone=True, phase=t * 1.2)
    elif i == 6:
        img = bg_map()
        d = ImageDraw.Draw(img)
        pins = [(220, 400), (420, 300), (300, 600), (520, 560), (380, 820), (560, 860)]
        n = max(1, int(lt * (len(pins))))
        for k in range(1, min(n, len(pins))):
            d.line([pins[k - 1], pins[k]], fill=RED, width=5)
        for k in range(min(n, len(pins))):
            x, y = pins[k]
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=RED, outline=BLACK, width=3)
    elif i == 7:
        img = bg_stage_dark()
        img = glow(img, 360, 420, 180, (200, 220, 255), alpha=80, blur=50)
        d = ImageDraw.Draw(img)
        # woman in white, seated on bed
        d.polygon([(260, 860), (460, 860), (500, 1000), (220, 1000)], fill=(240, 240, 248), outline=BLACK)
        d.ellipse([320, 690, 400, 790], fill=(50, 40, 56), outline=BLACK, width=4)  # hair
        d.ellipse([330, 700, 390, 780], fill=(230, 226, 220), outline=BLACK, width=3)  # face shadow
        limb(d, (330, 880), (300, 930), 1.0)
        limb(d, (430, 880), (380, 770), 1.0)  # arm to ear
        phone(d, 400, 720, s=0.45)
    else:
        img = bg_living()
        img = lamp(img, 220, 800, t)
        d = ImageDraw.Draw(img)
        dark = Image.new("RGB", (W, H), (0, 0, 0))
        img = Image.blend(img, dark, 0.25)
        d = ImageDraw.Draw(img)
        shake = 5 * math.sin(t * 70) if ring_active(t, 71.2, 80) else 0
        phone(d, 330, 860, s=1.1, shake=shake)
        if ring_active(t, 71.2, 80):
            ring_marks(d, 330, 860, t)
    # camera push-in
    if cam > 1.0:
        cw, ch = int(W / cam), int(H / cam)
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
    return img


def beat_index(t):
    for i, (a, b) in enumerate(BEATS):
        if a <= t < b:
            return i, (t - a) / (b - a)
    return len(BEATS) - 1, 1.0


def draw_caption(img, text):
    d = ImageDraw.Draw(img)
    size = 47
    f = font(size)
    lines = [text]
    if f.getlength(text) > W - 60:
        words = text.split()
        best = None
        for k in range(1, len(words)):
            a, b = " ".join(words[:k]), " ".join(words[k:])
            worst = max(f.getlength(a), f.getlength(b))
            if best is None or worst < best[0]:
                best = (worst, a, b)
        lines = [best[1], best[2]]
    for n, line in enumerate(lines):
        y = 914 - (len(lines) - 1 - n) * 58
        d.text((W // 2, y), line, font=f, fill=WHITE, stroke_width=4, stroke_fill=(23, 19, 25), anchor="ms")
    return img


def render_t(t):
    i, lt = beat_index(t)
    img = draw_beat(i, t, lt)
    text = caption_at(t)
    if text:
        img = draw_caption(img, text)
    return img


# ---------------------------------------------------------------- sound
def env(n, a=0.01, r=0.1):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] = np.linspace(1, 0, nr) if nr < n else e[-nr:]
    return e


def sine(f, dur, amp=0.4, decay=0.0, f2=None):
    t = np.arange(int(dur * SR)) / SR
    freq = f if f2 is None else np.linspace(f, f2, len(t))
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return amp * np.sin(phase) * np.exp(-decay * t)


def noise(dur, amp=0.2, smooth=8):
    x = np.random.uniform(-1, 1, int(dur * SR))
    if smooth > 1:
        x = np.convolve(x, np.ones(smooth) / smooth, mode="same")
    return amp * x


def place(track, sig, t0):
    i0 = int(t0 * SR)
    n = min(len(sig), len(track) - i0)
    if n > 0:
        track[i0:i0 + n] += sig[:n]


def build_sfx(total_s):
    np.random.seed(11)
    track = np.zeros(int(total_s * SR) + SR)
    # phone rings: two tones, 0.4 on / 0.2 off
    def ring(t0, t1):
        t = t0
        while t < t1:
            burst = sine(440, 0.4, 0.22) + sine(480, 0.4, 0.22)
            place(track, burst * env(len(burst), 0.005, 0.05), t)
            t += 0.6
    ring(0.3, 4.3)
    ring(71.2, 79.6)
    # whoosh on every cut
    for a, _ in BEATS[1:]:
        w = noise(0.35, 0.10, smooth=40) * env(int(0.35 * SR), 0.15, 0.2)
        place(track, w, a - 0.1)
    # creak
    cr = sine(180, 0.9, 0.18, f2=420) * env(int(0.9 * SR), 0.2, 0.3) + noise(0.9, 0.04, 30)
    place(track, cr, 17.4)
    # heartbeat (hallway)
    for k in range(10):
        t0 = 27.0 + k * 0.78
        thump = sine(58, 0.22, 0.6, decay=14)
        place(track, thump, t0)
        place(track, sine(48, 0.18, 0.4, decay=16), t0 + 0.18)
    # pen tick on notebook
    for k in range(5):
        place(track, noise(0.05, 0.12, 3) * env(int(0.05 * SR), 0.001, 0.04), 37.0 + k * 0.9)
    # clock chime (3 strikes) in the bedroom
    for k in range(3):
        place(track, sine(880, 0.9, 0.22, decay=3.5), 45.0 + k * 0.9)
    # whisper: filtered noise under the spoken line
    wh = noise(1.6, 0.10, smooth=60) * env(int(1.6 * SR), 0.3, 0.4)
    place(track, wh, 47.0)
    # sting at the white-dress cut
    place(track, sine(45, 1.6, 0.7, decay=2.5), 61.0)
    place(track, sine(1320, 0.5, 0.06, decay=5), 61.0)
    # soft heartbeat under the white-dress scene
    for k in range(9):
        t0 = 62.0 + k * 0.95
        place(track, sine(52, 0.2, 0.35, decay=15), t0)
    # final sting
    place(track, sine(60, 1.2, 0.55, decay=3), 79.0)
    return track[: int(total_s * SR)]


def cmd_sfx():
    with wave.open(NARR, "rb") as w:
        nch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        narr = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    assert fr == SR and nch == 1, (fr, nch)
    sfx = build_sfx(len(narr) / SR)
    mix = narr * 1.0 + sfx * 0.55
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix * (0.95 / peak)
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(MIX, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("sfx mix", MIX, round(len(pcm) / SR, 2), "s", "peak", round(float(min(peak, 9.9)), 3), flush=True)


def cmd_frame(t, out):
    render_t(t).save(out)
    print("ok", out, flush=True)


def cmd_video(out):
    if not os.path.exists(MIX):
        cmd_sfx()
    total = int(round(TOTAL * FPS))
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", MIX, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-t", f"{total / FPS:.3f}", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(total):
        img = render_t(f / FPS)
        proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
        if f % 300 == 0:
            print("frame", f, "/", total, flush=True)
    proc.stdin.close()
    print("encoded", out, proc.wait(), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "sfx":
        cmd_sfx()
    elif mode == "frame":
        cmd_frame(float(sys.argv[2]), sys.argv[3])
    elif mode == "video":
        cmd_video(sys.argv[2])
