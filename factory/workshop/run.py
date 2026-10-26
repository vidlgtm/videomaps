#!/usr/bin/env python3
"""Workshop: renders the 3D pieces of an order on Kaggle GPU (cached by content hash) and publishes them.
usage: python3 factory/workshop/run.py <orderDir> [--release factory_ws_cache] [--sha SHA] [--repo owner/name]
env  : GH_TOKEN; KAGGLE_API_TOKEN + KAGGLE_USERNAME only when a piece is not in the cache yet
out  : <orderDir>/out/workshop.json (clip assets for the director) + files in the release"""
import base64, glob, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
ORDER = Path(a[0]).resolve()
TAG, REPO = opt("--release", "factory_ws_cache"), opt("--repo", "vidlgtm/videomaps")
SHA = opt("--sha") or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
REG = json.load(open(HERE / "templates.json"))


def run(cmd, check=True, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if check and r.returncode:
        print("FAILED:", " ".join(cmd[:4]), "\n", r.stdout[-1200:], "\n", r.stderr[-1200:], flush=True); sys.exit(1)
    return r


def fail(msg): print("WORKSHOP ERROR:", msg, flush=True); sys.exit(2)


spec = json.load(open(ORDER / "workshop.json"))
pieces = spec.get("pieces", [])
if not pieces: fail("workshop.json has no pieces")
ids = [p["id"] for p in pieces]
if len(set(ids)) != len(ids): fail("piece ids must be unique")
jobs = []
for p in pieces:
    t = REG.get(p.get("template")) or fail(f"piece {p['id']}: unknown template {p.get('template')} (known: {', '.join(REG)})")
    sec = float(p.get("seconds", 0))
    if not 2 <= sec <= 40: fail(f"piece {p['id']}: seconds must be 2..40")
    files = [HERE / "templates" / t["script"], HERE / "templates" / "common.py"] + ([HERE / "templates" / t["prep"]] if t.get("prep") else [])
    h = hashlib.sha1()
    h.update(json.dumps({"template": p["template"], "params": p.get("params", {}), "seconds": sec}, sort_keys=True).encode())
    for f in files + [HERE / "kaggle_kernel.py"]: h.update(f.read_bytes())
    alpha = all(p.get("params", {}).get(k) == v for k, v in t.get("alpha_when", {"_": object()}).items()) if t.get("alpha_when") else False
    jobs.append({"id": p["id"], "template": p["template"], "script": t["script"], "prep": t.get("prep"), "labels": t.get("labels", False),
                 "alpha": alpha, "seconds": sec, "params": p.get("params", {}), "hash": h.hexdigest()[:14]})

if run(["gh", "release", "view", TAG, "-R", REPO], check=False).returncode:
    run(["gh", "release", "create", TAG, "-R", REPO, "--title", TAG, "--notes", "workshop cache (content-addressed 3D pieces)"])
have = {x["name"] for x in json.loads(run(["gh", "release", "view", TAG, "-R", REPO, "--json", "assets"]).stdout)["assets"]}
todo = [j for j in jobs if f"{j['hash']}.json" not in have]
print(f"pieces {len(jobs)} · cached {len(jobs) - len(todo)} · to render {len(todo)}", flush=True)

failed = []
if todo:
    TOKEN, USER = os.environ.get("KAGGLE_API_TOKEN", ""), os.environ.get("KAGGLE_USERNAME", "")
    if not TOKEN or not USER: fail("pieces to render need the Kaggle key (KAGGLE_API_TOKEN + KAGGLE_USERNAME secrets for this run)")
    slug = "ws-" + hashlib.sha1("".join(j["hash"] for j in todo).encode()).hexdigest()[:12]
    kd = Path("/tmp/kws") / slug; kd.mkdir(parents=True, exist_ok=True)
    batch = base64.b64encode(json.dumps(todo).encode()).decode()
    code = (HERE / "kaggle_kernel.py").read_text().replace("__REPO_URL__", f"https://github.com/{REPO}.git").replace("__SHA__", SHA).replace("__BATCH__", batch)
    (kd / "kernel.py").write_text(code)
    json.dump({"id": f"{USER}/{slug}", "title": slug, "code_file": "kernel.py", "language": "python", "kernel_type": "script",
               "is_private": "true", "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4",
               "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}, open(kd / "kernel-metadata.json", "w"))
    r = run(["kaggle", "kernels", "push", "-p", str(kd)], check=False)
    if r.returncode or "error" in (r.stdout + r.stderr).lower():
        print((r.stdout + r.stderr).replace(USER, "***")[-800:]); fail("Kaggle push failed")
    print("KAGGLE_PUSHED", slug, "·", ", ".join(j["id"] for j in todo), flush=True)
    t0, st = time.time(), ""
    while time.time() - t0 < 5.5 * 3600:
        time.sleep(60)
        out = run(["kaggle", "kernels", "status", f"{USER}/{slug}"], check=False).stdout
        m = re.search(r"(QUEUED|RUNNING|COMPLETE|ERROR|CANCEL\w*)", out.upper())
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
        files = [str(od / f) for f in (x["file"], f"{x['hash']}_sheet.jpg", f"{x['hash']}_labels.json", f"{x['hash']}.json") if (od / f).exists()]
        run(["gh", "release", "upload", TAG, "-R", REPO, "--clobber", *files])
        print(f"published {x['id']} ({x['minutes']} min on Kaggle)", flush=True)
    have = {x["name"] for x in json.loads(run(["gh", "release", "view", TAG, "-R", REPO, "--json", "assets"]).stdout)["assets"]}

clips = {}
for j in jobs:
    if f"{j['hash']}.json" not in have: continue
    t = REG[j["template"]]
    m = json.loads(run(["gh", "release", "download", TAG, "-R", REPO, "-p", f"{j['hash']}.json", "-O", "-"]).stdout)
    c = {"src": f"ws/{m['file']}", "kind": t.get("kind_alpha", "doll") if j["alpha"] else t["kind"], "segments": {t["segment"]: [0, m["seconds"]]},
         "hash": j["hash"], "sheet": f"{j['hash']}_sheet.jpg", "credits": t.get("credits", [])}
    if m.get("labels"): c["labels"] = f"{j['hash']}_labels.json"
    if m.get("credit"): c["credit"] = m["credit"]
    clips[j["id"]] = c
(ORDER / "out").mkdir(exist_ok=True)
json.dump({"release": TAG, "clips": clips}, open(ORDER / "out" / "workshop.json", "w"), indent=1)
print(f"workshop.json: {len(clips)} clips ready" + (f" · FAILED: {', '.join(failed)}" if failed else ""), flush=True)
sys.exit(1 if failed or len(clips) < len(jobs) else 0)
