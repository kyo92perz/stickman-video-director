#!/usr/bin/env python3
"""A Moça do Telefone Mudo — scenes authored on anim_engine (keyframes per beat).

  python3 scenes_moca.py frame T OUT.png
  python3 scenes_moca.py sheet OUT.png        (contact sheet of key moments)
  python3 scenes_moca.py video OUT.mp4
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anim_engine as AE  # noqa: E402
import render_moca as RM  # noqa: E402

W, H, FPS = AE.W, AE.H, RM.FPS
FFMPEG = RM.FFMPEG
TOTAL = RM.TOTAL

NARR_HAIR = (92, 56, 34)
GREY = (150, 150, 158)


def pose(**kw):
    base = dict(x=430, y=735, lean=0, tilt=0,
                arm_r1=12, arm_r2=6, arm_l1=-12, arm_l2=-6,
                leg_r1=4, leg_r2=0, leg_l1=-4, leg_l2=0, expr="neutral")
    base.update(kw)
    return base


def drift(t_on, t_off, t, x0, x1):
    u = min(1.0, max(0.0, (t - t_on) / max(1e-6, t_off - t_on)))
    return x0 + (x1 - x0) * AE.ease(u)


# ------------------------------------------------------------------ beats
def beat_hook(t):
    """0–9.86 s: phone rings, narrator looks at it, reaches, then steps back."""
    keys = [
        (0.0, pose(x=430, y=735, expr="worried")),
        (1.6, pose(x=430, y=735, lean=-6, tilt=-24, expr="worried")),
        (3.0, pose(x=430, y=735, lean=-6, tilt=-24, arm_r1=-98, arm_r2=-30, expr="skeptical")),
        (5.2, pose(x=430, y=735, lean=-3, tilt=-10, arm_r1=-98, arm_r2=-30, expr="skeptical")),
        (6.8, pose(x=430, y=735, lean=0, tilt=0, expr="smirk")),
        (9.86, pose(x=430, y=735, lean=0, tilt=0, expr="smirk")),
    ]
    p = AE.interp_pose(keys, t)
    p["breath"] = AE.breath(t)
    return dict(bg=RM.bg_living(), actors=[(AE.Rig(1.25), p, None)],
                props=dict(front=[lambda d, tt: _phone(d, 130, 760, tt, ring=(0.3, 4.3))]),
                cam=(1.0 + 0.06 * min(1, t / 9.86), 360 + 0, 640))


def beat_skeptic(t):
    """9.86–15.34 s: arms crossed, eyebrow, small head tilt."""
    keys = [
        (9.86, pose(x=380, y=735, lean=-2, tilt=0, arm_r1=22, arm_r2=-92, arm_l1=-22, arm_l2=92, expr="skeptical")),
        (12.5, pose(x=380, y=735, lean=-2, tilt=8, arm_r1=22, arm_r2=-92, arm_l1=-22, arm_l2=92, expr="skeptical")),
        (15.34, pose(x=380, y=735, lean=0, tilt=4, arm_r1=22, arm_r2=-92, arm_l1=-22, arm_l2=92, expr="smirk")),
    ]
    p = AE.interp_pose(keys, t)
    p["breath"] = AE.breath(t, 1.5)
    return dict(bg=RM.bg_living(), actors=[(AE.Rig(1.25), p, None)],
                props=dict(front=[lambda d, tt: _phone(d, 130, 760, tt)]),
                cam=(1.0 + 0.05 * min(1, (t - 9.86) / 5.5), 360, 640))


def beat_house(t):
    """15.34–25.34 s: 1987 house, camera pans right, cord sways."""
    lt = (t - 15.34) / 10.0
    def cord(d, tt):
        sway = 10 * math.sin(tt * 2.0)
        d.line([(290, 740), (340 + sway, 900), (300, 1000)], fill=AE.BLACK, width=5)
        RM.phone(d, 320, 1020, s=0.6, shake=sway * 0.3)
    return dict(bg=RM.bg_house(), actors=[], props=dict(front=[cord]),
                cam=(1.1, 360 + 80 * AE.ease(lt), 600))


def beat_eunice(t):
    """25.34–35.34 s: Eunice in the hallway, phone at her ear, heartbeat."""
    keys = [
        (25.34, pose(x=380, y=735, lean=-4, tilt=6, arm_r1=110, arm_r2=60, arm_l1=-18, arm_l2=-8, expr="scared", skirt=0.4)),
        (30.0, pose(x=380, y=735, lean=2, tilt=-2, arm_r1=110, arm_r2=60, arm_l1=-18, arm_l2=-8, expr="scared", skirt=0.4)),
        (35.34, pose(x=380, y=735, lean=-2, tilt=4, arm_r1=110, arm_r2=60, arm_l1=-18, arm_l2=-8, expr="shock", skirt=0.4)),
    ]
    p = AE.interp_pose(keys, t)
    p["breath"] = AE.breath(t, 2.2, 0.9)
    p.update(hair=GREY, bun=True, shirt=(120, 84, 58), skirt=0.4, skirt_color=(60, 50, 60))
    rig = AE.Rig(1.3)
    return dict(bg=RM.bg_hall(), actors=[(rig, p, None)],
                props=dict(front=[lambda d, tt: RM.phone(d, 560, 820, s=0.7)]),
                cam=(1.06 + 0.04 * (t - 25.34) / 10, 380, 620))


def beat_notebook(t):
    """35.34–42.82 s: the number is written, crossed out and circled in red."""
    lt = (t - 35.34) / 7.48
    def circle(d, tt):
        prog = min(1.0, lt * 1.8)
        d.arc([300 - 150 * prog, 470 - 60 * prog, 300 + 150 * prog, 530 + 60 * prog], 0, 360, fill=RM.RED, width=10)
        if prog > 0.6:
            d.line([(420, 490), (520, 490)], fill=RM.RED, width=8)
    return dict(bg=RM.bg_notebook(), actors=[], props=dict(front=[circle]), cam=(1.0 + 0.1 * lt, 360, 640))


def beat_voice(t):
    """42.82–53.14 s: Eunice in the bedroom, voice speaks, lamp flickers."""
    keys = [
        (42.82, pose(x=360, y=735, lean=-3, tilt=4, arm_r1=110, arm_r2=60, arm_l1=-20, arm_l2=-10, expr="shock")),
        (48.0, pose(x=360, y=735, lean=-1, tilt=0, arm_r1=110, arm_r2=60, arm_l1=-20, arm_l2=-10, expr="talk")),
        (53.14, pose(x=360, y=735, lean=-3, tilt=6, arm_r1=110, arm_r2=60, arm_l1=-20, arm_l2=-10, expr="scared")),
    ]
    p = AE.interp_pose(keys, t)
    p["breath"] = AE.breath(t, 2.0)
    p["_t"] = t
    p.update(hair=GREY, bun=True, shirt=(232, 232, 240), skirt=0.4, skirt_color=(228, 228, 236))
    def lamp_fx(img_draw, tt):
        pass
    return dict(bg=RM.lamp(RM.bg_bedroom(dark=False), 260, 700, t, flicker=0.35),
                actors=[(AE.Rig(1.25), p, None)],
                props=dict(front=[lambda d, tt: RM.phone(d, 580, 680, s=0.6)]),
                cam=(1.05, 360, 640))


def beat_map(t):
    """53.14–61.02 s: pins are placed on a map and linked by a red thread."""
    lt = (t - 53.14) / 7.88
    pins = [(220, 400), (420, 300), (300, 600), (520, 560), (380, 820), (560, 860)]
    def thread(d, tt):
        n = max(1, int(lt * len(pins)))
        for k in range(1, min(n, len(pins))):
            d.line([pins[k - 1], pins[k]], fill=RM.RED, width=5)
        for k in range(min(n, len(pins))):
            x, y = pins[k]
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=RM.RED, outline=AE.BLACK, width=3)
    return dict(bg=RM.bg_map(), actors=[], props=dict(front=[thread]), cam=(1.0 + 0.08 * lt, 360, 620))


def beat_white(t):
    """61.02–70.82 s: a woman in white sits on the bed, phone at her ear, heartbeat."""
    keys = [
        (61.02, pose(x=360, y=735, lean=14, tilt=18, arm_r1=110, arm_r2=60, arm_l1=10, arm_l2=-20, expr="neutral")),
        (66.0, pose(x=360, y=735, lean=16, tilt=22, arm_r1=110, arm_r2=60, arm_l1=10, arm_l2=-20, expr="neutral")),
        (70.82, pose(x=360, y=735, lean=12, tilt=14, arm_r1=110, arm_r2=60, arm_l1=10, arm_l2=-20, expr="neutral")),
    ]
    p = AE.interp_pose(keys, t)
    p["breath"] = AE.breath(t, 1.0, 0.25)
    p.update(hair=(50, 40, 56), bun=False, shirt=(240, 240, 248), skirt=0.6, skirt_color=(240, 240, 248))
    return dict(bg=RM.bg_stage_dark(), actors=[(AE.Rig(1.2), p, None)],
                props=dict(front=[]), cam=(1.0 + 0.06 * (t - 61.02) / 9.8, 360, 640))


def beat_final(t):
    """70.82–79.72 s: the phone rings alone, camera pulls back."""
    lt = (t - 70.82) / 8.9
    def phone_ring(d, tt):
        shake = 5 * math.sin(tt * 70) if RM.ring_active(tt, 71.2, 80) else 0
        RM.phone(d, 330, 860, s=1.1, shake=shake)
        if RM.ring_active(tt, 71.2, 80):
            RM.ring_marks(d, 330, 860, tt)
    return dict(bg=RM.bg_living(), actors=[], props=dict(front=[phone_ring]),
                cam=(1.12 - 0.12 * AE.ease(lt), 360, 640))


def _phone(d, x, y, t, ring=None):
    shake = 4 * math.sin(t * 70) if (ring and ring[0] <= t < ring[1]) else 0
    RM.phone(d, x, y, shake=shake)
    if ring and ring[0] <= t < ring[1] and int((t - ring[0]) / 0.6) % 2 == 0:
        RM.ring_marks(d, x, y, t)


BEATS = [(0.0, 9.86, beat_hook), (9.86, 15.34, beat_skeptic), (15.34, 25.34, beat_house),
         (25.34, 35.34, beat_eunice), (35.34, 42.82, beat_notebook), (42.82, 53.14, beat_voice),
         (53.14, 61.02, beat_map), (61.02, 70.82, beat_white), (70.82, TOTAL, beat_final)]


def render_t(t):
    for a, b, fn in BEATS:
        if a <= t < b or (b == TOTAL and t >= a):
            sc = fn(t)
            break
    img = AE.render_world(sc["bg"], sc["actors"], sc["props"], t, sc["cam"])
    text = RM.caption_at(t)
    if text:
        img = RM.draw_caption(img, text)
    return img


def cmd_sheet(out):
    times = [1.0, 2.5, 4.0, 7.0, 11.0, 13.5, 17.0, 22.0, 27.5, 31.0, 38.0, 45.0, 50.0, 57.0, 64.0, 67.0, 73.0, 77.0]
    ims = [render_t(t).resize((180, 320)) for t in times]
    sheet = Image.new("RGB", (9 * 190, 2 * 330), (0, 0, 0))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 9) * 190, (i // 9) * 330))
    sheet.save(out)
    print("sheet", out, flush=True)


def cmd_video(out):
    if not os.path.exists(RM.MIX):
        RM.cmd_sfx()
    total = int(round(TOTAL * FPS))
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", RM.MIX, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-t", f"{total / FPS:.3f}", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(total):
        proc.stdin.write(np.asarray(render_t(f / FPS), dtype=np.uint8).tobytes())
        if f % 300 == 0:
            print("frame", f, "/", total, flush=True)
    proc.stdin.close()
    print("encoded", out, proc.wait(), flush=True)


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "frame":
        render_t(float(sys.argv[2])).save(sys.argv[3])
        print("ok", sys.argv[3], flush=True)
    elif m == "sheet":
        cmd_sheet(sys.argv[2])
    elif m == "video":
        cmd_video(sys.argv[2])
