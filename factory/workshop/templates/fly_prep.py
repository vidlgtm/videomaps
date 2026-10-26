"""Workshop template 'fly' - region data: terrain (AWS terrarium DEM) + colour (EOX Sentinel-2 cloudless 2016,
CC BY 4.0) on the same web-mercator grid, border lines (Natural Earth 10m), places.
usage: python3 fly_prep.py <params.json> <out_dir>
params: bbox [lon0, lon1, lat0, lat1]; zoom (optional); borders.countries [ISO3...] (shared borders inside the bbox);
        highlight [{key, admin0 | admin1 + country | disputed}]; places {name: [lon, lat]}"""
import json, math, os, io, sys, time, itertools
import concurrent.futures as cf
import numpy as np, requests
from PIL import Image

P = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1 = [float(v) for v in P["bbox"]]
Z = int(P.get("zoom") or max(6, min(12, math.floor(math.log2(9000 * 360 / (256 * (LON1 - LON0)))))))
N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
tx0, tx1, ty0, ty1 = int(x0 // 256), int(x1 // 256), int(y0 // 256), int(y1 // 256)
print("zoom", Z, "grid", round(x1 - x0), "x", round(y1 - y0), flush=True)


def fetch(url):
    for i in range(7):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "videomaps-workshop/1.0"}); r.raise_for_status(); return r.content
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(url)


mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.float32)


def dem_tile(t):
    tx, ty = t
    a = np.asarray(Image.open(io.BytesIO(fetch(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"))).convert("RGB")).astype(np.float32)
    mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


with cf.ThreadPoolExecutor(24) as ex:
    list(ex.map(dem_tile, [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]))
print("DEM mosaic", mos.shape, flush=True)

Z2, S = Z + 1, 2
sx0, sx1, sy0, sy1 = x0 * S, x1 * S, y0 * S, y1 * S
stx0, stx1, sty0, sty1 = int(sx0 // 256), int(sx1 // 256), int(sy0 // 256), int(sy1 // 256)
smos = np.zeros(((sty1 - sty0 + 1) * 256, (stx1 - stx0 + 1) * 256, 3), np.uint8)


def s2_tile(t):
    tx, ty = t
    a = np.asarray(Image.open(io.BytesIO(fetch(f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{Z2}/{ty}/{tx}.jpg"))).convert("RGB"))
    smos[(ty - sty0) * 256:(ty - sty0 + 1) * 256, (tx - stx0) * 256:(tx - stx0 + 1) * 256] = a


with cf.ThreadPoolExecutor(24) as ex:
    list(ex.map(s2_tile, [(tx, ty) for ty in range(sty0, sty1 + 1) for tx in range(stx0, stx1 + 1)]))
tex = smos[int(sy0 - sty0 * 256):int(sy1 - sty0 * 256), int(sx0 - stx0 * 256):int(sx1 - stx0 * 256)]
Image.MAX_IMAGE_PIXELS = None
ti = Image.fromarray(tex)
if ti.width > 16384: ti = ti.resize((16384, round(ti.height * 16384 / ti.width)), Image.LANCZOS)
ti.save(f"{OUT}/texture.jpg", quality=93)
print("S2 texture", ti.size, flush=True)
del smos, tex

ox, oy = tx0 * 256, ty0 * 256
hm = mos[int(y0 - oy):int(y1 - oy), int(x0 - ox):int(x1 - ox)]
from scipy.ndimage import gaussian_filter
hm = gaussian_filter(hm, 1.0)
np.save(f"{OUT}/height.npy", hm.astype(np.float32))
H, W = hm.shape
mpp = 40075016.686 * math.cos(math.radians((LAT0 + LAT1) / 2)) / N
meta = {"u": 400.0, "lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "zoom": Z, "w": W, "h": H, "m_per_px": mpp,
        "hmin": float(hm.min()), "hmax": float(hm.max())}
g2px = lambda lon, lat: (mx(lon) - x0, my(lat) - y0)

# ---- lines: shared borders of the listed countries + highlighted outlines (all clipped to the bbox)
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
meta["places"] = {k: list(g2px(float(v[0]), float(v[1]))) for k, v in P.get("places", {}).items()}
meta["lines"] = lines
json.dump(meta, open(f"{OUT}/meta.json", "w"))
print({k: len(v) for k, v in lines.items()}, "places", len(meta["places"]), flush=True)
