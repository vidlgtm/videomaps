#!/usr/bin/env python3
"""Objects: the order's 3D objects (<orderDir>/objects.json) - small map icons made with TripoSR and larger models made
with Hunyuan3D-2, both only from order-store pictures; a GLB kept in the order store is used as it is.
stage preview (no GPU): object check -> cut-out of each picture (with checks) -> coarse stand-in made on the CPU
              (TripoSR) rendered from 4 azimuths with automatic checks -> <pkey>_preview.jpg/.json in the release;
              a store GLB needs no GPU, so its final renders are made and checked here
stage render : objects whose current preview passed and was approved -> one Kaggle GPU batch (TripoSR fine for icons,
              Hunyuan3D-2 shape + texture for models, Blender GPU renders) -> final checks -> <rkey>_a<az>.png,
              <rkey>.glb (models), <rkey>_sheet.jpg, <rkey>.json. A final that failed is never made again unless
              --retry names it.
stage collect: the film line - <orderDir>/out/objects.json from objects already made (no GPU; fails when an object of
              the current version is not made yet)
keys: ikey = cut-out (store sha256 + cut code); pkey = preview (ikey + stand-in recipe + render code);
      rkey = final (ikey + final recipe version - a code fix that keeps the result never makes an object again)
usage: python3 factory/objects/objects.py <orderDir> --stage preview|render|collect [--blender PATH] [--triposr DIR]
       [--release TAG] [--repo o/n] [--sha SHA] [--retry a,b] [--dry]
env  : GH_TOKEN; KAGGLE_API_TOKEN + KAGGLE_USERNAME when the render stage has objects to make"""
import base64, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import checks, cut

ROOT = HERE.parents[1]
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
ORDER = Path(a[0]).resolve()
STAGE = opt("--stage", "preview")
TAG, REPO = opt("--release", "objects_cache"), opt("--repo", "vidlgtm/videomaps")
BLENDER = opt("--blender", "blender")
TSR = Path(opt("--triposr", os.path.expanduser("~/TripoSR")))
SHA = opt("--sha") or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
RETRY = set(filter(None, (opt("--retry") or "").split(",")))
OUT = ORDER / "out"; REV = OUT / "objects_review"
WORK = Path("/tmp/obj_run")
AZ = (0, 90, 180, 270)
NAME = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
IMAGE = ("image/jpeg", "image/png", "image/webp")
GLB = "model/gltf-binary"
# final recipes: change the version only when the result must change (it makes every object of that kind again)
ICON_FINAL = "triposr@107cefd mc320 | blender 768px 256spp | colours matched to the picture | v2"
MODEL_FINAL = "hunyuan3d-2@f8db630 dit-v2-0 50 steps octree 380 + paint-v2-0-turbo | blender 768px 160spp | exposure matched | v2"
STANDIN = "triposr cpu mc160 | blender 384px 24spp | colours matched to the picture | v2"
RENDER = (HERE / "render_obj.py").read_bytes()
CUTCODE = (HERE / "cut.py").read_bytes()
KERNEL = (HERE / "objects_kernel.py").read_text()


def run(cmd, check=True, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if check and r.returncode:
        print("FAILED:", " ".join(map(str, cmd[:6])), "\n", r.stdout[-1500:], "\n", r.stderr[-1500:], flush=True); sys.exit(1)
    return r


def fail(msg): print("OBJECTS ERROR:", msg, flush=True); sys.exit(2)


def sha(*parts):
    h = hashlib.sha1()
    for p in parts: h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True).encode())
    return h.hexdigest()[:14]


# ------------------------------------------------------------------ object check
def check_spec(order):
    errs, objs = [], {}
    p = order / "objects.json"
    if not p.exists(): return ["objects.json is missing"], {}, {}
    try: O = json.load(open(p, encoding="utf-8"))
    except Exception as e: return [f"objects.json is not valid JSON: {e}"], {}, {}
    sp = order / "store.json"
    store = json.load(open(sp, encoding="utf-8")).get("items", {}) if sp.exists() else {}
    for k in O:
        if k not in ("icons", "models", "approved", "hunyuan_terms", "note"):
            errs.append(f'unknown key "{k}" (icons, models, approved, hunyuan_terms, note)')
    for kind, sect, keys in (("icon", "icons", {"from", "az", "size", "note"}), ("model", "models", {"from", "seed", "faces", "texture", "note"})):
        S = O.get(sect, {})
        if not isinstance(S, dict): errs.append(f"{sect} must be an object {{name: {{...}}}}"); continue
        for n, e in S.items():
            where = f"{sect}.{n}"
            if not NAME.match(n): errs.append(f"{where}: names are lower-case letters, digits and _ (2-31 characters)"); continue
            if n in objs: errs.append(f"{where}: the name is used twice"); continue
            if not isinstance(e, dict): errs.append(f"{where} must be an object"); continue
            for k in e:
                if k not in keys: errs.append(f'{where}: unknown key "{k}" ({", ".join(sorted(keys))})')
            src = e.get("from")
            it = store.get(src) if isinstance(src, str) else None
            if not it: errs.append(f'{where}: "from" must be a key of the order store (store.json), got {src!r}'); continue
            mime = it.get("mime", "")
            if mime not in IMAGE + (GLB,): errs.append(f"{where}: {src} is {mime}; a 3D object needs a JPEG/PNG/WebP picture or a GLB"); continue
            if mime in IMAGE and min(it.get("width") or 0, it.get("height") or 0) < 256:
                errs.append(f"{where}: the picture {src} is smaller than 256 px"); continue
            o = {"name": n, "kind": kind, "from": src, "file": it["file"], "sha256": it["sha256"], "mime": mime,
                 "engine": "glb" if mime == GLB else ("triposr" if kind == "icon" else "hunyuan"),
                 "credit": {"what": it.get("title") or src, "license": it.get("licence"), "author": it.get("author"),
                            "page": it.get("source")}}
            if kind == "icon":
                o["az"] = e.get("az", 270); o["size"] = e.get("size", 1.0)
                if o["az"] not in AZ: errs.append(f"{where}: az must be one of 0, 90, 180, 270 (the preview sheet shows each)")
                if not isinstance(o["size"], (int, float)) or not 0.4 <= o["size"] <= 1.6: errs.append(f"{where}: size must be 0.4-1.6")
            else:
                o["seed"] = e.get("seed", 0); o["faces"] = e.get("faces", 40000); o["texture"] = e.get("texture", True)
                if not isinstance(o["seed"], int) or not 0 <= o["seed"] < 2 ** 31: errs.append(f"{where}: seed must be a whole number")
                if not isinstance(o["faces"], int) or not 10000 <= o["faces"] <= 120000: errs.append(f"{where}: faces must be 10000-120000")
                if not isinstance(o["texture"], bool): errs.append(f"{where}: texture must be true or false")
            objs[n] = o
    ni, nm = sum(o["kind"] == "icon" for o in objs.values()), sum(o["kind"] == "model" for o in objs.values())
    if ni > 16: errs.append(f"{ni} icons: at most 16 per order")
    if nm > 8: errs.append(f"{nm} models: at most 8 per order")
    if not objs and not errs: errs.append("objects.json holds no icon and no model")
    if any(o["engine"] == "hunyuan" for o in objs.values()) and O.get("hunyuan_terms") != "accepted":
        errs.append('models made with Hunyuan3D-2 need "hunyuan_terms": "accepted" in objects.json: its licence (Tencent '
                    'Hunyuan 3D 2.0 Community License) excludes the EU, the UK and South Korea, including showing its results there')
    for n in (O.get("approved") or {}):
        if n not in objs: errs.append(f'approved: "{n}" is not an object of this order')
    return errs, objs, O


errs, OBJ, META = check_spec(ORDER)
if errs:
    print("OBJECT CHECK FAILED - nothing was downloaded or made:", flush=True)
    for e in errs: print("  -", e, flush=True)
    sys.exit(2)
for o in OBJ.values():
    o["ikey"] = sha(o["sha256"], CUTCODE)
    if o["engine"] == "glb":
        o["pkey"] = o["rkey"] = sha(o["sha256"], o["kind"], o["name"], RENDER)
    elif o["engine"] == "triposr":
        o["pkey"] = sha(o["ikey"], o["kind"], o["name"], STANDIN, RENDER); o["rkey"] = sha(o["ikey"], ICON_FINAL)
    else:
        fin = {k: o[k] for k in ("seed", "faces", "texture")}
        o["pkey"] = sha(o["ikey"], o["kind"], o["name"], STANDIN, RENDER); o["rkey"] = sha(o["ikey"], fin, MODEL_FINAL)
print(f"object check ok: {len(OBJ)} objects", flush=True)
for o in OBJ.values():
    print(f"  {o['name']:20s} {o['kind']:5s} {o['engine']:7s} from {o['from']:20s} preview {o['pkey']}  final {o['rkey']}", flush=True)
if "--dry" in a: sys.exit(0)

if run(["gh", "release", "view", TAG, "-R", REPO], check=False).returncode:
    run(["gh", "release", "create", TAG, "-R", REPO, "--title", TAG, "--notes", "3D objects cache (content-addressed)"])


def assets():
    return {x["name"] for x in json.loads(run(["gh", "release", "view", TAG, "-R", REPO, "--json", "assets"]).stdout)["assets"]}


def get_json(name):
    return json.loads(run(["gh", "release", "download", TAG, "-R", REPO, "-p", name, "-O", "-"]).stdout)


def get(name, out):
    return run(["gh", "release", "download", TAG, "-R", REPO, "-p", name, "-O", str(out), "--clobber"], check=False).returncode == 0


def upload(*files):
    run(["gh", "release", "upload", TAG, "-R", REPO, "--clobber", *map(str, files)])


have = assets()
OUT.mkdir(exist_ok=True); REV.mkdir(parents=True, exist_ok=True)
STORE = Path(os.environ.get("STORE_DIR") or ORDER / "store_files")


def store_path(o):
    p = STORE / o["file"]
    if not p.exists(): return None, f"{o['file']} is missing from the order store files"
    if hashlib.sha256(p.read_bytes()).hexdigest() != o["sha256"]: return None, f"{o['file']} differs from store.json (sha256)"
    return p, None


def blender(mesh, out, name, res, samples, ref=None):
    cmd = [BLENDER, "-b", "--python-exit-code", "1", "-P", str(HERE / "render_obj.py"), "--", "--mesh", str(mesh), "--out", str(out),
           "--name", name, "--res", str(res), "--samples", str(samples), "--views", ",".join(map(str, AZ))] + (["--ref", str(ref)] if ref else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    for l in r.stdout.splitlines():
        if l.startswith(("rendered", "OBJECT ERROR")): print("   ", l, flush=True)
    rj = Path(out) / f"{name}_render.json"
    info = json.load(open(rj)) if rj.exists() else {"error": "no render report"}
    if r.returncode or "error" in info:
        return None, f"render failed (exit {r.returncode}): {info.get('error', '')}\n{r.stdout[-1200:]}\n{r.stderr[-800:]}"
    return info, None


def title(o, final):
    if o["engine"] == "glb": return f"{o['kind']} · GLB from the order store · final renders"
    if o["kind"] == "icon":
        return "icon · TripoSR final (GPU)" if final else "icon · TripoSR stand-in (CPU, coarse) - the final is made on the GPU"
    return "model · Hunyuan3D-2 final (GPU)" if final else "model · stand-in shape (TripoSR on CPU) - the final model: Hunyuan3D-2 on the GPU"


# ------------------------------------------------------------------ stage preview
if STAGE == "preview":
    index = get_json("objects_index.json") if "objects_index.json" in have else {}
    summary, bad, session, tri = [], False, None, []
    for o in OBJ.values():
        n, wd = o["name"], WORK / o["pkey"]
        if f"{o['pkey']}_preview.json" in have:
            pj = get_json(f"{o['pkey']}_preview.json")
            get(f"{o['pkey']}_preview.jpg", REV / f"{n}_preview.jpg")
            summary.append((n, pj, "cached")); bad |= not pj["ok"]; continue
        shutil.rmtree(wd, ignore_errors=True); wd.mkdir(parents=True)
        src, err = store_path(o)
        o["wd"], o["errs"], o["warns"] = wd, [], []
        if err: o["errs"].append(err); continue
        others = sorted(set(index.get(o["ikey"], [])) - {ORDER.name})
        if others: o["warns"].append("this picture already made a 3D object for " + ", ".join(others) + " (a repeat)")
        if o["engine"] == "glb":
            o["src"] = src; continue
        cp = wd / "cut.png"
        if f"{o['ikey']}_cut.png" in have and f"{o['ikey']}_cut.json" in have:
            get(f"{o['ikey']}_cut.png", cp); info = get_json(f"{o['ikey']}_cut.json")
        else:
            if session is None:
                import rembg
                session = rembg.new_session("u2net")
            info = cut.cut_out(str(src), str(cp), session)
            json.dump(info, open(wd / "cut.json", "w"))
            if cp.exists():
                shutil.copy(cp, wd / f"{o['ikey']}_cut.png"); shutil.copy(wd / "cut.json", wd / f"{o['ikey']}_cut.json")
                upload(wd / f"{o['ikey']}_cut.png", wd / f"{o['ikey']}_cut.json")
        e, w = checks.check_cut(info)
        o["errs"] += e; o["warns"] += w; o["cut"] = cp; o["cut_info"] = info
        if not e:
            cut.grey_input(str(cp), str(wd / "tsr_in.png")); tri.append(o)
    if tri:                                               # one TripoSR run for every stand-in (the model loads once)
        t = time.time()
        for i, o in enumerate(tri): (WORK / "tsr" / str(i)).mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable, "run.py", *[str(o["wd"] / "tsr_in.png") for o in tri], "--device", "cpu",
                            "--mc-resolution", "160", "--no-remove-bg", "--output-dir", str(WORK / "tsr"), "--model-save-format", "obj"],
                           capture_output=True, text=True, cwd=TSR)
        print(f"TripoSR (CPU) {len(tri)} stand-ins in {time.time() - t:.0f}s, exit {r.returncode}", flush=True)
        for i, o in enumerate(tri):
            m = WORK / "tsr" / str(i) / "mesh.obj"
            if m.exists(): o["mesh"] = m
            else: o["errs"].append("TripoSR made no mesh:\n" + (r.stdout + r.stderr)[-1500:])
    for o in OBJ.values():
        if "wd" not in o: continue
        n, wd = o["name"], o["wd"]
        t, final, views, M = time.time(), o["engine"] == "glb", {}, {}
        if not o["errs"]:
            mesh = o.get("src") if final else o.get("mesh")
            info, err = blender(mesh, wd / "views", o["rkey"] if final else n, 768 if final else 384, 128 if final else 24,
                                None if final else o.get("cut"))
            if err: o["errs"].append(err)
            else:
                views = {az: str(wd / "views" / f"{o['rkey'] if final else n}_a{az}.png") for az in AZ}
                e, w, M = checks.check_views(views, None if final else str(o["cut"]), final, info)
                o["errs"] += e; o["warns"] += w; M["mesh"] = info
        ok = not o["errs"]
        pj = {"ok": ok, "name": n, "kind": o["kind"], "engine": o["engine"], "pkey": o["pkey"], "rkey": o["rkey"], "ikey": o["ikey"],
              "errors": o["errs"], "warnings": o["warns"], "metrics": M, "cut": o.get("cut_info"), "preview_s": round(time.time() - t),
              "final": final and ok}
        note = None if final or not ok else ("approve with objects.json \"approved\": {\"%s\": \"%s\"}" % (n, o["pkey"]))
        im = checks.sheet(n, title(o, final), str(o["cut"]) if o.get("cut") else None, views or {az: None for az in AZ},
                          o.get("az", -1), ok, o["errs"], o["warns"], note)
        im.save(wd / f"{o['pkey']}_preview.jpg", quality=90)
        json.dump(pj, open(wd / f"{o['pkey']}_preview.json", "w"), indent=1)
        files = [wd / f"{o['pkey']}_preview.jpg", wd / f"{o['pkey']}_preview.json"]
        if final and ok:                                   # a store GLB: the final is made here
            fin = {"name": n, "kind": o["kind"], "engine": "glb", "rkey": o["rkey"], "files": [Path(v).name for v in views.values()],
                   "checks": M, "warnings": o["warns"]}
            for v in views.values(): files.append(Path(v))
            if o["kind"] == "model":
                shutil.copy(o["src"], wd / f"{o['rkey']}.glb"); files.append(wd / f"{o['rkey']}.glb"); fin["glb"] = f"{o['rkey']}.glb"
            shutil.copy(wd / f"{o['pkey']}_preview.jpg", wd / f"{o['rkey']}_sheet.jpg"); files.append(wd / f"{o['rkey']}_sheet.jpg")
            json.dump(fin, open(wd / f"{o['rkey']}.json", "w"), indent=1); files.append(wd / f"{o['rkey']}.json")
        upload(*files)
        shutil.copy(wd / f"{o['pkey']}_preview.jpg", REV / f"{n}_preview.jpg")
        index.setdefault(o["ikey"], [])
        if ORDER.name not in index[o["ikey"]]: index[o["ikey"]].append(ORDER.name)
        summary.append((n, pj, "new")); bad |= not ok
    json.dump(index, open(WORK / "objects_index.json", "w"), indent=0); upload(WORK / "objects_index.json")
    print("\nPREVIEW RESULTS", flush=True)
    for n, pj, how in summary:
        print(f"  {n}: {'PASS' if pj['ok'] else 'FAIL'} ({how}) {pj['kind']} {pj['engine']} preview {pj['pkey']}", flush=True)
        for e in pj.get("errors", []): print("     ERROR:", e[:1500], flush=True)
        for w in pj.get("warnings", []): print("     warning:", w, flush=True)
    json.dump({"stage": "preview", "objects": {n: pj for n, pj, _ in summary}}, open(OUT / "objects_preview.json", "w"), indent=1)
    sys.exit(1 if bad else 0)

# ------------------------------------------------------------------ stage render / collect
if STAGE not in ("render", "collect"): fail(f"unknown stage {STAGE}")
todo, missing = [], []
for o in OBJ.values():
    n = o["name"]
    if f"{o['rkey']}.json" in have: continue
    if o["engine"] == "glb":
        missing.append(f"{n}: the GLB has no checked renders yet (objects preview stage)"); continue
    pn = f"{o['pkey']}_preview.json"
    if pn not in have: missing.append(f"{n}: no preview of the current version"); continue
    pj = get_json(pn)
    if not pj.get("ok"): missing.append(f"{n}: its preview did not pass"); continue
    if (META.get("approved") or {}).get(n) != o["pkey"]:
        missing.append(f"{n}: its preview {o['pkey']} is not approved yet (objects.json \"approved\": {{\"{n}\": \"{o['pkey']}\"}})"); continue
    if f"{o['rkey']}_failed.json" in have and n not in RETRY:
        missing.append(f"{n}: its final failed before (see {o['rkey']}_sheet.jpg / _failed.json); it is made again only "
                       f"with --retry {n}, or change the picture or the seed"); continue
    todo.append(o)
if STAGE == "collect" and (todo or missing):
    fail("3D objects not made yet (objects workflow: preview, approval, render):\n  "
         + "\n  ".join(missing + [f"{o['name']}: approved, not made yet" for o in todo]))
if missing: fail("render needs a passing, approved preview first:\n  " + "\n  ".join(missing))
print(f"objects {len(OBJ)} · made before {len(OBJ) - len(todo)} · to make {len(todo)}", flush=True)
failed = []
if todo:
    import kaggle_job
    seen, uniq = set(), []
    for o in todo:                                         # objects with the same final are made once
        if o["rkey"] not in seen: seen.add(o["rkey"]); uniq.append(o)
    todo = uniq
    jobs = [{"name": o["name"], "kind": o["kind"], "engine": o["engine"], "rkey": o["rkey"], "ikey": o["ikey"],
             "cut": f"{o['ikey']}_cut.png", **({k: o[k] for k in ("seed", "faces", "texture")} if o["kind"] == "model" else {})}
            for o in todo]
    code = KERNEL.replace("__REPO_URL__", f"https://github.com/{REPO}.git").replace("__SHA__", SHA) \
        .replace("__BATCH__", base64.b64encode(json.dumps(jobs).encode()).decode()) \
        .replace("__DATA_URL__", f"https://github.com/{REPO}/releases/download/{TAG}/")
    nm = sum(o["engine"] == "hunyuan" for o in todo); ni = len(todo) - nm
    limit = min(330, (40 if nm else 18) + 3 * ni + 22 * nm + 15)
    slug = "obj-" + hashlib.sha1("".join(o["rkey"] for o in todo).encode()).hexdigest()[:12]
    print(f"Kaggle batch {slug}: {ni} icons + {nm} models · waiting at most {limit} min", flush=True)
    try:
        od, st = kaggle_job.run(code, slug, limit, f"/tmp/kout/{slug}")
    except kaggle_job.KaggleError as e:
        fail(str(e))
    res = json.load(open(od / "batch.json")) if (od / "batch.json").exists() else []
    if not res:
        print(kaggle_job.log_tail(od)); fail(f"the Kaggle run ended ({st}) without results")
    for x in res:
        o = OBJ[x["name"]]; wd = WORK / o["rkey"]; wd.mkdir(parents=True, exist_ok=True)
        cp = wd / "cut.png"; get(f"{o['ikey']}_cut.png", cp)
        views = {az: str(od / f"{o['rkey']}_a{az}.png") for az in AZ}
        rj = od / f"{o['rkey']}_render.json"
        if "error" in x or not rj.exists():
            errs_, warns_, M = [x.get("error") or "the run returned no render report"], [], {}
        else:
            info = json.load(open(rj))
            errs_, warns_, M = checks.check_views(views, str(cp), True, info); M["mesh"] = info
        ok = not errs_
        im = checks.sheet(o["name"], title(o, True), str(cp), views, o.get("az", -1), ok, [e[:300] for e in errs_], warns_)
        im.save(wd / f"{o['rkey']}_sheet.jpg", quality=90)
        meta = {"name": o["name"], "kind": o["kind"], "engine": o["engine"], "rkey": o["rkey"], "checks": M, "warnings": warns_,
                "stats": x.get("stats", {}), "minutes": x.get("minutes")}
        files = [wd / f"{o['rkey']}_sheet.jpg"]
        if ok:
            meta["files"] = [f"{o['rkey']}_a{az}.png" for az in AZ]
            files += [od / f for f in meta["files"]]
            if o["kind"] == "model": meta["glb"] = f"{o['rkey']}.glb"; files.append(od / meta["glb"])
            json.dump(meta, open(wd / f"{o['rkey']}.json", "w"), indent=1); files.append(wd / f"{o['rkey']}.json")
        else:
            meta["errors"] = errs_; failed.append(o["name"])
            json.dump(meta, open(wd / f"{o['rkey']}_failed.json", "w"), indent=1); files.append(wd / f"{o['rkey']}_failed.json")
        upload(*files)
        shutil.copy(wd / f"{o['rkey']}_sheet.jpg", REV / f"{o['name']}_final.jpg")
        print(f"{'made' if ok else 'FAILED'} {o['name']} ({o['kind']}, {x.get('minutes', '-')} min into the run)", flush=True)
        for e in errs_: print("   ERROR:", e[:1500], flush=True)
        for w in warns_: print("   warning:", w, flush=True)
    have = assets()

# collect: what the film line reads
res_i, res_m = {}, {}
for o in OBJ.values():
    if f"{o['rkey']}.json" not in have: continue
    m = get_json(f"{o['rkey']}.json")
    get(f"{o['rkey']}_sheet.jpg", REV / f"{o['name']}_final.jpg")
    if o["kind"] == "icon":
        res_i[o["name"]] = {"files": {str(az): f"{o['rkey']}_a{az}.png" for az in AZ}, "az": o["az"], "size": o["size"],
                            "credit": o["credit"], "rkey": o["rkey"]}
    else:
        res_m[o["name"]] = {"glb": m["glb"], "views": {str(az): f"{o['rkey']}_a{az}.png" for az in AZ}, "credit": o["credit"],
                            "rkey": o["rkey"], "engine": o["engine"]}
json.dump({"release": TAG, "icons": res_i, "models": res_m}, open(OUT / "objects.json", "w"), indent=1, ensure_ascii=False)
print(f"objects.json: {len(res_i)} icons, {len(res_m)} models" + (f" · FAILED: {', '.join(failed)}" if failed else ""), flush=True)
sys.exit(1 if failed or len(res_i) + len(res_m) < len(OBJ) else 0)
