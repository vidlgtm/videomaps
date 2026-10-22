"""v3 Caucasus fly-over data: terrarium DEM z10 (~115 m) + Sentinel-2 cloudless 2016 colour texture z11 (~57 m,
EOX, CC BY 4.0) on the exact same web-mercator grid, plus borders (Natural Earth) and places. U = 400 px/unit keeps the
v1 world scale (1 unit = 4 z8 px), so the camera path and label tracks keep their meaning."""
import json, math, os, io
import numpy as np, requests
from PIL import Image
import geopandas as gpd
from shapely.geometry import box, LineString, MultiLineString
from shapely.ops import unary_union

OUT = "out/cauc3"; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1, Z = 37.6, 50.2, 40.0, 45.4, 10
N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
tx0, tx1, ty0, ty1 = int(x0 // 256), int(x1 // 256), int(y0 // 256), int(y1 // 256)
mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.float32)
import concurrent.futures as cf, time


def fetch(url):
    for i in range(6):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "videomaps/3.0"}); r.raise_for_status(); return r.content
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(url)


def dem_tile(t):
    tx, ty = t
    a = np.asarray(Image.open(io.BytesIO(fetch(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"))).convert("RGB")).astype(np.float32)
    mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


with cf.ThreadPoolExecutor(24) as ex:
    list(ex.map(dem_tile, [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]))
print("DEM mosaic", mos.shape, flush=True)

# Sentinel-2 cloudless colour, z = Z + 1 on the same bounds
Z2 = Z + 1; S = 2
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
ox, oy = tx0 * 256, ty0 * 256
hm = mos[int(y0 - oy):int(y1 - oy), int(x0 - ox):int(x1 - ox)]
from scipy.ndimage import gaussian_filter
hm = gaussian_filter(hm, 1.0)          # remove single-pixel spikes
np.save(f"{OUT}/height.npy", hm.astype(np.float32))
H, W = hm.shape
# metres per mercator pixel at mid latitude -> for true horizontal scale
mpp = 40075016.686 * math.cos(math.radians((LAT0 + LAT1) / 2)) / N
meta = {"u": 400.0, "lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "zoom": Z, "w": W, "h": H, "m_per_px": mpp,
        "hmin": float(hm.min()), "hmax": float(hm.max())}
print(meta)


def g2px(lon, lat):  # -> grid pixel (col,row)
    return mx(lon) - x0, my(lat) - y0


lines = {}
adm0 = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries_lakes.geojson")
adm1 = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces_lakes.geojson")
dis = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_disputed_areas.geojson")
bb = box(LON0, LAT0, LON1, LAT1)
A = lambda iso: unary_union(adm0[adm0["ADM0_A3"] == iso].geometry.values)
countries = {k: A(k) for k in ["RUS", "GEO", "ARM", "AZE", "TUR", "IRN"]}


def shared(a, b):
    g = countries[a].boundary.intersection(countries[b].buffer(0.01)).intersection(bb)
    return g


def to_list(g):
    out = []
    geoms = [g] if isinstance(g, LineString) else list(getattr(g, "geoms", []))
    for l in geoms:
        if isinstance(l, LineString) and l.length > 0.02:
            l = l.segmentize(0.01)
            out.append([list(g2px(x, y)) for x, y in l.coords])
    return out


lines["intl"] = []
for a, b in [("RUS", "GEO"), ("RUS", "AZE"), ("GEO", "ARM"), ("GEO", "AZE"), ("ARM", "AZE"), ("GEO", "TUR"), ("ARM", "TUR"), ("ARM", "IRN"), ("AZE", "IRN"), ("AZE", "TUR")]:
    lines["intl"] += to_list(shared(a, b))
chech = adm1[(adm1["adm0_a3"] == "RUS") & adm1["name"].fillna("").str.contains("Chechn")]
lines["chechnya"] = to_list(unary_union(chech.geometry.values).boundary.intersection(bb)) if len(chech) else []
for nm in ["Abkhaz", "South Ossetia"]:
    m = dis[dis.apply(lambda r: any(isinstance(v, str) and nm.lower() in v.lower() for v in r.values), axis=1)]
    lines[nm.split()[0].lower()] = to_list(unary_union(m.geometry.values).boundary.intersection(bb)) if len(m) else []
PLACES = {"Mount Elbrus": (42.439, 43.352), "Kazbek": (44.518, 42.697), "Grozny": (45.69, 43.32), "Tbilisi": (44.79, 41.72),
          "Sukhumi": (41.02, 43.00), "Tskhinvali": (43.96, 42.23), "Makhachkala": (47.50, 42.98), "Vladikavkaz": (44.68, 43.02),
          "Sochi": (39.73, 43.60), "Baku": (49.87, 40.41), "Yerevan": (44.51, 40.18), "Nalchik": (43.61, 43.49),
          "BLACK SEA": (38.6, 42.6), "CASPIAN SEA": (49.6, 42.4)}
meta["places"] = {k: list(g2px(*v)) for k, v in PLACES.items()}
meta["lines"] = lines
json.dump(meta, open(f"{OUT}/meta.json", "w"))
Image.fromarray(np.clip((hm + 100) / 5800 * 255, 0, 255).astype(np.uint8)).resize((W // 4, H // 4)).save(f"{OUT}/height_preview.png")
print({k: len(v) for k, v in lines.items()})
