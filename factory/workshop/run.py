#!/usr/bin/env python3
"""Workshop: the 3D scenes of an order (<orderDir>/scenes.json - every scene described in the order, built from the
general tools of kit/; there are no ready-made scenes).
stage preview (no GPU): scene check (spec.py) + no repeats (novelty.py) -> data of each scene (its order-store pictures,
              cached by content) -> CPU preview with exposure calibration and automatic checks -> <lkey>_preview.jpg/.json
              (+ <lkey>_labels.json) in the release
stage render : only scenes whose current preview passed -> Kaggle GPU within each scene's time budget -> <rkey>.mp4,
              <rkey>_sheet.jpg, <rkey>.json -> <orderDir>/out/workshop.json (clip assets for the director)
stage clips  : the film line - <orderDir>/out/workshop.json from pieces already rendered (no GPU; fails when a piece
              of the current version is not rendered yet)
keys: dkey = data (store files + prep code + map code when the scene uses map data); vkey = look (scene + kit code + dkey);
      lkey = preview (vkey + preview code); rkey = clip (vkey + exposure + kernel code)
usage: python3 factory/workshop/run.py <orderDir> --stage preview|render|clips [--blender PATH] [--release TAG] [--sha SHA] [--repo o/n] [--dry]
env  : GH_TOKEN; KAGGLE_API_TOKEN + KAGGLE_USERNAME when the render stage has pieces to render"""
import base64, hashlib, json, os, re, shutil, subprocess, sys, tarfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import novelty, prep, spec

ROOT = HERE.parents[1]
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
ORDER = Path(a[0]).resolve()
STAGE = opt("--stage", "preview")
TAG, REPO = opt("--release", "factory_ws_cache"), opt("--repo", "vidlgtm/videomaps")
BLENDER = opt("--blender", "blender")
SHA = opt("--sha") or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
KIT = HERE / "kit"
OUT = ORDER / "out"; REV = OUT / "ws_review"
WORKD = Path("/tmp/ws_run")


# gh commands go through net_retry.sh: a transient failure (timeout, HTTP 5xx, rate limit) is tried again
NET = str(Path(__file__).resolve().parents[1] / "tools" / "net_retry.sh")


def run(cmd, check=True, **kw):
    if cmd and cmd[0] == "gh": cmd = ["bash", NET, *cmd]
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if check and r.returncode:
        print("FAILED:", " ".join(map(str, cmd[:5])), "\n", r.stdout[-1500:], "\n", r.stderr[-1500:], flush=True); sys.exit(1)
    return r


def fail(msg): print("WORKSHOP ERROR:", msg, flush=True); sys.exit(2)


def sha(*parts):
    h = hashlib.sha1()
    for p in parts: h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True).encode())
    return h.hexdigest()[:14]


def tail(p, n=2500):
    try: return Path(p).read_text(errors="replace")[-n:]
    except Exception: return ""


# ------------------------------------------------------------------ scene check + keys
errs, S = spec.check(str(ORDER))
if errs:
    print("SCENE CHECK FAILED - nothing was downloaded or rendered:", flush=True)
    for e in errs: print("  -", e, flush=True)
    sys.exit(2)
if novelty.main(str(ORDER)): fail("a scene repeats an earlier one (see REPEATED above): describe a new idea")
print(f"scene check ok: {len(S)} scenes, no repeats", flush=True)
meta_o = json.load(open(ORDER / "scenes.json", encoding="utf-8"))
if meta_o.get("preview_only") and STAGE in ("render", "clips"): fail("this order is for previews only (preview_only)")
store = json.load(open(ORDER / "store.json", encoding="utf-8")).get("items", {}) if (ORDER / "store.json").exists() else {}
KITCODE = b"".join((KIT / f).read_bytes() for f in sorted(os.listdir(KIT)) if f.endswith(".py"))
PREP, PREV, KERNEL = (HERE / "prep.py").read_bytes(), (HERE / "preview.py").read_bytes(), (HERE / "kaggle_kernel.py").read_bytes()
GEOCODE = (HERE / "geodata.py").read_bytes()                     # builds the data of every scene (cut-outs, pieces, models, maps)
MAPCODE = b"".join((ROOT / "factory" / "maps" / f).read_bytes() for f in ("mapdef.py", "terrain.py", "geo_build.py"))
uses_map = lambda nd: bool(nd["tiles"] or nd["terrains"] or nd["place"] or nd["globe"] or nd["routes"] or nd["fly"] or nd["at"])
GPU_S_PER_FRAME = 9.0                # T4 OptiX, 1920x1080, 160 samples + denoise (measured once, raised when a scene needs it)
COST = {"terrain": 1.5, "sea": 1.5, "haze_in": 1.6, "rain": 1.3, "snow": 1.3}   # heavier scenes get a longer budget
if any(str(c.get("from", "")).startswith("obj:") for sc in S.values() for c in (sc.get("cast") or {}).values()) \
        and not (OUT / "objects.json").exists() and "--dry" not in a:
    r = run([sys.executable, str(ROOT / "factory" / "objects" / "objects.py"), str(ORDER), "--stage", "collect", "--repo", REPO], check=False)
    print(r.stdout[-1500:], flush=True)
    if r.returncode or not (OUT / "objects.json").exists(): fail("a scene uses a model of the objects stage that is not made yet (objects.py --stage collect failed)")
OBJ = json.load(open(OUT / "objects.json")).get("models", {}) if (OUT / "objects.json").exists() else {}
jobs = []
for sid, sc in S.items():
    files = {k: store[k]["sha256"] for k in prep.used(sc) + prep.models(sc)}
    objs = {n: OBJ.get(str(c["from"])[4:], {}).get("rkey") for n, c in (sc.get("cast") or {}).items() if str(c.get("from", "")).startswith("obj:")}
    look = {k: v for k, v in sc.items() if k not in ("note", "idea")}
    nd = prep.key_parts(sc)                                     # the map code is a key part only of scenes drawn from map data
    dkey = sha(files, nd, objs, PREP, GEOCODE + (MAPCODE if uses_map(nd) else b""))
    vkey = sha(look, KITCODE, dkey)
    lkey = sha(vkey, PREV)
    frames = int(round(float(sc["seconds"]) * 30))
    wx, pk = (sc.get("light") or {}).get("weather", "clear"), (sc.get("place") or {}).get("kind")
    cost = COST.get(pk, 1.0) * (COST["haze_in"] if wx == "haze" and pk not in ("terrain", "sea", "sky") else COST.get(wx, 1.0))
    budget = max(12.0, round(frames * GPU_S_PER_FRAME * cost / 60 * 1.6 + 4))
    jobs.append({"id": sid, "script": "build.py", "labels": any(b.get("do") == "label" for b in sc.get("beats", [])),
                 "alpha": sc.get("output") == "over_map", "seconds": sc["seconds"], "params": sc, "budget_min": budget,
                 "dkey": dkey, "vkey": vkey, "lkey": lkey})
for j in jobs: print(f"  {j['id']:24s} data {j['dkey']}  preview {j['lkey']}  budget {j['budget_min']:.0f} min", flush=True)
if "--dry" in a: sys.exit(0)

if run(["gh", "release", "view", TAG, "-R", REPO], check=False).returncode:
    run(["gh", "release", "create", TAG, "-R", REPO, "--title", TAG, "--notes", "workshop cache (content-addressed 3D pieces)"])


def assets():
    return {x["name"] for x in json.loads(run(["gh", "release", "view", TAG, "-R", REPO, "--json", "assets"]).stdout)["assets"]}


def get_json(name):
    return json.loads(run(["gh", "release", "download", TAG, "-R", REPO, "-p", name, "-O", "-"]).stdout)


def upload(*files):
    run(["gh", "release", "upload", TAG, "-R", REPO, "--clobber", *map(str, files)])


have = assets()
OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------ stage preview
if STAGE == "preview":
    import preview
    REV.mkdir(parents=True, exist_ok=True)
    summary, any_bad = [], False
    for j in jobs:
        if f"{j['lkey']}_preview.json" in have:
            pj = get_json(f"{j['lkey']}_preview.json")
            run(["gh", "release", "download", TAG, "-R", REPO, "-p", f"{j['lkey']}_preview.jpg", "-O", str(REV / f"{j['id']}_preview.jpg")], check=False)
            summary.append((j["id"], pj, "cached")); any_bad |= not pj["ok"]; continue
        wd = WORKD / j["lkey"]; dd = wd / "data"; od = wd / "out"
        shutil.rmtree(wd, ignore_errors=True); od.mkdir(parents=True)
        json.dump({**j["params"], "seconds": j["seconds"]}, open(wd / "params.json", "w"))
        t0 = time.time()
        dname = f"{j['dkey']}_data.tar"
        if dname in have:
            run(["gh", "release", "download", TAG, "-R", REPO, "-p", dname, "-D", str(wd), "--clobber"])
            with tarfile.open(wd / dname) as tf: tf.extractall(wd)
            (wd / dname).unlink()
            print(f"{j['id']}: data from the cache", flush=True)
        else:
            r = run([sys.executable, str(HERE / "prep.py"), str(ORDER), j["id"], str(dd)], check=False)
            (wd / "prep.log").write_text(r.stdout + r.stderr)
            if r.returncode:
                pj = {"ok": False, "errors": ["data preparation failed:\n" + (r.stdout + r.stderr)[-2000:]], "warnings": []}
                summary.append((j["id"], pj, "failed")); any_bad = True; continue
            with tarfile.open(wd / dname, "w") as tf: tf.add(dd, arcname="data")
            upload(wd / dname); (wd / dname).unlink()
            print(f"{j['id']}: data prepared in {time.time() - t0:.0f}s\n{r.stdout[-600:]}", flush=True)
        t1 = time.time()
        cmd = [BLENDER, "-b", "--python-exit-code", "1", "-P", str(KIT / j["script"]), "--", "--params", str(wd / "params.json"),
               "--data", str(dd), "--out", str(od), "--preview"]
        with open(wd / "blender.log", "w") as lf: rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
        if not (od / "check.json").exists() or (rc and not json.load(open(od / "check.json")).get("fatal")):
            pj = {"ok": False, "errors": [f"preview render failed (rc {rc}):\n" + tail(wd / "blender.log", 3000)], "warnings": []}
            summary.append((j["id"], pj, "failed")); any_bad = True; continue
        for l in tail(wd / "blender.log", 20000).splitlines():
            if l.startswith(("SCENE ERROR", "exposure", "check grid", "preview written", "picture colours", "preview:")): print(f"  {j['id']}: {l}", flush=True)
        pj, sheet = preview.evaluate(str(od), j["seconds"])
        if sheet is None:
            summary.append((j["id"], pj, "failed")); any_bad = True; continue
        pj.update({"id": j["id"], "lkey": j["lkey"], "vkey": j["vkey"], "dkey": j["dkey"], "preview_s": round(time.time() - t1),
                   "data_s": round(t1 - t0)})
        sheet.save(wd / f"{j['lkey']}_preview.jpg", quality=90)
        json.dump(pj, open(wd / f"{j['lkey']}_preview.json", "w"), indent=1)
        files = [wd / f"{j['lkey']}_preview.jpg", wd / f"{j['lkey']}_preview.json"]
        if (od / "labels.json").exists():
            shutil.copy(od / "labels.json", wd / f"{j['lkey']}_labels.json"); files.append(wd / f"{j['lkey']}_labels.json")
        upload(*files)
        shutil.copy(wd / f"{j['lkey']}_preview.jpg", REV / f"{j['id']}_preview.jpg")
        summary.append((j["id"], pj, "new")); any_bad |= not pj["ok"]
        shutil.rmtree(wd, ignore_errors=True)
    print("\nPREVIEW RESULTS", flush=True)
    for pid, pj, how in summary:
        print(f"  {pid}: {'PASS' if pj['ok'] else 'FAIL'} ({how})  ev {pj.get('ev', '-')}  subject {pj.get('subject_luma', '-')} "
              f"target {pj.get('luma_target', '-')}  cpu {pj.get('cpu_s_per_frame', '-')} s/frame", flush=True)
        for e in pj.get("errors", []): print("     ERROR:", e[:1500], flush=True)
        for w in pj.get("warnings", []): print("     warning:", w, flush=True)
    json.dump({"stage": "preview", "pieces": {pid: pj for pid, pj, _ in summary}}, open(OUT / "workshop_preview.json", "w"), indent=1)
    sys.exit(1 if any_bad else 0)

# ------------------------------------------------------------------ stage render
if STAGE not in ("render", "clips"): fail(f"unknown stage {STAGE}")
todo, missing = [], []
for j in jobs:
    pn = f"{j['lkey']}_preview.json"
    if pn not in have: missing.append(f"{j['id']}: no preview of the current version"); continue
    pj = get_json(pn)
    if not pj.get("ok"): missing.append(f"{j['id']}: its preview did not pass"); continue
    if not pj.get("approved") and not meta_o.get("approved", {}).get(j["id"]) == j["lkey"]:
        missing.append(f"{j['id']}: its preview {j['lkey']} is not approved yet (scenes.json \"approved\": {{\"{j['id']}\": \"{j['lkey']}\"}})"); continue
    j["ev"] = round(float(pj["ev"]), 2)
    j["credits_extra"] = pj.get("stats", {}).get("credits", [])
    j["hash"] = sha(j["vkey"], j["ev"], KERNEL)
    if f"{j['hash']}.json" not in have: todo.append(j)
if missing: fail("render needs a passing preview first:\n  " + "\n  ".join(missing))
print(f"pieces {len(jobs)} · rendered before {len(jobs) - len(todo)} · to render {len(todo)}", flush=True)
failed = []
if todo and STAGE == "clips":
    fail("3D pieces not rendered yet (workshop render stage, after their previews are approved): "
         + ", ".join(j["id"] for j in todo))
if todo:
    TOKEN, USER = os.environ.get("KAGGLE_API_TOKEN", ""), os.environ.get("KAGGLE_USERNAME", "")
    if not TOKEN or not USER: fail("pieces to render need the Kaggle key (KAGGLE_API_TOKEN + KAGGLE_USERNAME secrets for this run)")
    slug = "ws-" + hashlib.sha1("".join(j["hash"] for j in todo).encode()).hexdigest()[:12]
    kd = Path("/tmp/kws") / slug; kd.mkdir(parents=True, exist_ok=True)
    batch = base64.b64encode(json.dumps(todo).encode()).decode()
    code = KERNEL.decode().replace("__REPO_URL__", f"https://github.com/{REPO}.git").replace("__SHA__", SHA).replace("__BATCH__", batch) \
        .replace("__DATA_URL__", f"https://github.com/{REPO}/releases/download/{TAG}/")
    (kd / "kernel.py").write_text(code)
    json.dump({"id": f"{USER}/{slug}", "title": slug, "code_file": "kernel.py", "language": "python", "kernel_type": "script",
               "is_private": "true", "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4",
               "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}, open(kd / "kernel-metadata.json", "w"))
    r = run(["kaggle", "kernels", "push", "-p", str(kd)], check=False)
    if r.returncode or "error" in (r.stdout + r.stderr).lower():
        print((r.stdout + r.stderr).replace(USER, "***")[-800:]); fail("Kaggle push failed")
    limit = min(5.5 * 3600, (sum(j["budget_min"] for j in todo) + 45) * 60)
    print(f"KAGGLE_PUSHED {slug} · {', '.join(j['id'] for j in todo)} · budgets {sum(j['budget_min'] for j in todo):.0f} min "
          f"(+ setup) · waiting at most {limit / 60:.0f} min", flush=True)
    t0, st = time.time(), ""
    while time.time() - t0 < limit:
        time.sleep(60)
        o = run(["kaggle", "kernels", "status", f"{USER}/{slug}"], check=False).stdout
        m = re.search(r"(QUEUED|RUNNING|COMPLETE|ERROR|CANCEL\w*)", o.upper())
        st = m.group(1) if m else "?"
        print(f"  {int((time.time() - t0) / 60):3d} min  {st}", flush=True)
        if st in ("COMPLETE", "ERROR") or st.startswith("CANCEL"): break
    od = Path("/tmp/kout") / slug; od.mkdir(parents=True, exist_ok=True)
    run(["kaggle", "kernels", "output", f"{USER}/{slug}", "-p", str(od), "-o"], check=False)
    res = json.load(open(od / "batch.json")) if (od / "batch.json").exists() else []
    if not res:
        logs = sorted(od.glob("*.log"))
        print((logs[0].read_text(errors="replace")[-3000:] if logs else "no log").replace(USER, "***"))
        fail(f"the Kaggle run ended ({st}) without results")
    for x in res:
        if "error" in x:
            failed.append(x["id"]); print(f"PIECE FAILED {x['id']}:\n{x['error'][-2500:]}", flush=True); continue
        files = [od / f for f in (x["file"], f"{x['hash']}_sheet.jpg", f"{x['hash']}.json") if (od / f).exists()]
        upload(*files)
        print(f"published {x['id']} ({x['minutes']} min on Kaggle, budget {x.get('budget_min')} min)", flush=True)
    have = assets()

clips = {}
REV.mkdir(parents=True, exist_ok=True)
for j in jobs:
    if f"{j['hash']}.json" not in have: continue
    m = get_json(f"{j['hash']}.json")
    c = {"src": f"ws/{m['file']}", "kind": "over_map" if j["alpha"] else "film", "segments": {"shot": [0, m["seconds"]]},
         "hash": j["hash"], "sheet": f"{j['hash']}_sheet.jpg", "credits": j.get("credits_extra", [])}
    if j["labels"]: c["labels"] = f"{j['lkey']}_labels.json"
    clips[j["id"]] = c
    run(["gh", "release", "download", TAG, "-R", REPO, "-p", c["sheet"], "-O", str(REV / f"{j['id']}_sheet.jpg")], check=False)
json.dump({"release": TAG, "clips": clips}, open(OUT / "workshop.json", "w"), indent=1)
print(f"workshop.json: {len(clips)} clips ready" + (f" · FAILED: {', '.join(failed)}" if failed else ""), flush=True)
sys.exit(1 if failed or len(clips) < len(jobs) else 0)
