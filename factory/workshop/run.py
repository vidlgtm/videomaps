#!/usr/bin/env python3
"""Workshop: the 3D pieces of an order.
stage preview (no GPU): preflight -> data of each piece (cached by content) -> CPU preview with exposure calibration and
              automatic checks -> <lkey>_preview.jpg/.json (+ <lkey>_labels.json) in the release
stage render : only pieces whose current preview passed -> Kaggle GPU within each piece's time budget -> <rkey>.mp4|.webm,
              <rkey>_sheet.jpg, <rkey>.json -> <orderDir>/out/workshop.json (clip assets for the director)
keys: dkey = data (prep params + prep script); vkey = look (render params + template code + dkey);
      lkey = preview (vkey + labels/places + preview code); rkey = clip (vkey + exposure + kernel code)
usage: python3 factory/workshop/run.py <orderDir> --stage preview|render [--blender PATH] [--release TAG] [--sha SHA] [--repo o/n] [--dry]
env  : GH_TOKEN; KAGGLE_API_TOKEN + KAGGLE_USERNAME when the render stage has pieces to render"""
import base64, hashlib, json, os, re, shutil, subprocess, sys, tarfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight

ROOT = HERE.parents[1]
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
ORDER = Path(a[0]).resolve()
STAGE = opt("--stage", "preview")
TAG, REPO = opt("--release", "factory_ws_cache"), opt("--repo", "vidlgtm/videomaps")
BLENDER = opt("--blender", "blender")
SHA = opt("--sha") or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
REG = json.load(open(HERE / "templates.json"))
TPL = HERE / "templates"
OUT = ORDER / "out"; REV = OUT / "ws_review"
WORKD = Path("/tmp/ws_run")


def run(cmd, check=True, **kw):
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


# ------------------------------------------------------------------ preflight + keys
spec = json.load(open(ORDER / "workshop.json"))
pieces, rep = preflight.check(spec, REG)
for n in rep.notes: print("note:", n, flush=True)
if rep.errors:
    print("PREFLIGHT FAILED - nothing was downloaded or rendered:", flush=True)
    for e in rep.errors: print("  -", e, flush=True)
    sys.exit(2)
print(f"preflight ok: {len(pieces)} pieces", flush=True)
COMMON, PREV, KERNEL = (TPL / "common.py").read_bytes() + (TPL / "terrain_mesh.py").read_bytes(), (HERE / "preview.py").read_bytes(), (HERE / "kaggle_kernel.py").read_bytes()
jobs = []
for p in pieces:
    t = REG[p["template"]]; prm = p["params"]
    prep_b = (TPL / t["prep"]).read_bytes() if t.get("prep") else b""
    dkey = sha(p["template"], {k: prm.get(k) for k in t.get("prep_keys", [])}, prep_b)
    rparams = {k: v for k, v in prm.items() if k not in t.get("overlay_keys", [])}
    vkey = sha(p["template"], rparams, p["seconds"], (TPL / t["script"]).read_bytes(), COMMON, dkey)
    lkey = sha(vkey, {k: prm.get(k) for k in t.get("overlay_keys", [])}, PREV)
    alpha = bool(t.get("alpha_when")) and all(prm.get(k) == v for k, v in t["alpha_when"].items())
    jobs.append({"id": p["id"], "template": p["template"], "script": t["script"], "prep": t.get("prep"), "labels": t.get("labels", False),
                 "alpha": alpha, "seconds": p["seconds"], "params": prm, "budget_min": p["budget_min"],
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
        elif j["prep"]:
            r = run([sys.executable, str(TPL / j["prep"]), str(wd / "params.json"), str(dd)], check=False)
            (wd / "prep.log").write_text(r.stdout + r.stderr)
            if r.returncode:
                pj = {"ok": False, "errors": ["data preparation failed:\n" + (r.stdout + r.stderr)[-2000:]], "warnings": []}
                summary.append((j["id"], pj, "failed")); any_bad = True; continue
            with tarfile.open(wd / dname, "w") as tf: tf.add(dd, arcname="data")
            upload(wd / dname); (wd / dname).unlink()
            print(f"{j['id']}: data prepared in {time.time() - t0:.0f}s\n{r.stdout[-600:]}", flush=True)
        t1 = time.time()
        cmd = [BLENDER, "-b", "--python-exit-code", "1", "-P", str(TPL / j["script"]), "--", "--params", str(wd / "params.json"),
               "--data", str(dd), "--out", str(od), "--preview"]
        with open(wd / "blender.log", "w") as lf: rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
        if rc or not (od / "check.json").exists():
            pj = {"ok": False, "errors": [f"preview render failed (rc {rc}):\n" + tail(wd / "blender.log", 3000)], "warnings": []}
            summary.append((j["id"], pj, "failed")); any_bad = True; continue
        for l in tail(wd / "blender.log", 20000).splitlines():
            if l.startswith(("built:", "weather", "exposure", "check grid", "preview written", "streak")): print(f"  {j['id']}: {l}", flush=True)
        pj, sheet = preview.evaluate(str(od), j["seconds"])
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
if STAGE != "render": fail(f"unknown stage {STAGE}")
todo, missing = [], []
for j in jobs:
    pn = f"{j['lkey']}_preview.json"
    if pn not in have: missing.append(f"{j['id']}: no preview of the current version"); continue
    pj = get_json(pn)
    if not pj.get("ok"): missing.append(f"{j['id']}: its preview did not pass"); continue
    j["ev"] = round(float(pj["ev"]), 2)
    j["hash"] = sha(j["vkey"], j["ev"], KERNEL)
    if f"{j['hash']}.json" not in have: todo.append(j)
if missing: fail("render needs a passing preview first:\n  " + "\n  ".join(missing))
print(f"pieces {len(jobs)} · rendered before {len(jobs) - len(todo)} · to render {len(todo)}", flush=True)
failed = []
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
    t = REG[j["template"]]
    m = get_json(f"{j['hash']}.json")
    c = {"src": f"ws/{m['file']}", "kind": t.get("kind_alpha", "doll") if j["alpha"] else t["kind"], "segments": {t["segment"]: [0, m["seconds"]]},
         "hash": j["hash"], "sheet": f"{j['hash']}_sheet.jpg", "credits": t.get("credits", [])}
    if j["labels"]: c["labels"] = f"{j['lkey']}_labels.json"
    if m.get("credit"): c["credit"] = m["credit"]
    clips[j["id"]] = c
    run(["gh", "release", "download", TAG, "-R", REPO, "-p", c["sheet"], "-O", str(REV / f"{j['id']}_sheet.jpg")], check=False)
json.dump({"release": TAG, "clips": clips}, open(OUT / "workshop.json", "w"), indent=1)
print(f"workshop.json: {len(clips)} clips ready" + (f" · FAILED: {', '.join(failed)}" if failed else ""), flush=True)
sys.exit(1 if failed or len(clips) < len(jobs) else 0)
