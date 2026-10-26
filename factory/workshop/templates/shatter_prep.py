"""Workshop template 'shatter' - data: a base map and map pieces with flags, on one web-mercator grid over the bbox.
base   : base.jpg - Sentinel-2 cloudless 2016 (EOX IT Services, CC BY 4.0) or a dark land/sea map from Natural Earth -
         with the international land borders (Natural Earth 10m; only between given countries / groups when listed)
pieces : Natural Earth 10m countries (one, or several merged), provinces or disputed areas, in base pixels: top
         triangles + outline rings (side walls), a distance field (R: inside distance to the outline, G: distance to the
         borders shared with other pieces, B: outside distance) and a label point inside the shape
flags  : Wikimedia Commons files (rendered to PNG by Commons) or direct PNG/JPG urls, licences checked, credits listed
usage: python3 shatter_prep.py <params.json> <out_dir>
params: bbox [lon0, lon1, lat0, lat1]; zoom (set by the preflight); base satellite|dark; base_borders true|false|
        [ISO3 | [ISO3, ...]]; pieces [{key, admin0 ISO3|[ISO3...] | admin1 [names] + country | disputed, flag}];
        union {flag} (action break)"""
import io, json, math, os, re, sys, time
import concurrent.futures as cf
import numpy as np, requests
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

P = json.load(open(sys.argv[1])); OUT = sys.argv[2]
os.makedirs(f"{OUT}/flags", exist_ok=True)
LON0, LON1, LAT0, LAT1 = [float(v) for v in P["bbox"]]
Z = int(P["zoom"])
N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
W, H = int(round(x1 - x0)), int(round(y1 - y0))
Image.MAX_IMAGE_PIXELS = None
SES = requests.Session()
SES.headers["User-Agent"] = "videomaps-workshop/1.2 (map history films)"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
print("zoom", Z, "base", W, "x", H, flush=True)


def fetch(url, **kw):
    for i in range(7):
        try:
            r = SES.get(url, timeout=90, **kw); r.raise_for_status(); return r
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"download failed: {url}")


def s2_mosaic(z, px0, py0, w, h):
    nt = 2 ** z
    tx0, ty0 = int(px0 // 256), int(py0 // 256)
    tx1, ty1 = int((px0 + w - 1e-6) // 256), int((py0 + h - 1e-6) // 256)
    arr = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8)

    def one(t):
        tx, ty = t
        if not 0 <= ty < nt: return
        im = Image.open(io.BytesIO(fetch(f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{ty}/{tx % nt}.jpg").content))
        arr[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = np.asarray(im.convert("RGB"))

    tiles = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    with cf.ThreadPoolExecutor(24) as ex: list(ex.map(one, tiles))
    print(f"  s2 z{z}: {len(tiles)} tiles", flush=True)
    r0, c0 = int(round(py0 - ty0 * 256)), int(round(px0 - tx0 * 256))
    return arr[r0:r0 + h, c0:c0 + w]


import geopandas as gpd
import shapely
from shapely.geometry import box, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polylabel


def to_px(g):
    def f(c):
        lat = np.clip(c[:, 1], -85.0, 85.0)
        return np.column_stack([(c[:, 0] + 180) / 360 * N - x0,
                                (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / np.pi) / 2 * N - y0])
    return shapely.transform(g, f)


def polys(g):
    if g is None or g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)): return [p for x in g.geoms for p in polys(x)]
    return []


def lines(g):
    if g is None or g.is_empty: return []
    if isinstance(g, LineString): return [g]
    if isinstance(g, (MultiLineString, GeometryCollection)): return [l for x in g.geoms for l in lines(x)]
    if isinstance(g, (Polygon, MultiPolygon)): return lines(g.boundary)
    return []


adm0 = gpd.read_file(NE + "ne_10m_admin_0_countries_lakes.geojson")
adm1 = dis = None


def country(iso):
    g = adm0[adm0["ADM0_A3"] == iso].geometry.values
    if not len(g): g = adm0[adm0["ISO_A3"] == iso].geometry.values
    if not len(g): raise SystemExit(f"no Natural Earth country {iso}")
    return unary_union(g)


def geometry(pc):
    global adm1, dis
    if "admin0" in pc:
        isos = pc["admin0"] if isinstance(pc["admin0"], list) else [pc["admin0"]]
        return unary_union([country(i) for i in isos])
    if "admin1" in pc:
        if adm1 is None: adm1 = gpd.read_file(NE + "ne_10m_admin_1_states_provinces_lakes.geojson")
        sub = adm1[adm1["adm0_a3"] == pc["country"]]
        names = [n.lower() for n in pc["admin1"]]
        m = sub[sub["name"].fillna("").str.lower().isin(names) | sub["name_en"].fillna("").str.lower().isin(names)]
        found = set(m["name"].fillna("").str.lower()) | set(m["name_en"].fillna("").str.lower())
        miss = [n for n in names if n not in found]
        if miss: raise SystemExit(f"{pc['key']}: no Natural Earth province {', '.join(miss)} in {pc['country']}")
        return unary_union(m.geometry.values)
    if dis is None: dis = gpd.read_file(NE + "ne_10m_admin_0_disputed_areas.geojson")
    m = dis[dis.apply(lambda r: any(isinstance(v, str) and pc["disputed"].lower() in v.lower() for v in r.values), axis=1)]
    if not len(m): raise SystemExit(f"{pc['key']}: no Natural Earth disputed area matching {pc['disputed']!r}")
    return unary_union(m.geometry.values)


# ---------------------------------------------------------------- pieces in base pixels
FRAME = box(0, 0, W, H)
G = {}
for pc in P["pieces"]:
    g = to_px(geometry(pc)).buffer(0)
    if g.area <= 0: raise SystemExit(f"{pc['key']}: empty shape")
    parts, far = [], 0
    for q in polys(g):                                   # parts far away (overseas) are left out; a part cut by the bbox is an error
        iq = q.intersection(FRAME)
        if iq.is_empty or iq.area < 1e-6: far += 1; continue
        cut = 1 - iq.area / q.area
        if cut > 0.02: raise SystemExit(f"{pc['key']}: part of the shape is cut by the bbox ({cut:.0%} outside) - enlarge the bbox")
        parts += polys(iq)
    if not parts: raise SystemExit(f"{pc['key']}: the shape lies outside the bbox")
    if far: print(f"{pc['key']}: {far} part(s) outside the bbox left out", flush=True)
    g = unary_union(parts).simplify(0.35, preserve_topology=True).buffer(0)
    ps = polys(g)
    big = max(p.area for p in ps)
    keep = [orient(p, 1.0) for p in ps if p.area >= max(12.0, 0.002 * big)]
    G[pc["key"]] = MultiPolygon(keep) if len(keep) > 1 else keep[0]
    print(f"{pc['key']}: {len(keep)} part(s) (of {len(ps)}), {G[pc['key']].area:.0f} px2", flush=True)

import mapbox_earcut as earcut
arrays, info = {}, []
# outline of all pieces together (slivers between neighbours closed): shared borders stop short of it
OUTER = unary_union([x.buffer(0.6) for x in G.values()]).buffer(-0.6).boundary if len(G) > 1 else None
for pc in P["pieces"]:
    k = pc["key"]; g = G[k]
    others = unary_union([G[o] for o in G if o != k]) if len(G) > 1 else None
    V, T, RL, RT = [], [], [], []
    nv = 0
    for p in polys(g):
        rings = [np.asarray(p.exterior.coords, np.float64)[:-1]] + [np.asarray(h.coords, np.float64)[:-1] for h in p.interiors]
        rings = [r for r in rings if len(r) >= 3]
        v = np.concatenate(rings)
        idx = np.asarray(earcut.triangulate_float64(v, np.cumsum([len(r) for r in rings]).astype(np.uint32)), np.int64).reshape(-1, 3)
        V.append(v); T.append(idx + nv); nv += len(v)
        RL += [len(r) for r in rings]; RT += [1] + [0] * (len(rings) - 1)
    V = np.concatenate(V).astype(np.float32); T = np.concatenate(T).astype(np.int32)
    # distance field around the piece
    minx, miny, maxx, maxy = g.bounds
    m = max(0.15 * max(maxx - minx, maxy - miny), 0.012 * W, 6.0)
    bx0, by0 = minx - m, miny - m
    bw, bh = maxx - minx + 2 * m, maxy - miny + 2 * m
    r = min(3.0, 1024.0 / max(bw, bh))
    wr, hr = int(math.ceil(bw * r)), int(math.ceil(bh * r))
    mk = Image.new("L", (wr, hr), 0); d = ImageDraw.Draw(mk)
    tr = lambda cs: [((x - bx0) * r, (y - by0) * r) for x, y in cs]
    for p in polys(g):
        d.polygon(tr(p.exterior.coords), fill=255)
        for h in p.interiors: d.polygon(tr(h.coords), fill=0)
    M = np.asarray(mk) > 127
    inside = ndimage.distance_transform_edt(M) / r
    outside = ndimage.distance_transform_edt(~M) / r
    shared = g.boundary.intersection(others.buffer(0.8)).difference(OUTER.buffer(1.2)) if others is not None else None
    sl = [l for l in lines(shared) if l.length > 1.0]
    if sl:
        lm = Image.new("L", (wr, hr), 0); dl = ImageDraw.Draw(lm)
        for l in sl: dl.line(tr(l.coords), fill=255, width=1)
        inner = ndimage.distance_transform_edt(~(np.asarray(lm) > 127)) / r
    else:
        inner = np.full(M.shape, 1000.0)
    sdf = np.clip(np.round(np.stack([inside, inner, outside], -1) * 64), 0, 65535).astype(np.uint16)
    big = max(polys(g), key=lambda p: p.area)
    lab = polylabel(big, tolerance=1.0)
    arrays.update({f"{k}_v": V, f"{k}_t": T, f"{k}_rl": np.asarray(RL, np.int32), f"{k}_rt": np.asarray(RT, np.int8), f"{k}_sdf": sdf})
    info.append({"key": k, "bounds": [round(minx, 2), round(miny, 2), round(maxx, 2), round(maxy, 2)], "area": round(g.area, 1),
                 "verts": int(len(V)), "tris": int(len(T)), "label": [round(lab.x, 2), round(lab.y, 2)],
                 "sdf": [round(bx0, 3), round(by0, 3), r, wr, hr], "shared_px": round(sum(l.length for l in sl), 1)})
    print(f"{k}: {len(V)} verts, {len(T)} triangles, distance field {wr}x{hr} (x{r:.2f}), shared border {info[-1]['shared_px']:.0f} px", flush=True)
np.savez_compressed(f"{OUT}/pieces.npz", **arrays)
ub = unary_union(list(G.values())).bounds

# ---------------------------------------------------------------- flags
H_UA = {"User-Agent": "videomaps-workshop/1.2 (map history films)"}


def flag(spec, name):
    meta = {}
    if spec.get("commons"):
        t = spec["commons"] if spec["commons"].startswith("File:") else "File:" + spec["commons"]
        q = fetch("https://commons.wikimedia.org/w/api.php", params={"action": "query", "titles": t, "prop": "imageinfo",
                  "iiprop": "url|size|extmetadata", "iiurlwidth": 2048, "format": "json", "redirects": 1}, headers=H_UA).json()
        pg = next(iter(q["query"]["pages"].values()))
        if "imageinfo" not in pg: raise SystemExit(f"Commons has no file {t}")
        ii = pg["imageinfo"][0]; em = ii.get("extmetadata", {})
        lic = em.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"public domain|^pd|cc0|cc by(-sa)? ", lic.lower() + " "): raise SystemExit(f"licence not allowed for {t}: {lic}")
        art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
        url = ii.get("thumburl") or ii["url"]
        pd = "public domain" in lic.lower() or lic.lower().startswith("pd") or "cc0" in lic.lower()
        meta = {"what": pg["title"][5:].rsplit(".", 1)[0], "license": "Public domain" if pd else lic, "author": "" if pd else art,
                "page": ii.get("descriptionurl", "")}
    else:
        url = spec["url"]
    im = Image.open(io.BytesIO(fetch(url, headers=H_UA).content)).convert("RGB")
    if im.width < 1600: im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(f"{OUT}/flags/{name}.png")
    a = np.asarray(im, np.float32) / 255
    meta.update({"file": f"flags/{name}.png", "aspect": round(im.width / im.height, 5),
                 "luma": round(float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean()), 4)})
    print("flag", name, im.size, meta.get("license", "url"), flush=True)
    return meta


for pc, inf in zip(P["pieces"], info): inf["flag"] = flag(pc["flag"], pc["key"])
union = None
if P.get("union"):
    union = {"bounds": [round(v, 2) for v in ub], "flag": flag(P["union"]["flag"], "_union")}

# ---------------------------------------------------------------- base map
kind = P.get("base", "satellite")
if kind == "satellite":
    base = s2_mosaic(Z, x0, y0, W, H)
else:
    clip = box(LON0 - 1, LAT0 - 1, LON1 + 1, LAT1 + 1)
    land = unary_union([g for g in adm0.geometry.values if g is not None and g.intersects(clip)]).intersection(clip)
    im = Image.new("RGB", (W, H), (9, 15, 25)); d = ImageDraw.Draw(im)
    for p in polys(to_px(land)):
        d.polygon([tuple(c) for c in np.asarray(p.exterior.coords)], fill=(29, 34, 42))
        for h in p.interiors: d.polygon([tuple(c) for c in np.asarray(h.coords)], fill=(9, 15, 25))
    base = np.asarray(im).copy()
bb = P.get("base_borders", True)
blines = []
if bb:
    clip = box(LON0 - 0.5, LAT0 - 0.5, LON1 + 0.5, LAT1 + 0.5)
    if bb is True:
        bl = gpd.read_file(NE + "ne_10m_admin_0_boundary_lines_land.geojson")
        keep = bl["FEATURECLA"].fillna("").str.startswith("International") if "FEATURECLA" in bl else bl["featurecla"].fillna("").str.startswith("International")
        blines = [to_px(g.intersection(clip)) for g in bl[keep].geometry.values if g is not None and g.intersects(clip)]
    else:
        groups = [unary_union([country(i) for i in (x if isinstance(x, list) else [x])]) for x in bb]
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i], groups[j]
                if a.buffer(0.02).intersects(b): blines.append(to_px(a.boundary.intersection(b.buffer(0.01)).intersection(clip)))
    lw = max(1.5, W / 2400.0)
    lm = Image.new("L", (W, H), 0); d = ImageDraw.Draw(lm)
    nl = 0
    for g in blines:
        for l in lines(g):
            if l.length < 2: continue
            d.line([tuple(c) for c in np.asarray(l.coords)], fill=255, width=max(1, int(round(lw)))); nl += 1
    a = np.asarray(lm.filter(ImageFilter.GaussianBlur(0.6)), np.float32)[..., None] / 255
    col, op = (np.array([255, 255, 255], np.float32), 0.42) if kind == "satellite" else (np.array([92, 104, 120], np.float32), 0.85)
    base = (base.astype(np.float32) * (1 - op * a) + col * op * a).clip(0, 255).astype(np.uint8)
    print(f"base borders: {nl} lines, {lw:.1f} px", flush=True)
Image.fromarray(base).save(f"{OUT}/base.jpg", quality=92)
del base

credits = []
if kind == "satellite":
    credits.append("Sentinel-2 cloudless 2016 by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2016), CC BY 4.0")
for name, fm in [(i["key"], i["flag"]) for i in info] + ([("union", union["flag"])] if union else []):
    if fm.get("what"):
        credits.append(f"{fm['what']}: {fm['license']}" + (f", {fm['author']}" if fm.get("author") else "") + " (Wikimedia Commons)")
meta = {"zoom": Z, "N": N, "x0": x0, "y0": y0, "w": W, "h": H, "lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1,
        "base": kind, "pieces": info, "union": union, "credits": sorted(set(credits), key=credits.index)}
json.dump(meta, open(f"{OUT}/meta.json", "w"), indent=1)
print("pieces", [i["key"] for i in info], "union", bool(union), flush=True)
