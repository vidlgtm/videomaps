#!/usr/bin/env python3
"""Offline renderer of the film's AudioMix: exact events + per-frame volume curves exported from Remotion's AudioMix.tsx
(scripts/audio_events.tsx). Writes stems voice / music / sfx (48 kHz float WAV).
usage: mix.py EVENTS_JSON PUBLIC_DIR OUT_DIR"""
import json, subprocess, sys, numpy as np
EV, PUB, OUT = sys.argv[1], sys.argv[2].rstrip('/') + '/', sys.argv[3].rstrip('/') + '/'
SR = 48000
d = json.load(open(EV))
fps, NF = d['fps'], d['totalFrames']
SPF = SR // fps                      # 1600 samples per video frame
N = NF * SPF

def decode(path, ch):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', str(ch), '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    return a.reshape(-1, ch) if ch > 1 else a

def write_wav(name, x):
    x = np.ascontiguousarray(x, dtype=np.float32)
    ch = 1 if x.ndim == 1 else x.shape[1]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', str(ch), '-i', '-',
                    '-c:a', 'pcm_f32le', OUT + name], input=x.tobytes(), check=True)


def fit(a, dur, src):
    """v3: music shorter than its slot (the corrected narration is longer) -> gentle tempo stretch (pitch kept,
    the musical ending stays at the end); for big gaps a crossfaded loop of the second part"""
    L = len(a); r = L / dur
    if r >= 0.82:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', PUB + src, '-af', f'atempo={r:.6f}', '-f', 'f32le', '-ac', '2',
                              '-ar', str(SR), '-'], capture_output=True, check=True).stdout
        b = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
        if len(b) < dur: b = np.concatenate([b, np.zeros((dur - len(b), 2), np.float32)])
        print(f'FIT {src}: {L / SR:.2f}s -> tempo x{r:.4f} -> {len(b) / SR:.2f}s (slot {dur / SR:.2f}s)')
        return b
    xf = 3 * SR; out = a.copy(); seg = a[L // 3:]
    while len(out) < dur:
        w = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
        out[-xf:] = out[-xf:] * (1 - w) + seg[:xf] * w
        out = np.concatenate([out, seg[xf:]])
    print(f'FIT {src}: {L / SR:.2f}s looped to {len(out) / SR:.2f}s (slot {dur / SR:.2f}s)')
    return out

voice = np.zeros(N, np.float32)
music = np.zeros((N, 2), np.float32)
sfx = np.zeros((N, 2), np.float32)
cache = {}
for e in d['events']:
    src, s0, dur = e['src'], e['from'] * SPF, e['dur'] * SPF
    is_voice = src == 'voice.wav'
    a = decode(PUB + src, 1) if is_voice else cache.setdefault(src, decode(PUB + src, 2))
    if src.startswith('music/') and len(a) < dur:
        a = fit(a, dur, src)
    n = min(dur, len(a), N - s0)          # v4: after fit() - the stretched cue now plays to the end of its slot
    seg = a[:n]
    if e['vols'] is not None:   # per-frame volume -> per-sample, linearly interpolated (smoother than frame steps)
        v = np.asarray(e['vols'], np.float32)
        seg = seg * np.interp(np.arange(n) / SPF, np.arange(len(v)), v).astype(np.float32)[:, None]
    else:
        seg = seg * np.float32(e['vol'])
    if is_voice: voice[s0:s0 + n] += seg
    elif src.startswith('music/'): music[s0:s0 + n] += seg; cache.pop(src, None)
    else: sfx[s0:s0 + n] += seg
print('events', len(d['events']), 'duration %.3f s' % (N / SR))
write_wav('stem_voice.wav', voice); write_wav('stem_music.wav', music); write_wav('stem_sfx.wav', sfx)
