#!/usr/bin/env python3
"""A Perna Cabeluda (LENDAS DO BRASIL) — shot-by-shot renderer.

Reuses the drawing primitives, character rig, camera and caption overlays from
render_engine (v3) and adds: a night road, a truck cab interior with headlight
beam, a hairy leg monster with walking/hopping animation, claw marks, glowing
eyes, and lip-sync driven by the narration envelope.
"""
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, "/tmp/loira_v2")
import render_engine as re_  # noqa: E402

SS, W, H, FPS = re_.SS, re_.W, re_.H, re_.FPS
re_.AUDIO = "/tmp/bus/master.wav"
T = json.load(open("/tmp/bus/timing.json"))
TOTAL = T["total"]

SCENES = [
    dict(text="Não entre nesse ônibus, mesmo que o letreiro tenha o seu nome.",
         bg="night", cab=False, leg=None, zé=None, bus=None, cz="cida", cida=dict(x=360, y=760, s=1.25, expr="worried", talk=False),
         banner=("NÃO ENTRE", "red"), cams=["push_in", "zoom_in"], fx=["fog"]),
    dict(text="Quinta-feira, meia-noite. A Dona Cida esperava o último ônibus no ponto da rodovia. Sem sinal, sem gente, só o asfalto molhado.",
         bg="night", cab=False, leg=None, zé=None, bus=None, cz="cida", cida=dict(x=360, y=760, s=1.25, expr="neutral", talk=True),
         banner=("PONTO DA RODOVIA", "yellow"), cams=["medium_two", "wide_pan", "push_in"], fx=["dust", "fog"]),
    dict(text="Então as luzes apareceram ao longe. Um ônibus antigo, azul desbotado, com o letreiro piscando: Vila Esperança.",
         bg="night", cab=False, leg=None, zé=None, bus=dict(x0=900, x1=330, y=700, s=1.0, door=0.0, lights=True), cz="cida", cida=dict(x=200, y=780, s=1.0, expr="shock", talk=False),
         banner=("VILA ESPERANÇA", "yellow"), cams=["wide_pan", "pan_right", "medium_front"], fx=["beam"]),
    dict(text="A porta abriu sozinha. Lá dentro, dezenas de passageiros, todos imóveis, com o rosto virado para a janela.",
         bg="night", cab=False, leg=None, zé=None, bus=dict(x0=360, x1=360, y=700, s=1.3, door=1.0, lights=True), cz=None, cida=None,
         banner=("PORTA ABERTA", "red"), cams=["zoom_in", "push_in", "shake_wide"], fx=["beam", "fog"]),
    dict(text="O motorista não tinha rosto. Só um sorriso pintado à mão, e uma voz que disse o nome dela.",
         bg="interior", cab=False, leg=None, zé=None, bus=None, driver=True, cz="cida", cida=None,
         banner=("O MOTORISTA", "red"), cams=["extreme_close", "close_up", "zoom_in"], fx=["flicker"]),
    dict(text="Cida deu um passo para trás. Mas a porta já estava aberta, e o nome dela piscava no letreiro.",
         bg="interior", cab=False, leg=None, zé=None, bus=None, cz="cida", cida=dict(x=360, y=860, s=1.0, expr="scared", talk=True), passengers=True,
         banner=("NOME NO LETREIRO", "yellow"), cams=["shake_heavy", "shake_wide", "impact_zoom"], fx=["flicker"], sfx=[("TUM!", 560, 420, re_.YEL, 8)]),
    dict(text="Na manhã seguinte, o ponto estava vazio. E no vidro embaçado do ônibus, alguém tinha escrito com a mão: falta um.",
         bg="dawn", cab=False, leg=None, zé=None, bus=None, claws=True, cz=None, cida=None,
         banner=("FALTA UM", "red"), cams=["push_door", "close_up", "extreme_eyes"], fx=["dust"]),
    dict(text="Dizem que, à meia-noite, o ônibus ainda passa. Se ele parar na sua frente, você ainda acha que é só um ônibus?",
         bg="night", cab=False, leg=None, zé=None, bus=dict(x0=360, x1=360, y=760, s=1.5, door=0.6, lights=True), cz=None, cida=None,
         banner=("SÓ UM ÔNIBUS?", "yellow"), cams=["zoom_out", "push_in", "final_punch"], fx=["fog", "flicker"]),
]

KEYWORD_SKIP = {"ninguém", "quando", "começou", "dizem", "numa", "estrada", "perto", "sozinho", "pelo", "pelo"}


def chunk_words(text, n=4):
    words = text.split()
    out = []
    cur = []
    for w in words:
        cur.append(w)
        if len(cur) >= n or w.endswith((".", "?", "!")) or w.endswith(","):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [" ".join(c) for c in out]


def build_shots():
    shots = []
    for si, sc in enumerate(SCENES):
        s0 = T["starts"][si]
        d = T["durs"][si]
        chunks = chunk_words(sc["text"], 4)
        weights = [len(c.split()) for c in chunks]
        tot = sum(weights)
        t = s0
        for ci, (c, wgt) in enumerate(zip(chunks, weights)):
            dur = d * wgt / tot
            cap = c.upper()
            cand = [w.strip(".,?!").upper() for w in c.split()]
            cand = [w for w in cand if len(w) >= 5 and w.lower() not in KEYWORD_SKIP]
            hl = max(cand, key=len) if cand else ""
            shot = dict(
                id=len(shots) + 1, scene=si, start=t, end=t + dur,
                text=cap, highlight=hl,
                banner=sc["banner"][0] if ci == 0 else None,
                banner_color=sc["banner"][1] if ci == 0 else None,
                camera=sc["cams"][ci % len(sc["cams"])],
                sfx_on=(ci == min(1, len(chunks) - 1)),
            )
            shots.append(shot)
            t += dur
    return shots


SHOTS = build_shots()
ENV = None


def scene_of(t):
    cur = SHOTS[0]
    for s in SHOTS:
        if s["start"] <= t:
            cur = s
        else:
            break
    return cur


# ----------------------------------------------------------- backgrounds
def road_night(d, lt):
    re_._CANVAS[0].paste(re_.grad((8, 10, 30), (34, 40, 66)).convert("RGB"), (0, 0))
    re_.moon(d, 560, 230, 70, lt)
    for x in range(-40, 760, 110):
        re_.poly(d, [(x, 620), (x + 55, 330), (x + 110, 620)], (14, 22, 26, 255), None, 0)
    re_.rect(d, 0, 620, 720, 1280, (24, 38, 34, 255))
    re_.poly(d, [(200, 620), (520, 620), (720, 1280), (0, 1280)], (46, 46, 52, 255), None, 0)
    off = (lt * 500) % 120
    for k in range(-1, 12):
        y0 = 640 + k * 120 + off
        y0 = 640 + ((k * 120 + off) % 1320) - 0
        re_.poly(d, [(355, y0), (365, y0), (368, y0 + 60), (352, y0 + 60)], (230, 220, 150, 255), None, 0)


def road_dawn(d, lt):
    re_._CANVAS[0].paste(re_.grad((250, 170, 110), (90, 120, 170)).convert("RGB"), (0, 0))
    re_.ell(d, 360, 760, 110, 110, (255, 226, 150, 255), (210, 150, 80, 255), 4)
    re_.rect(d, 0, 640, 720, 1280, (56, 70, 60, 255))
    re_.poly(d, [(260, 640), (460, 640), (720, 1280), (0, 1280)], (60, 60, 64, 255), None, 0)
    for x in range(-40, 760, 120):
        re_.poly(d, [(x, 640), (x + 60, 420), (x + 120, 640)], (60, 80, 70, 255), None, 0)


def draw_cab(d, lt):
    # roof pillars and dashboard, drawn over the road
    re_.rect(d, 0, 0, 720, 130, (22, 18, 20, 255), None)
    re_.poly(d, [(0, 0), (120, 0), (0, 1280)], (30, 24, 26, 255), (10, 8, 10, 255), 4)
    re_.poly(d, [(720, 0), (600, 0), (720, 1280)], (30, 24, 26, 255), (10, 8, 10, 255), 4)
    re_.rect(d, 0, 1040, 720, 1280, (40, 34, 36, 255), (10, 8, 10, 255), 6)
    re_.ell(d, 200, 1090, 120, 80, None, (16, 14, 16, 255), 16)  # steering wheel
    re_.ell(d, 520, 1110, 60, 50, (20, 20, 24, 255), (120, 120, 120, 255), 6)
    ang = math.radians(-120 + 120 * min(1.0, lt / 4.0))
    re_.line(d, [(520, 1110), (520 + math.cos(ang) * 44, 1110 + math.sin(ang) * 44)], (255, 80, 60, 255), 4)


def draw_leg(d, cx, base, s, step, eyes=False, hop=False, seed=3):
    rnd = random.Random(seed)
    sway = 26 * math.sin(step) * s
    bounce = (abs(math.sin(step * 1.0)) * 90 * s) if hop else 0.0
    base = base - bounce
    hip_y = base - 560 * s
    knee_y = base - 300 * s
    if eyes:
        for ex in (-70, 70):
            re_.ell(d, cx + ex * s, hip_y - 60 * s, 16 * s, 12 * s, (255, 240, 120, 255), None)
    skin = (196, 160, 140, 255)
    outline = (30, 18, 14, 255)
    hip = [(cx - 40 * s, hip_y), (cx + 40 * s, hip_y)]
    knee = [(cx - 24 * s + sway * 0.5, knee_y), (cx + 24 * s + sway * 0.5, knee_y)]
    calf = [(cx - 30 * s + sway * 0.8, knee_y + 130 * s), (cx + 30 * s + sway * 0.8, knee_y + 130 * s)]
    ank = [(cx - 16 * s + sway, base - 60 * s), (cx + 18 * s + sway, base - 60 * s)]
    poly_pts = [hip[0], hip[1], knee[1], calf[1], ank[1], ank[0], calf[0], knee[0]]
    re_.poly(d, poly_pts, skin, outline, 4 * s)
    # shading on the shin
    re_.poly(d, [(cx + 14 * s + sway * 0.6, knee_y + 20 * s), (cx + 28 * s + sway * 0.8, knee_y + 130 * s),
                 (cx + 14 * s + sway, base - 60 * s), (cx + 6 * s + sway * 0.6, knee_y + 120 * s)], (160, 122, 104, 255), None, 0)
    # knee cap
    re_.ell(d, cx + sway * 0.5, knee_y + 6 * s, 14 * s, 12 * s, None, (90, 60, 48, 255), 2.5 * s)
    # dark coarse hair, denser toward the top
    for k in range(110):
        tt = rnd.random() ** 0.8
        y = hip_y + (base - 60 * s - hip_y) * tt
        half = (40 - 22 * tt) * s
        x = cx + sway * tt + rnd.uniform(-half, half)
        dx, dy = rnd.uniform(-8, 8) * s, rnd.uniform(14, 26) * s
        re_.line(d, [(x, y), (x + dx, y + dy)], (46, 30, 22, 255), 2.0 * s)
    # foot with toes
    re_.ell(d, cx + sway + 14 * s, base - 36 * s, 58 * s, 22 * s, skin, outline, 4 * s)
    for k in range(5):
        tx = cx + sway - 26 * s + k * 20 * s
        re_.ell(d, tx, base - 22 * s, 7 * s, 6 * s, (236, 226, 210, 255), outline, 2)


def draw_claws(d, lt):
    re_.rect(d, 180, 260, 540, 1040, (92, 56, 34, 255), (30, 18, 12, 255), 8)
    for k, dx in enumerate((-70, 0, 70)):
        for j in range(3):
            x0 = 330 + dx + j * 10 - 10
            re_.line(d, [(x0, 360 + k * 6), (x0 + 30, 520 + k * 6), (x0 + 22, 620)], (210, 200, 180, 255), 6)
            re_.line(d, [(x0 + 4, 365 + k * 6), (x0 + 34, 520 + k * 6)], (40, 24, 16, 255), 2)
    # hair strand caught on the door
    pts_ = [(360 + 40 * math.sin(i * 0.5), 690 + i * 14) for i in range(18)]
    re_.line(d, pts_, (30, 20, 16, 255), 4)


# ----------------------------------------------------------- frame compose

def draw_bus(d, cx, y, s, door, lt):
    body = (40, 90, 170, 255)
    w, h = 300 * s, 210 * s
    re_.rect(d, cx - w / 2, y - h, cx + w / 2, y, body, (12, 18, 30, 255), 6)
    re_.rect(d, cx - w / 2, y - h * 0.82, cx + w / 2, y - h * 0.62, (250, 220, 130, 255), (12, 18, 30, 255), 3)
    re_.rect(d, cx - w * 0.44, y - h * 0.6, cx + w * 0.44, y - h * 0.22, (250, 236, 180, 255), (12, 18, 30, 255), 3)
    for k in range(4):
        x0 = cx - w * 0.42 + k * w * 0.2
        re_.rect(d, x0, y - h * 0.58, x0 + w * 0.15, y - h * 0.26, (140, 190, 220, 255), (12, 18, 30, 255), 2)
    re_.rect(d, cx + w * 0.32, y - h * 0.58, cx + w * 0.44, y - h * 0.1, (30, 40, 60, 255), (12, 18, 30, 255), 3)
    ddx = w * 0.32 * (1 - door * 0.9)
    re_.rect(d, cx + w * 0.32 + ddx * 0.2, y - h * 0.58, cx + w * 0.44, y - h * 0.1, (60, 80, 110, 255), (12, 18, 30, 255), 2)
    re_.text(d, cx, y - h * 0.72, "VILA ESPERANÇA", int(30 * s), (30, 20, 10, 255), 0, "Anton.ttf")
    for wx in (-0.3, 0.3):
        re_.ell(d, cx + w * wx, y + 6, 36 * s, 36 * s, (20, 20, 22, 255), (120, 120, 120, 255), 4)
    re_.ell(d, cx + w * 0.5, y - h * 0.22, 14 * s, 10 * s, (255, 240, 150, 255), None)


def draw_interior(d, lt, passengers=True):
    re_._CANVAS[0].paste(re_.grad((16, 12, 22), (40, 32, 44)).convert("RGB"), (0, 0))
    re_.rect(d, 0, 0, 720, 240, (30, 30, 40, 255), None)
    for k in range(4):
        x0 = 40 + k * 170
        re_.rect(d, x0, 40, x0 + 140, 190, (40, 70, 100, 255), (10, 10, 14, 255), 4)
    re_.rect(d, 0, 900, 720, 1280, (60, 50, 56, 255))
    for row in range(4):
        yy = 520 + row * 110
        for col in range(3):
            if not passengers:
                continue
            xx = 130 + col * 230 + (row % 2) * 20
            re_.rect(d, xx - 60, yy, xx + 60, yy + 60, (70, 36, 44, 255), (10, 10, 14, 255), 3)
            re_.ell(d, xx, yy - 30, 34, 36, (34, 30, 38, 255), (10, 10, 14, 255), 3)
    flick = 0.5 + 0.5 * math.sin(lt * 9)
    re_.ell(d, 360, 110, 320, 60, (255, 240, 200, int(40 * flick)), None)


def draw_driver(d, lt):
    re_.ell(d, 360, 380, 120, 150, (230, 228, 226, 255), (10, 10, 14, 255), 6)
    re_.ell(d, 310, 350, 14, 22, (20, 20, 22, 255), None)
    re_.ell(d, 410, 350, 14, 22, (20, 20, 22, 255), None)
    arc = [(330 + 60 * math.cos(math.radians(a)) * 0.6 + 30, 430 + 40 * math.sin(math.radians(a))) for a in range(20, 160, 10)]
    re_.line(d, [(x - 30, y) for x, y in arc], (200, 20, 30, 255), 8)


def render_world(shot, lt, env_val):
    sc = SCENES[shot["scene"]]
    world = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 255))
    re_._CANVAS[0] = world
    d = ImageDraw.Draw(world)
    if sc["bg"] == "night":
        road_night(d, lt)
    elif sc["bg"] == "interior":
        draw_interior(d, lt, passengers=sc.get("passengers", True))
    else:
        road_dawn(d, lt)
    if sc.get("claws"):
        draw_claws(d, lt)
    if sc.get("bus"):
        B = sc["bus"]
        prog = min(1.0, lt / 3.0)
        cx = B["x0"] + (B["x1"] - B["x0"]) * (1 - (1 - prog) ** 3)
        draw_bus(d, cx, B["y"], B["s"], B["door"], lt)
    if sc.get("driver"):
        draw_driver(d, lt)
    if sc["leg"] is not None:
        L = dict(sc["leg"])
        L["step"] = L["step"] + lt * 5.0
        shadow = Image.new("RGBA", world.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        re_.ell(sd, L["x"], L["base"] - 4, 150 * L["s"], 26 * L["s"], (0, 0, 0, 0), None)
        draw_leg(d, L["x"], L["base"], L["s"], L["step"], eyes=L.get("eyes", False), hop=L.get("hop", False), seed=shot["id"] % 5 + 3)
    if "fog" in sc["fx"]:
        re_.ell(d, 360, 760, 520, 90, (200, 210, 230, 45), None)
    world_cast = None
    if sc.get("cida") is not None:
        Z = sc["cida"]
        c = dict(kind="bia", x=Z["x"], y=Z["y"], s=Z["s"], expr=Z["expr"], hands=None, gaze=(0, 0),
                 alpha=1.0, flip=False, kick=False)
        if Z.get("talk"):
            c["mouth"] = min(1.0, env_val)
        bp = (lt + shot["id"] * 0.37) % 3.4
        c["blink"] = 1.0 if bp < 0.12 else 0.0
        layer = Image.new("RGBA", world.size, (0, 0, 0, 0))
        re_.draw_char(layer, c, lt)
        world = Image.alpha_composite(world, re_.drop_shadow(layer))
        world = Image.alpha_composite(world, layer)
        re_._CANVAS[0] = world
        d = ImageDraw.Draw(world)
    if sc["zé"] is not None:
        Z = sc["zé"]
        c = dict(kind="lucas", x=Z["x"], y=Z["y"], s=Z["s"], expr=Z["expr"], hands=None, gaze=(0, 0),
                 alpha=1.0, flip=False, kick=False)
        if Z.get("talk"):
            c["mouth"] = min(1.0, env_val)
        bp = (lt + shot["id"] * 0.37) % 3.4
        c["blink"] = 1.0 if bp < 0.12 else 0.0
        layer = Image.new("RGBA", world.size, (0, 0, 0, 0))
        re_.draw_char(layer, c, lt)
        world = Image.alpha_composite(world, re_.drop_shadow(layer))
        world = Image.alpha_composite(world, layer)
        re_._CANVAS[0] = world
        d = ImageDraw.Draw(world)
    if sc["cab"]:
        draw_cab(d, lt)
    if "beam" in sc["fx"]:
        re_._CANVAS[0] = world
        re_.poly(d, [(250, 1040), (120, 520), (600, 520), (470, 1040)], (255, 240, 170, 55), None, 0)
    if "flicker" in sc["fx"] and int(lt * 24) % 11 == 0:
        world = Image.alpha_composite(world, Image.new("RGBA", world.size, (0, 0, 0, 90)))
    if "speed" in sc["fx"]:
        rr = random.Random(shot["id"] * 13 + int(lt * 30))
        dd = ImageDraw.Draw(world)
        for k in range(10):
            y = 180 + k * 70
            re_.line(dd, [(0, y), (rr.random() * 200, y)], (255, 255, 255, 120), 3)
    if "dust" in sc["fx"]:
        rr = random.Random(shot["id"] * 7 + int(lt * 30))
        dd = ImageDraw.Draw(world)
        for k in range(24):
            px = (rr.random() * 720 + lt * 120) % 720
            py = rr.random() * 1280
            re_.ell(dd, px, py, 3, 3, (230, 220, 200, 110), None)
    if shot.get("sfx_on"):
        re_._CANVAS[0] = world
        dd = ImageDraw.Draw(world)
        for label, x, y, col, rot in sc.get("sfx", []):
            re_.starburst(dd, x, y, 130, col, label, label_size=50, rot=rot)
    return world


def render_frame(shot, t, env_val):
    lt = max(0.0, t - shot["start"])
    dur = shot["end"] - shot["start"]
    world = render_world(shot, lt, env_val)
    warped = re_.camera_warp(world, shot["camera"], lt, dur, (360, 640))
    base = Image.fromarray(warped).convert("RGBA")
    ov = re_.overlays(dict(id=shot["id"], text=shot["text"], highlight=shot["highlight"],
                           banner=shot["banner"], banner_color=shot["banner_color"], end=shot["end"]),
                      lt, dur, t)
    comp = Image.alpha_composite(base, ov).convert("RGB")
    out = np.asarray(comp.resize((W, H), Image.LANCZOS)).astype(np.float32)
    out = out * re_.VIG[..., None]
    out += np.random.normal(0, 3.0, out.shape).astype(np.float32)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def env_array():
    return re_.load_env()


def shot_at(t):
    return scene_of(t)


def cmd_sheet(out_png):
    from PIL import ImageFont
    env = env_array()
    cols = 8
    rows = int(math.ceil(len(SHOTS) / cols))
    tw, th = 180, 320
    gap = 10
    head = 90
    sheet = Image.new("RGB", (cols * (tw + gap) + gap, head + rows * (th + gap + 22) + gap), (14, 12, 18))
    dr = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype(os.path.join(re_.FONT_DIR, "Anton.ttf"), 34)
    dr.text((sheet.width // 2, 36), "LENDAS DO BRASIL #3 · O ÔNIBUS DA MEIA-NOITE — STORYBOARD", font=fnt, fill=(255, 207, 40), anchor="mm")
    dr.text((sheet.width // 2, 70), f"9:16 · {len(SHOTS)} frames · 0.3s–{T['total']:.1f}s · pt-BR", font=ImageFont.truetype(os.path.join(re_.FONT_DIR, "ArchivoBlack.ttf"), 18), fill=(240, 240, 240), anchor="mm")
    small = ImageFont.truetype(os.path.join(re_.FONT_DIR, "ArchivoBlack.ttf"), 12)
    for k, s in enumerate(SHOTS):
        mid = (s["start"] + s["end"]) / 2
        img = render_frame(s, mid, float(env[min(int(mid * FPS), len(env) - 1)]))
        c, r = k % cols, k // cols
        x = gap + c * (tw + gap)
        y = head + r * (th + gap + 22)
        sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y))
        dr.rectangle([x, y, x + tw, y + th], outline=(255, 207, 40), width=2)
        dr.text((x + tw / 2, y + th + 11), f"#{s['id']:02d}  {s['start']:.1f}s", font=small, fill=(230, 230, 230), anchor="mm")
        print("shot", s["id"], flush=True)
    sheet.save(out_png, optimize=True)
    print("saved", out_png, sheet.size, flush=True)


def cmd_video(out_mp4, limit=None):
    env = env_array()
    total = int(round(TOTAL * FPS))
    if limit:
        total = min(total, limit)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", "/tmp/bus/master.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-t", f"{total / FPS:.3f}", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    np.random.seed(7)
    random.seed(7)
    for f in range(total):
        t = f / FPS
        s = shot_at(t)
        img = render_frame(s, t, float(env[min(f, len(env) - 1)]))
        proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
        if f % 300 == 0:
            print("frame", f, "/", total, flush=True)
    proc.stdin.close()
    proc.wait()
    print("done", out_mp4, proc.returncode, flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "sheet":
        cmd_sheet(sys.argv[2])
    elif mode == "video":
        lim = int(os.environ.get("LIMIT", "0")) or None
        cmd_video(sys.argv[2], lim)
    elif mode == "frame":
        t = float(sys.argv[2])
        s = shot_at(t)
        env = env_array()
        render_frame(s, t, float(env[int(t * FPS)])).save(sys.argv[3])
        print("ok", s["id"], s["text"])
    elif mode == "list":
        for s in SHOTS:
            print(s["id"], round(s["start"], 2), round(s["end"], 2), s["camera"], "|", s["banner"], "|", s["text"], "|", s["highlight"])
