"""Real terrain for the Caucasus fly-over: AWS Terrain Tiles (terrarium, public) -> height grid,
plus borders (Natural Earth) and place points, all converted to the same local grid."""
import json, math, os, io
import numpy as np, requests
from PIL import Image
import geopandas as gpd
from shapely.geometry import box, LineString, MultiLineString
from shapely.ops import unary_union

OUT = "out/cauc"; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1, Z = 37.6, 50.2, 40.0, 45.4, 8
N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
tx0, tx1, ty0, ty1 = int(x0 // 256), int(x1 // 256), int(y0 // 256), int(y1 // 256)
mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.float32)
for ty in range(ty0, ty1 + 1):
    for tx in range(tx0, tx1 + 1):
        r = requests.get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png", timeout=60)
        a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB")).astype(np.float32)
        mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
ox, oy = tx0 * 256, ty0 * 256
hm = mos[int(y0 - oy):int(y1 - oy), int(x0 - ox):int(x1 - ox)]
np.save(f"{OUT}/height.npy", hm.astype(np.float32))
H, W = hm.shape
# metres per mercator pixel at mid latitude -> for true horizontal scale
mpp = 40075016.686 * math.cos(math.radians((LAT0 + LAT1) / 2)) / N
meta = {"lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "zoom": Z, "w": W, "h": H, "m_per_px": mpp,
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
Image.fromarray(np.clip((hm + 100) / 5800 * 255, 0, 255).astype(np.uint8)).save(f"{OUT}/height_preview.png")
print({k: len(v) for k, v in lines.items()})
