"""v3 narration: build the master voice track from production/voice3 and time every script word
(torchaudio MMS_FA forced alignment, ~20 ms).  Chunk 2 was synthesised in two halves (02a + 02b) and is
joined here with a natural sentence pause.  out/align: voice.wav, timeline.json, subtitles.srt, align_report.txt"""
import json, os, re, subprocess
import numpy as np, soundfile as sf, torch, torchaudio
from num2words import num2words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "out/align"; os.makedirs(OUT, exist_ok=True)
CH = [c["text"] if isinstance(c, dict) else c for c in json.load(open(f"{ROOT}/narration_chunks.json"))]
SR = 48000
LEAD, TITLE_GAP, GAP, TAIL, JOIN = 1.2, 4.0, 1.8, 8.0, 0.55


def load(f):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim(x, lead=True, tail=True, thr_db=-45, keep=0.04):
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode="same")
    on = np.where(env > 10 ** (thr_db / 20))[0]
    a = max(0, on[0] - int(keep * SR)) if lead else 0
    b = min(len(x), on[-1] + int(keep * SR)) if tail else len(x)
    return x[a:b]


V = f"{ROOT}/voice3"
clips = [load(f"{V}/vo_00.mp3"), load(f"{V}/vo_01.mp3"),
         np.concatenate([trim(load(f"{V}/vo_02a.mp3"), lead=False), np.zeros(int(JOIN * SR), np.float32),
                         trim(load(f"{V}/vo_02b.mp3"), tail=False)]),
         *[load(f"{V}/vo_{i:02d}.mp3") for i in range(3, 7)]]
assert len(clips) == len(CH) == 7
starts, t = [], LEAD
for i, c in enumerate(clips):
    starts.append(round(t, 3))
    t += len(c) / SR + (TITLE_GAP if i == 0 else (GAP if i < len(clips) - 1 else TAIL))
TOTAL = round(round(t * 30) / 30, 3)
master = np.zeros(int(round(TOTAL * SR)), np.float32)
for s, c in zip(starts, clips):
    a = int(round(s * SR)); master[a:a + len(c)] += c
sf.write(f"{OUT}/voice.wav", np.clip(master, -1, 1), SR, subtype="PCM_16")

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
