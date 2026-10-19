"""Original sound-effects library, synthesised from scratch (no third-party samples)."""
import os
import numpy as np
from scipy import signal
import scipy.io.wavfile as wav

SR = 48000
OUT = "out/sfx"; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)
T = lambda s: np.arange(int(s * SR)) / SR


def save(name, x, stereo_width=0.0):
    x = x / (np.abs(x).max() + 1e-9) * 0.89
    if stereo_width:
        d = int(SR * 0.012)
        l = x; r = np.concatenate([np.zeros(d), x[:-d]]) * (1 - stereo_width) + x * stereo_width
        x = np.stack([l, r], 1)
    else:
        x = np.stack([x, x], 1)
    wav.write(f"{OUT}/{name}.wav", SR, (x * 32767).astype(np.int16))


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos"); return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    sos = signal.butter(order, f, btype="low", fs=SR, output="sos"); return signal.sosfilt(sos, x)


def hp(x, f, order=2):
    sos = signal.butter(order, f, btype="high", fs=SR, output="sos"); return signal.sosfilt(sos, x)


def reverb(x, sec=1.6, mix=0.25):
    ir = rng.standard_normal(int(sec * SR)) * np.exp(-T(sec) * 5.5)
    ir = lp(ir, 6000)
    wet = signal.fftconvolve(x, ir)[: len(x) + int(sec * SR)]
    dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return dry * (1 - mix) + wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max() * mix


def sweep_noise(sec, f0, f1, q=3.0):
    """band-passed noise whose centre frequency glides f0->f1 (block-wise)."""
    n = rng.standard_normal(int(sec * SR)); out = np.zeros_like(n)
    blocks = 64; L = len(n) // blocks
    for b in range(blocks):
        fc = f0 * (f1 / f0) ** (b / (blocks - 1))
        lo, hi = fc / (1 + 1 / q), min(fc * (1 + 1 / q), SR / 2 - 100)
        seg = bp(n[max(0, b * L - 2000): (b + 1) * L], lo, hi)
        out[b * L:(b + 1) * L] = seg[-L:]
    return out


# 1. whoosh (camera moves)
for i, (sec, f0, f1) in enumerate([(0.9, 300, 2500), (1.3, 200, 1800), (0.7, 600, 4000)]):
    t = T(sec); env = np.sin(np.pi * t / sec) ** 2.2
    save(f"whoosh_{i+1}", reverb(sweep_noise(sec, f0, f1) * env, 0.8, 0.18), 0.6)

# 2. flag drop impact: soft cloth flap + low thud
sec = 0.9; t = T(sec)
thud = np.sin(2 * np.pi * (70 * t + 25 * np.exp(-t * 20) / 20 * 20)) * np.exp(-t * 9)
flap = bp(rng.standard_normal(len(t)), 800, 3500) * np.exp(-t * 28) * 0.5
save("flag_drop", reverb(thud + flap, 0.9, 0.15))

# 3. pop (labels appear)
sec = 0.25; t = T(sec)
save("pop", np.sin(2 * np.pi * (900 + 600 * np.exp(-t * 40)) * t) * np.exp(-t * 30))

# 4. tick (timeline / counters)
sec = 0.08; t = T(sec)
save("tick", hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 120) + np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 90) * 0.4)

# 5. riser (before reveals)
sec = 2.6; t = T(sec)
tone = np.sin(2 * np.pi * (180 * t + 220 * t ** 2 / sec)) * (t / sec) ** 2
save("riser", reverb(sweep_noise(sec, 200, 6000) * (t / sec) ** 2.5 + tone * 0.35, 1.2, 0.3), 0.5)

# 6. boom (chapter titles)
sec = 3.0; t = T(sec)
boom = np.sin(2 * np.pi * (45 + 40 * np.exp(-t * 6)) * t) * np.exp(-t * 2.2)
save("boom", reverb(boom + lp(rng.standard_normal(len(t)), 300) * np.exp(-t * 8) * 0.4, 2.0, 0.35))

# 7. shimmer (highlights)
sec = 1.8; t = T(sec); x = np.zeros_like(t)
for f in [1318.5, 1760, 2093, 2637, 3136]:
    x += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * rng.uniform(2.5, 4.5))
save("shimmer", reverb(x * (1 - np.exp(-t * 60)), 1.5, 0.4), 0.7)

# 8. paper / card slide
sec = 0.5; t = T(sec)
save("paper", bp(rng.standard_normal(len(t)), 1500, 7000) * np.sin(np.pi * t / sec) ** 3 * (1 + 0.5 * np.sin(2 * np.pi * 23 * t)))

# 9. stamp (X / check marks)
sec = 0.5; t = T(sec)
save("stamp", lp(rng.standard_normal(len(t)), 1200) * np.exp(-t * 35) + np.sin(2 * np.pi * 110 * t) * np.exp(-t * 18))

# 10. line draw (borders drawing)
sec = 1.5; t = T(sec)
save("line_draw", bp(rng.standard_normal(len(t)), 3000, 9000) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)) * np.sin(np.pi * t / sec) * 0.6)

# 11. low drone hit (dramatic moments)
sec = 4.0; t = T(sec); x = np.zeros_like(t)
for f in [55, 82.4, 110]:
    x += np.sin(2 * np.pi * f * t) * (1 - np.exp(-t * 3)) * np.exp(-t * 0.9)
save("drone_hit", reverb(x, 2.5, 0.4), 0.4)

# 12. crowd murmur bed (Baltic Way) - filtered noise texture with slow modulations
sec = 6.0; t = T(sec)
x = bp(rng.standard_normal(len(t)), 250, 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * t)) * np.minimum(1, t / 1.0) * np.minimum(1, (sec - t) / 1.5)
save("crowd_bed", x, 0.8)
print(sorted(os.listdir(OUT)))
