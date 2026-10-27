#!/usr/bin/env python3
"""MAP LIBRARY - the factory's base maps. One map = one conformal canvas (mapdef.py) + its terrain (terrain.py):
basemap, HD cells and UHD tiles, kept as assets of the release "map_<key>" of this repository. A film whose places fit
inside a library map at a good resolution reuses it; a new region is defined and added once. Tiles are built only
where a camera path needs them and are then kept for every later film on that map.
The index of the library is the asset maps.json of the release "map_library".

usage:
  python factory/maps/library.py pick    <orderDir> <mapDir>             choose or define the map -> map.json, pick.json
  python factory/maps/library.py base    <mapDir>                        basemap of the map (download, else build + publish)
  python factory/maps/library.py tiles   <mapDir> <need.json>            HD/UHD tiles a camera path needs: download the ones
                                                                         the library has, build + publish the missing ones
  python factory/maps/library.py engine  <mapDir> <engineDir>            basemap + tiles + indexes (+ geo.json) into the engine
env: GH_TOKEN (contents: write) for publishing."""
import json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapdef

REPO = os.environ.get("GITHUB_REPOSITORY", "vidlgtm/videomaps")
API = "https://api.github.com/repos/" + REPO
UPLOADS = "https://uploads.github.com/repos/" + REPO
DL = f"https://github.com/{REPO}/releases/download"
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_TAG = "map_library"
MIN_MARGIN = 0.03            # the order's places must stay this far inside a library map (share of the canvas)
RES_TOL = 1.6                # a library map may be at most this much coarser than a map made for the order

# the map of the v5 film: its terrain lives in releases that are never modified (read only)
LEGACY = {
    "ussr_v5": {
        "def": {"kind": "lcc", "lon0": 90.0, "lat0": 55.0, "lat1": 45.0, "lat2": 62.0, "res_m": 1166.223316610423,
                "minx": -4847942.965522453, "maxy": 4577776.76183801, "width": 8192, "height": 5996, "name": "ussr_v5",
                "hd_origin": [0, 1024], "key": "ussr_v5"},
        "base": [("assets3", "basemap_v2.jpg", "basemap.jpg"), ("assets3", "basemap_v2_half.jpg", "basemap_half.jpg"),
                 ("assets3", "globe_night.jpg", "globe_night.jpg")],
        "zips": [("assets3", "hd_tiles.zip"), ("tiles5", "hd5.zip"), ("assets4", "uhd.zip"), ("tiles5", "uhd5.zip")],
        "geo": "factory/engine/src/data/geo.json",
    }
}


# ------------------------------------------------------------------ GitHub releases
def gh(path, method="GET", data=None, body=None, ctype=None, base=API):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "videomaps-maps"}
    if tok: h["Authorization"] = "Bearer " + tok
    if data is not None: body = json.dumps(data).encode(); ctype = "application/json"
    if ctype: h["Content-Type"] = ctype
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=h, method=method), timeout=600) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code == 422 and method == "POST": raise
            if i == 4: raise
        except Exception:
            if i == 4: raise
        time.sleep(3 + 5 * i)


def release(tag, create=False, note=""):
    r = gh(f"/releases/tags/{tag}")
    if r or not create: return r
    return gh("/releases", "POST", {"tag_name": tag, "name": tag, "body": note or "map library", "target_commitish": "main",
                                    "draft": False, "prerelease": True})


def assets(rel):
    """every asset of a release (paginated)"""
    out, page = [], 1
    while True:
        a = gh(f"/releases/{rel['id']}/assets?per_page=100&page={page}") or []
        out += a
        if len(a) < 100: return out
        page += 1


def upload(rel, path, name, replace=True):
    for a in assets(rel):
        if a["name"] == name:
            if not replace: return
            gh(f"/releases/assets/{a['id']}", "DELETE")
    ctype = "image/jpeg" if name.endswith(".jpg") else "application/json"
    gh(f"/releases/{rel['id']}/assets?name={urllib.parse.quote(name)}", "POST", body=open(path, "rb").read(), ctype=ctype, base=UPLOADS)


def download(url, path, tries=5):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "videomaps-maps"}), timeout=600) as r:
                open(path + ".part", "wb").write(r.read())
            os.replace(path + ".part", path); return True
        except urllib.error.HTTPError as e:
            if e.code == 404: return False
            if i == tries - 1: raise
        except Exception:
            if i == tries - 1: raise
        time.sleep(2 + 3 * i)


def library_index():
    rel = release(INDEX_TAG)
    if not rel: return {"maps": []}
    for a in assets(rel):
        if a["name"] == "maps.json":
            p = "/tmp/maps_index.json"
            if download(a["browser_download_url"], p): return json.load(open(p))
    return {"maps": []}


def save_index(idx):
    rel = release(INDEX_TAG, create=True, note="map library index (maps.json)")
    p = "/tmp/maps_index_new.json"; json.dump(idx, open(p, "w"), indent=1)
    upload(rel, p, "maps.json")


# ------------------------------------------------------------------ the order's extent
def order_extent(o):
    """lon/lat box of what the film must show: the main land of its countries, its point places and capitals"""
    import requests
    from shapely.geometry import shape as to_shape
    pts = []
    want = set(o.get("countries") or []) | set((o.get("map") or {}).get("countries") or [])
    if want:
        p = "cache/ne_10m_admin_0_countries_lakes.geojson"
        os.makedirs("cache", exist_ok=True)
        if not os.path.exists(p):
            r = requests.get("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries_lakes.geojson",
                             timeout=600, headers={"User-Agent": "videomaps-maps"}); r.raise_for_status()
            open(p, "wb").write(r.content)
        found = set()
        for f in json.load(open(p, encoding="utf-8"))["features"]:
            pr = {k.lower(): v for k, v in f["properties"].items()}
            iso = next((pr.get(k) for k in ("adm0_a3", "iso_a3", "iso_a3_eh") if pr.get(k) in want), None)
            if not iso: continue
            found.add(iso)
            g = to_shape(f["geometry"])
            parts = list(getattr(g, "geoms", [g]))
            main = max(parts, key=lambda q: q.area)
            mc = main.centroid
            for q in parts:                                 # main land + nearby parts (no far overseas territories)
                c = q.centroid
                if q.area >= 0.02 * g.area and abs(c.x - mc.x) <= 35 and abs(c.y - mc.y) <= 25 or q is main:
                    x0, y0, x1, y1 = q.bounds; pts += [(x0, y0), (x1, y1)]
        miss = want - found
        if miss: raise SystemExit(f"MAP ERROR: countries not in Natural Earth: {sorted(miss)}")
    for v in list((o.get("places") or {}).values()) + list((o.get("capitals") or {}).values()):
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v): pts.append(tuple(v))
    for v in (o.get("map") or {}).get("include") or []: pts.append(tuple(v))
    b = (o.get("map") or {}).get("bounds")
    if b: pts += [(b[0], b[1]), (b[2], b[3])]
    if not pts: raise SystemExit("MAP ERROR: the order has no countries, places or map bounds")
    a = np.array(pts, float)
    return [float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max())]


# ------------------------------------------------------------------ commands
def cmd_pick(odir, mdir):
    os.makedirs(mdir, exist_ok=True)
    o = json.load(open(os.path.join(odir, "order.json"), encoding="utf-8"))
    use = (o.get("map") or {}).get("use")
    if use in LEGACY:
        md = mapdef.MapDef(LEGACY[use]["def"]); mapdef.save(md, f"{mdir}/map.json")
        json.dump({"key": use, "legacy": True, "new": False, "release": "map_" + use}, open(f"{mdir}/pick.json", "w"))
        print(f"map: {use} (the v5 map, read-only releases + map_{use} for new tiles)"); return
    ext = order_extent(o)
    fresh = mapdef.define(ext, o.get("slug", ""))
    L, B = mapdef.extent_points(ext)
    idx = library_index()
    best = None
    for m in idx.get("maps", []):
        if use and use not in (m["key"], m.get("name")): continue
        md = mapdef.MapDef(m["def"])
        if md.kind != fresh.kind and not use: continue
        mg = md.margin_of(L, B)
        if use or (mg >= MIN_MARGIN and md.res <= fresh.res * RES_TOL):
            if best is None or md.res < best[0].res: best = (md, m)
    if use and not best: raise SystemExit(f'MAP ERROR: map "{use}" is not in the library')
    if best:
        md, m = best; mapdef.save(md, f"{mdir}/map.json")
        json.dump({"key": m["key"], "legacy": False, "new": False, "release": m["release"], "extent": ext}, open(f"{mdir}/pick.json", "w"))
        print(f"map: library map {m['key']} ({m.get('name')}) {md.kind} {md.W}x{md.H} {md.res / 1000:.3f} km/px for extent {ext}")
    else:
        mapdef.save(fresh, f"{mdir}/map.json")
        key = fresh.d["key"]
        json.dump({"key": key, "legacy": False, "new": True, "release": "map_" + key, "extent": ext}, open(f"{mdir}/pick.json", "w"))
        print(f"map: NEW map {key} {fresh.kind} {fresh.W}x{fresh.H} {fresh.res / 1000:.3f} km/px for extent {ext}")


def pick_of(mdir): return json.load(open(f"{mdir}/pick.json"))


def terrain(mdir, *args):
    subprocess.run([sys.executable, "-u", os.path.join(HERE, "terrain.py"), *args[:1], mdir, *args[1:]], check=True)


def cmd_base(mdir):
    p = pick_of(mdir)
    if p["legacy"]:
        L = LEGACY[p["key"]]
        for tag, src, dst in L["base"]:
            if not download(f"{DL}/{tag}/{src}", f"{mdir}/{dst}"): raise SystemExit(f"missing {tag}/{src}")
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        Image.open(f"{mdir}/globe_night.jpg").convert("RGB").resize((4096, 2048), Image.LANCZOS).save(f"{mdir}/globe_night_4k.jpg", quality=90)
        for tag, z in L["zips"]:
            zp = f"/tmp/{z}"
            if download(f"{DL}/{tag}/{z}", zp):
                subprocess.run(["unzip", "-q", "-o", zp, "-d", mdir], check=True)
        for f in ("hd/index.json", "uhd/index.json"):
            if os.path.exists(f"{mdir}/{f}"): os.remove(f"{mdir}/{f}")
        extra = release(p["release"])                          # tiles added to the v5 map later
        if extra:
            for a in assets(extra):
                m = re.fullmatch(r"(hd|uhd)_(.+\.jpg)", a["name"])
                if m: download(a["browser_download_url"], f"{mdir}/{m.group(1)}/{m.group(2)}")
        print("legacy map ready:", len(os.listdir(f"{mdir}/hd")) if os.path.isdir(f"{mdir}/hd") else 0, "HD,",
              len(os.listdir(f"{mdir}/uhd")) if os.path.isdir(f"{mdir}/uhd") else 0, "UHD"); return
    rel = release(p["release"])
    have = {a["name"]: a for a in assets(rel)} if rel else {}
    names = ("basemap.jpg", "basemap_half.jpg", "globe_day_4k.jpg", "globe_night_4k.jpg")
    if all(n in have for n in names):
        for n in names: download(have[n]["browser_download_url"], f"{mdir}/{n}")
        print(f"map {p['key']}: basemap from the library"); return
    terrain(mdir, "basemap")
    rel = release(p["release"], create=True, note=f"map library: map {p['key']} (map.json, basemap, HD cells hd_*, UHD tiles uhd_*)")
    upload(rel, f"{mdir}/map.json", "map.json")
    for n in names: upload(rel, f"{mdir}/{n}", n)
    idx = library_index()
    if not any(m["key"] == p["key"] for m in idx["maps"]):
        md = mapdef.load(f"{mdir}/map.json")
        idx["maps"].append({"key": p["key"], "name": md.d.get("name", ""), "def": md.d, "release": p["release"],
                            "lonlat_box": md.lonlat_box(), "added": time.strftime("%Y-%m-%d")})
        save_index(idx)
    print(f"map {p['key']}: basemap built and added to the library")


def cmd_tiles(mdir, need_path):
    p = pick_of(mdir)
    need = json.load(open(need_path)) if os.path.exists(need_path) else {}
    rel = release(p["release"], create=True, note=f"map library: map {p['key']}")
    have = {a["name"]: a for a in assets(rel)}
    built = {"hd": [], "uhd": []}
    for kind, pre in (("hd", "t"), ("uhd", "u")):
        todo = []
        for t in need.get(kind, []):
            name = f"{pre}_{t[0]}_{t[1]}.jpg"
            if os.path.exists(f"{mdir}/{kind}/{name}"): continue
            a = have.get(f"{kind}_{name}")
            if a and download(a["browser_download_url"], f"{mdir}/{kind}/{name}"): continue
            todo.append(t)
        if todo:
            terrain(mdir, kind, json.dumps(todo))
            for t in todo:
                name = f"{pre}_{t[0]}_{t[1]}.jpg"
                if os.path.exists(f"{mdir}/{kind}/{name}"):
                    upload(rel, f"{mdir}/{kind}/{name}", f"{kind}_{name}"); built[kind].append(t)
        print(f"{kind}: needed {len(need.get(kind, []))}, built {len(built[kind])}")
    json.dump(built, open(f"{mdir}/built_tiles.json", "w"))


def cmd_engine(mdir, edir):
    import shutil
    p = pick_of(mdir)
    md = mapdef.load(f"{mdir}/map.json")
    pub, data = f"{edir}/public", f"{edir}/src/data"
    os.makedirs(f"{pub}/hd", exist_ok=True); os.makedirs(f"{pub}/uhd", exist_ok=True)
    for src, dst in (("basemap.jpg", "basemap_v2.jpg"), ("basemap_half.jpg", "basemap_v2_half.jpg"),
                     ("globe_night_4k.jpg", "globe_night_4k.jpg"), ("globe_day_4k.jpg", "globe_day_4k.jpg")):
        if os.path.exists(f"{mdir}/{src}"): shutil.copy(f"{mdir}/{src}", f"{pub}/{dst}")
    hd = []
    for f in sorted(os.listdir(f"{mdir}/hd")) if os.path.isdir(f"{mdir}/hd") else []:
        m = re.fullmatch(r"t_(-?\d+)_(-?\d+)\.jpg", f)
        if m: shutil.copy(f"{mdir}/hd/{f}", f"{pub}/hd/{f}"); hd.append([int(m.group(1)), int(m.group(2))])
    uhd = []
    for f in sorted(os.listdir(f"{mdir}/uhd")) if os.path.isdir(f"{mdir}/uhd") else []:
        m = re.fullmatch(r"u_(-?\d+)_(-?\d+)\.jpg", f)
        if m and os.path.getsize(f"{mdir}/uhd/{f}"): shutil.copy(f"{mdir}/uhd/{f}", f"{pub}/uhd/{f}"); uhd.append([int(m.group(1)), int(m.group(2))])
    x0, y0 = md.d.get("hd_origin", [0, 0])
    json.dump({"x0": x0, "y0": y0, "tile": 512, "k": 4, "tiles": sorted(hd)}, open(f"{data}/hd_index.json", "w"))
    json.dump({"tile": 256, "k": 8, "tiles": sorted(uhd)}, open(f"{data}/uhd_index.json", "w"))
    if os.path.exists(f"{mdir}/geo.json"): shutil.copy(f"{mdir}/geo.json", f"{data}/geo.json")
    print(f"engine: map {p['key']} - basemap, {len(hd)} HD cells, {len(uhd)} UHD tiles" + (", geo.json" if os.path.exists(f"{mdir}/geo.json") else ""))


def main(a):
    if len(a) < 2: print(__doc__); sys.exit(1)
    c = a[0]
    if c == "pick" and len(a) == 3: cmd_pick(a[1], a[2])
    elif c == "base": cmd_base(a[1])
    elif c == "tiles" and len(a) == 3: cmd_tiles(a[1], a[2])
    elif c == "engine" and len(a) == 3: cmd_engine(a[1], a[2])
    else: print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
