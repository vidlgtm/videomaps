"""Data for the photoreal Caucasus fly-over (v2).
height: AWS Terrain Tiles z11 (~55 m), colour: NASA Blue Marble NG July (500 m), borders/places: Natural Earth 10m.
out/cauc2: height_mesh.npy (float32 m), height_full.png (16-bit), color.png, meta.json, borders.json"""
import io, json, math, os, zipfile, time
import concurrent.futures as cf
import numpy as np, requests, shapefile
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
OUT = "out/cauc2"; os.makedirs(OUT, exist_ok=True); os.makedirs("cache", exist_ok=True)
LON0, LON1, LAT0, LAT1, Z = 43.6, 48.3, 41.35, 44.55, 11
UA = {"User-Agent": "videomaps-ci/2.0"}


def get(url, tries=6):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=120, headers=UA)
            if r.status_code == 404: return None
            r.raise_for_status(); return r.content
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 + 3 * i)


N = 256 * 2 ** Z
mx = lambda lon: (lon + 180) / 360 * N
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
x0, x1, y0, y1 = mx(LON0), mx(LON1), my(LAT1), my(LAT0)
tx0, tx1, ty0, ty1 = int(x0 // 256), int(x1 // 256), int(y0 // 256), int(y1 // 256)
mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.float32)


def fetch(t):
    tx, ty = t
    c = get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png")
    a = np.asarray(Image.open(io.BytesIO(c)).convert("RGB")).astype(np.float32)
    mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


with cf.ThreadPoolExecutor(32) as ex:
    list(ex.map(fetch, [(a, b) for a in range(tx0, tx1 + 1) for b in range(ty0, ty1 + 1)]))
ox, oy = tx0 * 256, ty0 * 256
hm = mos[int(y0 - oy):int(y1 - oy), int(x0 - ox):int(x1 - ox)]
hm = ndimage.median_filter(hm, 3)                       # remove single-pixel spikes
H, W = hm.shape
print("height grid", hm.shape, hm.min(), hm.max())
mpp = 40075016.686 * math.cos(math.radians((LAT0 + LAT1) / 2)) / N   # metres per mercator px at mid latitude
# 16-bit full-res height for bump/displacement detail
Image.fromarray(np.clip((hm + 200) / 6000 * 65535, 0, 65535).astype(np.uint16)).save(f"{OUT}/height_full.png")
# mesh grid (~2600 px on the long side)
f = 2600 / max(H, W)
hmm = ndimage.zoom(hm, f, order=1)
np.save(f"{OUT}/height_mesh.npy", hmm.astype(np.float32))

# colour: Blue Marble C1 (0..90E, 90..0N, 240 px/deg) sampled on the mercator grid, 2x the mesh resolution
p = "cache/bm_c1.jpg"
if not os.path.exists(p):
    open(p, "wb").write(get("https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x21600x21600.C1.jpg"))
C1 = Image.open(p)
r0, r1, c0, c1 = int((90 - LAT1 - 0.2) * 240), int((90 - LAT0 + 0.2) * 240), int((LON0 - 0.2) * 240), int((LON1 + 0.2) * 240)
bm = np.asarray(C1.crop((c0, r0, c1, r1)).convert("RGB")).astype(np.float32)
CW_, CH_ = 4096, int(4096 * H / W)
cx = np.linspace(x0, x1, CW_); cy = np.linspace(y0, y1, CH_)
lon = cx / N * 360 - 180
lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * cy / N))))
LON, LAT = np.meshgrid(lon, lat)
col = LON * 240 - c0 - 0.5
row = (90 - LAT) * 240 - r0 - 0.5
img = np.stack([ndimage.map_coordinates(bm[..., k], [row, col], order=3, mode="nearest") for k in range(3)], -1)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(f"{OUT}/color.png")


# borders + places
def ne(name, cat):
    z = zipfile.ZipFile(io.BytesIO(get(f"https://naciscdn.org/naturalearth/10m/{cat}/{name}.zip")))
    s = [n for n in z.namelist() if n.endswith(".shp")][0][:-4]
    return shapefile.Reader(shp=io.BytesIO(z.read(s + ".shp")), shx=io.BytesIO(z.read(s + ".shx")), dbf=io.BytesIO(z.read(s + ".dbf")), encoding="utf-8")


def parts(shape):
    pts, pp = shape.points, list(shape.parts) + [len(shape.points)]
    return [pts[a:b] for a, b in zip(pp[:-1], pp[1:])]


inb = lambda q: LON0 - 0.3 <= q[0] <= LON1 + 0.3 and LAT0 - 0.3 <= q[1] <= LAT1 + 0.3
a1 = ne("ne_10m_admin_1_states_provinces", "cultural")
che = []
for s, r in zip(a1.shapes(), a1.records()):
    if r.as_dict().get("iso_3166_2") == "RU-CE":
        che = [[list(map(float, q)) for q in pr] for pr in parts(s)]
bl = ne("ne_10m_admin_0_boundary_lines_land", "cultural")
intl = []
for s in bl.shapes():
    for pr in parts(s):
        seg = []
        for q in pr:
            if inb(q): seg.append([float(q[0]), float(q[1])])
            else:
                if len(seg) > 1: intl.append(seg)
                seg = []
        if len(seg) > 1: intl.append(seg)
json.dump({"chechnya": che, "intl": intl}, open(f"{OUT}/borders.json", "w"))
places = {"CHECHNYA": (45.75, 43.25), "DAGESTAN": (46.95, 42.75), "GEORGIA": (44.95, 41.95), "INGUSHETIA": (44.95, 43.12),
          "GROZNY": (45.694, 43.318), "MAKHACHKALA": (47.502, 42.983), "CASPIAN SEA": (47.95, 43.6), "MT KAZBEK": (44.518, 42.697)}
json.dump({"lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "zoom": Z, "W": W, "H": H, "mesh_shape": list(hmm.shape),
           "mpp": mpp, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "places": places, "chechnya_parts": len(che), "intl_lines": len(intl)},
          open(f"{OUT}/meta.json", "w"), indent=1)
print("prep ok; chechnya parts", len(che), "intl lines", len(intl))
