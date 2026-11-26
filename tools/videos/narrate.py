#!/usr/bin/env python3
"""Generate narration clips and durations.json for render.py, then (with --mux) build the audio track and the final video."""
import sys, json, os, subprocess
import numpy as np, soundfile as sf
OUT = os.path.dirname(os.path.abspath(__file__)); TTS = "/home/claude/tts"
VOICE, SPEED, LEAD = "af_heart", 1.0, 0.35
NARR = {
 "title": "The cardiac action potential. Let's compare a ventricular muscle cell with a pacemaker cell of the S A node.",
 "vent0": "First, the ventricular muscle cell. In phase four, the cell rests at about minus ninety millivolts. Inward rectifier potassium channels stay open, so potassium leaks out, and the inside of the cell stays negative.",
 "vent1": "Phase zero is the rapid upstroke. A stimulus from a neighboring cell opens voltage-gated fast sodium channels. Sodium rushes in, and the membrane jumps to about plus twenty millivolts. Class one antiarrhythmic drugs block these sodium channels.",
 "vent2": "In phase one, the sodium channels inactivate, and a brief transient outward potassium current pulls the voltage down a little.",
 "vent3": "Phase two is the plateau, the signature of cardiac muscle. L-type calcium channels let calcium in while potassium leaves, so the voltage stays nearly flat. This calcium triggers a much larger release of calcium from the sarcoplasmic reticulum. This is calcium-induced calcium release, and it makes the cell contract.",
 "vent4": "In phase three, the calcium channels close, and delayed rectifier potassium channels carry potassium out, so the cell repolarizes quickly. Class three drugs block these potassium channels, which prolongs the action potential and the Q T interval.",
 "vent5": "The cell returns to phase four, and the sodium potassium pump restores the ion gradients. Notice the long effective refractory period, shaded here. The cell cannot fire again until it has mostly relaxed, so heart muscle cannot develop a tetanic contraction.",
 "pace0": "Now the pacemaker cell of the S A node. It has no stable resting potential. In phase four, H C N channels carry the funny current, mostly sodium moving in, and the voltage slowly drifts upward. Near the end, T-type calcium channels open too. The drug ivabradine blocks the funny current.",
 "pace1": "When the voltage reaches threshold, about minus forty millivolts, L-type calcium channels open. This upstroke is carried by calcium, not fast sodium, so it is slower. Calcium channel blockers such as verapamil and diltiazem slow it down.",
 "pace2": "In phase three, potassium channels open and potassium flows out, repolarizing the cell. Pacemaker cells have no phase one and no plateau.",
 "pace3": "The slope of phase four sets the heart rate. Sympathetic stimulation, through beta one receptors, increases the funny current and calcium current, so the slope gets steeper and the heart beats faster. Vagal stimulation releases acetylcholine, which opens potassium channels and reduces the funny current, so the slope gets flatter and the heart slows down.",
 "summary": "To summarize. Ventricular cells have a stable resting potential, a fast sodium upstroke, and a calcium plateau. Pacemaker cells drift upward on their own in phase four, depolarize with calcium, and have no plateau.",
}
SR = 24000
def gen():
    from kokoro_onnx import Kokoro
    k = Kokoro(f"{TTS}/kokoro-v1.0.onnx", f"{TTS}/voices-v1.0.bin"); d = {}
    os.makedirs(f"{OUT}/vo", exist_ok=True)
    for key, txt in NARR.items():
        a, sr = k.create(txt, voice=VOICE, speed=SPEED, lang="en-us"); assert sr == SR
        sf.write(f"{OUT}/vo/{key}.wav", a, sr); d[key] = len(a) / sr; print(key, round(d[key], 1))
    json.dump(d, open(f"{OUT}/durations.json", "w"), indent=1)

def mux():
    sys.path.insert(0, OUT); import render
    track, t0 = [], 0.0
    total = sum(render.SCENES[n][0] for n in render.ORDER)
    buf = np.zeros(int((total + 1) * SR), dtype=np.float32)
    def place(key, at):
        a, _ = sf.read(f"{OUT}/vo/{key}.wav", dtype="float32"); i = int(at * SR); buf[i:i + len(a)] += a
    for n in render.ORDER:
        if n in ("title", "summary"): place(n, t0 + LEAD + .2)
        else:
            sc = render.VENT if n == "vent" else render.PACE; acc = 0
            for i, s in enumerate(sc["segs"]): place(f"{n}{i}", t0 + acc + LEAD); acc += s[0]
        t0 += render.SCENES[n][0]
    buf = buf[:int(total * SR)]; buf *= 0.9 / max(1e-6, np.abs(buf).max())
    sf.write(f"{OUT}/voice.wav", buf, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{OUT}/silent.mp4", "-i", f"{OUT}/voice.wav", "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", f"{OUT}/Cardiac_Action_Potential.mp4"], check=True)

if __name__ == "__main__":
    mux() if "--mux" in sys.argv else gen()
