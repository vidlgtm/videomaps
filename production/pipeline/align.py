"""Build the master voice track (with designed pauses) and word-level timings.
faster-whisper (medium.en) transcribes each narration chunk with word timestamps;
the *script* words are then aligned onto the recognised words (difflib), so every
script word gets a time even if a proper noun is mis-heard.  Output: out/align/"""
import json, os, re, subprocess, difflib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = json.load(open(f"{ROOT}/narration_chunks.json"))
CH = [c["text"] if isinstance(c, dict) else c for c in CH]
VO = [f"{ROOT}/voice/vo_{i:02d}.mp3" for i in range(len(CH))]
OUT = "out/align"; os.makedirs(OUT, exist_ok=True)
LEAD, TITLE_GAP, GAP, TAIL = 1.2, 4.0, 1.8, 8.0   # seconds


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))


starts, t = [], LEAD
for i, f in enumerate(VO):
    starts.append(round(t, 3))
    t += dur(f) + (TITLE_GAP if i == 0 else (GAP if i < len(VO) - 1 else TAIL))
TOTAL = round(t, 3)

# master voice track: each chunk delayed to its start, mixed, padded to TOTAL
inp, fc = [], []
for i, f in enumerate(VO):
    inp += ["-i", f]
    ms = int(starts[i] * 1000)
    fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}:all=1[a{i}]")
fc.append("".join(f"[a{i}]" for i in range(len(VO))) + f"amix=inputs={len(VO)}:normalize=0,apad=whole_dur={TOTAL}[out]")
subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", ";".join(fc), "-map", "[out]",
                "-t", str(TOTAL), "-ar", "48000", "-ac", "1", f"{OUT}/voice.wav"], check=True)

from faster_whisper import WhisperModel
model = WhisperModel("medium.en", device="cpu", compute_type="int8", cpu_threads=4)
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())

words_out = []
for ci, (f, text) in enumerate(zip(VO, CH)):
    segs, _ = model.transcribe(f, language="en", word_timestamps=True, beam_size=5, vad_filter=False,
                               initial_prompt="Soviet Union, Tatarstan, Estonia, Chechnya, Stalin, matryoshka, uti possidetis juris")
    rec = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]
    script = text.split()
    a = [norm(w) for w in script]; b = [norm(w[0]) for w in rec]
    times = [None] * len(script)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (rec[blk.b + k][1], rec[blk.b + k][2])
    # interpolate the gaps
    D = dur(f)
    for k in range(len(script)):
        if times[k] is None:
            p = next((j for j in range(k - 1, -1, -1) if times[j]), None)
            n = next((j for j in range(k + 1, len(script)) if times[j]), None)
            t0 = times[p][1] if p is not None else 0.0
            t1 = times[n][0] if n is not None else D
            gap = (p if p is not None else -1), (n if n is not None else len(script))
            span = gap[1] - gap[0]
            pos = k - gap[0]
            s0 = t0 + (t1 - t0) * (pos - 1) / max(span - 1, 1)
            s1 = t0 + (t1 - t0) * pos / max(span - 1, 1)
            times[k] = (s0, max(s1, s0 + 0.05))
    matched = sum(1 for x in a if x) and sum(blk.size for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    print(f"chunk {ci}: {len(script)} script words, {len(rec)} recognised, {matched} matched")
    for k, w in enumerate(script):
        words_out.append({"w": w, "n": norm(w), "c": ci, "k": k,
                          "t0": round(starts[ci] + times[k][0], 3), "t1": round(starts[ci] + times[k][1], 3)})

chunks = [{"i": i, "start": starts[i], "end": round(starts[i] + dur(VO[i]), 3)} for i in range(len(VO))]
json.dump({"total": TOTAL, "fps": 30, "chunks": chunks, "words": words_out}, open(f"{OUT}/timeline.json", "w"), indent=0)


# subtitles (SRT) from script words, broken at punctuation / ~42 chars
def ts(x):
    h, r = divmod(x, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"

lines, cur = [], []
for w in words_out:
    cur.append(w)
    txt = " ".join(x["w"] for x in cur)
    if len(txt) > 38 or re.search(r"[.?!]$", w["w"]) or (re.search(r"[,;:]$", w["w"]) and len(txt) > 24):
        lines.append(cur); cur = []
if cur: lines.append(cur)
with open(f"{OUT}/subtitles.srt", "w") as fh:
    for i, L in enumerate(lines, 1):
        fh.write(f"{i}\n{ts(L[0]['t0'])} --> {ts(L[-1]['t1'])}\n{' '.join(x['w'] for x in L)}\n\n")
print("TOTAL", TOTAL, "s; words", len(words_out))
