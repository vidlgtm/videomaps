"""Precise word timings: forced alignment of the exact script onto the master voice track
(torchaudio MMS_FA, wav2vec2 CTC forced aligner, ~20 ms resolution).
in : voice.wav (release stage1), remotion/src/data/timeline.json (tokens + old whisper timings)
out: out/align/timeline_v2.json (same schema, new t0/t1), out/align/align_report.txt"""
import json, os, re, sys
import numpy as np, soundfile as sf, torch, torchaudio
from num2words import num2words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "out/align"; os.makedirs(OUT, exist_ok=True)
TL = json.load(open(f"{ROOT}/remotion/src/data/timeline.json"))
W, CH = TL["words"], TL["chunks"]
audio, sr = sf.read(sys.argv[1] if len(sys.argv) > 1 else "voice.wav", dtype="float32")
if audio.ndim > 1: audio = audio.mean(1)
torch.set_num_threads(4)
bundle = torchaudio.pipelines.MMS_FA
model = bundle.get_model(with_star=False).eval()
tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()
DICT = bundle.get_dict(star=None)
OK = set(k for k in DICT if len(k) == 1 and k not in "-*")


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


rep = []
for ci, ch in enumerate(CH):
    s = max(0.0, ch["start"] - 0.35); e = min(len(audio) / sr, ch["end"] + 0.6)
    seg = torch.from_numpy(audio[int(s * sr):int(e * sr)].copy())[None]
    wav = torchaudio.functional.resample(seg, sr, 16000)
    with torch.inference_mode():
        emission, _ = model(wav)
    words = [w for w in W if w["c"] == ci]
    sp = [spoken(w["w"]) for w in words]
    flat = [x for l in sp for x in l]
    spans = aligner(emission[0], tokenizer(flat))
    spf = wav.size(1) / emission.size(1) / 16000
    k = 0
    for w, l in zip(words, sp):
        w["old"] = (w["t0"], w["t1"])
        if not l:
            w["new"] = None; continue
        a, b = spans[k][0].start * spf + s, spans[k + len(l) - 1][-1].end * spf + s
        w["new"] = (round(a, 3), round(b, 3)); k += len(l)
    assert k == len(flat)
    print(f"chunk {ci}: {len(words)} tokens, {len(flat)} spoken words", flush=True)

# fill tokens without letters (e.g. a lone dash) from neighbours
for i, w in enumerate(W):
    if w["new"] is None:
        prev = next((W[j]["new"][1] for j in range(i - 1, -1, -1) if W[j]["new"]), 0.0)
        w["new"] = (prev, prev)
d0 = np.array([w["new"][0] - w["old"][0] for w in W])
d1 = np.array([w["new"][1] - w["old"][1] for w in W])
lines = [f"tokens {len(W)}",
         f"start shift new-old: mean {d0.mean():+.3f}s median {np.median(d0):+.3f}s  |mean| {np.abs(d0).mean():.3f}s  p90 {np.percentile(np.abs(d0), 90):.3f}s  max {np.abs(d0).max():.3f}s",
         f"end shift   new-old: mean {d1.mean():+.3f}s median {np.median(d1):+.3f}s  |mean| {np.abs(d1).mean():.3f}s"]
for ci in range(len(CH)):
    dd = np.array([w["new"][0] - w["old"][0] for w in W if w["c"] == ci])
    lines.append(f"  chunk {ci}: mean {dd.mean():+.3f}  |mean| {np.abs(dd).mean():.3f}  max {np.abs(dd).max():.3f}")
lines.append("largest start shifts:")
for i in np.argsort(-np.abs(d0))[:20]:
    w = W[i]; lines.append(f"  {w['w']:>16}  old {w['old'][0]:8.3f}  new {w['new'][0]:8.3f}  ({d0[i]:+.3f})")
open(f"{OUT}/align_report.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
for w in W:
    w["t0"], w["t1"] = w["new"]; del w["new"]; del w["old"]
json.dump(TL, open(f"{OUT}/timeline_v2.json", "w"))
