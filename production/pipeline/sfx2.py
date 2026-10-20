"""v2 Foley, synthesised from scratch (no third-party samples): bells, winter wind, cloth flaps, wood thunk,
war rumble, molten-metal hiss, soft swell. Writes into out/sfx (same folder/format as sfx.py)."""
import os
import numpy as np
from scipy import signal
import scipy.io.wavfile as wav

SR = 48000
OUT = "out/sfx"; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)
T = lambda s: np.arange(int(s * SR)) / SR


def save(name, x, width=0.0, peak=0.89):
    if x.ndim == 1:
        if width:
            d = int(SR * 0.013)
            r = np.concatenate([np.zeros(d), x[:-d]]) * width + x * (1 - width)
            x = np.stack([x, r], 1)
        else:
            x = np.stack([x, x], 1)
    x = x / (np.abs(x).max() + 1e-9) * peak
    wav.write(f"{OUT}/{name}.wav", SR, (x * 32767).astype(np.int16))


def filt(x, kind, f, order=2):
    sos = signal.butter(order, f, btype=kind, fs=SR, output="sos"); return signal.sosfilt(sos, x)


def reverb(x, sec=2.5, mix=0.3, damp=4.0):
    n = int(sec * SR)
    irs = [filt(rng.standard_normal(n) * np.exp(-T(sec) * damp), "low", 5000) for _ in range(2)]
    wet = np.stack([signal.fftconvolve(x, ir)[: len(x) + n] for ir in irs], 1)
    wet /= np.abs(wet).max() + 1e-9
    dry = np.concatenate([x, np.zeros(n)])
    return np.stack([dry, dry], 1) * (1 - mix) + wet * mix * np.abs(x).max()


# 1. Kremlin-style bell toll (inharmonic church-bell partials, long decay)
def bell(f0, sec=9.0):
    t = T(sec)
    partials = [(0.5, 0.55, 0.35), (1.0, 1.0, 0.55), (1.19, 0.65, 0.7), (1.5, 0.45, 0.8), (2.0, 0.6, 1.0),
                (2.52, 0.3, 1.4), (2.99, 0.25, 1.7), (4.16, 0.15, 2.4), (5.43, 0.08, 3.2)]
    x = np.zeros_like(t)
    for ratio, amp, dec in partials:
        f = f0 * ratio
        beat = 1 + 0.004 * np.sin(2 * np.pi * (0.7 + ratio * 0.3) * t)     # slight warble
        x += amp * np.sin(2 * np.pi * f * t * beat + rng.uniform(0, 6.28)) * np.exp(-t * dec / 2.2)
    strike = filt(rng.standard_normal(len(t)), "band", [900, 5000]) * np.exp(-t * 60) * 0.5
    return (x + strike) * (1 - np.exp(-t * 400))


save("bell_toll", reverb(bell(98.0), 3.5, 0.38, 2.2))
save("bell_small", reverb(bell(196.0, 6.0) * 0.8, 2.5, 0.32, 3.0))

# 2. winter wind bed (16 s, gusting, stereo)
sec = 16.0; t = T(sec)
g = filt(rng.standard_normal(len(t)), "low", 0.6, 1); g = (g - g.min()) / (np.ptp(g) + 1e-9)
gust = 0.35 + 0.65 * g ** 1.5
chans = []
for k in range(2):
    n = rng.standard_normal(len(t))
    w = filt(n, "band", [180, 1400]) * gust + 0.35 * filt(n, "band", [1800, 4200]) * gust ** 2
    chans.append(w * np.minimum(1, t / 2.5) * np.minimum(1, (sec - t) / 2.5))
save("wind_bed", np.stack(chans, 1), peak=0.8)

# 3. cloth flap (banner unfurling in wind)
sec = 1.1; t = T(sec); x = np.zeros_like(t)
for k, (t0, a) in enumerate([(0.0, 1.0), (0.16, 0.7), (0.3, 0.85), (0.47, 0.5), (0.62, 0.35)]):
    s = int(t0 * SR); n = len(t) - s
    burst = filt(rng.standard_normal(n), "band", [500, 3800]) * np.exp(-np.arange(n) / SR * 22) * a
    x[s:] += burst
save("cloth_flap", reverb(x, 0.8, 0.12, 6.0), 0.3)

# 4. wood thunk (pole planted into the map)
sec = 0.9; t = T(sec)
x = (np.sin(2 * np.pi * 132 * t) * 0.9 + np.sin(2 * np.pi * 318 * t) * 0.45 + np.sin(2 * np.pi * 611 * t) * 0.2) * np.exp(-t * 16)
x += filt(rng.standard_normal(len(t)), "band", [1500, 6000]) * np.exp(-t * 90) * 0.6
x += filt(rng.standard_normal(len(t)), "low", 200) * np.exp(-t * 10) * 0.5
save("wood_thunk", reverb(x, 0.7, 0.15, 7.0))

# 5. war rumble (distant artillery + armour, 5 s)
sec = 5.0; t = T(sec)
x = filt(rng.standard_normal(len(t)), "low", 110, 4) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.9 * t) ** 2)
for t0 in (0.35, 1.6, 2.4, 3.7):
    s = int(t0 * SR); n = len(t) - s
    x[s:] += filt(rng.standard_normal(n), "low", 180, 2) * np.exp(-np.arange(n) / SR * 3.2) * 2.2
x *= np.minimum(1, t / 0.4) * np.minimum(1, (sec - t) / 1.2)
save("war_rumble", reverb(x, 2.0, 0.3, 2.5), 0.5)

# 6. molten-metal hiss (borders forged) 3 s
sec = 3.0; t = T(sec)
x = filt(rng.standard_normal(len(t)), "high", 2500) * (np.minimum(1, t / 0.15) * np.exp(-t * 0.9)) * 0.6
cr = (rng.random(len(t)) > 0.9993).astype(float) * rng.uniform(0.3, 1.0, len(t))
x += filt(cr, "band", [2000, 9000]) * 3.0
x += np.sin(2 * np.pi * 70 * t) * 0.25 * np.exp(-t * 1.5)
save("forge_hiss", reverb(x, 1.2, 0.2, 4.0), 0.4)

# 7. soft cinematic swell (title) 4 s
sec = 4.0; t = T(sec); x = np.zeros_like(t)
for f in (65.4, 98.0, 130.8, 196.0, 261.6):
    x += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * (1 / (1 + f / 200))
x = filt(x, "low", 1800) * (np.minimum(1, t / 3.2) ** 2) * np.minimum(1, (sec - t) / 0.35)
save("swell", reverb(x, 3.0, 0.35, 2.0))
print("sfx2:", sorted(f for f in os.listdir(OUT)))
