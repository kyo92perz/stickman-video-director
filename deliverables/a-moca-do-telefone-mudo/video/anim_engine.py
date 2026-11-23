#!/usr/bin/env python3
"""Small 2D keyframe animation engine for stickman-style characters.

Concepts
- Rig: articulated skeleton (hip, spine, neck/head, two arms, two legs) solved with
  forward kinematics from joint angles. Angles are in degrees.
- Keyframes: a list of (time, pose_dict). Numeric values are interpolated with a
  smootherstep ease; string values (expressions) switch at the next key.
- Secondary motion: idle breathing, head follow-through (damped spring toward the
  torso lean), squash/stretch of the body from vertical velocity of the hip.
- Camera: keyframed zoom and centre, applied as crop + resize on the whole world.
- Props: plain functions taking (draw, t, state) and placing shapes in world space.

Coordinates: world is W x H pixels (720 x 1280). Angles: 0 = limb straight down,
positive = counter-clockwise toward the figure's back (x+ on screen = right).
"""
import math
from PIL import Image, ImageDraw

W, H = 720, 1280
BLACK = (18, 14, 16)
WHITE = (255, 255, 255)

# default proportions at scale 1.0
UPPER_ARM, FORE_ARM = 92.0, 84.0
THIGH, SHIN = 118.0, 118.0
SPINE, NECK, HEAD_R = 170.0, 26.0, 70.0


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def dir_down(a):
    r = math.radians(a)
    return (math.sin(r), math.cos(r))


def dir_up(a):
    r = math.radians(a)
    return (math.sin(r), -math.cos(r))


def add(p, v, k):
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def interp_pose(keys, t):
    """keys: list of (time, dict). Returns an interpolated dict for time t."""
    if t <= keys[0][0]:
        return dict(keys[0][1])
    if t >= keys[-1][0]:
        return dict(keys[-1][1])
    for (ta, pa), (tb, pb) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            u = ease((t - ta) / max(1e-6, tb - ta))
            out = {}
            for k in set(pa) | set(pb):
                a, b = pa.get(k, pb.get(k)), pb.get(k, pa.get(k))
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    out[k] = a + (b - a) * u
                else:
                    out[k] = b if u >= 0.5 else a
            return out
    return dict(keys[-1][1])


class Rig:
    """Solves a pose into joint positions and draws the figure."""

    def __init__(self, s=1.0):
        self.s = s

    def solve(self, p):
        s = self.s
        hip = (p["x"], p["y"])
        lean = p["lean"] + p.get("breath", 0.0)
        sh = add(hip, dir_up(lean), SPINE * s)
        head_c = add(sh, dir_up(lean + p["tilt"]), (NECK + HEAD_R) * s)
        j = {"hip": hip, "sh": sh, "head": head_c, "lean": lean}
        for side in ("r", "l"):
            a1, a2 = p["arm_" + side + "1"], p["arm_" + side + "2"]
            el = add(sh, dir_down(a1), UPPER_ARM * s)
            wr = add(el, dir_down(a1 + a2), FORE_ARM * s)
            j["el_" + side], j["wr_" + side] = el, wr
            l1, l2 = p["leg_" + side + "1"], p["leg_" + side + "2"]
            kn = add(hip, dir_down(l1), THIGH * s)
            an = add(kn, dir_down(l1 + l2), SHIN * s)
            j["kn_" + side], j["an_" + side] = kn, an
        return j

    def draw(self, d, p, expr=None, phone_in_hand=None):
        s = self.s
        j = self.solve(p)
        ink = max(3, int(15 * s))
        def limb(pts, w=ink):
            d.line(pts, fill=BLACK, width=w, joint="curve")
            r = w / 2
            for x, y in (pts[0], pts[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)
        # back limbs first (left), then torso, then front limbs (right)
        limb([j["hip"], j["kn_l"], j["an_l"]])
        limb([j["hip"], j["kn_r"], j["an_r"]])
        d.ellipse([j["an_l"][0] - 26 * s, j["an_l"][1] - 6 * s, j["an_l"][0] + 16 * s, j["an_l"][1] + 8 * s], fill=BLACK)
        d.ellipse([j["an_r"][0] - 16 * s, j["an_r"][1] - 6 * s, j["an_r"][0] + 26 * s, j["an_r"][1] + 8 * s], fill=BLACK)
        # torso as a tapered shirt
        sh, hip = j["sh"], j["hip"]
        torso_w = 58 * s
        ln = p["lean"] + p.get("breath", 0.0)
        perp = dir_up(ln + 90)
        body = [add(sh, perp, torso_w), add(sh, perp, -torso_w),
                add(hip, perp, -torso_w * 0.85), add(hip, perp, torso_w * 0.85)]
        if p.get("skirt"):
            sk = p["skirt"]
            d.polygon([add(hip, perp, -torso_w * 0.9), add(hip, perp, torso_w * 0.9),
                       add(hip, dir_down(0), 150 * s + sk * 60 * s), add(hip, dir_down(0), 150 * s)],
                      fill=p.get("skirt_color", (60, 60, 70)), outline=BLACK)
        d.polygon(body, fill=p.get("shirt", (70, 110, 170)), outline=BLACK)
        d.line([sh, j["head"]], fill=BLACK, width=max(2, int(12 * s)))
        # front limbs
        limb([sh, j["el_r"], j["wr_r"]])
        if phone_in_hand is not None:
            pass
        r = max(4, 8 * s)
        d.ellipse([j["wr_r"][0] - r, j["wr_r"][1] - r, j["wr_r"][0] + r, j["wr_r"][1] + r], fill=BLACK)
        # head
        hc = j["head"]
        hr = HEAD_R * s
        d.ellipse([hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr], fill=WHITE, outline=BLACK, width=max(3, int(6 * s)))
        hair = p.get("hair", (92, 56, 34))
        if p.get("bun"):
            d.ellipse([hc[0] - 28 * s, hc[1] - hr - 24 * s, hc[0] + 28 * s, hc[1] - hr + 14 * s], fill=hair, outline=BLACK, width=3)
        d.chord([hc[0] - hr - 4, hc[1] - hr - 6, hc[0] + hr + 4, hc[1] + 2 * s], 180, 360, fill=hair, outline=BLACK, width=3)
        self._face(d, hc, s, expr or p.get("expr", "neutral"), p)
        # arm holding the phone is drawn after the head so the hand stays visible
        return j

    def _face(self, d, c, s, expr, p):
        bw = max(3, int(6 * s))
        ex = 26 * s
        ey = -6 * s
        er = 12 * s if expr in ("scared", "shock") else 7 * s
        for sx in (-1, 1):
            x, y = c[0] + sx * ex, c[1] + ey
            d.ellipse([x - er, y - er, x + er, y + er], fill=BLACK)
        if expr == "skeptical":
            d.line([(c[0] - 44 * s, c[1] - 26 * s), (c[0] - 10 * s, c[1] - 24 * s)], fill=BLACK, width=bw)
            d.line([(c[0] + 10 * s, c[1] - 38 * s), (c[0] + 44 * s, c[1] - 30 * s)], fill=BLACK, width=bw)
            d.line([(c[0] - 22 * s, c[1] + 34 * s), (c[0] + 22 * s, c[1] + 30 * s)], fill=BLACK, width=bw)
        elif expr == "smirk":
            d.arc([c[0] - 26 * s, c[1] + 18 * s, c[0] + 26 * s, c[1] + 44 * s], 20, 160, fill=BLACK, width=bw)
        elif expr in ("scared", "shock"):
            d.ellipse([c[0] - 12 * s, c[1] + 28 * s, c[0] + 12 * s, c[1] + 50 * s], fill=BLACK)
        elif expr == "worried":
            d.arc([c[0] - 22 * s, c[1] + 36 * s, c[0] + 22 * s, c[1] + 56 * s], 200, 340, fill=BLACK, width=bw)
        elif expr == "talk":
            open_ = 0.5 + 0.5 * math.sin(p.get("_t", 0) * 28)
            hh = (6 + 14 * open_) * s
            d.ellipse([c[0] - 14 * s, c[1] + 34 * s, c[0] + 14 * s, c[1] + 34 * s + hh], fill=BLACK)
        else:
            d.line([(c[0] - 18 * s, c[1] + 36 * s), (c[0] + 18 * s, c[1] + 36 * s)], fill=BLACK, width=bw)


class Camera:
    def __init__(self, keys):
        # keys: (t, zoom, cx, cy)
        self.keys = keys

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1:]
        if t >= ks[-1][0]:
            return ks[-1][1:]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t <= b[0]:
                u = ease((t - a[0]) / max(1e-6, b[0] - a[0]))
                return tuple(a[i] + (b[i] - a[i]) * u for i in (1, 2, 3))
        return ks[-1][1:]


class HeadSpring:
    """Damped spring for head tilt: follow-through lags behind the torso."""

    def __init__(self, k=60.0, c=9.0):
        self.k, self.c = k, c
        self.x, self.v = 0.0, 0.0

    def step(self, target, dt):
        a = self.k * (target - self.x) - self.c * self.v
        self.v += a * dt
        self.x += self.v * dt
        return self.x


def breath(t, amp=1.2, hz=0.35):
    return amp * math.sin(2 * math.pi * hz * t)


def render_world(bg_img, actors, props, t, cam):
    """actors: list of (Rig, pose_dict, expr); props: list of callables(d, t)."""
    img = bg_img.copy()
    d = ImageDraw.Draw(img)
    for fn in props.get("back", []):
        fn(d, t)
    for rig, pose, expr in actors:
        rig.draw(d, pose, expr=expr)
    for fn in props.get("front", []):
        fn(d, t)
    zoom, cx, cy = cam
    cw, ch = W / zoom, H / zoom
    x0 = min(max(0, cx - cw / 2), W - cw)
    y0 = min(max(0, cy - ch / 2), H - ch)
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)
