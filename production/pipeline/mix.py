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

voice = np.zeros(N, np.float32)
music = np.zeros((N, 2), np.float32)
sfx = np.zeros((N, 2), np.float32)
cache = {}
for e in d['events']:
    src, s0, dur = e['src'], e['from'] * SPF, e['dur'] * SPF
    is_voice = src == 'voice.wav'
    a = decode(PUB + src, 1) if is_voice else cache.setdefault(src, decode(PUB + src, 2))
    n = min(dur, len(a), N - s0)
    if src.startswith('music/') and len(a) < dur:
        print(f'WARN {src}: media {len(a) / SR:.2f}s shorter than its slot {dur / SR:.2f}s')
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
