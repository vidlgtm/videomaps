"""Workshop template 'fly' - region data on one web-mercator grid: terrain (AWS terrarium DEM) + colour (EOX Sentinel-2
cloudless 2016, CC BY 4.0) for the region, and a coarse ring of both around it out to the horizon (2 zoom levels lower).
Open sea is forced well below the water plane: the DEM has flat 0 m patches at sea that would otherwise sit exactly at
water level and show as pale slabs. Border lines (Natural Earth 10m) clipped to the region.
usage: python3 fly_prep.py <params.json> <out_dir>
params: bbox [lon0, lon1, lat0, lat1]; zoom; sea (m); borders.countries [ISO3...];
        highlight [{key, admin0 | admin1 + country | disputed}]"""
import json, math, os, io, sys, time, itertools
import concurrent.futures as cf
import numpy as np, requests
from PIL import Image
from scipy import ndimage

P = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1 = [float(v) for v in P["bbox"]]
Z = int(P.get("zoom") or max(6, min(12, math.floor(math.log2(9000 * 360 / (256 * (LON1 - LON0)))))))
SEA = float(P.get("sea", 0.0))
N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
W, H = int(round(x1 - x0)), int(round(y1 - y0))
Image.MAX_IMAGE_PIXELS = None
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "videomaps-workshop/1.1"
print("zoom", Z, "region", W, "x", H, flush=True)


def fetch(url):
    for i in range(7):
        try:
            r = SESSION.get(url, timeout=60); r.raise_for_status(); return r.content
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(url)


def mosaic(kind, z, px0, py0, w, h):
    """w x h pixels from (px0, py0) at zoom z: 'dem' -> float32 metres, 's2' -> uint8 RGB"""
    nt = 2 ** z
    tx0, ty0 = int(px0 // 256), int(py0 // 256)
    tx1, ty1 = int((px0 + w - 1e-6) // 256), int((py0 + h - 1e-6) // 256)
    arr = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256) + ((3,) if kind == "s2" else ()), np.uint8 if kind == "s2" else np.float32)

    def one(t):
        tx, ty = t
        if not (0 <= ty < nt): return
        txw = tx % nt
        if kind == "dem":
            a = np.asarray(Image.open(io.BytesIO(fetch(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{txw}/{ty}.png"))).convert("RGB")).astype(np.float32)
            v = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        else:
            v = np.asarray(Image.open(io.BytesIO(fetch(f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{ty}/{txw}.jpg"))).convert("RGB"))
        arr[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = v

    tiles = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    with cf.ThreadPoolExecutor(24) as ex:
        list(ex.map(one, tiles))
    r0, c0 = int(round(py0 - ty0 * 256)), int(round(px0 - tx0 * 256))
    print(f"  {kind} z{z}: {len(tiles)} tiles", flush=True)
    return arr[r0:r0 + h, c0:c0 + w]


def sea_fix(h, rgb, sea_level, border_seed=True):
    """open sea (low + water-coloured + connected to deep water or the edge) -> 400 m under the water plane;
    other ground at or below the water level -> 1 m above it (no surface exactly at water level)"""
    if rgb.shape[:2] != h.shape:
        rgb = np.asarray(Image.fromarray(rgb).resize((h.shape[1], h.shape[0]), Image.BILINEAR))
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    low = h <= sea_level + 0.5
    cand = low & (b >= r - 6) & (luma < 0.30)
    lab, n = ndimage.label(cand)
    seed = cand & (h < sea_level - 5)
    if border_seed:
        edge = np.zeros_like(cand); edge[0, :] = edge[-1, :] = True; edge[:, 0] = edge[:, -1] = True
        seed |= cand & edge
    keep = np.zeros(n + 1, bool); keep[np.unique(lab[seed])] = True; keep[0] = False
    sea = keep[lab]
    h = h.copy()
    h[sea] = sea_level - 400.0
    rest = low & ~sea
    h[rest] = np.maximum(h[rest], sea_level + 1.0)
    return h, float(sea.mean()), int(rest.sum())


# ---------------------------------------------------------------- region at full detail
hm = mosaic("dem", Z, x0, y0, W, H)
tex = mosaic("s2", Z + 1, 2 * x0, 2 * y0, 2 * W, 2 * H)
hm, sea_frac, lifted = sea_fix(hm, tex[::2, ::2], SEA)
hm = ndimage.gaussian_filter(hm, 1.0)
print(f"region: sea {sea_frac:.1%}, low ground lifted {lifted} px", flush=True)
ti = Image.fromarray(tex)
if ti.width > 16384: ti = ti.resize((16384, round(ti.height * 16384 / ti.width)), Image.LANCZOS)
ti.save(f"{OUT}/texture.jpg", quality=93)
print("texture", ti.size, flush=True)
del tex, ti

# ---------------------------------------------------------------- coarse ring out to the horizon
ZF = max(3, Z - 2); F = 2 ** (Z - ZF)
span = max(W, H); M = 2.5 * span
fx0, fx1 = x0 - M, x1 + M
fy0, fy1 = max(my(84.0), y0 - M), min(my(-84.0), y1 + M)
fw, fh = int(round((fx1 - fx0) / F)), int(round((fy1 - fy0) / F))
fx1, fy1 = fx0 + fw * F, fy0 + fh * F
hf = mosaic("dem", ZF, fx0 / F, fy0 / F, fw, fh)
tf = mosaic("s2", ZF, fx0 / F, fy0 / F, fw, fh)
hf, far_sea, _ = sea_fix(hf, tf, SEA)
hf = ndimage.gaussian_filter(hf, 0.7)
fi = Image.fromarray(tf)
if fi.width > 16384: fi = fi.resize((16384, round(fi.height * 16384 / fi.width)), Image.LANCZOS)
fi.save(f"{OUT}/far.jpg", quality=90)
print(f"ring: {fw} x {fh} px at z{ZF}, sea {far_sea:.1%}", flush=True)
del tf, fi

SCALE, OFFSET = 10.0, SEA - 500.0
enc = lambda a: np.clip(np.round((a - OFFSET) * SCALE), 0, 65535).astype(np.uint16)
np.savez_compressed(f"{OUT}/height.npz", main=enc(hm), far=enc(hf), scale=SCALE, offset=OFFSET)
mpp = 40075016.686 * math.cos(math.radians((LAT0 + LAT1) / 2)) / N
meta = {"u": 400.0, "lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "zoom": Z, "w": W, "h": H, "m_per_px": mpp,
        "sea": SEA, "hmin": float(hm.min()), "hmax": float(hm.max()), "sea_frac": sea_frac,
        "far": {"x0": fx0 - x0, "x1": fx1 - x0, "y0": fy0 - y0, "y1": fy1 - y0, "f": F, "zoom": ZF, "w": fw, "h": fh}}
g2px = lambda lon, lat: (mx(lon) - x0, my(lat) - y0)

# ---------------------------------------------------------------- lines: shared borders + highlighted outlines
lines = {}
countries = list(P.get("borders", {}).get("countries", []))
hl = P.get("highlight", [])
if countries or hl:
    import geopandas as gpd
    from shapely.geometry import box, LineString
    from shapely.ops import unary_union
    NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    bb = box(LON0, LAT0, LON1, LAT1)
    adm0 = gpd.read_file(NE + "ne_10m_admin_0_countries_lakes.geojson")
    A = {}
    for iso in set(countries + [h["admin0"] for h in hl if h.get("admin0")]):
        g = adm0[adm0["ADM0_A3"] == iso].geometry.values
        if len(g): A[iso] = unary_union(g)
        else: print("WARNING: no Natural Earth country", iso, flush=True)

    def to_list(g):
        out = []
        geoms = [g] if isinstance(g, LineString) else list(getattr(g, "geoms", []))
        for l in geoms:
            if isinstance(l, LineString) and l.length > 0.02:
                l = l.segmentize(0.01)
                out.append([list(g2px(x, y)) for x, y in l.coords])
            elif hasattr(l, "geoms"):
                out += to_list(l)
        return out

    lines["intl"] = []
    for a, b in itertools.combinations([c for c in countries if c in A], 2):
        if not A[a].buffer(0.02).intersects(A[b]): continue
        lines["intl"] += to_list(A[a].boundary.intersection(A[b].buffer(0.01)).intersection(bb))
    adm1 = dis = None
    for h in hl:
        key = h["key"]
        if h.get("admin0") and h["admin0"] in A:
            g = A[h["admin0"]]
        elif h.get("admin1"):
            if adm1 is None: adm1 = gpd.read_file(NE + "ne_10m_admin_1_states_provinces_lakes.geojson")
            m = adm1[(adm1["adm0_a3"] == h.get("country", "")) & adm1["name"].fillna("").str.contains("|".join(h["admin1"]))]
            g = unary_union(m.geometry.values) if len(m) else None
        elif h.get("disputed"):
            if dis is None: dis = gpd.read_file(NE + "ne_10m_admin_0_disputed_areas.geojson")
            m = dis[dis.apply(lambda r: any(isinstance(v, str) and h["disputed"].lower() in v.lower() for v in r.values), axis=1)]
            g = unary_union(m.geometry.values) if len(m) else None
        else:
            g = None
        lines[key] = to_list(g.boundary.intersection(bb)) if g is not None else []
        if not lines[key]: print("WARNING: highlight", key, "found nothing inside the region", flush=True)
meta["lines"] = lines
json.dump(meta, open(f"{OUT}/meta.json", "w"))
print({k: len(v) for k, v in lines.items()}, flush=True)
