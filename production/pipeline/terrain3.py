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
        with cf.ThreadPoolExecutor(24) as ex:
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


def do_cluster(ctiles, seed0):
    """render all UHD tiles of one spatial cluster with cluster-local DEM / S2 / land mask / water distance"""
    cx0, cy0 = min(t[0] for t in ctiles) - 64, min(t[1] for t in ctiles) - 64
    cx1, cy1 = max(t[0] for t in ctiles) + T3 + 64, max(t[1] for t in ctiles) + T3 + 64
    gx, gy = np.meshgrid(np.arange(cx0, cx1 + 1, 4.0), np.arange(cy0, cy1 + 1, 4.0))
    glon, glat = inv(gx, gy)
    lo0, lo1, la0, la1 = glon.min() - 0.3, glon.max() + 0.3, glat.min() - 0.3, glat.max() + 0.3
    print(f"cluster {len(ctiles)} tiles  lon {lo0:.1f}..{lo1:.1f}  lat {la0:.1f}..{la1:.1f}", flush=True)
    C1 = Image.open(bm_c1)
    r0, r1, c0, c1 = int((90 - la1) * 240), int((90 - la0) * 240) + 1, int(lo0 * 240), int(lo1 * 240) + 1
    im = np.asarray(C1.crop((c0, r0, c1, r1)).convert("RGB")); del C1
    bm = [np.ascontiguousarray(im[..., c]) for c in range(3)]; bm_geo = (c0 / 240, 90 - r0 / 240, 240); del im
    ppd = 900
    mask = land_mask(lo0, la1, ppd, int((lo1 - lo0) * ppd), int((la1 - la0) * ppd))
    mask_fn = lambda lon, lat: eq_sample(mask, lo0, la1, ppd, lon, lat, order=0)
    MG = 200
    dist = canvas_dist(mask_fn, cx0 - MG, cy0 - MG, cx1 + MG, cy1 + MG, 2)
    dem = Mosaic("dem", 10, glon, glat)
    s2 = Mosaic("s2", 10, glon, glat)
    for n, (tx, ty) in enumerate(ctiles):
        t1 = time.time()
        a = render_uhd(tx, ty, bm, bm_geo, dem, s2, mask, (lo0, la1, ppd), dist, (cx0 - MG, cy0 - MG, 2), seed0 + n)
        Image.fromarray(a).save(f"{OUT3}/uhd/u_{tx}_{ty}.jpg", quality=91)
        print(f"  tile {tx},{ty}  {time.time() - t1:.0f}s", flush=True)


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


# ---------- clusters: connected groups of tiles ----------
left = set(tiles); clusters = []
while left:
    st = [left.pop()]; grp = []
    while st:
        t = st.pop(); grp.append(t)
        for dx in (-T3, 0, T3):
            for dy in (-T3, 0, T3):
                nb = (t[0] + dx, t[1] + dy)
                if nb in left: left.remove(nb); st.append(nb)
    clusters.append(sorted(grp))
print("clusters:", [len(c) for c in clusters], flush=True)
t0 = time.time()
with cf.ProcessPoolExecutor(min(3, len(clusters))) as ex:
    list(ex.map(do_cluster, clusters, [i * 1000 for i in range(len(clusters))]))
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
sheet = Image.new("RGB", (640 * min(3, len(th)), 640 * math.ceil(len(th) / 3)), (20, 20, 20))
for n, im in enumerate(th): sheet.paste(im, ((n % 3) * 640, (n // 3) * 640))
sheet.save(f"{OUT3}/uhd_sheet.jpg", quality=88)
