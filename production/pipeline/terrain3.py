"""v3 deep-zoom terrain: UHD tiles (8 px per canvas px = 146 m/px) for every close-up camera view.
colour : the v2 palette (NASA Blue Marble, low-passed) -> seamless with basemap_v2 and the HD tiles
detail : Sentinel-2 cloudless 2016 by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2016, CC BY 4.0),
         used as *luminance* detail only (ratio to its own low-pass), so the film keeps one consistent colour world
relief : AWS terrarium DEM z10 -> the same multi-directional hillshade/style() as v2
outputs: out/terrain3/uhd/u_<cx>_<cy>.jpg (2048 px = 256 canvas px), uhd/index.json, uhd_sheet.jpg (QA contact sheet)"""
import os, io, json, math, time
import concurrent.futures as cf
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
src_txt = open(f"{HERE}/terrain2.py").read()
exec(compile(src_txt.split("# ======================= 1) world basemap")[0], "terrain2_head", "exec"))  # helpers only

OUT3 = "out/terrain3"; os.makedirs(f"{OUT3}/uhd", exist_ok=True); os.makedirs("cache/tiles", exist_ok=True)
K3, T3 = 8, 256                      # px per canvas px, tile size in canvas px
KM = RES / 1000.0
# close-up views of the film (lon, lat, view width km, tilt) - every key with w <= 1100 km in script.ts / v2.ts
VIEWS = [(45.7, 43.3, 520, 36), (34.3, 45.4, 620, 36), (45.3, 43.0, 900, 34), (25.0, 55.2, 900, 34),
         (25.0, 57.0, 1050, 32), (44.6, 42.0, 1050, 34), (45.6, 43.6, 1150, 36), (44.9, 41.4, 1250, 32),
         (47.0, 39.8, 900, 30)]   # last: Nagorno-Karabakh close-up (v3)
tiles = set()
for lon, lat, w, tilt in VIEWS:
    cx, cy = fwd(lon, lat); wc = w / KM
    x0, x1 = cx - 0.62 * wc, cx + 0.62 * wc
    y0, y1 = cy - (0.62 + tilt / 60) * wc, cy + 0.42 * wc
    for i in range(int(x0 // T3), int(x1 // T3) + 1):
        for j in range(int(y0 // T3), int(y1 // T3) + 1):
            tiles.add((i * T3, j * T3))
tiles = sorted(tiles)
if os.environ.get("UHD_TILES"):            # v5: explicit list from the screen-coverage audit (tools/uhd_need.ts)
    tiles = sorted(tuple(t) for t in json.loads(os.environ["UHD_TILES"]))
print(f"UHD tiles: {len(tiles)}", flush=True)


def cached(url, path):
    if os.path.exists(path):
        return open(path, "rb").read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return get(url, path)


class Mosaic:
    """web-mercator tile mosaic (S2 RGB jpg or terrarium DEM png) over the lon/lat samples given"""
    def __init__(self, kind, z, lon, lat):
        self.kind, self.z = kind, z
        mx, my = merc(lon, lat, z)
        tx, ty = np.floor(mx / 256).astype(int), np.floor(my / 256).astype(int)
        self.tx0, self.ty0 = int(tx.min()) - 1, int(ty.min()) - 1
        tx1, ty1 = int(tx.max()) + 1, int(ty.max()) + 1
        nb = 3 if kind == "s2" else 1
        self.a = np.zeros(((ty1 - self.ty0 + 1) * 256, (tx1 - self.tx0 + 1) * 256, nb), np.uint8 if kind == "s2" else np.float32)
        todo = [(a, b) for a in range(self.tx0, tx1 + 1) for b in range(self.ty0, ty1 + 1)]

        def fetch(t):
            a, b = t
            if kind == "s2":
                c = cached(f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{b}/{a}.jpg", f"cache/tiles/s2/{z}/{a}_{b}.jpg")
            else:
                c = cached(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{a}/{b}.png", f"cache/tiles/dem/{z}/{a}_{b}.png")
            if c is None: return 0
            v = np.asarray(Image.open(io.BytesIO(c)).convert("RGB"))
            blk = v if kind == "s2" else (v[..., 0:1].astype(np.float32) * 256 + v[..., 1:2] + v[..., 2:3] / 256 - 32768)
            self.a[(b - self.ty0) * 256:(b - self.ty0 + 1) * 256, (a - self.tx0) * 256:(a - self.tx0 + 1) * 256] = blk
            return 1
        with cf.ThreadPoolExecutor(10) as ex:
            got = sum(ex.map(fetch, todo))
        print(f"  {kind} z{z}: {got}/{len(todo)} tiles", flush=True)

    def sample(self, lon, lat, order=1):
        mx, my = merc(lon, lat, self.z)
        rr, cc = my - self.ty0 * 256 - 0.5, mx - self.tx0 * 256 - 0.5
        return np.stack([ndimage.map_coordinates(self.a[..., c], [rr, cc], order=order, mode="nearest").astype(np.float32)
                         for c in range(self.a.shape[2])], -1)


# ---------- colour source (Blue Marble C1, 240 px/deg) ----------
bm_c1 = "cache/bm_c1.jpg"
if not os.path.exists(bm_c1):
    get("https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x21600x21600.C1.jpg", bm_c1)


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


# Blue Marble crop over all UHD tiles, decoded once (children share it copy-on-write)
_ex = np.array([inv(np.array([tx + u for u in (0, T3 / 2, T3)] * 3, float), np.array([ty + v for v in (0, 0, 0, T3 / 2, T3 / 2, T3 / 2, T3, T3, T3)], float))
                for tx, ty in tiles])  # (n, 2, 9)
LO0, LO1 = float(_ex[:, 0].min()) - 1.5, float(_ex[:, 0].max()) + 1.5
LA0, LA1 = float(_ex[:, 1].min()) - 1.5, float(_ex[:, 1].max()) + 1.5
_C1 = Image.open(bm_c1)
_r0, _r1, _c0, _c1 = int((90 - LA1) * 240), int((90 - LA0) * 240) + 1, int(LO0 * 240), int(LO1 * 240) + 1
_im = np.asarray(_C1.crop((_c0, _r0, _c1, _r1)).convert("RGB")); del _C1
BM = [np.ascontiguousarray(_im[..., c]) for c in range(3)]; del _im
BM_GEO = (_c0 / 240, 90 - _r0 / 240, 240)
print(f"BM crop lon {LO0:.1f}..{LO1:.1f} lat {LA0:.1f}..{LA1:.1f}: {BM[0].shape}", flush=True)


def do_tile(t):
    """one UHD tile with tile-local DEM / S2 / land mask / water distance (windows wide enough to be seamless)"""
    tx, ty = t
    t1 = time.time()
    gx, gy = np.meshgrid(np.arange(tx - 16, tx + T3 + 17, 4.0), np.arange(ty - 16, ty + T3 + 17, 4.0))
    glon, glat = inv(gx, gy)
    lo0, lo1, la0, la1 = glon.min() - 0.15, glon.max() + 0.15, glat.min() - 0.15, glat.max() + 0.15
    ppd = 900
    mask = land_mask(lo0, la1, ppd, int((lo1 - lo0) * ppd) + 1, int((la1 - la0) * ppd) + 1)
    MG = 320                                                     # water-distance window: tile +- 373 km
    wx_, wy_ = np.meshgrid(np.arange(tx - MG, tx + T3 + MG + 1, 16.0), np.arange(ty - MG, ty + T3 + MG + 1, 16.0))
    wlon, wlat = inv(wx_, wy_)
    blo0, blo1, bla0, bla1 = wlon.min() - 0.3, wlon.max() + 0.3, wlat.min() - 0.3, wlat.max() + 0.3
    mask2 = land_mask(blo0, bla1, 300, int((blo1 - blo0) * 300) + 1, int((bla1 - bla0) * 300) + 1)
    dist = canvas_dist(lambda lon, lat: eq_sample(mask2, blo0, bla1, 300, lon, lat, order=0), tx - MG, ty - MG, tx + T3 + MG, ty + T3 + MG, 2)
    dem = Mosaic("dem", 10, glon, glat)
    s2 = Mosaic("s2", 10, glon, glat)
    a = render_uhd(tx, ty, BM, BM_GEO, dem, s2, mask, (lo0, la1, ppd), dist, (tx - MG, ty - MG, 2), tx * 7 + ty)
    Image.fromarray(a).save(f"{OUT3}/uhd/u_{tx}_{ty}.jpg", quality=91)
    print(f"tile {tx},{ty} done {time.time() - t1:.0f}s", flush=True)
    return t


def render_uhd(tx, ty, bm, bm_geo, dem, s2, mask, mask_geo, dist, dist_geo, seed, margin=64):
    w = h = T3 * K3
    u = (np.arange(-margin, w + margin, dtype=np.float64) + 0.5) / K3 + tx
    v = (np.arange(-margin, h + margin, dtype=np.float64) + 0.5) / K3 + ty
    X, Y = np.meshgrid(u, v)
    lon, lat = inv(X, Y)
    lonw = (lon + 180) % 360 - 180
    px_m = RES / K3
    sig = 1500.0 / px_m                                           # detail band: everything finer than ~1.5 km
    rgb_bm = eq_sample(bm, *bm_geo, lonw, lat).astype(np.float32) / 255
    rgb_lp = np.stack([ndimage.gaussian_filter(rgb_bm[..., c], sig) for c in range(3)], -1)
    s2rgb = s2.sample(lonw, lat) / 255.0
    L = lum(s2rgb); Llp = ndimage.gaussian_filter(L, sig)
    ratio = np.clip((L + 0.02) / (Llp + 0.02), 0.5, 1.75) ** 0.85
    land = eq_sample(mask, *mask_geo, lonw, lat).astype(np.float32) / 255
    landE = np.clip(ndimage.gaussian_filter(ndimage.minimum_filter(land, size=int(900 / px_m) * 2 + 1), 2.0), 0, 1)
    rgb = np.clip(rgb_lp * (1 + (ratio[..., None] - 1) * landE[..., None]), 0, 1)
    d = dem.sample(lonw, lat)[..., 0]
    dx0, dy0, dk = dist_geo
    dd = ndimage.map_coordinates(dist, [(Y - dy0) * dk - 0.5, (X - dx0) * dk - 0.5], order=1, mode="nearest").astype(np.float32)
    casp = (lonw > 46.0) & (lonw < 55.6) & (lat > 36.4) & (lat < 47.6) & (land < 0.5)
    d[casp] = 0.0
    out = style(rgb, d, land, dd, px_m, 3.0, 20.0, np.random.default_rng(seed))
    return (out[margin:margin + h, margin:margin + w] * 255 + 0.5).astype(np.uint8)


# ---------- render all tiles ----------
t0 = time.time()
with cf.ProcessPoolExecutor(4) as ex:
    for n, _ in enumerate(ex.map(do_tile, tiles)):
        if n % 10 == 0: print(f"{n + 1}/{len(tiles)} tiles, {time.time() - t0:.0f}s", flush=True)
json.dump({"tile": T3, "k": K3, "tiles": [list(t) for t in tiles]}, open(f"{OUT3}/uhd/index.json", "w"))
print(f"UHD done {time.time() - t0:.0f}s", flush=True)

# ---------- QA contact sheet: every view centre, UHD crop at 1:1 ----------
th = []
for lon, lat, w, tilt in VIEWS:
    cx, cy = fwd(lon, lat)
    tx, ty = int(cx // T3) * T3, int(cy // T3) * T3
    p = f"{OUT3}/uhd/u_{tx}_{ty}.jpg"
    if os.path.exists(p):
        im = Image.open(p); im.thumbnail((640, 640)); th.append(im)
if th:
    sheet = Image.new("RGB", (640 * min(3, len(th)), 640 * math.ceil(len(th) / 3)), (20, 20, 20))
    for n, im in enumerate(th): sheet.paste(im, ((n % 3) * 640, (n // 3) * 640))
    sheet.save(f"{OUT3}/uhd_sheet.jpg", quality=88)
