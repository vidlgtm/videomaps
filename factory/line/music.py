#!/usr/bin/env python3
"""MUSIC of a film order: an original, calm score made for this film (ACE-Step 1.5 on the Kaggle GPU), one cue per
music block of the order (order.json hook/chapters "music"), each as long as its block under the voice.
order.json "music":
  {"use": "score" (default) | "house",
   "cues": {"<cue>": {"caption": "calm cinematic documentary underscore, ...", "bpm": 72, "key": "D minor",
                      "timesig": 4, "seed": 11}, ...},
   "pick": {"<cue>": 0 | 1}}          take chosen after listening (default: the automatic choice)
  "house" = the house score of release stage1 (cues c1_hook, c2_origins, c3_annex, c4_collapse, c5_resolution).
Takes are kept by content (caption, tempo, key, length, seed, model) in the release music_cache: a cue that was made
once is never generated again.
usage: python factory/line/music.py <orderDir> <timeline.json> <outDir> [--plan]
env: GH_TOKEN; KAGGLE_API_TOKEN + KAGGLE_USERNAME when cues must be generated
out: <outDir>/music/music_<cue>.mp3, music.json ({cue: {file, lufs, take, seconds}}), music_report.txt
exit 2 = order problem (listed), 3 = generation needed but no Kaggle account in this run"""
import base64, hashlib, json, math, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
REPO = os.environ.get("GITHUB_REPOSITORY", "vidlgtm/videomaps")
CACHE = "music_cache"
ACE_COMMIT = "ca1e85fe9430179831e6bc6be790c332190a3866"     # ACE-Step 1.5, pinned
HOUSE = ("c1_hook", "c2_origins", "c3_annex", "c4_collapse", "c5_resolution")
SR = 48000


def fail(msg, code=2):
    print("MUSIC ERROR:", msg, flush=True); sys.exit(code)


# gh commands go through net_retry.sh: a transient failure (timeout, HTTP 5xx, rate limit) is tried again
NET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "net_retry.sh")


def sh(cmd, check=True):
    if cmd and cmd[0] == "gh": cmd = ["bash", NET, *cmd]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode: fail(f"{' '.join(map(str, cmd))[:200]}\n{r.stdout[-800:]}\n{r.stderr[-800:]}", 1)
    return r


# ------------------------------------------------------------------ blocks (same rules as the director's sound.ts)
def blocks_of(order, nar, tl):
    ids = [p["id"] for p in nar["paragraphs"]]
    ch = [{"music": order["hook"]["music"], "paragraphs": order["hook"]["paragraphs"]}] + order["chapters"]
    start = {c["i"]: c["start"] for c in tl["chunks"]}; end = {c["i"]: c["end"] for c in tl["chunks"]}
    bl = []
    for c in ch:
        cs = [ids.index(p) for p in c["paragraphs"]]
        if bl and bl[-1]["music"] == c["music"]: bl[-1]["c1"] = cs[-1]
        else: bl.append({"music": c["music"], "c0": cs[0], "c1": cs[-1]})
    END = tl["total"]
    for i, b in enumerate(bl):
        first, last = i == 0, i == len(bl) - 1
        b["from"] = 0.0 if first else start[b["c0"]] - 2.2
        b["to"] = END if last else (start[bl[1]["c0"]] + 3.0 if first else end[b["c1"]] + 2.5)
    return bl


def plan(odir, tl_path):
    o = json.load(open(f"{odir}/order.json", encoding="utf-8"))
    nar = json.load(open(f"{odir}/narration.json", encoding="utf-8"))
    tl = json.load(open(tl_path))
    M = o.get("music") or {}
    bl = blocks_of(o, nar, tl)
    use = M.get("use", "score")
    if use not in ("score", "house"): fail(f'order.json music.use must be "score" or "house", not "{use}"')
    need = {}
    for b in bl: need[b["music"]] = max(need.get(b["music"], 0), b["to"] - b["from"])
    errs, cues = [], {}
    for cue, sec in need.items():
        if use == "house":
            if cue not in HOUSE: errs.append(f'cue "{cue}" is not in the house score ({", ".join(HOUSE)})')
            cues[cue] = {"cue": cue, "need": round(sec, 2)}; continue
        c = (M.get("cues") or {}).get(cue)
        if not c or not str(c.get("caption", "")).strip():
            errs.append(f'cue "{cue}" has no caption in order.json music.cues (the film\'s own score is described per cue)'); continue
        cap = " ".join(str(c["caption"]).split())
        if not any(w in cap.lower() for w in ("instrumental", "no vocals")): cap += ", instrumental, no vocals"
        bpm = c.get("bpm")
        if bpm is not None and not (40 <= int(bpm) <= 160): errs.append(f'cue "{cue}": bpm {bpm} outside 40..160')
        dur = min(470, max(30, 5 * math.ceil((sec + 2.0) / 5)))
        j = {"cue": cue, "caption": cap, "bpm": int(bpm) if bpm is not None else None, "key": c.get("key", ""),
             "timesig": c.get("timesig", 4), "duration": dur, "seed": int(c.get("seed", 1000 + len(cues) * 17)),
             "need": round(sec, 2)}
        j["key_hash"] = hashlib.sha1(json.dumps({k: j[k] for k in ("caption", "bpm", "key", "timesig", "duration", "seed")},
                                                sort_keys=True).encode() + ACE_COMMIT.encode()
                                     + (HERE / "music_kernel.py").read_bytes()).hexdigest()[:16]
        cues[cue] = j
    if errs: fail("\n  " + "\n  ".join(errs))
    return use, cues, bl, M.get("pick") or {}


# ------------------------------------------------------------------ release cache
def gh_json(*args):
    r = sh(["gh", *args, "-R", REPO], check=False)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def cache_names():
    v = gh_json("release", "view", CACHE, "--json", "assets")
    return {a["name"] for a in v["assets"]} if v else set()


def ensure_cache():
    if sh(["gh", "release", "view", CACHE, "-R", REPO], check=False).returncode:
        sh(["gh", "release", "create", CACHE, "-R", REPO, "--title", CACHE, "--notes", "score takes kept by content (caption, tempo, key, length, seed, model)"])


def download(names, d):
    for n in names: sh(["gh", "release", "download", CACHE, "-R", REPO, "-p", n, "-D", str(d), "--clobber"])


# ------------------------------------------------------------------ audio measures
def decode_bin(f):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def measure(x):
    """integrated loudness, longest near-silence inside the piece, biggest 3 s loudness jump, peak"""
    import numpy as np, pyloudnorm as pyln
    m = pyln.Meter(SR)
    lufs = float(m.integrated_loudness(x)) if len(x) > SR * 3 else -70.0
    win, hop = 3 * SR, SR // 2
    st = []
    for a in range(0, max(1, len(x) - win), hop):
        seg = x[a:a + win]; ms = float(np.mean(seg ** 2))
        st.append(10 * math.log10(ms + 1e-12))
    st = np.array(st) if st else np.array([-120.0])
    body = st[2:-6] if len(st) > 10 else st
    quiet = body < (np.median(body) - 30)
    run = longest = 0
    for q in quiet:
        run = run + 1 if q else 0; longest = max(longest, run)
    lat = st[12:]                                                       # after the first 6 s (a fade-in is fine)
    jump = float(np.max(lat[8:] - lat[:-8])) if len(lat) > 8 else 0.0  # rise within 4 s
    peak = float(20 * math.log10(np.max(np.abs(x)) + 1e-9))
    return {"lufs": round(lufs, 2), "silence_s": round(longest * hop / SR, 1), "jump_db": round(jump, 1),
            "peak_db": round(peak, 2), "seconds": round(len(x) / SR, 2)}


def score(ms, need):
    s = 0.0
    if ms["silence_s"] > 1.5: s += 10 + ms["silence_s"]
    if ms["jump_db"] > 9: s += (ms["jump_db"] - 9) * 1.5          # calm beds: no sudden blasts
    if ms["seconds"] < need * 0.9: s += 5
    if ms["peak_db"] > -0.1: s += 1
    return round(s, 2)


# ------------------------------------------------------------------ main
def main(a):
    if len(a) < 3: print(__doc__); sys.exit(1)
    odir, tl_path, out = a[0].rstrip("/"), a[1], Path(a[2])
    use, cues, bl, pick = plan(odir, tl_path)
    rep = [f"MUSIC - order {os.path.basename(odir)} - {use}", "blocks:"]
    rep += [f"  {b['music']:16s} {b['from']:8.2f} -> {b['to']:8.2f}  ({b['to'] - b['from']:.1f} s)" for b in bl]
    print("\n".join(rep), flush=True)
    if "--plan" in a:
        print(json.dumps(cues, indent=1)); return
    (out / "music").mkdir(parents=True, exist_ok=True)
    res = {}
    if use == "house":
        for cue in cues:
            f = out / "music" / f"music_{cue}.mp3"
            sh(["gh", "release", "download", "stage1", "-R", REPO, "-p", f"music_{cue}.mp3", "-O", str(f), "--clobber"])
            ms = measure(decode_bin(f))
            res[cue] = {"file": f"music/music_{cue}.mp3", "lufs": ms["lufs"], "take": "house", "seconds": ms["seconds"]}
            rep.append(f"{cue}: house score {ms}")
        rep.append("WARNING: house score - the same music as other films (the film's own score: music.use score + captions)")
    else:
        ensure_cache()
        have = cache_names()
        todo = [j for j in cues.values() if f"{j['key_hash']}.json" not in have]      # .json = the cue was made (its takes are kept)
        rep.append(f"cues {len(cues)} · in the cache {len(cues) - len(todo)} · to generate {len(todo)}")
        print(rep[-1], flush=True)
        if todo:
            import kaggle_job
            try: kaggle_job.creds()
            except kaggle_job.KaggleError as e: fail(f"{len(todo)} cue(s) must be generated: {e}", 3)
            budget = 25 + sum(3 + j["duration"] / 60 * 1.5 for j in todo)
            code = (HERE / "music_kernel.py").read_text() \
                .replace("__JOBS__", base64.b64encode(json.dumps(todo).encode()).decode()) \
                .replace("__ACE_COMMIT__", ACE_COMMIT).replace("__BUDGET_MIN__", f"{budget:.0f}")
            slug = "mu-" + hashlib.sha1("".join(j["key_hash"] for j in todo).encode()).hexdigest()[:12]
            print(f"Kaggle: {len(todo)} cues, budget {budget:.0f} min", flush=True)
            od, st = kaggle_job.run(code, slug, budget + 30, f"/tmp/kmu/{slug}")
            r = json.load(open(od / "result.json")) if (od / "result.json").exists() else []
            if not r: fail(f"the Kaggle run ended ({st}) without results:\n{kaggle_job.log_tail(od)}", 1)
            for x in r:
                if "error" in x: print(f"CUE FAILED {x['key']}:\n{x['error'][-2000:]}", flush=True); continue
                files = [od / f for f in x["files"]] + [od / f"{x['key']}.json"]
                sh(["gh", "release", "upload", CACHE, "-R", REPO, "--clobber", *map(str, files)])
            have = cache_names()
        bad = []
        for cue, j in cues.items():
            names = [f"{j['key_hash']}_{k}.flac" for k in (0, 1) if f"{j['key_hash']}_{k}.flac" in have]
            if not names: bad.append(cue); continue
            download(names, out / "takes")
            ms = {n: measure(decode_bin(out / "takes" / n)) for n in names}
            sc = {n: score(ms[n], j["need"]) for n in names}
            if cue in pick and f"{j['key_hash']}_{int(pick[cue])}.flac" in names:
                best, how = f"{j['key_hash']}_{int(pick[cue])}.flac", "picked in the order"
            else:
                best, how = min(names, key=lambda n: (sc[n], n)), "automatic"
            f = out / "music" / f"music_{cue}.mp3"
            sh(["ffmpeg", "-v", "error", "-y", "-i", str(out / "takes" / best), "-af", "silenceremove=start_periods=1:start_threshold=-60dB",
                "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "320k", str(f)])
            fm = measure(decode_bin(f))
            res[cue] = {"file": f"music/music_{cue}.mp3", "lufs": fm["lufs"], "take": int(best[-6]), "seconds": fm["seconds"],
                        "key": j["key_hash"], "caption": j["caption"]}
            rep.append(f"{cue}: take {best[-6]} ({how}) of {len(names)} · need {j['need']} s · "
                       + " | ".join(f"take {n[-6]} {ms[n]} score {sc[n]}" for n in names))
        if bad: fail("no takes for cue(s) " + ", ".join(bad) + " (see the Kaggle log above)", 1)
    json.dump(res, open(out / "music.json", "w"), indent=1)
    (out / "music_report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep[-len(cues) - 1:]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
