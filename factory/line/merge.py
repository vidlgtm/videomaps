#!/usr/bin/env python3
"""Joins the line's parts into what the director and the engine read.
usage:
  python factory/line/merge.py workshop <orderDir> <workshop.json> <publicDir> <labelsDir>
        3D pieces of the order (workshop clips stage) -> <orderDir>/assets.json clips (film -> full-frame "cauc",
        over_map -> overlay "doll"), their store credits, clip files in <publicDir>/ws (publicDir - = no clip files),
        label tracks in <labelsDir>
  python factory/line/merge.py labels <orderDir> <labelsDir> <engineDataDir>
        one label track per labelled clip -> <engineDataDir>/clip_labels.json ({labels file: track})
  python factory/line/merge.py own <orderDir> <publicDir>
        order.json "own_assets": [{"release": tag, "file": name, "to": "path in public/", "unzip": false}] - earlier
        pieces of this repository (never pictures from the web) -> <publicDir>
  python factory/line/merge.py lufs <film.json> <music.json>
        measured loudness of the film's score cues -> film.json music entries
  python factory/line/merge.py noscore <film.json>
        stills run without the score (no cue made yet): the score cues leave film.json, so the engine and the
        soundtrack preview use only files that exist (voice and sound effects); such stills are never approvable
  python factory/line/merge.py objects <orderDir> <objects.json> <publicDir> <engineDataDir>
        the order's 3D icons (objects collect stage) -> <publicDir>/icons/<name>_a<az>.png (publicDir - = measure only),
        <orderDir>/assets.json icons {name: {az, size, bb}} + their store credits, measured content boxes ->
        <engineDataDir>/icon_boxes.json; models are listed for the workshop
env: GH_TOKEN, GITHUB_REPOSITORY"""
import json, os, subprocess, sys

REPO = os.environ.get("GITHUB_REPOSITORY", "vidlgtm/videomaps")


def fail(msg):
    print("LINE ERROR:", msg, flush=True); sys.exit(2)


def gh_download(tag, name, dest_dir=None, out=None):
    cmd = ["gh", "release", "download", tag, "-R", REPO, "-p", name, "--clobber"]
    cmd += ["-O", out] if out else ["-D", dest_dir]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: fail(f"cannot download {name} from release {tag}: {r.stderr.strip()[-300:]}")


def load(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def cmd_workshop(odir, wsj, pub, labdir):
    W = load(wsj)
    if not W: fail(f"{wsj} is missing")
    A = load(f"{odir}/assets.json", {})
    A.setdefault("clips", {}); A.setdefault("credits", [])
    if pub != "-": os.makedirs(f"{pub}/ws", exist_ok=True)
    os.makedirs(labdir, exist_ok=True)
    for cid, c in W["clips"].items():
        if cid in A["clips"]: fail(f'3D piece "{cid}" has the same id as a clip of assets.json')
        f = c["src"].split("/", 1)[1]
        if pub != "-": gh_download(W["release"], f, f"{pub}/ws")
        e = {"src": c["src"], "kind": "cauc" if c["kind"] == "film" else "doll", "segments": c["segments"]}
        if c.get("labels"):
            gh_download(W["release"], c["labels"], labdir); e["labels"] = c["labels"]
        A["clips"][cid] = e
        for cr in c.get("credits", []):
            A["credits"].append({**cr, "files": [c["src"]]})
        print(f"3D piece {cid}: {c['src']} ({e['kind']}){' + label track' if c.get('labels') else ''}", flush=True)
    json.dump(A, open(f"{odir}/assets.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def cmd_labels(odir, labdir, data):
    A = load(f"{odir}/assets.json", {})
    out = {}
    for cid, c in (A.get("clips") or {}).items():
        lab = c.get("labels")
        if not lab: continue
        for p in (f"{labdir}/{lab}", f"{odir}/data/{lab}"):
            if os.path.exists(p):
                t = json.load(open(p))
                if not t.get("tracks") or not t.get("frames"): fail(f"label track {lab} of clip {cid} is empty")
                out[lab] = t; break
        else:
            fail(f"label track {lab} of clip {cid} not found")
    json.dump(out, open(f"{data}/clip_labels.json", "w"))
    print(f"label tracks: {len(out)} ({', '.join(out) or 'none'})", flush=True)


def cmd_own(odir, pub):
    o = load(f"{odir}/order.json", {})
    for it in o.get("own_assets", []):
        tag, name, to = it["release"], it["file"], it.get("to", it["file"])
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".svg")) and not it.get("made_here"):
            fail(f"own_assets {tag}/{name}: pictures come from the order store, not from releases")
        if it.get("unzip"):
            z = f"/tmp/own_{name}"
            gh_download(tag, name, out=z)
            os.makedirs(f"{pub}/{to}", exist_ok=True)
            subprocess.run(["unzip", "-q", "-o", z, "-d", f"{pub}/{to}"], check=True)
        else:
            os.makedirs(os.path.dirname(f"{pub}/{to}") or pub, exist_ok=True)
            gh_download(tag, name, out=f"{pub}/{to}")
        print(f"own asset {tag}/{name} -> public/{to}", flush=True)


def cmd_lufs(filmp, musicp):
    F, M = load(filmp), load(musicp, {})
    by = {v["file"]: v["lufs"] for v in M.values()}
    n = 0
    for m in F.get("music", []):
        if m["src"] in by: m["lufs"] = by[m["src"]]; n += 1
    miss = [m["src"] for m in F.get("music", []) if m["src"] not in by]
    json.dump(F, open(filmp, "w"))
    print(f"score loudness: {n} cues measured" + (f" · not in music.json: {', '.join(miss)}" if miss else ""), flush=True)
    if miss: fail("score cues missing: " + ", ".join(miss))


def cmd_noscore(filmp):
    F = load(filmp)
    cues = [m["src"] for m in F.get("music", [])]
    F["music"] = []
    json.dump(F, open(filmp, "w"))
    print(f"no score: {len(cues)} cue(s) left out of these stills and of the soundtrack preview"
          + (f" ({', '.join(cues)})" if cues else ""), flush=True)


def icon_box(png):
    import numpy as np
    from PIL import Image
    al = np.asarray(Image.open(png).convert("RGBA"))[..., 3]
    ys, xs = np.where(al > 8)
    if not len(xs): fail(f"{png} is empty")
    h, w = al.shape
    return [float(round(v, 3)) for v in (xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h)]


def cmd_objects(odir, objp, pub, data):
    O = load(objp)
    if not O: fail(f"{objp} is missing")
    A = load(f"{odir}/assets.json", {})
    A.setdefault("icons", {}); A.setdefault("credits", [])
    B = load(f"{data}/icon_boxes.json", {})
    for n, ic in O.get("icons", {}).items():
        if n in A["icons"]: fail(f'3D icon "{n}" has the same name as an icon of assets.json')
        az = int(ic["az"]); f = ic["files"][str(az)]
        dest = f"{pub}/icons/{n}_a{az}.png" if pub != "-" else f"/tmp/objects_icons/{n}_a{az}.png"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        gh_download(O["release"], f, out=dest)
        bb = icon_box(dest)
        A["icons"][n] = {"az": az, "size": ic["size"], "bb": bb}
        B[f"{n}_a{az}"] = bb
        c = ic.get("credit") or {}
        if c.get("license"):
            A["credits"].append({"what": f"{c.get('what')} (3D icon)", "license": c["license"], "author": c.get("author"),
                                 "page": c.get("page"), "files": [f"icons/{n}_a{az}.png"]})
        print(f"3D icon {n}: a{az}, size {ic['size']}, content box {bb}", flush=True)
    json.dump(A, open(f"{odir}/assets.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(B, open(f"{data}/icon_boxes.json", "w"), indent=0)
    for n, m in O.get("models", {}).items():
        print(f"3D model {n}: {m['glb']} (for the workshop)", flush=True)


def main(a):
    if not a: print(__doc__); sys.exit(1)
    c = a[0]
    if c == "workshop" and len(a) == 5: cmd_workshop(*a[1:])
    elif c == "labels" and len(a) == 4: cmd_labels(*a[1:])
    elif c == "own" and len(a) == 3: cmd_own(*a[1:])
    elif c == "lufs" and len(a) == 3: cmd_lufs(*a[1:])
    elif c == "noscore" and len(a) == 2: cmd_noscore(a[1])
    elif c == "objects" and len(a) == 5: cmd_objects(*a[1:])
    else: print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
