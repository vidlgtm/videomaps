"""Basemap v2 in the reference style, on the exact LCC canvas of geo.json.
colour  : NASA Blue Marble NG, July 2004 (public domain)
relief  : AWS Terrain Tiles / terrarium (open data)  -> multi-directional hillshade + local relief
coasts  : Natural Earth 10m land minus lakes (+ historic Aral Sea), crisp at every zoom
sea     : turquoise depth ramp from real bathymetry, coastal shallows, 'raised land' drop shadow
outputs : out/terrain/basemap_v2.jpg (8192x5996), basemap_v2_half.jpg,
          hd/t_<col>_<row>.jpg (2048 px = 512 canvas px, 4 px per canvas px) + hd/index.json,
          globe_night.jpg (NASA Black Marble 2016), terrain_sheet.jpg (QA)"""
import os, io, json, math, zipfile, time
import concurrent.futures as cf
import numpy as np, requests, shapefile
from PIL import Image, ImageDraw
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = json.load(open(f"{ROOT}/remotion/src/data/geo.json"))
OUT = "out/terrain"; os.makedirs(f"{OUT}/hd", exist_ok=True); os.makedirs("cache", exist_ok=True)
R, D = 6371000.0, math.pi / 180
NC, LON0, RES, MINX, MAXY, CW, CH = G["cone_n"], G["lon0"], G["res_m"], G["minx"], G["maxy"], G["width"], G["height"]
LAT1 = 45 * D
FF = math.cos(LAT1) * math.tan(math.pi / 4 + LAT1 / 2) ** NC / NC
RHO0 = R * FF / math.tan(math.pi / 4 + 55 * D / 2) ** NC
UA = {"User-Agent": "videomaps-ci/2.0"}


def get(url, path=None, tries=6):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=120, headers=UA)
            if r.status_code == 404: return None
            r.raise_for_status()
            if path: open(path, "wb").write(r.content)
            return r.content
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 + 3 * i)


def inv(X, Y):
    """canvas px -> lon (unwrapped), lat (deg)"""
    x = MINX + X * RES; dy = RHO0 - (MAXY - Y * RES)
    rho = np.sqrt(x * x + dy * dy); th = np.arctan2(x, dy)
    lon = LON0 + th / NC / D
    lat = (2 * np.arctan((R * FF / np.maximum(rho, 1.0)) ** (1 / NC)) - math.pi / 2) / D
    return lon, lat


def fwd(lon, lat):
    dl = (np.asarray(lon) - LON0 + 180) % 360 - 180
    th = NC * dl * D; rho = R * FF / np.tan(math.pi / 4 + np.asarray(lat) * D / 2) ** NC
    return (rho * np.sin(th) - MINX) / RES, (MAXY - (RHO0 - rho * np.cos(th))) / RES


# ---------------- Natural Earth ----------------
def ne(name, cat="physical"):
    p = f"cache/{name}.zip"
    if not os.path.exists(p): get(f"https://naciscdn.org/naturalearth/10m/{cat}/{name}.zip", p)
    z = zipfile.ZipFile(p)
    shp = [n for n in z.namelist() if n.endswith(".shp")][0][:-4]
    return shapefile.Reader(shp=io.BytesIO(z.read(shp + ".shp")), shx=io.BytesIO(z.read(shp + ".shx")),
                            dbf=io.BytesIO(z.read(shp + ".dbf")), encoding="latin1")


def rings(shape):
    pts, parts = shape.points, list(shape.parts) + [len(shape.points)]
    for a, b in zip(parts[:-1], parts[1:]):
        r = np.asarray(pts[a:b], np.float64)
        if len(r) >= 3: yield r


def signed_area(r):
    x, y = r[:, 0], r[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


LAND = ne("ne_10m_land"); LAKES = ne("ne_10m_lakes"); HIST = ne("ne_10m_lakes_historic")
LAKE_SHAPES = [s for s, rec in zip(LAKES.shapes(), LAKES.records()) if (rec.as_dict().get("scalerank", 9) or 9) <= 7]
ARAL = [s for s, rec in zip(HIST.shapes(), HIST.records()) if "aral" in str(rec.as_dict().get("name", "")).lower()]
print("lakes", len(LAKE_SHAPES), "historic aral parts", len(ARAL))


def land_mask(lon0, lat1, ppd, w, h):
    """equirectangular land mask (uint8 0/255): origin (lon0, lat1) top-left, ppd pixels per degree"""
    im = Image.new("L", (w, h), 0); dr = ImageDraw.Draw(im)
    tr = lambda r: [((p[0] - lon0) * ppd, (lat1 - p[1]) * ppd) for p in r]
    lon_hi, lat_lo = lon0 + w / ppd, lat1 - h / ppd

    def visible(r):
        return not (r[:, 0].max() < lon0 or r[:, 0].min() > lon_hi or r[:, 1].max() < lat_lo or r[:, 1].min() > lat1)
    holes = []
    for s in LAND.shapes():
        for r in rings(s):
            if not visible(r): continue
            (holes.append(r) if signed_area(r) > 0 else dr.polygon(tr(r), fill=255))  # shapefile: outer rings clockwise
    for r in holes: dr.polygon(tr(r), fill=0)
    for s in LAKE_SHAPES + ARAL:
        for r in rings(s):
            if visible(r) and signed_area(r) < 0: dr.polygon(tr(r), fill=0)
    return np.asarray(im)


# ---------------- terrarium DEM ----------------
def merc(lon, lat, z):
    n = 256 * 2 ** z
    la = np.clip(lat, -85.05, 85.05) * D
    return (lon + 180) / 360 * n, (1 - np.log(np.tan(la) + 1 / np.cos(la)) / math.pi) / 2 * n


class Dem:
    def __init__(self, z, lon, lat):
        """lon/lat: sample arrays covering the area that will be needed"""
        self.z = z
        mx, my = merc(lon, lat, z)
        tx, ty = np.floor(mx / 256).astype(int), np.floor(my / 256).astype(int)
        need = set(zip(tx.ravel().tolist(), ty.ravel().tolist()))
        need |= {(a + dx, b + dy) for a, b in list(need) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        self.tx0, self.ty0 = min(a for a, _ in need), max(0, min(b for _, b in need))
        tx1, ty1 = max(a for a, _ in need), min(2 ** z - 1, max(b for _, b in need))
        self.a = np.zeros(((ty1 - self.ty0 + 1) * 256, (tx1 - self.tx0 + 1) * 256), np.float32)
        todo = [(a, b) for a, b in need if self.ty0 <= b <= ty1]
        print(f"DEM z{z}: {len(todo)} tiles, mosaic {self.a.shape}", flush=True)

        def fetch(t):
            a, b = t
            c = get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{a % 2 ** z}/{b}.png")
            if c is None: return
            v = np.asarray(Image.open(io.BytesIO(c)).convert("RGB")).astype(np.float32)
            self.a[(b - self.ty0) * 256:(b - self.ty0 + 1) * 256, (a - self.tx0) * 256:(a - self.tx0 + 1) * 256] = \
                v[..., 0] * 256 + v[..., 1] + v[..., 2] / 256 - 32768
        with cf.ThreadPoolExecutor(32) as ex: list(ex.map(fetch, todo))

    def sample(self, lon, lat):
        mx, my = merc(lon, lat, self.z)
        return ndimage.map_coordinates(self.a, [my - self.ty0 * 256 - 0.5, mx - self.tx0 * 256 - 0.5], order=1, mode="nearest")


# ---------------- raster sampling helpers ----------------
def eq_sample(arr, lon0, lat1, ppd, lon, lat, wrap=False, order=1):
    col = (lon - lon0) * ppd - 0.5; row = (lat1 - lat) * ppd - 0.5
    if wrap: col = np.mod(col, arr.shape[1])
    if isinstance(arr, (list, tuple)):
        return np.stack([ndimage.map_coordinates(a, [row, col], order=order, mode="nearest") for a in arr], -1)
    return ndimage.map_coordinates(arr, [row, col], order=order, mode="nearest")


SEA_STOPS = np.array([[0.0, 0.66, 0.86, 0.87], [0.18, 0.55, 0.80, 0.83], [0.45, 0.39, 0.67, 0.75], [0.75, 0.27, 0.53, 0.65], [1.0, 0.21, 0.43, 0.56]])


def sea_ramp(t):
    out = np.zeros(t.shape + (3,), np.float32)
    for c in range(3): out[..., c] = np.interp(t, SEA_STOPS[:, 0], SEA_STOPS[:, c + 1])
    return out


def style(rgb, dem, land, dist_km, px_m, ve, shadow_px, rng):
    """rgb 0..1 (Blue Marble), dem m, land 0..1, dist_km (water distance to coast) -> styled rgb 0..1"""
    # ---- land: graded colour + relief
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    c = lum[..., None] + (rgb - lum[..., None]) * 0.86
    c = np.clip(c, 0, 1) ** 0.7 * np.array([1.05, 1.0, 0.9], np.float32)
    c = 0.05 + 0.95 * c
    z = np.where(land > 0.5, np.maximum(dem, -50), 0).astype(np.float32) * ve
    gy, gx = np.gradient(ndimage.gaussian_filter(z, 0.6), px_m)
    nz = 1 / np.sqrt(gx * gx + gy * gy + 1)
    shade = 0
    for az, alt, wgt in ((315, 38, 0.6), (270, 45, 0.2), (0, 45, 0.2)):   # azimuth clockwise from canvas-up
        a, b = az * D, alt * D
        lx, ly, lz = math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b)
        shade = shade + wgt * np.clip((-gx * lx - gy * ly + lz) * nz, 0, 1)
    flat = math.sin(40 * D)
    rel = np.tanh((z / ve - ndimage.gaussian_filter(z / ve, 10)) / 350)
    k = np.clip(0.92 + 0.95 * (shade - flat) + 0.10 * rel, 0.35, 1.4)
    cl = c * k[..., None]
    cl += (1 - np.clip(k, 0, 1))[..., None] * np.array([-0.015, 0.0, 0.035], np.float32)      # cool shadows
    cl += np.clip(k - 1, 0, 1)[..., None] * np.array([0.05, 0.04, 0.0], np.float32)          # warm light
    # ---- sea: depth ramp + shallows + texture
    depth = np.clip(-dem, 0, 4000)
    depth = np.maximum(depth, np.clip(dist_km, 0, 400) * 3.0)
    t = np.clip(np.log1p(depth / 15) / math.log1p(3000 / 15), 0, 1)
    cs = sea_ramp(t)
    cs += (np.exp(-np.clip(dist_km, 0, 50) / 2.5) * 0.06)[..., None]
    cs *= (1 + 0.018 * ndimage.gaussian_filter(rng.standard_normal(dem.shape).astype(np.float32), 1.2))[..., None]
    # raised land: drop shadow toward bottom-right + thin dark coastline on the water side
    sh = ndimage.gaussian_filter(ndimage.shift(land, (shadow_px, shadow_px), order=1, mode="nearest"), shadow_px * 0.9)
    edge = np.clip((ndimage.gaussian_filter(land, max(0.8, shadow_px / 8)) - land) * 2.2, 0, 1)
    cs *= (1 - 0.32 * sh - 0.30 * edge)[..., None]
    # land bevel: light rim on coasts facing the light
    bev = ndimage.gaussian_filter(land, max(1.0, shadow_px / 5))
    by, bx = np.gradient(bev)
    rim = np.clip(-(bx * -0.7 + by * -0.7) * 6, -0.25, 0.25)
    cl += (rim * land)[..., None] * 0.35
    out = cs * (1 - land[..., None]) + cl * land[..., None]
    return np.clip(out, 0, 1)


def render(origin, k, w, h, src, margin=48, seed=0):
    """render canvas region: origin canvas px (x0, y0), k px per canvas px, w x h output pixels"""
    x0, y0 = origin
    u = (np.arange(-margin, w + margin, dtype=np.float64) + 0.5) / k + x0
    v = (np.arange(-margin, h + margin, dtype=np.float64) + 0.5) / k + y0
    X, Y = np.meshgrid(u, v)
    lon, lat = inv(X, Y)
    lonw = (lon + 180) % 360 - 180
    rgb = eq_sample(src["bm"], *src["bm_geo"], lonw, lat).astype(np.float32) / 255
    dem = src["dem"].sample(lon, lat).astype(np.float32)
    land = eq_sample(src["mask"], *src["mask_geo"], lonw, lat).astype(np.float32) / 255
    dist = eq_sample(src["dist"], *src["dist_geo"], lonw, lat).astype(np.float32)
    polar = lat > 84.5
    land[polar] = 0; dem[polar] = -3000
    out = style(rgb, dem, land, dist, RES / k, src["ve"], src["shadow_px"], np.random.default_rng(seed))
    return (out[margin:margin + h, margin:margin + w] * 255 + 0.5).astype(np.uint8)


def water_dist(mask, km_per_px):
    return ndimage.distance_transform_edt(mask < 128).astype(np.float32) * km_per_px


# ======================= 1) world basemap (k = 1) =======================
t0 = time.time()
bm_world = "cache/bm_world.jpg"
if not os.path.exists(bm_world):
    get("https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x21600x10800.jpg", bm_world)
_im = np.asarray(Image.open(bm_world).convert("RGB"))
BMW = [np.ascontiguousarray(_im[..., c]) for c in range(3)]; del _im
print("blue marble world", BMW[0].shape, flush=True)
gx, gy = np.meshgrid(np.arange(0, CW + 1, 16.0), np.arange(0, CH + 1, 16.0))
glon, glat = inv(gx, gy)
dem_w = Dem(7, glon, glat)
MW = land_mask(-180, 90, 60, 21600, 10800)
MW_half = np.asarray(Image.fromarray(MW).resize((10800, 5400), Image.BILINEAR))
DW = water_dist(MW_half, 111.0 / 30 * 0.6)    # ~km (latitude-averaged)
src_w = dict(bm=BMW, bm_geo=(-180, 90, 60), dem=dem_w, mask=MW, mask_geo=(-180, 90, 60), dist=DW, dist_geo=(-180, 90, 30),
             ve=9.0, shadow_px=4.0)
rows = []
for y in range(0, CH, 1024):
    hh = min(1024, CH - y)
    rows.append(render((0, y), 1, CW, hh, src_w, margin=40, seed=y))
    print("world rows", y, flush=True)
world = np.concatenate(rows, 0)
Image.fromarray(world).save(f"{OUT}/basemap_v2.jpg", quality=92)
Image.fromarray(world).resize((CW // 2, CH // 2), Image.LANCZOS).save(f"{OUT}/basemap_v2_half.jpg", quality=90)
print(f"world done {time.time() - t0:.0f}s", flush=True)
del BMW, dem_w, MW, MW_half, DW, src_w, rows

# ======================= 2) HD tiles (k = 4) for the western USSR =======================
LO0, LO1, LA0, LA1 = 17.0, 63.0, 36.0, 67.0           # sample region (deg)
bm_c1 = "cache/bm_c1.jpg"
if not os.path.exists(bm_c1):
    get("https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x21600x21600.C1.jpg", bm_c1)
C1 = Image.open(bm_c1)  # 0..90E, 90N..0, 240 px/deg
r0, r1, c0_, c1_ = int((90 - LA1) * 240), int((90 - LA0) * 240), int(LO0 * 240), int(LO1 * 240)
_im = np.asarray(C1.crop((c0_, r0, c1_, r1)).convert("RGB")); del C1
BMC = [np.ascontiguousarray(_im[..., c]) for c in range(3)]; del _im
print("blue marble C1 crop", BMC[0].shape, flush=True)
PPD = 400
MH = land_mask(LO0, LA1, PPD, int((LO1 - LO0) * PPD), int((LA1 - LA0) * PPD))
DH = water_dist(MH, 111.0 / PPD * 0.66)
K, TILE = 4, 512
ex = np.array([fwd(lo, la) for lo in np.linspace(18, 62, 45) for la in (37.5, 66.0)] +
              [fwd(lo, la) for lo in (18, 62) for la in np.linspace(37.5, 66, 30)])
gx0 = int(math.floor(ex[:, 0].min() / TILE) * TILE); gy0 = int(math.floor(ex[:, 1].min() / TILE) * TILE)
gx1 = int(math.ceil(ex[:, 0].max() / TILE) * TILE); gy1 = int(math.ceil(ex[:, 1].max() / TILE) * TILE)
gx0, gy0 = max(gx0, 0), max(gy0, 0); gx1, gy1 = min(gx1, int(math.ceil(CW / TILE) * TILE)), min(gy1, int(math.ceil(CH / TILE) * TILE))
sx, sy = np.meshgrid(np.arange(gx0, gx1 + 1, 8.0), np.arange(gy0, gy1 + 1, 8.0))
slon, slat = inv(sx, sy)
inside = (slon > LO0 + 0.3) & (slon < LO1 - 0.3) & (slat > LA0 + 0.3) & (slat < LA1 - 0.3)
dem_h = Dem(9, slon[inside], slat[inside])
src_h = dict(bm=BMC, bm_geo=(LO0, LA1, 240), dem=dem_h, mask=MH, mask_geo=(LO0, LA1, PPD), dist=DH, dist_geo=(LO0, LA1, PPD),
             ve=3.4, shadow_px=11.0)
tiles = []
for j in range((gy1 - gy0) // TILE):
    for i in range((gx1 - gx0) // TILE):
        cx, cy = gx0 + i * TILE, gy0 + j * TILE
        bx, by = np.meshgrid(np.linspace(cx, cx + TILE, 9), np.linspace(cy, cy + TILE, 9))
        blon, blat = inv(bx, by)
        ok = (blon > LO0 + 0.5) & (blon < LO1 - 0.5) & (blat > LA0 + 0.5) & (blat < LA1 - 0.5)
        if ok.mean() > 0.999: tiles.append((i, j, cx, cy))      # tile fully inside the HD source region
print(f"HD grid x {gx0}-{gx1} y {gy0}-{gy1}: {len(tiles)} tiles", flush=True)


def do_tile(t):
    i, j, cx, cy = t
    a = render((cx, cy), K, TILE * K, TILE * K, src_h, margin=48, seed=i * 100 + j)
    Image.fromarray(a).save(f"{OUT}/hd/t_{i}_{j}.jpg", quality=90)
    return t


with cf.ProcessPoolExecutor(4) as ex_:
    for n_, t in enumerate(ex_.map(do_tile, tiles)):
        if n_ % 8 == 0: print("tile", n_, t, flush=True)
json.dump({"x0": gx0, "y0": gy0, "tile": TILE, "k": K, "tiles": [[i, j] for i, j, _, _ in tiles]}, open(f"{OUT}/hd/index.json", "w"))
print(f"HD done {time.time() - t0:.0f}s", flush=True)

# ======================= 3) QA sheet: views at film zooms =======================
views = [("CRIMEA", 34.3, 45.25, 3.6), ("CHECHNYA", 45.7, 43.2, 3.6), ("KARABAKH", 46.6, 40.0, 2.4),
         ("BALTIC", 24.3, 57.3, 1.8), ("MOSCOW", 37.6, 55.75, 3.0), ("TATARSTAN", 50.5, 55.4, 2.2)]
sheet = Image.new("RGB", (1920, 1440), (20, 20, 20))
for n_, (name, lo, la, zoom) in enumerate(views):
    cx, cy = fwd(lo, la)
    w_c, h_c = 1920 / zoom, 1080 / zoom
    a = render((cx - w_c / 2, cy - h_c / 2), zoom, 1920, 1080, src_h, margin=48, seed=n_)
    sheet.paste(Image.fromarray(a).resize((640, 360), Image.LANCZOS), ((n_ % 3) * 640, (n_ // 3) * 360))
    Image.fromarray(a).save(f"{OUT}/qa_{name.lower()}.jpg", quality=88)
wv = Image.open(f"{OUT}/basemap_v2.jpg"); wv.thumbnail((1920, 720))
sheet.paste(wv, ((1920 - wv.width) // 2, 720))
sheet.save(f"{OUT}/terrain_sheet.jpg", quality=86)

# ======================= 4) night globe texture =======================
bmk = "cache/blackmarble.jpg"
if not os.path.exists(bmk):
    get("https://eoimages.gsfc.nasa.gov/images/imagerecords/144000/144898/BlackMarble_2016_3km.jpg", bmk)
Image.open(bmk).convert("RGB").resize((8192, 4096), Image.LANCZOS).save(f"{OUT}/globe_night.jpg", quality=90)
print(f"all done {time.time() - t0:.0f}s")
