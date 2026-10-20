#!/usr/bin/env python3
"""Balance + master the film mix from the stems written by mix.py.
VO: HPF 70 Hz + gentle RMS compression, make-up back to its original loudness.
Music bed -4 dB (VO sits ~12 dB above the music under speech), SFX -5 dB (accents ~5 dB under the voice).
Master: gain to ~-14 LUFS -> peak limiter -> two-pass linear loudnorm (-14 LUFS integrated, -1.5 dBTP).
usage: master.py DIR   (reads DIR/stem_*.wav, writes DIR/mix_final.wav)"""
import subprocess, json, re, sys, numpy as np
SR = 48000; OUT = sys.argv[1].rstrip('/') + '/'
MUSIC_DB, SFX_DB = -4.0, -5.0

def run(cmd, **k): return subprocess.run(cmd, capture_output=True, check=True, **k)
def load(f, ch):
    a = np.frombuffer(run(['ffmpeg', '-v', 'error', '-i', OUT + f, '-f', 'f32le', '-ac', str(ch), '-ar', str(SR), '-']).stdout, np.float32)
    return a.reshape(-1, ch) if ch > 1 else a
def save(f, x):
    x = np.ascontiguousarray(x, np.float32); ch = 1 if x.ndim == 1 else x.shape[1]
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', str(ch), '-i', '-', '-c:a', 'pcm_f32le', OUT + f], input=x.tobytes())
def lufs(f):
    e = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', OUT + f, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    return float(re.findall(r'I:\s+(-?[0-9.]+) LUFS', e)[-1]), float(re.findall(r'Peak:\s+(-?[0-9.inf]+) dBFS', e)[-1])

run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + 'stem_voice.wav', '-af',
     'highpass=f=70:poles=2,acompressor=threshold=0.1:ratio=2.5:attack=10:release=140:knee=2.8:makeup=1:detection=rms',
     '-c:a', 'pcm_f32le', OUT + 'stem_voice_p.wav'])
Io, _ = lufs('stem_voice.wav'); Ip, _ = lufs('stem_voice_p.wav')
print('VO loudness %.1f LUFS, compressed %.1f -> make-up %+.1f dB' % (Io, Ip, Io - Ip))
mix = load('stem_music.wav', 2) * np.float32(10 ** (MUSIC_DB / 20))
mix += load('stem_sfx.wav', 2) * np.float32(10 ** (SFX_DB / 20))
mix += (load('stem_voice_p.wav', 1) * np.float32(10 ** ((Io - Ip) / 20)))[:, None]
save('mix_bal.wav', mix); del mix
I, P = lufs('mix_bal.wav'); print('balanced mix %.1f LUFS, sample peak %.1f dBFS' % (I, P))
g = -14.0 - I + 0.3
run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + 'mix_bal.wav', '-af',
     f'volume={g:.2f}dB,alimiter=limit=0.75:attack=4:release=60:level=disabled:asc=1', '-c:a', 'pcm_f32le', OUT + 'mix_lim.wav'])
e = subprocess.run(['ffmpeg', '-hide_banner', '-i', OUT + 'mix_lim.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                    '-f', 'null', '-'], capture_output=True, text=True).stderr
j = json.loads(e[e.rindex('{'):e.rindex('}') + 1])
run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + 'mix_lim.wav', '-af',
     f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
     f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000",
     '-ar', '48000', '-c:a', 'pcm_s24le', OUT + 'mix_final.wav'])
I2, P2 = lufs('mix_final.wav'); print('FINAL MIX %.1f LUFS integrated, true peak %.1f dBFS' % (I2, P2))
