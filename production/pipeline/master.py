#!/usr/bin/env python3
"""Balance + master the film mix from the stems written by mix.py.
VO: HPF 70 Hz + gentle RMS compression, make-up back to its original loudness.
Music bed -4 dB (VO sits ~12 dB above the music under speech), SFX -5 dB (accents ~5 dB under the voice).
Master: gain to ~-14 LUFS -> peak limiter -> two-pass linear loudnorm (-14 LUFS integrated, true-peak ceiling C).
Checked as delivered: a lossy codec adds its own overshoot on top of the PCM peak (AES TD1008: max -1 dBTP at the
codec input, overshoot grows as the bit rate drops; Apple: levels without overs in PCM can still clip once encoded).
So the master is encoded the way the film is (AAC 320 kb/s, 48 kHz) and the way its preview is (that AAC again at
160 kb/s), decoded and measured; while a decoded true peak is above -1.0 dBTP the ceiling C goes down by the excess
and the master is made again. Exit 1 when no ceiling down to -6 dBTP is enough (a click or a broken stem, not level).
usage: master.py DIR                  reads DIR/stem_*.wav, writes DIR/mix_final.wav (+ the report on stdout)
       master.py --check FILE         the delivered true peaks of an existing master and its loudest decoded blocks"""
import json, os, subprocess, sys
import numpy as np

SR = 48000
MUSIC_DB, SFX_DB = -4.0, -5.0
DELIVERED_TP = -1.0                                         # decoded film and preview sound never above this (dBTP)
FILM_AAC = ['-c:a', 'aac', '-b:a', '320k', '-ar', '48000']  # = factory/line/assemble.sh, the final file
PREVIEW_AAC = ['-c:a', 'aac', '-b:a', '160k']               # = assemble.sh, the 720p preview made from the final file
LOWEST_CEILING = -6.0


def run(cmd, **k): return subprocess.run(cmd, capture_output=True, check=True, **k)


def ebur(path, frames=False):
    """integrated loudness (LUFS) and true peak (dBTP) of a file; with frames=True also [(t, frame true peak)]"""
    e = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-af', 'ebur128=peak=true:framelog=info',
                        '-f', 'null', '-'], capture_output=True, text=True).stderr
    summ = e[e.rfind('Summary:'):]
    I = float(summ.split('I:')[1].split('LUFS')[0])
    tp = float(summ.split('Peak:')[-1].split('dBFS')[0])
    if not frames: return I, tp
    fr = []
    for line in e.splitlines():
        if 'FTPK:' not in line or ' t:' not in line: continue
        try:
            t = float(line.split(' t:')[1].split()[0])
            v = [float(x) for x in line.split('FTPK:')[1].split('dBFS')[0].split()]
        except (ValueError, IndexError):
            continue
        v = [x for x in v if x == x and x != float('inf')]
        if v: fr.append((t, max(v)))
    return I, tp, fr


def delivered(path, tmp):
    """true peaks of path as delivered: the film's AAC, and the preview's AAC made from that file, both decoded"""
    film, prev = os.path.join(tmp, 'check_film.m4a'), os.path.join(tmp, 'check_preview.m4a')
    run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vn', *FILM_AAC, film])
    run(['ffmpeg', '-v', 'error', '-y', '-i', film, *PREVIEW_AAC, prev])
    return ebur(film)[1], ebur(prev)[1], film


def mmss(t): return '%d:%04.1f' % (t // 60, t % 60)


def loudest(path, film, n=3):
    """the n loudest 100 ms blocks of the decoded film sound, with the PCM true peak of the same block"""
    _, _, dec = ebur(film, frames=True)
    _, _, pcm = ebur(path, frames=True)
    at = {round(t, 1): v for t, v in pcm}
    top = sorted(dec, key=lambda x: -x[1])[:n]
    return ', '.join('%s %.1f dBTP (PCM %.1f)' % (mmss(t), v, at.get(round(t, 1), float('nan'))) for t, v in top)


def check(path):
    tmp = os.path.dirname(os.path.abspath(path))
    I, tp = ebur(path)
    pf, pp, film = delivered(path, tmp)
    print('%s: %.1f LUFS, PCM true peak %.1f | decoded film AAC 320k %.1f, preview AAC 160k %.1f dBTP (limit %.1f)'
          % (os.path.basename(path), I, tp, pf, pp, DELIVERED_TP))
    print('loudest decoded blocks:', loudest(path, film))
    return max(pf, pp) <= DELIVERED_TP


def main(OUT):
    OUT = OUT.rstrip('/') + '/'

    def load(f, ch):
        a = np.frombuffer(run(['ffmpeg', '-v', 'error', '-i', OUT + f, '-f', 'f32le', '-ac', str(ch), '-ar', str(SR), '-']).stdout, np.float32)
        return a.reshape(-1, ch) if ch > 1 else a

    def save(f, x):
        x = np.ascontiguousarray(x, np.float32); ch = 1 if x.ndim == 1 else x.shape[1]
        run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', str(ch), '-i', '-', '-c:a', 'pcm_f32le', OUT + f], input=x.tobytes())

    def loudnorm(f, C, second=None):
        """loudnorm json of f: first pass (measure) or, with second=<first-pass json>, the linear pass -> mix_final.wav"""
        if second is None:
            af, out = f'loudnorm=I=-14:TP={C:.2f}:LRA=11:print_format=json', ['-f', 'null', '-']
        else:
            j = second
            af = (f"loudnorm=I=-14:TP={C:.2f}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                  f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:"
                  f"linear=true:print_format=json,aresample=48000")
            out = ['-ar', '48000', '-c:a', 'pcm_s24le', OUT + 'mix_final.wav']
        e = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-y', '-i', OUT + f, '-af', af, *out], capture_output=True, text=True)
        if second is not None and e.returncode: raise SystemExit('MASTER ERROR: loudnorm pass 2 failed: ' + e.stderr[-400:])
        s = e.stderr
        return json.loads(s[s.rindex('{'):s.rindex('}') + 1])

    run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + 'stem_voice.wav', '-af',
         'highpass=f=70:poles=2,acompressor=threshold=0.1:ratio=2.5:attack=10:release=140:knee=2.8:makeup=1:detection=rms',
         '-c:a', 'pcm_f32le', OUT + 'stem_voice_p.wav'])
    Io, _ = ebur(OUT + 'stem_voice.wav'); Ip, _ = ebur(OUT + 'stem_voice_p.wav')
    print('VO loudness %.1f LUFS, compressed %.1f -> make-up %+.1f dB' % (Io, Ip, Io - Ip))
    mix = load('stem_music.wav', 2) * np.float32(10 ** (MUSIC_DB / 20))
    mix += load('stem_sfx.wav', 2) * np.float32(10 ** (SFX_DB / 20))
    mix += (load('stem_voice_p.wav', 1) * np.float32(10 ** ((Io - Ip) / 20)))[:, None]
    save('mix_bal.wav', mix); del mix
    e = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', OUT + 'mix_bal.wav', '-af', 'ebur128=peak=sample',
                        '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float(e[e.rfind('Summary:'):].split('I:')[1].split('LUFS')[0]); P = float(e.split('Peak:')[-1].split('dBFS')[0])
    print('balanced mix %.1f LUFS, sample peak %.1f dBFS' % (I, P))
    g = -14.0 - I + 0.3

    C, first = -1.5, None
    for it in range(6):
        lim = C - 1.0                       # sample-peak limiter 1 dB under the ceiling (-2.5 dBFS at C = -1.5)
        for _ in range(4):                  # keep loudnorm linear: its gain must not lift the true peak over C
            run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + 'mix_bal.wav', '-af',
                 f'volume={g:.2f}dB,alimiter=limit={10 ** (lim / 20):.5f}:attack=4:release=60:level=disabled:asc=1',
                 '-c:a', 'pcm_f32le', OUT + 'mix_lim.wav'])
            j = loudnorm('mix_lim.wav', C)
            over = float(j['input_tp']) + (-14.0 - float(j['input_i'])) - C
            if over <= 0: break
            lim -= over + 0.1
        j2 = loudnorm('mix_lim.wav', C, second=j)
        I2, P2 = ebur(OUT + 'mix_final.wav')
        pf, pp, film = delivered(OUT + 'mix_final.wav', OUT)
        worst = max(pf, pp)
        print('ceiling %.2f dBTP (limiter %.2f dBFS, loudnorm %s): %.1f LUFS, PCM true peak %.1f | decoded film AAC 320k '
              '%.1f, preview AAC 160k %.1f dBTP' % (C, lim, j2.get('normalization_type', '?'), I2, P2, pf, pp))
        if it == 0 and worst > DELIVERED_TP: first = loudest(OUT + 'mix_final.wav', film)
        if worst <= DELIVERED_TP or C <= LOWEST_CEILING: break
        C = max(LOWEST_CEILING, round(C - (worst - DELIVERED_TP) - 0.2, 2))
    if first: print('over the limit at ceiling -1.5 - loudest decoded blocks:', first)
    print('loudest decoded blocks now:', loudest(OUT + 'mix_final.wav', film))
    print('FINAL MIX %.1f LUFS integrated, true peak %.1f dBFS (ceiling %.2f); delivered true peak: film %.1f, preview %.1f dBTP '
          '(limit %.1f)' % (I2, P2, C, pf, pp, DELIVERED_TP))
    for f in ('check_film.m4a', 'check_preview.m4a'):
        if os.path.exists(OUT + f): os.remove(OUT + f)
    if worst > DELIVERED_TP:
        print('MASTER ERROR: the delivered sound stays over %.1f dBTP even with a %.1f dBTP ceiling - look for a click or a '
              'broken stem at the loudest blocks above' % (DELIVERED_TP, C))
        sys.exit(1)
    if abs(I2 + 14.0) > 0.5:
        print('MASTER ERROR: integrated loudness %.1f LUFS, not -14' % I2); sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--check':
        sys.exit(0 if check(sys.argv[2]) else 1)
    if len(sys.argv) != 2: print(__doc__); sys.exit(2)
    main(sys.argv[1])
