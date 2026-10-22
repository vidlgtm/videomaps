"""v4 narration master. The 8 TTS takes (separate synthesis calls) are first matched to ONE consistent read -
loudness (BS.1770), pitch level (median F0, formant-preserving shift), pace (articulation rate) and timbre
(long-term-spectrum EQ) - then joined with natural paragraph pauses instead of the old 2 s holes, so no chunk
join sounds like a different recording. Then every script word is timed (torchaudio MMS_FA, ~20 ms).
out/align: voice.wav, timeline.json, subtitles.srt, align_report.txt (+ dsp_report.txt)"""
import json, os, re, subprocess, tempfile
import numpy as np, soundfile as sf, torch, torchaudio, pyloudnorm as pyln, pyworld as pw
from scipy.signal import firwin2, fftconvolve, welch
from num2words import num2words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "out/align"; os.makedirs(OUT, exist_ok=True)
CH = [c["text"] if isinstance(c, dict) else c for c in json.load(open(f"{ROOT}/narration_chunks.json"))]
SR = 48000
LEAD, TAIL = 1.2, 8.0
TITLE_GAP, GAP, JOIN = 3.0, 0.85, 0.6      # word-to-word pauses: after the hook (title beat), chunk joins, 02a|02b
KEEP_IN, KEEP_OUT = 0.05, 0.10             # speech edges kept around each take (s)
# articulation rate of each take (letters per second of speech, measured on the v3 alignment)
RATE = {"00": 13.45, "01": 14.39, "02a": 12.42, "02b": 14.24, "03": 13.95, "04": 13.94, "05": 13.09, "06": 13.64}


def load(f):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim(x, thr_db=-48):
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode="same")
    on = np.where(env > 10 ** (thr_db / 20))[0]
    return x[max(0, on[0] - int(KEEP_IN * SR)): min(len(x), on[-1] + int(KEEP_OUT * SR))]


def median_f0(x):
    d = x.astype(np.float64)
    f0, t = pw.dio(d, SR, f0_floor=60, f0_ceil=320, frame_period=10)
    f0 = pw.stonemask(d, f0, t, SR)
    v = f0[f0 > 0]
    return float(np.median(v)) if len(v) else 0.0


BANDS = np.geomspace(90, 11000, 22)


def ltas(x):
    f, p = welch(x, SR, nperseg=4096, noverlap=2048)
    db = []
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        m = (f >= lo) & (f < hi)
        db.append(10 * np.log10(np.mean(p[m]) + 1e-20))
    return np.array(db)


def rubberband(x, ratio, semis):
    if abs(ratio - 1) < 0.012 and abs(semis) < 0.2:
        return x
    with tempfile.TemporaryDirectory() as d:
        sf.write(f"{d}/i.wav", x, SR, subtype="FLOAT")
        cmd = ["rubberband", "-3", "-q", "-t", f"{ratio:.5f}"]
        if abs(semis) >= 0.2:
            cmd += ["-p", f"{semis:.3f}", "-F"]
        subprocess.run(cmd + [f"{d}/i.wav", f"{d}/o.wav"], check=True, capture_output=True)
        y, _ = sf.read(f"{d}/o.wav", dtype="float32")
    return y if y.ndim == 1 else y.mean(1)


V = f"{ROOT}/voice3"
names = ["00", "01", "02a", "02b", "03", "04", "05", "06"]
takes = {n: trim(load(f"{V}/vo_{n}.mp3")) for n in names}
meter = pyln.Meter(SR)
rep = []
f0 = {n: median_f0(takes[n]) for n in names}
F0T = float(np.median(list(f0.values())))
RT = float(np.median(list(RATE.values())))
rep.append(f"target median F0 {F0T:.1f} Hz, target rate {RT:.2f} letters/s")
for n in names:
    speed = (RT / RATE[n]) ** 0.75                       # partial correction: keeps each take natural
    semis = float(np.clip(12 * np.log2(F0T / f0[n]), -1.5, 1.5)) if f0[n] > 0 else 0.0
    l0 = meter.integrated_loudness(takes[n])
    takes[n] = rubberband(takes[n], 1 / speed, semis)
    rep.append(f"take {n}: F0 {f0[n]:.1f} Hz -> shift {semis:+.2f} st, pace x{speed:.3f}, loudness {l0:.1f} LUFS")
# timbre: gentle EQ of each take towards the average long-term spectrum (max +-4 dB, smoothed)
spec = {n: ltas(takes[n]) for n in names}
target = 10 * np.log10(np.mean([10 ** (spec[n] / 10) for n in names], axis=0))
centers = np.sqrt(BANDS[:-1] * BANDS[1:])
for n in names:
    g = np.clip(target - spec[n], -4, 4) * 0.8
    g = np.convolve(np.pad(g, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    freqs = np.concatenate([[0], centers, [SR / 2]]) / (SR / 2)
    gains = 10 ** (np.concatenate([[g[0]], g, [g[-1]]]) / 20)
    fir = firwin2(2049, freqs, gains)
    takes[n] = fftconvolve(takes[n], fir, mode="same").astype(np.float32)
    rep.append(f"take {n}: EQ " + " ".join(f"{c:.0f}:{v:+.1f}" for c, v in zip(centers[::3], g[::3])))
# loudness: every take to the same integrated loudness
for n in names:
    l = meter.integrated_loudness(takes[n])
    takes[n] = (takes[n] * 10 ** ((-19.0 - l) / 20)).astype(np.float32)
    fade = int(0.008 * SR); w = np.linspace(0, 1, fade, dtype=np.float32)
    takes[n][:fade] *= w; takes[n][-fade:] *= w[::-1]
    rep.append(f"take {n}: {l:.1f} -> -19.0 LUFS, F0 after {median_f0(takes[n]):.1f} Hz, dur {len(takes[n]) / SR:.2f}s")
edge = KEEP_IN + KEEP_OUT
clips = [takes["00"], takes["01"],
         np.concatenate([takes["02a"], np.zeros(int((JOIN - edge) * SR), np.float32), takes["02b"]]),
         *[takes[f"{i:02d}"] for i in range(3, 7)]]
assert len(clips) == len(CH) == 7
starts, t = [], LEAD
for i, c in enumerate(clips):
    starts.append(round(t, 3))
    t += len(c) / SR + ((TITLE_GAP if i == 0 else GAP) - edge if i < len(clips) - 1 else TAIL)
TOTAL = round(round(t * 30) / 30, 3)
master = np.zeros(int(round(TOTAL * SR)), np.float32)
for s, c in zip(starts, clips):
    a = int(round(s * SR)); master[a:a + len(c)] += c
sf.write(f"{OUT}/voice.wav", np.clip(master, -1, 1), SR, subtype="PCM_16")
open(f"{OUT}/dsp_report.txt", "w").write("\n".join(rep) + "\n")
print("\n".join(rep))

torch.set_num_threads(4)
bundle = torchaudio.pipelines.MMS_FA
model = bundle.get_model(with_star=False).eval()
tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()
OK = set(k for k in bundle.get_dict(star=None) if len(k) == 1 and k not in "-*")
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def year_words(n):
    return num2words(n, to="year").replace("-", " ").replace(",", "").split()


def spoken(tok):
    t = tok.lower().replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"[\u2014\u2013\-/]", " ", t)
    out = []
    for part in t.split():
        p = re.sub(r"[^a-z0-9']", "", part)
        if not p: continue
        m = re.fullmatch(r"(\d+)(st|nd|rd|th)", p)
        if m:
            out += num2words(int(m.group(1)), to="ordinal").replace("-", " ").split(); continue
        m = re.fullmatch(r"(\d{4})s", p)
        if m:
            y = year_words(int(m.group(1)))
            y[-1] = y[-1][:-1] + "ies" if y[-1].endswith("y") else y[-1] + "s"
            out += y; continue
        if p.isdigit():
            out += year_words(int(p)) if len(p) == 4 else num2words(int(p)).replace("-", " ").replace(",", "").split(); continue
        p = "".join(ch for ch in re.sub(r"\d", "", p) if ch in OK)
        if p.strip("'"): out.append(p)
    return out


words, rep = [], []
for ci, (text, clip) in enumerate(zip(CH, clips)):
    seg = torch.from_numpy(clip)[None]
    wav = torchaudio.functional.resample(seg, SR, 16000)
    with torch.inference_mode():
        emission, _ = model(wav)
    toks = text.split()
    sp = [spoken(w) for w in toks]
    flat = [x for l in sp for x in l]
    spans = aligner(emission[0], tokenizer(flat))
    spf = wav.size(1) / emission.size(1) / 16000
    k = 0
    for j, (w, l) in enumerate(zip(toks, sp)):
        if l:
            a, b = spans[k][0].start * spf, spans[k + len(l) - 1][-1].end * spf; k += len(l)
        else:
            a = b = words[-1]["t1"] - starts[ci] if words and words[-1]["c"] == ci else 0.0
        words.append({"w": w, "n": norm(w), "c": ci, "k": j, "t0": round(starts[ci] + a, 3), "t1": round(starts[ci] + b, 3)})
    assert k == len(flat)
    cw = [w for w in words if w["c"] == ci]
    longest = max(cw, key=lambda w: w["t1"] - w["t0"])
    rep.append(f"chunk {ci}: start {starts[ci]:.3f}  dur {len(clip) / SR:.3f}s  tokens {len(toks)}  first {cw[0]['t0']:.3f}  "
               f"last {cw[-1]['t1']:.3f}  longest '{longest['w']}' {longest['t1'] - longest['t0']:.2f}s")
    print(rep[-1], flush=True)

chunks = [{"i": i, "start": starts[i], "end": round(starts[i] + len(c) / SR, 3)} for i, c in enumerate(clips)]
mono = all(words[i]["t0"] <= words[i + 1]["t0"] + 1e-6 for i in range(len(words) - 1))
rep += [f"TOTAL {TOTAL}s = {round(TOTAL * 30)} frames; words {len(words)}; monotonic {mono}"]
json.dump({"total": TOTAL, "fps": 30, "chunks": chunks, "words": words}, open(f"{OUT}/timeline.json", "w"), indent=0)
open(f"{OUT}/align_report.txt", "w").write("\n".join(rep) + "\n")
print(rep[-1])


def ts(x):
    h, r = divmod(x, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


lines, cur = [], []
for w in words:
    cur.append(w)
    txt = " ".join(x["w"] for x in cur)
    if len(txt) > 38 or re.search(r"[.?!]$", w["w"]) or (re.search(r"[,;:]$", w["w"]) and len(txt) > 24):
        lines.append(cur); cur = []
if cur: lines.append(cur)
with open(f"{OUT}/subtitles.srt", "w") as fh:
    for i, L in enumerate(lines, 1):
        fh.write(f"{i}\n{ts(L[0]['t0'])} --> {ts(L[-1]['t1'])}\n{' '.join(x['w'] for x in L)}\n\n")
