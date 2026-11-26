#!/usr/bin/env python3
"""Cardiac action potential teaching animation. Usage: render.py [scene|all] [--still t] """
import sys, math, subprocess, os, random, json
from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS = 1280, 720, 2, 30
OUT = os.path.dirname(os.path.abspath(__file__))
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(sz, b=False): return ImageFont.truetype(FB if b else F, int(sz * S))
BG = (15, 22, 38); PANEL = (24, 34, 58); LINE = (60, 74, 104); TXT = (236, 240, 248); MUTE = (150, 162, 188)
NA = (245, 166, 35); K = (160, 118, 245); CA = (60, 201, 139); ACC = (120, 170, 255); RED = (240, 110, 100)
ION = {"Na": NA, "K": K, "Ca": CA}
LBL = {"Na": "Na⁺", "K": "K⁺", "Ca": "Ca²⁺"}

def P(x, y): return (x * S, y * S)
def ease(u): u = max(0, min(1, u)); return u * u * (3 - 2 * u)
def lerp(a, b, u): return a + (b - a) * u

# ---------- curves (x in 0..1 -> mV) ----------
def v_vent(x):
    if x < .10: return -90
    if x < .13: return lerp(-90, 25, ease((x - .10) / .03))
    if x < .18: return lerp(25, 5, ease((x - .13) / .05))
    if x < .55: return lerp(5, -10, (x - .18) / .37)
    if x < .75: return lerp(-10, -90, ease((x - .55) / .20))
    return -90
def v_pace(x, slope=1.0):
    if x < .35: return -60 + 20 * (x / .35) ** 1.6
    if x < .50: return lerp(-40, 10, ease((x - .35) / .15))
    if x < .75: return lerp(10, -60, ease((x - .50) / .25))
    return min(-40, -60 + 20 * slope * ((x - .75) / .35) ** 1.6)

GX0, GX1, GY0, GY1 = 655, 1225, 120, 560   # plot area
def gy(v): return lerp(GY1, GY0, (v + 100) / 140)
def gx(x): return lerp(GX0, GX1, x)

# ---------- scene scripts ----------
# segment: (dur, x_from, x_to, phase_label, caption, {channel: intensity}, extras)
VENT = dict(title="Ventricular muscle cell", curve=v_vent, labels=[(.05, "4"), (.115, "0"), (.17, "1"), (.36, "2"), (.66, "3"), (.88, "4")],
  channels=[("Na", 130, "Fast Na⁺"), ("K", 270, "K⁺ channels"), ("Ca", 410, "L-type Ca²⁺")],
  segs=[
  (6, 0, .10, "Phase 4 · Resting potential", "The cell rests at about −90 mV. Inward-rectifier K⁺ channels (IK1) stay open, so K⁺ leaks out and keeps the inside negative.", {"K": -.45}, {}),
  (6, .10, .13, "Phase 0 · Rapid upstroke", "A stimulus opens voltage-gated fast Na⁺ channels. Na⁺ rushes in and the cell depolarizes to about +20 mV. Class I antiarrhythmics block these channels.", {"Na": 1}, {}),
  (5, .13, .18, "Phase 1 · Initial repolarization", "Na⁺ channels inactivate, and a brief transient outward K⁺ current (Ito) pulls the voltage down a little.", {"Na": (1, 0), "K": -.7}, {}),
  (8, .18, .55, "Phase 2 · Plateau", "L-type Ca²⁺ channels let Ca²⁺ in, balancing K⁺ going out. This Ca²⁺ triggers more Ca²⁺ release from the sarcoplasmic reticulum, and the cell contracts.", {"Ca": .85, "K": -.55}, {"sr": 1}),
  (6, .55, .75, "Phase 3 · Rapid repolarization", "Ca²⁺ channels close. Delayed-rectifier K⁺ channels (IKr, IKs) carry K⁺ out. Class III drugs block them and prolong the QT interval.", {"Ca": (.85, 0), "K": -1}, {}),
  (7, .75, 1.0, "Back to phase 4", "The Na⁺/K⁺-ATPase restores the ion gradients. The long refractory period (shaded) prevents tetanic contraction of heart muscle.", {"K": -.45}, {"erp": 1}),
])
PACE = dict(title="Pacemaker cell (SA node)", curve=v_pace, labels=[(.17, "4"), (.43, "0"), (.62, "3"), (.86, "4")],
  channels=[("Na", 130, "HCN (funny, If)"), ("Ca", 270, "Ca²⁺ (T, then L-type)"), ("K", 410, "K⁺ channels")],
  segs=[
  (9, 0, .35, "Phase 4 · Slow diastolic depolarization", "No stable resting potential. HCN channels carry the funny current (If, mostly Na⁺ in), then T-type Ca²⁺ channels open. Ivabradine blocks If.", {"Na": .8, "Ca": (0, .5)}, {"thr": 1}),
  (6, .35, .50, "Phase 0 · Upstroke", "At threshold (about −40 mV), L-type Ca²⁺ channels open. Ca²⁺, not fast Na⁺, carries the upstroke, so it is slower. Verapamil and diltiazem slow it.", {"Ca": 1}, {"thr": 1}),
  (6, .50, .75, "Phase 3 · Repolarization", "K⁺ channels open and K⁺ flows out. Pacemaker cells have no phase 1 and no phase 2 plateau.", {"Ca": (1, 0), "K": -1}, {"thr": 1}),
  (9, .75, 1.0, "Heart rate control", "Sympathetic (β1) stimulation increases If and Ca²⁺ current: steeper phase 4, faster rate. Vagal acetylcholine opens K⁺ channels: flatter slope, slower rate.", {"Na": .8}, {"thr": 1, "auto": 1}),
])

rng = random.Random(7)
AMB = [(rng.uniform(50, 540), rng.uniform(150, 300), "Na" if rng.random() < .65 else "Ca") for _ in range(26)] + \
      [(rng.uniform(50, 540), rng.uniform(420, 560), "K") for _ in range(20)]

def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= width * S: cur = t
        else: lines.append(cur); cur = w_
    lines.append(cur); return lines

def dot(d, x, y, r, col, a=1.0):
    c = tuple(int(lerp(PANEL[i], col[i], a)) for i in range(3))
    d.ellipse([*P(x - r, y - r), *P(x + r, y + r)], fill=c)

def channel(d, x, kind, label, inten, t):
    col = ION[kind]; open_ = abs(inten) > .05
    gap = 6 + 10 * min(1, abs(inten))
    c = col if open_ else (90, 100, 124)
    for sgn in (-1, 1):
        x0 = x + sgn * gap
        d.rounded_rectangle([*P(min(x0, x0 + sgn * 18), 326), *P(max(x0, x0 + sgn * 18), 394)], radius=6 * S, fill=c)
    f = font(14)
    d.text(P(x, 410), label, font=f, fill=TXT if open_ else MUTE, anchor="mt")
    if open_:  # particles through pore
        n, a = 6, min(1, abs(inten))
        for i in range(n):
            u = (t * .55 * (0.6 + .6 * a) + i / n) % 1
            y = lerp(170, 540, u) if inten > 0 else lerp(540, 170, u)
            fade = min(1, u * 5, (1 - u) * 5)
            dot(d, x + 3 * math.sin(i * 2.1 + t * 3), y, 8, col, a * fade)
        ay = 300 if inten > 0 else 440
        tri = [(x - 8, ay - 6), (x + 8, ay - 6), (x, ay + 8)] if inten > 0 else [(x - 8, ay + 6), (x + 8, ay + 6), (x, ay - 8)]
        d.polygon([P(*p) for p in tri], fill=col)

def frame(sc, si, u_seg, t):
    im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
    dur, xa, xb, phase, cap, ch, ex = sc["segs"][si]
    xcur = lerp(xa, xb, ease(u_seg) if xb - xa < .1 else u_seg)
    # header
    d.text(P(32, 22), sc["title"], font=font(17), fill=MUTE)
    d.text(P(32, 46), phase, font=font(28, True), fill=TXT)
    # left panel: membrane
    d.rounded_rectangle([*P(24, 100), *P(560, 600)], radius=14 * S, fill=PANEL)
    d.text(P(44, 112), "Outside the cell", font=font(15), fill=MUTE)
    d.text(P(44, 574), "Inside the cell", font=font(15), fill=MUTE, anchor="lb")
    for x, y, k in AMB: dot(d, x, y, 4, ION[k], .45)
    for row in (334, 386):
        for x in range(36, 552, 16): d.ellipse([*P(x - 6, row - 6), *P(x + 6, row + 6)], fill=(196, 170, 120))
    d.rectangle([*P(30, 340), *P(554, 380)], fill=(120, 104, 78))
    for kind, x, label in sc["channels"]:
        v = ch.get(kind, 0)
        if isinstance(v, tuple): v = lerp(v[0], v[1], ease(u_seg))
        if kind == "K" and kind in ch and not isinstance(ch[kind], tuple): v = ch[kind]
        channel(d, x, kind, label, v, t)
    if ex.get("sr"):  # sarcoplasmic reticulum releasing Ca2+
        d.rounded_rectangle([*P(300, 500), *P(530, 550)], radius=20 * S, fill=(40, 70, 64), outline=CA, width=2 * S)
        d.text(P(415, 525), "Sarcoplasmic reticulum", font=font(13), fill=TXT, anchor="mm")
        for i in range(7):
            u = (t * .6 + i / 7) % 1
            dot(d, 320 + i * 32, lerp(495, 440, u), 6, CA, min(1, (1 - u) * 3) * min(1, u_seg * 4))
    # legend
    lx = 44
    for k in ("Na", "K", "Ca"):
        dot(d, lx + 6, 148, 7, ION[k]); d.text(P(lx + 18, 148), LBL[k], font=font(15), fill=TXT, anchor="lm"); lx += 80
    # right panel: graph
    d.rounded_rectangle([*P(580, 100), *P(1256, 600)], radius=14 * S, fill=PANEL)
    for v in (40, 0, -40, -80):
        y = gy(v); d.line([*P(GX0, y), *P(GX1, y)], fill=LINE, width=1 * S)
        d.text(P(GX0 - 10, y), "mV" if v == 40 else (f"{v:+d}" if v else "0"), font=font(13), fill=MUTE, anchor="rm")
    d.text(P((GX0 + GX1) / 2, 582), "time", font=font(13), fill=MUTE, anchor="mm")
    curve = sc["curve"]
    if ex.get("thr"):
        y = gy(-40)
        for x in range(GX0, GX1, 14): d.line([*P(x, y), *P(x + 7, y)], fill=RED, width=2 * S)
        d.text(P(GX0 + 6, y - 6), "threshold −40 mV", font=font(12), fill=RED, anchor="lb")
    if ex.get("erp"):
        a = ease(u_seg * 2)
        x0, x1 = gx(.10), gx(.70)
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rectangle([*P(x0, GY0), *P(x1, GY1)], fill=(120, 170, 255, int(46 * a)))
        im.paste(Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")); d = ImageDraw.Draw(im)
        d.text(P((x0 + x1) / 2, GY1 - 16), "Effective refractory period", font=font(14), fill=(170, 200, 255), anchor="mm")
    if ex.get("auto"):
        a = ease(min(1, u_seg * 1.5))
        for slope, col, lab in ((1.8, (255, 140, 120), "Sympathetic: faster"), (.55, (130, 200, 255), "Vagal: slower")):
            pts = [P(gx(x), gy(v_pace(x, slope))) for x in [ .75 + i * .0025 for i in range(int(100 * a) + 1)]]
            if len(pts) > 1:
                for i in range(0, len(pts) - 1, 2): d.line([pts[i], pts[i + 1]], fill=col, width=3 * S)
        if a > .9:
            d.text(P(gx(.80), gy(-26)), "Sympathetic: faster", font=font(13), fill=(255, 140, 120))
            d.text(P(gx(.80), gy(-66)), "Vagal: slower", font=font(13), fill=(130, 200, 255))
    pts = [P(gx(x), gy(curve(x))) for x in [i / 600 * xcur for i in range(601)]]
    d.line(pts, fill=ACC, width=4 * S, joint="curve")
    cx, cy = gx(xcur), gy(curve(xcur))
    d.ellipse([*P(cx - 8, cy - 8), *P(cx + 8, cy + 8)], fill=(255, 255, 255))
    for lx_, num in sc["labels"]:
        if lx_ <= xcur:
            v = curve(lx_); y = gy(v) - 30 if v > -85 else gy(v) - 26
            if num == "0": y = gy(-20); lx_ -= .03
            d.ellipse([*P(gx(lx_) - 14, y - 14), *P(gx(lx_) + 14, y + 14)], fill=(48, 64, 100))
            d.text(P(gx(lx_), y), num, font=font(16, True), fill=TXT, anchor="mm")
    # caption
    f = font(21); lines = wrap(d, cap, f, 1210)
    for i, ln in enumerate(lines[:3]): d.text(P(36, 620 + i * 31), ln, font=f, fill=TXT)
    return im

def card(lines, u):
    im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
    for (txt, sz, b, col, y) in lines: d.text(P(W / 2, y), txt, font=font(sz, b), fill=col, anchor="mm")
    return im

def summary():
    im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
    d.text(P(W / 2, 54), "Side by side", font=font(32, True), fill=TXT, anchor="mm")
    rows = [("", "Ventricular muscle", "Pacemaker (SA node)"),
            ("Resting / phase 4", "Stable, about −90 mV (IK1)", "Drifts up from about −60 mV (If, T-type Ca²⁺)"),
            ("Phase 0 upstroke", "Fast Na⁺ in: very steep", "L-type Ca²⁺ in: slower"),
            ("Plateau (phase 2)", "Yes: L-type Ca²⁺ in, K⁺ out", "None (no phases 1 or 2)"),
            ("Repolarization", "K⁺ out (IKr, IKs)", "K⁺ out"),
            ("Drugs", "Class I block Na⁺, class III block K⁺", "Class II (β-blockers), class IV (Ca²⁺), ivabradine (If)")]
    y = 110
    for i, (a, b, c) in enumerate(rows):
        h = 84
        if i: d.rounded_rectangle([*P(40, y), *P(1240, y + h - 8)], radius=10 * S, fill=PANEL)
        f = font(19, i == 0)
        d.text(P(64, y + 38), a, font=font(18, True), fill=MUTE if i else TXT, anchor="lm")
        for x, txt in ((330, b), (790, c)):
            ls = wrap(d, txt, font(19, i == 0), 420)
            for j, ln in enumerate(ls): d.text(P(x, y + 38 + (j - (len(ls) - 1) / 2) * 26), ln, font=font(19, i == 0), fill=ACC if i == 0 else TXT, anchor="lm")
        y += h if i else 60
    return im

# Stretch each segment to fit its narration (durations.json from narrate.py).
_DJ = os.path.join(OUT, "durations.json")
DUR = json.load(open(_DJ)) if os.path.exists(_DJ) else {}
for _n, _sc in (("vent", VENT), ("pace", PACE)):
    _sc["segs"] = [(max(s[0], DUR.get(f"{_n}{i}", 0) + 1.1),) + s[1:] for i, s in enumerate(_sc["segs"])]
SCENES = {}
SCENES["title"] = (max(4, DUR.get("title", 0) + 1.3), lambda t: card([("The Cardiac Action Potential", 46, True, TXT, 320), ("Ventricular muscle cell vs. pacemaker cell", 24, False, MUTE, 385), ("Step1 Fast Track", 18, False, ACC, 640)], t))
def sc_fn(sc):
    total = sum(s[0] for s in sc["segs"])
    def f(t):
        acc = 0
        for i, s in enumerate(sc["segs"]):
            if t < acc + s[0] or i == len(sc["segs"]) - 1: return frame(sc, i, min(1, (t - acc) / s[0]), t)
            acc += s[0]
    return total, f
SCENES["vent"] = sc_fn(VENT); SCENES["pace"] = sc_fn(PACE)
SCENES["summary"] = (max(9, DUR.get("summary", 0) + 2), lambda t: summary())
ORDER = ["title", "vent", "pace", "summary"]

def fade(im, t, dur):
    a = min(1, t / .5, (dur - t) / .5)
    if a >= 1: return im
    return Image.blend(Image.new("RGB", im.size, (0, 0, 0)), im, max(0, a))

def render(name):
    dur, fn = SCENES[name]; tmp = f"{OUT}/{name}.part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    static = None
    for i in range(int(dur * FPS)):
        t = i / FPS
        if name in ("title", "summary"):
            static = static or fn(0).resize((W, H), Image.LANCZOS); im = static
        else: im = fn(t).resize((W, H), Image.LANCZOS)
        p.stdin.write(fade(im, t, dur).tobytes())
    p.stdin.close()
    if p.wait() == 0: os.replace(tmp, f"{OUT}/{name}.mp4")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--still":
        name = sys.argv[1]; t = float(sys.argv[3]); SCENES[name][1](t).resize((W, H), Image.LANCZOS).save(f"{OUT}/still_{name}_{t}.png")
    else:
        for n in (ORDER if sys.argv[1] == "all" else [sys.argv[1]]): render(n); print("done", n)
