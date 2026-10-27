#!/usr/bin/env python3
"""Data of one 3D scene: the order-store pictures its cast uses, copied from <order>/store_files (or $STORE_DIR) into
DIR with their size, aspect and credit (DIR/meta.json). No picture is fetched here: pictures come only from the order
store, and each file must match the sha256 recorded in store.json. Map tiles, terrain, routes, the globe's Earth, models
and cut-outs are made by geodata.py (base-map sources only) into the same DIR (geo.json).
usage: python3 factory/workshop/prep.py <orderDir> <sceneId> <DIR>"""
import hashlib, json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geodata
LONG_MAX = 8192                       # longest side a texture keeps (GPU memory); larger pictures are scaled down


def used(sc):
    """order-store keys of the pictures a scene uses (models are files, not pictures: see models())"""
    keys = []
    for c in (sc.get("cast") or {}).values():
        s = str(c.get("from", ""))
        if s.startswith("store:") and c.get("is") != "model": keys.append(s[6:])
    for b in sc.get("beats") or []:
        w = str(b.get("with", ""))
        if w.startswith("store:"): keys.append(w[6:])
    return list(dict.fromkeys(keys))


def models(sc):
    """order-store keys of the GLB models a scene uses"""
    return [str(c["from"])[6:] for c in (sc.get("cast") or {}).values() if c.get("is") == "model" and str(c.get("from", "")).startswith("store:")]


def key_parts(sc):
    """what the scene data depends on besides the store files (map sources, regions, paths, models of the objects stage)"""
    return geodata.needs(sc)


def main(order, sid, out):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 400_000_000
    S = json.load(open(os.path.join(order, "scenes.json"), encoding="utf-8"))["scenes"][sid]
    sp = os.path.join(order, "store.json")
    store = json.load(open(sp, encoding="utf-8")).get("items", {}) if os.path.exists(sp) else {}
    src = os.environ.get("STORE_DIR") or os.path.join(order, "store_files")
    os.makedirs(out, exist_ok=True)
    items, credits, errs = {}, [], []
    for k in used(S):
        it = store.get(k)
        if not it: errs.append(f"{k}: not in store.json"); continue
        p = os.path.join(src, it["file"])
        if not os.path.exists(p): errs.append(f"{k}: {it['file']} is missing from the order store files"); continue
        data = open(p, "rb").read()
        if hashlib.sha256(data).hexdigest() != it["sha256"]: errs.append(f"{k}: {it['file']} differs from store.json (sha256)"); continue
        ext = os.path.splitext(it["file"])[1].lower()
        if ext == ".svg": errs.append(f"{k}: an SVG drawing cannot be a picture in a 3D scene yet (store a raster version)"); continue
        im = Image.open(p); w, h = im.size
        dst = os.path.splitext(it["file"])[0] + (".png" if ext not in (".jpg", ".jpeg") else ext)
        if max(w, h) > LONG_MAX or ext not in (".jpg", ".jpeg", ".png"):
            im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
            if max(w, h) > LONG_MAX: im = im.resize((round(w * LONG_MAX / max(w, h)), round(h * LONG_MAX / max(w, h))), Image.LANCZOS)
            if dst.endswith((".jpg", ".jpeg")): im.convert("RGB").save(os.path.join(out, dst), quality=95)
            else: im.save(os.path.join(out, dst))
        else: shutil.copy(p, os.path.join(out, dst))
        items[k] = {"file": dst, "aspect": w / h, "width": w, "height": h, "licence": it.get("licence"), "author": it.get("author"),
                    "source": it.get("source"), "title": it.get("title")}
        credits.append({"what": it.get("title") or k, "license": it.get("licence"), "author": it.get("author"), "page": it.get("source")})
    if not errs:
        nd = geodata.needs(S)
        if any(nd[k] for k in ("tiles", "splits", "terrains", "place", "globe", "routes", "models", "cutouts")):
            geodata.build(order, S, out, items, store, src, credits, errs)
    for e in errs: print("DATA ERROR:", e, flush=True)
    if errs: return 2
    json.dump({"scene": sid, "items": items, "credits": credits}, open(os.path.join(out, "meta.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{sid}: {len(items)} items in the scene data", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
