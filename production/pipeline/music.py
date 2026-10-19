"""Original score generated with ACE-Step (open-source music model, via its public HF Space).
One cue per narrative section; the final mix places each cue at its chapter boundary.
If the Space refuses (quota) a cue is rebuilt from a successful one, and as a last
resort a procedural ambient pad is synthesised - the pipeline never blocks."""
import json, os, shutil, subprocess, time, traceback
import numpy as np

OUT = "out/music"; os.makedirs(OUT, exist_ok=True)
NEG = "vocals, singing, voice, choir, lyrics, drums heavy, edm, rock"
CUES = [  # name, seconds, prompt
    ("c1_hook", 75, "cinematic documentary underscore, mysterious, dark ambient, low sustained strings, sparse soft piano notes, subtle low drone, slow, 70 bpm, instrumental"),
    ("c2_origins", 215, "cinematic documentary underscore, curious, light pizzicato strings, soft felt piano, warm pads, gentle steady pulse, intellectual, 88 bpm, instrumental"),
    ("c3_annex", 80, "cinematic documentary underscore, melancholic, solo cello, soft string ensemble, eastern european, slow, 70 bpm, instrumental"),
    ("c4_collapse", 110, "cinematic documentary underscore, building tension, string ostinato, soft timpani, low brass swells, rising, dramatic but restrained, 100 bpm, instrumental"),
    ("c5_resolution", 140, "cinematic documentary underscore, reflective, emotional strings, warm piano, hopeful resolution, slow, 74 bpm, instrumental"),
]
report = {}


def first_audio(res):
    found = []
    def walk(x):
        if isinstance(x, str) and os.path.exists(x) and x.lower().endswith((".mp3", ".wav", ".flac", ".ogg")):
            found.append(x)
        elif isinstance(x, dict): [walk(v) for v in x.values()]
        elif isinstance(x, (list, tuple)): [walk(v) for v in x]
    walk(res)
    return found[0] if found else None


def ace(prompt, seconds, seed):
    from gradio_client import Client
    tok = os.environ.get("HF_TOKEN") or None
    c = Client("ACE-Step/ACE-Step", token=tok, verbose=False) if tok else Client("ACE-Step/ACE-Step", verbose=False)
    res = c.predict(audio_duration=seconds, prompt=prompt, lyrics="[instrumental]", manual_seeds=str(seed),
                    infer_step=60, api_name="/__call__")
    return first_audio(res)


def pad(seconds, path, sr=48000):
    """Procedural fallback: slow evolving minor-key string pad."""
    t = np.arange(int(seconds * sr)) / sr
    chords = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]]  # Am F G Em
    out = np.zeros_like(t)
    seg = 8.0
    for ci in range(int(seconds / seg) + 1):
        notes = chords[ci % 4]
        env = np.clip(1 - np.abs((t - ci * seg - seg / 2) / (seg * 0.75)), 0, 1) ** 1.5
        for n in notes + [notes[0] - 12]:
            f = 440 * 2 ** ((n - 69) / 12)
            for det in (-0.12, 0, 0.12):
                out += env * np.sin(2 * np.pi * f * (1 + det / 100) * t + det) / 10
    out *= 0.25 / (np.abs(out).max() + 1e-9)
    import scipy.io.wavfile as w
    w.write(path, sr, (out * 32767).astype(np.int16))


for i, (name, sec, prompt) in enumerate(CUES):
    ok = False
    for attempt in range(3):
        try:
            p = ace(prompt, sec, 4100 + i * 17 + attempt)
            if p:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ar", "48000", "-ac", "2", f"{OUT}/{name}.wav"], check=True)
                report[name] = {"source": "ACE-Step", "attempt": attempt}
                ok = True; break
        except Exception as e:
            report[name] = {"error": repr(e)[:300]}
            traceback.print_exc(limit=1)
            time.sleep(20 + 40 * attempt)
    print(name, "OK" if ok else "FAILED")

def orchestral(name, seconds, mood):
    """Fallback composer: algorithmic cinematic cue rendered with FluidSynth (FluidR3 GM, MIT) + pedalboard reverb."""
    import pretty_midi, random
    random.seed(hash(name) % 1000)
    bpm = {"mysterious": 66, "curious": 84, "melancholic": 66, "tension": 96, "reflective": 72}[mood]
    prog = {"mysterious": [(50, "m"), (46, "M"), (53, "M"), (48, "M")], "curious": [(50, "m"), (53, "M"), (48, "M"), (46, "M")],
            "melancholic": [(50, "m"), (43, "m"), (46, "M"), (45, "M")], "tension": [(50, "m"), (50, "m"), (46, "M"), (48, "M")],
            "reflective": [(46, "M"), (48, "M"), (50, "m"), (53, "M")]}[mood]
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    beat = 60 / bpm; bar = 4 * beat; chord_len = 2 * bar
    ins = {k: pretty_midi.Instrument(program=p) for k, p in
           {"str": 48, "str2": 49, "bass": 43, "pno": 0, "horn": 60, "pizz": 45, "timp": 47}.items()}
    t = 0.0; i = 0
    while t < seconds:
        root, q = prog[i % len(prog)]
        tri = [root, root + (3 if q == "m" else 4), root + 7]
        for n in tri + [root + 12]:
            ins["str"].notes.append(pretty_midi.Note(70, n + 12, t, t + chord_len))
        ins["str2"].notes.append(pretty_midi.Note(62, tri[1] + 24, t, t + chord_len))
        ins["bass"].notes.append(pretty_midi.Note(78, root - 12, t, t + chord_len))
        if mood in ("mysterious", "melancholic", "reflective"):
            for b in range(0, 8, 2 if mood != "mysterious" else 3):
                n = random.choice(tri) + 24 + random.choice([0, 0, 12])
                ins["pno"].notes.append(pretty_midi.Note(random.randint(38, 55), n, t + b * beat, t + b * beat + 2 * beat))
        if mood == "curious":
            for b in range(16):
                n = tri[b % 3] + 24 + (12 if b % 8 > 5 else 0)
                ins["pizz"].notes.append(pretty_midi.Note(random.randint(50, 66), n, t + b * beat / 2, t + b * beat / 2 + 0.3))
        if mood == "tension":
            for b in range(32):
                ins["str2"].notes.append(pretty_midi.Note(58 + (b % 4 == 0) * 12, tri[b % 2] + 12, t + b * beat / 4, t + b * beat / 4 + 0.12))
            for b in (0, 4):
                ins["timp"].notes.append(pretty_midi.Note(84, root - 12, t + b * beat, t + b * beat + 1.5))
            ins["horn"].notes.append(pretty_midi.Note(60, tri[2] + 12, t + 2 * beat, t + chord_len))
        t += chord_len; i += 1
    for v in ins.values(): pm.instruments.append(v)
    pm.write(f"{OUT}/{name}.mid")
    sf = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
    subprocess.run(["fluidsynth", "-ni", "-g", "0.6", "-r", "48000", "-F", f"{OUT}/{name}_dry.wav", sf, f"{OUT}/{name}.mid"], check=True)
    from pedalboard import Pedalboard, Reverb, Compressor, HighpassFilter, Gain
    from pedalboard.io import AudioFile
    with AudioFile(f"{OUT}/{name}_dry.wav") as fh: audio = fh.read(fh.frames); sr = fh.samplerate
    board = Pedalboard([HighpassFilter(40), Reverb(room_size=0.85, damping=0.4, wet_level=0.35, dry_level=0.7, width=1.0),
                        Compressor(threshold_db=-18, ratio=2.5), Gain(-1)])
    out = board(audio, sr)[:, : int(seconds * sr)]
    with AudioFile(f"{OUT}/{name}.wav", "w", sr, out.shape[0]) as fh: fh.write(out)


MOODS = {"c1_hook": "mysterious", "c2_origins": "curious", "c3_annex": "melancholic", "c4_collapse": "tension", "c5_resolution": "reflective"}
# fill failed cues: original algorithmic orchestral cue (FluidSynth); last resort procedural pad
for name, sec, _ in CUES:
    if os.path.exists(f"{OUT}/{name}.wav"):
        continue
    try:
        orchestral(name, sec, MOODS[name]); report[name] = {"source": "algorithmic orchestral (FluidSynth)"}
    except Exception as e:
        traceback.print_exc(limit=2)
        pad(sec, f"{OUT}/{name}.wav"); report[name] = {"source": "procedural pad", "err": repr(e)[:200]}
json.dump(report, open(f"{OUT}/report.json", "w"), indent=1)
print(json.dumps(report, indent=1))
