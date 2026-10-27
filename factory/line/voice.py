"""VOICE of a film order: the voice takes (one per paragraph of <order>/narration.json) are matched to ONE consistent
read - loudness (BS.1770), pitch level (median F0, formant-preserving shift), pace (articulation rate) and timbre
(long-term-spectrum EQ) - then joined with natural paragraph pauses, then every narration word is timed with torchaudio
MMS_FA forced alignment (~20 ms).
Takes: <order>/vo/vo_<id>.(mp3|wav|flac) or the order store (<order>/store_files/vo_<id>.(mp3|wav|flac), store key vo_<id>).
usage: python factory/line/voice.py <orderDir> [outDir=out/voice]
out: voice.wav, timeline.json (total, fps, chunks, words), subtitles.srt, align_report.txt, dsp_report.txt
exit 2 = takes missing (all listed)."""
import json, os, re, subprocess, sys, tempfile
import numpy as np, soundfile as sf, torch, torchaudio, pyloudnorm as pyln, pyworld as pw
from scipy.signal import firwin2, fftconvolve, welch
from num2words import num2words

if len(sys.argv) < 2: print(__doc__); sys.exit(1)
ORDER = sys.argv[1].rstrip("/")
N = json.load(open(f"{ORDER}/narration.json", encoding="utf-8"))
PARAS = N["paragraphs"]; CH = [p["text"] for p in PARAS]; IDS = [p["id"] for p in PARAS]
TM = N.get("timing", {})
OUT = sys.argv[2] if len(sys.argv) > 2 else "out/voice"; os.makedirs(OUT, exist_ok=True)
SR = 48000
LEAD, TAIL = TM.get("lead", 1.2), TM.get("tail", 3.4)
TITLE_GAP, GAP = TM.get("title_gap", 1.6), TM.get("gap", 0.85)   # pause after the hook paragraph / between paragraphs
KEEP_IN, KEEP_OUT = 0.05, 0.10                                    # speech edges kept around each take (s)
FPS = 30


def find_take(i):
    for d in ("vo", "store_files"):
        for e in ("wav", "flac", "mp3"):
            f = f"{ORDER}/{d}/vo_{i}.{e}"
            if os.path.exists(f) and os.path.getsize(f): return f
    return None


missing = [i for i in IDS if not find_take(i)]
if missing:
    print(f"VOICE ERROR: no take for paragraph(s) {', '.join(missing)} - one take per paragraph of narration.json, "
          f"in {ORDER}/vo/vo_<id>.mp3|wav or in the order store as key vo_<id>", flush=True)
    sys.exit(2)


def take_path(i):
    return find_take(i)


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


def speech_seconds(x):
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode="same")
    return max(0.5, float((env > 10 ** (-40 / 20)).sum()) / SR)


BANDS = np.geomspace(90, 11000, 22)


def ltas(x):
    f, p = welch(x, SR, nperseg=4096, noverlap=2048)
    return np.array([10 * np.log10(np.mean(p[(f >= lo) & (f < hi)]) + 1e-20) for lo, hi in zip(BANDS[:-1], BANDS[1:])])


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


takes = {i: trim(load(take_path(i))) for i in IDS}
meter = pyln.Meter(SR)
rep = [f"order {os.path.basename(ORDER)}: {len(IDS)} paragraphs, takes: " + ", ".join(os.path.basename(take_path(i)) for i in IDS)]
f0 = {i: median_f0(takes[i]) for i in IDS}
RATE = {i: len(re.sub(r"[^a-z]", "", t.lower())) / speech_seconds(takes[i]) for i, t in zip(IDS, CH)}   # letters / s of speech
F0T = float(np.median(list(f0.values()))); RT = float(np.median(list(RATE.values())))
rep.append(f"target median F0 {F0T:.1f} Hz, target articulation rate {RT:.2f} letters/s")
for i in IDS:
    speed = (RT / RATE[i]) ** 0.75                     # partial correction keeps each take natural
    semis = float(np.clip(12 * np.log2(F0T / f0[i]), -1.5, 1.5)) if f0[i] > 0 else 0.0
    l0 = meter.integrated_loudness(takes[i])
    takes[i] = rubberband(takes[i], 1 / speed, semis)
    rep.append(f"take {i}: F0 {f0[i]:.1f} Hz -> shift {semis:+.2f} st, rate {RATE[i]:.2f} -> pace x{speed:.3f}, loudness {l0:.1f} LUFS")
spec = {i: ltas(takes[i]) for i in IDS}
target = 10 * np.log10(np.mean([10 ** (spec[i] / 10) for i in IDS], axis=0))
centers = np.sqrt(BANDS[:-1] * BANDS[1:])
for i in IDS:
    g = np.clip(target - spec[i], -4, 4) * 0.8
    g = np.convolve(np.pad(g, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    freqs = np.concatenate([[0], centers, [SR / 2]]) / (SR / 2)
    gains = 10 ** (np.concatenate([[g[0]], g, [g[-1]]]) / 20)
    takes[i] = fftconvolve(takes[i], firwin2(2049, freqs, gains), mode="same").astype(np.float32)
for i in IDS:
    l = meter.integrated_loudness(takes[i])
    takes[i] = (takes[i] * 10 ** ((-19.0 - l) / 20)).astype(np.float32)
    fade = int(0.008 * SR); w = np.linspace(0, 1, fade, dtype=np.float32)
    takes[i][:fade] *= w; takes[i][-fade:] *= w[::-1]
    rep.append(f"take {i}: {l:.1f} -> -19.0 LUFS, F0 after {median_f0(takes[i]):.1f} Hz, dur {len(takes[i]) / SR:.2f}s")
edge = KEEP_IN + KEEP_OUT
clips = [takes[i] for i in IDS]
starts, t = [], LEAD
for k, c in enumerate(clips):
    starts.append(round(t, 3))
    t += len(c) / SR + ((TITLE_GAP if k == 0 else GAP) - edge if k < len(clips) - 1 else TAIL)
TOTAL = round(round(t * FPS) / FPS, 3)
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


words, arep = [], []
for ci, (text, clip) in enumerate(zip(CH, clips)):
    wav = torchaudio.functional.resample(torch.from_numpy(clip)[None], SR, 16000)
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
    arep.append(f"paragraph {ci} ({IDS[ci]}): start {starts[ci]:.3f}  dur {len(clip) / SR:.3f}s  tokens {len(toks)}  first {cw[0]['t0']:.3f}  "
                f"last {cw[-1]['t1']:.3f}  longest '{longest['w']}' {longest['t1'] - longest['t0']:.2f}s")
    print(arep[-1], flush=True)

chunks = [{"i": i, "start": starts[i], "end": round(starts[i] + len(c) / SR, 3)} for i, c in enumerate(clips)]
mono = all(words[i]["t0"] <= words[i + 1]["t0"] + 1e-6 for i in range(len(words) - 1))
arep += [f"TOTAL {TOTAL}s = {round(TOTAL * FPS)} frames; paragraphs {len(clips)}; words {len(words)}; monotonic {mono}"]
json.dump({"total": TOTAL, "fps": FPS, "chunks": chunks, "words": words}, open(f"{OUT}/timeline.json", "w"), indent=0)
open(f"{OUT}/align_report.txt", "w").write("\n".join(arep) + "\n")
print(arep[-1])


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
