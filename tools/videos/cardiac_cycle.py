#!/usr/bin/env python3
"""Cardiac cycle + pressure-volume loop narrated animation.
Usage: make.py vo | make.py render | make.py mux | make.py still <scene> <t>"""
import sys, math, subprocess, os, json
from PIL import Image, ImageDraw, ImageFont
W, H, S, FPS = 1280, 720, 2, 30
OUT = os.path.dirname(os.path.abspath(__file__)); TTS = "/home/claude/tts"
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(sz, b=False): return ImageFont.truetype(FB if b else F, int(sz * S))
BG = (15, 22, 38); PANEL = (24, 34, 58); LINE = (60, 74, 104); TXT = (236, 240, 248); MUTE = (150, 162, 188)
AO = (240, 96, 96); LVC = (110, 168, 255); LAC = (245, 170, 60); VOL = (70, 200, 140); BLOOD = (214, 64, 72)
def P(x, y): return (x * S, y * S)
def ease(u): u = max(0, min(1, u)); return u * u * (3 - 2 * u)
def lerp(a, b, u): return a + (b - a) * u
def clamp(u): return max(0, min(1, u))

# ---------- physiology model (x = fraction of one beat) ----------
X_AS, X_IVC, X_EJ, X_IVR, X_F = 0.0, .10, .16, .45, .53
BASE = dict(EDV=120, ESV=50, EDP=10, DBP=80, PK=122, ESP=100)
def lvV(x, p=BASE):
    EDV, ESV = p["EDV"], p["ESV"]; Vd = ESV + .86 * (EDV - ESV)
    if x < X_IVC: return lerp(Vd, EDV, ease(x / X_IVC))
    if x < X_EJ: return EDV
    if x < X_IVR: t = (x - X_EJ) / (X_IVR - X_EJ); return EDV - (EDV - ESV) * (1 - (1 - t) ** 2.2)
    if x < X_F: return ESV
    t = (x - X_F) / (1 - X_F); return ESV + (Vd - ESV) * (1 - math.exp(-5 * t)) / (1 - math.exp(-5))
def pfill(V, p=BASE):
    u = clamp((V - p["ESV"]) / (p["EDV"] - p["ESV"])); return 3 + (p["EDP"] - 3) * u ** 2.5
def lvP(x, p=BASE):
    if x < X_IVC or x >= X_F: return pfill(lvV(x, p), p)
    if x < X_EJ: return lerp(p["EDP"], p["DBP"], ease((x - X_IVC) / (X_EJ - X_IVC)))
    if x < X_IVR:
        t = (x - X_EJ) / (X_IVR - X_EJ); bump = p["PK"] - (p["DBP"] + p["ESP"]) / 2
        return lerp(p["DBP"], p["ESP"], t) + bump * math.sin(math.pi * t ** 0.55)
    return lerp(p["ESP"], 3, ease((x - X_IVR) / (X_F - X_IVR)))
def aoP(x, p=BASE):
    if X_EJ <= x < X_IVR: return max(p["DBP"], lvP(x, p) - 2)
    w = ((x - X_IVR) if x >= X_IVR else (x + 1 - X_IVR)) / (1 + X_EJ - X_IVR)
    a = p["DBP"] + (p["ESP"] - 2 - p["DBP"]) * (math.exp(-3 * w) - math.exp(-3)) / (1 - math.exp(-3))
    if X_IVR <= x < X_IVR + .04: a -= 6 * math.sin(math.pi * (x - X_IVR) / .04)
    return a
def laP(x, p=BASE):
    if x < X_IVC: return pfill(lvV(x, p), p) + 1.5 + 4 * math.sin(math.pi * x / X_IVC)
    if x < X_EJ: return 6 + 2.5 * math.sin(math.pi * (x - X_IVC) / (X_EJ - X_IVC))
    if x < X_IVR: return lerp(4, 12, (x - X_EJ) / (X_IVR - X_EJ))
    if x < X_F: return lerp(12, 13.5, (x - X_IVR) / (X_F - X_IVR))
    return max(pfill(lvV(x, p), p) + 1.5, 13.5 - 10 * clamp((x - X_F) / .09))
def mitral_open(x): return x < X_IVC or x >= X_F
def aortic_open(x): return X_EJ <= x < X_IVR

# ---------- script ----------
CC = [  # (key, x_from, x_to, phase title, caption)
 ("cc0", 0, X_IVC, "Atrial contraction", "Late in diastole the left atrium contracts (P wave on the ECG). It tops up the ventricle, adding the last 10–20% of its filling. Mitral valve open, aortic valve closed."),
 ("cc1", X_IVC, X_EJ, "Isovolumetric contraction", "The ventricle contracts (after the QRS). LV pressure rises above atrial pressure and the mitral valve closes: S1. Both valves are closed, so volume stays the same while pressure climbs fast."),
 ("cc2", X_EJ, X_IVR, "Ventricular ejection", "When LV pressure exceeds aortic pressure (about 80 mm Hg), the aortic valve opens. Blood is ejected; LV and aortic pressure peak near 120 mm Hg and LV volume falls from 120 to 50 mL."),
 ("cc3", X_IVR, X_F, "Isovolumetric relaxation", "The ventricle relaxes. When LV pressure falls below aortic pressure, the aortic valve closes: S2, seen as the dicrotic notch. Both valves are closed again and volume stays at 50 mL."),
 ("cc4", X_F, 1.0, "Ventricular filling", "When LV pressure drops below atrial pressure, the mitral valve opens. Rapid filling comes first (an S3 here suggests volume overload), then slow filling, and the cycle repeats."),
]
PRE = dict(BASE, EDV=150, ESV=52, EDP=16, PK=130, ESP=106)
AFT = dict(BASE, DBP=110, PK=158, ESP=140, ESV=66)
CON = dict(BASE, ESV=28, PK=138, ESP=104)
PV = [  # (key, loop-draw x range or None, title, caption, compare params, label)
 ("pv0", (X_F, 1.0 + X_EJ), "The pressure-volume loop", "Plot LV pressure against LV volume through one beat. Filling runs along the bottom to end-diastolic volume (A, mitral closes). Isovolumetric contraction rises straight up to B (aortic valve opens).", None, ""),
 ("pv1", (X_EJ, X_F), "Ejection and relaxation", "From B the ventricle ejects to C (aortic valve closes), then relaxes straight down to D (mitral opens). Loop width = stroke volume, 70 mL. Ejection fraction = 70/120, about 58%.", None, ""),
 ("pv2", None, "Increased preload", "More venous return (IV fluids, volume overload) moves end-diastolic volume to the right. By the Frank-Starling law the heart ejects more: a wider loop and a larger stroke volume.", PRE, "↑ Preload"),
 ("pv3", None, "Increased afterload", "Higher aortic pressure (hypertension, aortic stenosis) makes the ventricle reach a higher pressure before the valve opens. It ejects less: a taller, narrower loop with a larger end-systolic volume.", AFT, "↑ Afterload"),
 ("pv4", None, "Increased contractility", "Sympathetic stimulation or inotropes (dobutamine, digoxin) make the end-systolic pressure-volume line steeper. The ventricle empties more: smaller end-systolic volume, larger stroke volume.", CON, "↑ Contractility"),
]
NARR = {
 "title": "The cardiac cycle and the pressure volume loop. We will follow the left side of the heart through one heartbeat, then see how the same beat looks as a loop.",
 "cc0": "We start late in diastole. The ventricle is already mostly full from passive filling. Now the left atrium contracts, which follows the P wave on the E C G. This atrial kick adds the last ten to twenty percent of filling. The mitral valve is open and the aortic valve is closed.",
 "cc1": "Next, the ventricle begins to contract, just after the Q R S complex. As soon as left ventricular pressure rises above atrial pressure, the mitral valve snaps shut. That is the first heart sound, S one. Now both valves are closed, so the volume cannot change, but the pressure climbs very fast. This is isovolumetric contraction.",
 "cc2": "When left ventricular pressure exceeds aortic pressure, about eighty millimeters of mercury, the aortic valve opens and blood is ejected. Ventricular and aortic pressures rise together to a peak of about one hundred twenty. Ventricular volume falls from about one hundred twenty to fifty milliliters.",
 "cc3": "As the ventricle starts to relax, its pressure falls below aortic pressure, and the aortic valve closes. That is the second heart sound, S two, and it makes the small dicrotic notch on the aortic pressure curve. With both valves closed again, pressure drops quickly at a constant volume. This is isovolumetric relaxation.",
 "cc4": "When ventricular pressure falls below atrial pressure, the mitral valve opens and filling begins. Rapid filling comes first. A third heart sound here suggests volume overload, as in heart failure. Then filling slows down, and the cycle starts again.",
 "pv0": "Now let's plot the same beat as left ventricular pressure against volume. Filling runs along the bottom of the loop, from left to right, until end diastolic volume at point A, where the mitral valve closes. Isovolumetric contraction is a straight vertical line up to point B, where the aortic valve opens.",
 "pv1": "From B, the ventricle ejects blood, moving to the left across the top of the loop to point C, where the aortic valve closes. Isovolumetric relaxation drops straight down to point D, where the mitral valve opens. The width of the loop is the stroke volume, about seventy milliliters. Ejection fraction is stroke volume divided by end diastolic volume, about fifty eight percent.",
 "pv2": "Increased preload, for example from I V fluids or volume overload, moves end diastolic volume to the right. By the Frank Starling law, the stretched ventricle contracts more forcefully, so the loop gets wider and stroke volume increases.",
 "pv3": "Increased afterload, for example from hypertension or aortic stenosis, means the ventricle must reach a higher pressure before the aortic valve opens. It ejects less blood, so the loop becomes taller and narrower, and end systolic volume increases.",
 "pv4": "Increased contractility, from sympathetic stimulation or drugs such as dobutamine and digoxin, makes the end systolic pressure volume line steeper. The ventricle empties more completely, so end systolic volume falls and stroke volume rises.",
 "summary": "To summarize. S one marks mitral closure at the start of systole, and S two marks aortic closure at the end. On the loop, preload changes the width on the right side, afterload raises the top, and contractility moves the left side.",
}
DUR = json.load(open(f"{OUT}/durations.json")) if os.path.exists(f"{OUT}/durations.json") else {}
def segdur(k, mn=6): return max(mn, DUR.get(k, 0) + 1.1)

def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= width * S: cur = t
        else: lines.append(cur); cur = w_
    lines.append(cur); return lines
def caption(d, text):
    f = font(20);
    for i, ln in enumerate(wrap(d, text, f, 1210)[:3]): d.text(P(36, 616 + i * 29), ln, font=f, fill=TXT)
def header(d, small, big):
    d.text(P(32, 20), small, font=font(17), fill=MUTE); d.text(P(32, 44), big, font=font(28, True), fill=TXT)

# ---------- heart diagram (left panel) ----------
def heart(d, x, t, p=BASE, label_events=True):
    d.rounded_rectangle([*P(24, 100), *P(470, 600)], radius=14 * S, fill=PANEL)
    V = lvV(x % 1, p); r = 0.6 + 0.4 * (V - 40) / 110
    cx, cy = 230, 392; w, h = 140 * r, 104 * r
    # LV
    d.ellipse([*P(cx - w, cy - h * .55), *P(cx + w * .9, cy + h)], fill=(120, 40, 52), outline=(220, 120, 130), width=3 * S)
    d.text(P(cx - 10, cy + 20), "LV", font=font(22, True), fill=TXT, anchor="mm")
    # LA
    d.rounded_rectangle([*P(70, 150), *P(220, 255)], radius=30 * S, fill=(110, 46, 56), outline=(220, 120, 130), width=3 * S)
    d.text(P(145, 202), "LA", font=font(22, True), fill=TXT, anchor="mm")
    # aorta
    d.rounded_rectangle([*P(300, 150), *P(370, cy - h * .45 + 6)], radius=12 * S, fill=(110, 46, 56), outline=(220, 120, 130), width=3 * S)
    d.text(P(335, 135), "Aorta", font=font(16, True), fill=TXT, anchor="mm")
    # valves
    mo, ao = mitral_open(x % 1), aortic_open(x % 1)
    for (vx, vy, op, name) in ((145, 268, mo, "Mitral"), (335, cy - h * .45 - 2, ao, "Aortic")):
        col = (90, 220, 150) if op else (250, 210, 90)
        if op: d.line([*P(vx - 26, vy - 4), *P(vx - 16, vy + 16)], fill=col, width=5 * S); d.line([*P(vx + 26, vy - 4), *P(vx + 16, vy + 16)], fill=col, width=5 * S)
        else: d.line([*P(vx - 26, vy), *P(vx + 26, vy)], fill=col, width=6 * S)
        d.text(P(44, 516 if name == "Mitral" else 540), f"{name} valve: {'open' if op else 'closed'}", font=font(15, True), fill=col, anchor="lm")
    # flow particles
    flows = []
    if mo and (x % 1 < X_IVC or (x % 1) < X_F + .2): flows.append((145, 240, 145, 330))
    if ao: flows.append((335, cy - 30, 335, 170))
    for (x0, y0, x1, y1) in flows:
        for i in range(5):
            u = (t * .9 + i / 5) % 1; a = min(1, u * 4, (1 - u) * 4)
            px, py = lerp(x0, x1, u), lerp(y0, y1, u); c = tuple(int(lerp(PANEL[k], BLOOD[k], a)) for k in range(3))
            d.ellipse([*P(px - 6, py - 6), *P(px + 6, py + 6)], fill=c)
    # readouts
    d.text(P(44, 566), f"LV {lvP(x % 1, p):.0f} mm Hg   ·   {V:.0f} mL", font=font(16), fill=TXT)
    # heart sounds flash
    if label_events:
        for xe, s_ in ((X_IVC, "S1"), (X_IVR, "S2")):
            dx = (x % 1) - xe
            if 0 <= dx < .05:
                a = 1 - dx / .05; c = tuple(int(lerp(PANEL[k], (255, 255, 255)[k], a)) for k in range(3))
                d.text(P(410, 470), s_, font=font(40, True), fill=c, anchor="mm")

# ---------- Wiggers graph (right panel) ----------
GX0, GX1 = 560, 1225
def wig(d, xcur, highlight):
    d.rounded_rectangle([*P(490, 100), *P(1256, 600)], radius=14 * S, fill=PANEL)
    PY0, PY1, VY0, VY1 = 125, 400, 450, 570
    gy = lambda v: lerp(PY1, PY0, v / 140); vy = lambda v: lerp(VY1, VY0, (v - 40) / 100); gx = lambda x: lerp(GX0, GX1, x)
    for (a, b, name) in ((X_AS, X_IVC, ""), (X_IVC, X_EJ, ""), (X_EJ, X_IVR, ""), (X_IVR, X_F, ""), (X_F, 1, "")):
        if a <= highlight < b or (highlight == 1 and b == 1 and a == X_F):
            d.rectangle([*P(gx(a), PY0 - 10), *P(gx(b), VY1)], fill=(34, 48, 80))
    for v in (0, 40, 80, 120):
        d.line([*P(GX0, gy(v)), *P(GX1, gy(v))], fill=LINE, width=S); d.text(P(GX0 - 8, gy(v)), str(v), font=font(12), fill=MUTE, anchor="rm")
    d.text(P(GX0 - 8, PY0 - 14), "mm Hg", font=font(12), fill=MUTE, anchor="rm")
    for v in (50, 120):
        d.line([*P(GX0, vy(v)), *P(GX1, vy(v))], fill=LINE, width=S); d.text(P(GX0 - 8, vy(v)), str(v), font=font(12), fill=MUTE, anchor="rm")
    d.text(P(GX0 - 8, VY0 - 14), "mL", font=font(12), fill=MUTE, anchor="rm")
    for xe, lab in ((X_IVC, "Mitral closes · S1"), (X_EJ, "Aortic opens"), (X_IVR, "Aortic closes · S2"), (X_F, "Mitral opens")):
        if xe <= xcur:
            for yy in range(PY0, VY1, 12): d.line([*P(gx(xe), yy), *P(gx(xe), yy + 6)], fill=(110, 124, 156), width=S)
    n = max(2, int(500 * xcur))
    xs = [xcur * i / n for i in range(n + 1)]
    for fn, col, gyf in ((aoP, AO, gy), (lvP, LVC, gy), (laP, LAC, gy), (lvV, VOL, vy)):
        d.line([P(gx(x), gyf(fn(x))) for x in xs], fill=col, width=3 * S, joint="curve")
        d.ellipse([*P(gx(xcur) - 6, gyf(fn(xcur)) - 6), *P(gx(xcur) + 6, gyf(fn(xcur)) + 6)], fill=col)
    lx = 600
    for col, lab in ((AO, "Aortic pressure"), (LVC, "LV pressure"), (LAC, "LA pressure"), (VOL, "LV volume")):
        d.rounded_rectangle([*P(lx, 418), *P(lx + 18, 426)], radius=3 * S, fill=col); d.text(P(lx + 24, 422), lab, font=font(13), fill=TXT, anchor="lm"); lx += 160
    # event labels at top
    for xe, lab in ((X_IVC, "S1"), (X_IVR, "S2")):
        if xe <= xcur: d.text(P(gx(xe), PY0 - 4), lab, font=font(14, True), fill=TXT, anchor="mb")

# ---------- PV loop (right panel) ----------
def pvpanel(d, base_x, cmp=None, cu=0, lab=""):
    d.rounded_rectangle([*P(490, 100), *P(1256, 600)], radius=14 * S, fill=PANEL)
    X0, X1, Y0, Y1 = 600, 1200, 130, 540
    px = lambda v: lerp(X0, X1, v / 180); py = lambda p: lerp(Y1, Y0, p / 180)
    for v in (0, 50, 100, 150):
        d.line([*P(px(v), Y0), *P(px(v), Y1)], fill=LINE, width=S); d.text(P(px(v), Y1 + 14), str(v), font=font(12), fill=MUTE, anchor="mm")
    for p_ in (0, 40, 80, 120, 160):
        d.line([*P(X0, py(p_)), *P(X1, py(p_))], fill=LINE, width=S); d.text(P(X0 - 8, py(p_)), str(p_), font=font(12), fill=MUTE, anchor="rm")
    d.text(P((X0 + X1) / 2, Y1 + 36), "LV volume (mL)", font=font(14), fill=MUTE, anchor="mm")
    d.text(P(X0 - 8, Y0 - 16), "LV pressure (mm Hg)", font=font(14), fill=MUTE, anchor="lm")
    def esp(p, col, dash=False):  # end-systolic pressure-volume relationship line
        V0 = 10; k = p["ESP"] / (p["ESV"] - V0); a, b = (V0, 0), (V0 + 170 / k, 170)
        pts = [P(px(lerp(a[0], b[0], i / 40)), py(lerp(a[1], b[1], i / 40))) for i in range(41)]
        for i in range(0, 40, 2): d.line([pts[i], pts[i + 1]], fill=col, width=2 * S)
    def edp():
        pts = [P(px(v), py(pfill(v) if v <= 120 else pfill(120) * math.exp((v - 120) / 32))) for v in range(50, 171, 4)]
        for i in range(0, len(pts) - 1, 2): d.line([pts[i], pts[i + 1]], fill=(120, 132, 160), width=2 * S)
    edp(); esp(BASE, (160, 172, 200))
    d.text(P(px(14), py(64)), "ESPVR", font=font(12), fill=MUTE); d.text(P(px(150), py(36)), "EDPVR", font=font(12), fill=MUTE)
    a, b = base_x
    n = max(2, int(400 * (b - a)))
    pts = [P(px(lvV(lerp(a, b, i / n) % 1)), py(lvP(lerp(a, b, i / n) % 1))) for i in range(n + 1)]
    d.line(pts, fill=LVC, width=4 * S, joint="curve")
    if cmp is None: d.ellipse([pts[-1][0] - 7 * S, pts[-1][1] - 7 * S, pts[-1][0] + 7 * S, pts[-1][1] + 7 * S], fill=(255, 255, 255))
    for xe, L, dx, dy in ((X_IVC, "A", 14, 8), (X_EJ, "B", 14, -4), (X_IVR, "C", -16, -14), (X_F, "D", -16, 10)):
        xx = xe if xe >= a else xe + 1
        if a <= xx <= b or (cmp is not None):
            d.text(P(px(lvV(xe)) + dx, py(lvP(xe)) + dy), L, font=font(18, True), fill=TXT, anchor="mm")
    if cmp is not None:
        if cmp is CON: esp(cmp, (255, 190, 90))
        n = int(400 * cu); col = (255, 190, 90)
        pts = [P(px(lvV(i / 400, cmp)), py(lvP(i / 400, cmp))) for i in range(n + 1)]
        if len(pts) > 1:
            for i in range(0, len(pts) - 1, 3): d.line([pts[i], pts[min(i + 2, len(pts) - 1)]], fill=col, width=4 * S)
        d.text(P(1190, 150), lab, font=font(20, True), fill=col, anchor="rm")
        sv0, sv1 = BASE["EDV"] - BASE["ESV"], cmp["EDV"] - cmp["ESV"]
        if cu > .95:
            d.text(P(1190, 182), f"Stroke volume {sv0} → {sv1} mL", font=font(15), fill=TXT, anchor="rm")
            d.text(P(1190, 206), f"End-systolic volume {BASE['ESV']} → {cmp['ESV']} mL", font=font(15), fill=TXT, anchor="rm")
    elif b - a >= .999:
        sv = BASE["EDV"] - BASE["ESV"]
        d.line([*P(px(BASE["ESV"]), py(-6) - 10), *P(px(BASE["EDV"]), py(-6) - 10)], fill=VOL, width=3 * S)
        d.text(P(px(85), py(-6) - 24), f"Stroke volume {sv} mL · EF {round(100 * sv / BASE['EDV'])}%", font=font(15, True), fill=VOL, anchor="mm")

# ---------- scenes ----------
def sc_cc():
    segs = [(segdur(k), a, b, ttl, cap) for k, a, b, ttl, cap in CC]
    total = sum(s[0] for s in segs)
    def f(t):
        acc = 0
        for i, (du, a, b, ttl, cap) in enumerate(segs):
            if t < acc + du or i == len(segs) - 1:
                u = clamp((t - acc) / du); x = lerp(a, b, u)
                im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
                header(d, "The cardiac cycle · left heart", ttl); heart(d, x, t); wig(d, x, (a + b) / 2); caption(d, cap); return im
            acc += du
    return total, f
def sc_pv():
    segs = [(segdur(k, 7), rng, ttl, cap, cmp, lab) for k, rng, ttl, cap, cmp, lab in PV]
    total = sum(s[0] for s in segs)
    def f(t):
        acc = 0
        for i, (du, rng, ttl, cap, cmp, lab) in enumerate(segs):
            if t < acc + du or i == len(segs) - 1:
                u = clamp((t - acc) / du)
                im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
                header(d, "Pressure-volume loop", ttl)
                if rng: a, b = rng; x = lerp(a, b, u); bx = (X_F, X_F + (x - X_F)) if i == 0 else (X_F, 1 + X_F) if False else (X_F, 1 + X_EJ + (x - X_EJ))
                if i == 0: heart(d, x % 1, t); pvpanel(d, (X_F, x))
                elif i == 1: heart(d, x, t); pvpanel(d, (X_F, 1 + x))
                else:
                    xx = (t * .35) % 1; heart(d, xx, t, cmp, False); pvpanel(d, (0, 1), cmp, ease(min(1, u * 1.6)), lab)
                caption(d, cap); return im
            acc += du
    return total, f
def card_title(t):
    im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
    d.text(P(W / 2, 300), "The Cardiac Cycle", font=font(46, True), fill=TXT, anchor="mm")
    d.text(P(W / 2, 362), "and the Pressure-Volume Loop", font=font(30), fill=TXT, anchor="mm")
    d.text(P(W / 2, 420), "Valves, heart sounds, and preload, afterload and contractility", font=font(20), fill=MUTE, anchor="mm")
    d.text(P(W / 2, 640), "Step1 Fast Track", font=font(18), fill=LVC, anchor="mm"); return im
def card_sum(t):
    im = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(im)
    d.text(P(W / 2, 56), "Key points", font=font(32, True), fill=TXT, anchor="mm")
    rows = [("S1", "Mitral (and tricuspid) closure: start of isovolumetric contraction"),
            ("S2", "Aortic (and pulmonic) closure: start of isovolumetric relaxation; dicrotic notch"),
            ("Loop", "Width = stroke volume; EF = SV / EDV (normal 55–70%)"),
            ("↑ Preload", "Loop wider to the right, ↑ SV (Frank-Starling)"),
            ("↑ Afterload", "Loop taller and narrower, ↑ ESV, ↓ SV"),
            ("↑ Contractility", "Steeper ESPVR, ↓ ESV, ↑ SV")]
    y = 112
    for a, b in rows:
        d.rounded_rectangle([*P(60, y), *P(1220, y + 70)], radius=10 * S, fill=PANEL)
        d.text(P(86, y + 35), a, font=font(20, True), fill=LVC, anchor="lm"); d.text(P(330, y + 35), b, font=font(19), fill=TXT, anchor="lm"); y += 84
    return im
SCENES = {"title": (max(5, DUR.get("title", 0) + 1.4), card_title), "cc": sc_cc(), "pv": sc_pv(), "summary": (max(9, DUR.get("summary", 0) + 2), card_sum)}
ORDER = ["title", "cc", "pv", "summary"]
STATIC = ("title", "summary")

def fade(im, t, dur):
    a = min(1, t / .5, (dur - t) / .5)
    return im if a >= 1 else Image.blend(Image.new("RGB", im.size, (0, 0, 0)), im, max(0, a))
def render(name):
    dur, fn = SCENES[name]; tmp = f"{OUT}/{name}.part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    st = None
    for i in range(int(dur * FPS)):
        t = i / FPS
        if name in STATIC: st = st or fn(0).resize((W, H), Image.LANCZOS); im = st
        else: im = fn(t).resize((W, H), Image.LANCZOS)
        p.stdin.write(fade(im, t, dur).tobytes())
    p.stdin.close()
    if p.wait() == 0: os.replace(tmp, f"{OUT}/{name}.mp4")

def vo():
    import soundfile as sf; from kokoro_onnx import Kokoro
    k = Kokoro(f"{TTS}/kokoro-v1.0.onnx", f"{TTS}/voices-v1.0.bin"); d = {}; os.makedirs(f"{OUT}/vo", exist_ok=True)
    for key, txt in NARR.items():
        a, sr = k.create(txt, voice="af_heart", speed=1.0, lang="en-us"); sf.write(f"{OUT}/vo/{key}.wav", a, sr); d[key] = len(a) / sr; print(key, round(d[key], 1))
    json.dump(d, open(f"{OUT}/durations.json", "w"), indent=1)
def mux():
    import numpy as np, soundfile as sf
    SR = 24000; total = sum(SCENES[n][0] for n in ORDER); buf = np.zeros(int((total + 1) * SR), dtype=np.float32)
    def place(key, at):
        a, _ = sf.read(f"{OUT}/vo/{key}.wav", dtype="float32"); i = int(at * SR); buf[i:i + len(a)] += a
    t0 = 0
    for n in ORDER:
        if n in STATIC: place(n, t0 + .55)
        else:
            acc = 0
            for k in ([c[0] for c in CC] if n == "cc" else [p[0] for p in PV]):
                place(k, t0 + acc + .35); acc += segdur(k, 6 if n == "cc" else 7)
        t0 += SCENES[n][0]
    buf = buf[:int(total * SR)]; buf *= .9 / max(1e-6, np.abs(buf).max()); sf.write(f"{OUT}/voice.wav", buf, SR)
    open(f"{OUT}/list.txt", "w").write("".join(f"file '{n}.mp4'\n" for n in ORDER))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/list.txt", "-i", f"{OUT}/voice.wav", "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", f"{OUT}/Cardiac_Cycle_PV_Loop.mp4"], check=True)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "vo": vo()
    elif cmd == "render": [render(n) or print("done", n) for n in (sys.argv[2:] or ORDER)]
    elif cmd == "mux": mux()
    elif cmd == "still":
        n, t = sys.argv[2], float(sys.argv[3]); SCENES[n][1](t).resize((W, H), Image.LANCZOS).save(f"{OUT}/still_{n}_{t}.png")
