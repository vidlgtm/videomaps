#!/usr/bin/env python3
"""TERRAIN of the map library - the house look of every map (the v5 film look, unchanged): NASA Blue Marble colour,
AWS terrarium relief (multi-directional hillshade + local relief), Natural Earth 10 m coasts and lakes, a turquoise sea
ramp from the real bathymetry and the 'raised land' drop shadow; close-up tiles add Sentinel-2 cloudless (EOX, 2016,
CC BY 4.0) as luminance detail only. Everything is rendered on the map's own canvas (mapdef.py), so it aligns with the
borders exactly.
usage:
  python factory/maps/terrain.py basemap <mapDir>                 basemap.jpg + basemap_half.jpg + globe_day_4k.jpg + globe_night_4k.jpg
  python factory/maps/terrain.py hd  <mapDir> '[[i, j], ...]'     hd/t_<i>_<j>.jpg  (4 px per canvas px, 512 canvas px cells from map.json hd_origin)
  python factory/maps/terrain.py uhd <mapDir> '[[x, y], ...]'     uhd/u_<x>_<y>.jpg (8 px per canvas px, 256 canvas px tiles at x, y)
  python factory/maps/terrain.py sheet <mapDir>                   sheet.jpg (whole basemap + borders check, for the record)
<mapDir>/map.json = the map definition. Source downloads are cached in ./cache (base-map sources only: rules/hermetic.py)."""
import concurrent.futures as cf, io, json, math, multiprocessing as mp, os, sys, time
import numpy as np
import requests
import shapefile
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapdef

Image.MAX_IMAGE_PIXELS = None
D = math.pi / 180
UA = {"User-Agent": "videomaps-terrain/1.0 (https://github.com/vidlgtm/videomaps)"}
BM = "https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/"
BM_WORLD = BM + "world.200407.3x21600x10800.jpg"                       # 60 px/deg
BM_TILE = BM + "world.200407.3x21600x21600.{}.jpg"                      # 240 px/deg, 90 x 90 deg
BM_TILES = {"A1": (-180, 90), "B1": (-90, 90), "C1": (0, 90), "D1": (90, 90),
            "A2": (-180, 0), "B2": (-90, 0), "C2": (0, 0), "D2": (90, 0)}  # name: (west lon, north lat)
BLACK_MARBLE = "https://eoimages.gsfc.nasa.gov/images/imagerecords/144000/144898/BlackMarble_2016_3km.jpg"
NE_PHYS = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_physical/{}.{}"
HD_K, HD_TILE = 4, 512
UHD_K, UHD_TILE = 8, 256
MD = None                     # the map (set in main before worker processes fork)
HD_X0, HD_Y0 = 0, 0           # HD grid origin in canvas px (map.json "hd_origin"; the v5 map: 0, 1024)
os.makedirs("cache", exist_ok=True)


def get(url, path=None, tries=6):
    if path and os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, "rb").read()
    for i in range(tries):
        try:
            r = requests.get(url, timeout=300, headers=UA)
            if r.status_code == 404: return None
            r.raise_for_status()
            if path:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                open(path + ".part", "wb").write(r.content); os.replace(path + ".part", path)
            return r.content
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 + 3 * i)


def inv(X, Y): return MD.inv(X, Y)
def fwd(lon, lat): return MD.fwd(lon, lat)
def wrap(lon): return (np.asarray(lon) + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------ Natural Earth land + lakes
def ne(name):
    f = {e: get(NE_PHYS.format(name, e), f"cache/ne/{name}.{e}") for e in ("shp", "shx", "dbf")}
    return shapefile.Reader(shp=io.BytesIO(f["shp"]), shx=io.BytesIO(f["shx"]), dbf=io.BytesIO(f["dbf"]), encoding="latin1")


def rings(shape):
    pts, parts = shape.points, list(shape.parts) + [len(shape.points)]
    for a, b in zip(parts[:-1], parts[1:]):
        r = np.asarray(pts[a:b], np.float64)
        if len(r) >= 3: yield r


def signed_area(r):
    x, y = r[:, 0], r[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


_NE = {}


def ne_shapes():
    if not _NE:
        land, lakes, hist = ne("ne_10m_land"), ne("ne_10m_lakes"), ne("ne_10m_lakes_historic")
        rank = lambda rec: 9 if rec.as_dict().get("scalerank") is None else rec.as_dict().get("scalerank")
        _NE["land"] = [list(rings(s)) for s in land.shapes()]
        _NE["lakes"] = [list(rings(s)) for s, rec in zip(lakes.shapes(), lakes.records()) if rank(rec) <= 7]
        _NE["aral"] = [list(rings(s)) for s, rec in zip(hist.shapes(), hist.records()) if "aral" in str(rec.as_dict().get("name", "")).lower()]
    return _NE


def land_mask(lon0, lat1, ppd, w, h):
    """equirectangular land mask (uint8 0/255): origin (lon0, lat1) top-left, ppd pixels per degree; lon0 may be
    outside -180..180 (rings are drawn with a +-360 shift where they fall in the window)"""
    S = ne_shapes()
    im = Image.new("L", (w, h), 0); dr = ImageDraw.Draw(im)
    lon_hi, lat_lo = lon0 + w / ppd, lat1 - h / ppd

    def draw(r, fill, hole_test):
        for sh in (-360.0, 0.0, 360.0):
            x0, x1 = r[:, 0].min() + sh, r[:, 0].max() + sh
            if x1 < lon0 or x0 > lon_hi or r[:, 1].max() < lat_lo or r[:, 1].min() > lat1: continue
            dr.polygon([((p[0] + sh - lon0) * ppd, (lat1 - p[1]) * ppd) for p in r], fill=fill)
    holes = []
    for parts in S["land"]:
        for r in parts:
            (holes.append(r) if signed_area(r) > 0 else draw(r, 255, None))      # shapefile: outer rings clockwise
    for r in holes: draw(r, 0, None)
    for parts in S["lakes"] + S["aral"]:
        for r in parts:
            if signed_area(r) < 0: draw(r, 0, None)
    return np.asarray(im)


# ------------------------------------------------------------------ web-mercator mosaics (terrarium DEM, Sentinel-2)
def merc(lon, lat, z):
    n = 256 * 2 ** z
    la = np.clip(lat, -85.05, 85.05) * D
    return (wrap(lon) + 180) / 360 * n, (1 - np.log(np.tan(la) + 1 / np.cos(la)) / math.pi) / 2 * n


class Mosaic:
    """web-mercator tile mosaic ("dem" terrarium png -> metres, "s2" EOX Sentinel-2 cloudless jpg) over the lon/lat samples"""
    def __init__(self, kind, z, lon, lat, threads=16):
        self.kind, self.z = kind, z
        mx, my = merc(lon, lat, z)
        tx, ty = np.floor(mx / 256).astype(int), np.floor(my / 256).astype(int)
        self.tx0, self.ty0 = int(tx.min()) - 1, max(0, int(ty.min()) - 1)
        tx1, ty1 = int(tx.max()) + 1, min(2 ** z - 1, int(ty.max()) + 1)
        nb = 3 if kind == "s2" else 1
        self.a = np.zeros(((ty1 - self.ty0 + 1) * 256, (tx1 - self.tx0 + 1) * 256, nb), np.uint8 if kind == "s2" else np.float32)
        todo = [(a, b) for a in range(self.tx0, tx1 + 1) for b in range(self.ty0, ty1 + 1)]

        def fetch(t):
            # a CDN can answer 200 with an error page: decode and validate every tile, never keep a bad body
            a, b = t
            aw = a % 2 ** z
            if kind == "s2":
                url, path = f"https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{b}/{aw}.jpg", f"cache/tiles/s2/{z}/{aw}_{b}.jpg"
            else:
                url, path = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{aw}/{b}.png", f"cache/tiles/dem/{z}/{aw}_{b}.png"
            last = None
            for attempt in range(5):
                try:
                    c = get(url, path)
                    if c is None: return 0
                    with Image.open(io.BytesIO(c)) as im:
                        im.load(); v = np.asarray(im.convert("RGB"))
                    if v.shape != (256, 256, 3): raise ValueError(f"unexpected decoded size {v.shape}")
                    blk = v if kind == "s2" else (v[..., 0:1].astype(np.float32) * 256 + v[..., 1:2] + v[..., 2:3] / 256 - 32768)
                    self.a[(b - self.ty0) * 256:(b - self.ty0 + 1) * 256, (a - self.tx0) * 256:(a - self.tx0 + 1) * 256] = blk
                    return 1
                except Exception as e:
                    last = e
                    try: os.unlink(path)
                    except FileNotFoundError: pass
                    time.sleep(1 + attempt * 2)
            raise RuntimeError(f"invalid {kind} source tile z{z}/{aw}/{b} after retries: {last}")
        with cf.ThreadPoolExecutor(threads) as ex:
            got = sum(ex.map(fetch, todo))
        self.got = got

    def sample(self, lon, lat, order=1):
        mx, my = merc(lon, lat, self.z)
        n = 256 * 2 ** self.z
        cc = mx - self.tx0 * 256 - 0.5
        cc = np.where(cc < -256, cc + n, cc)                       # tiles left of x = 0 were stored unwrapped
        rr = my - self.ty0 * 256 - 0.5
        out = np.stack([ndimage.map_coordinates(self.a[..., c], [rr, cc], order=order, mode="nearest").astype(np.float32)
                        for c in range(self.a.shape[2])], -1)
        return out


# ------------------------------------------------------------------ raster helpers + the house style (v5, unchanged)
def eq_sample(arr, lon0, lat1, ppd, lon, lat, order=1):
    """sample an equirectangular raster (origin lon0, lat1; ppd px/deg); lon is brought next to the raster first"""
    w = (arr[0] if isinstance(arr, (list, tuple)) else arr).shape[1] / ppd
    c = lon0 + w / 2                                                # centre meridian of the raster
    lon = (np.asarray(lon) - c + 180.0) % 360.0 - 180.0 + c
    col = (lon - lon0) * ppd - 0.5; row = (lat1 - lat) * ppd - 0.5
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
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    c = lum[..., None] + (rgb - lum[..., None]) * 0.86
    c = np.clip(c, 0, 1) ** 0.68 * np.array([1.08, 1.0, 0.86], np.float32)
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
    depth = np.clip(-ndimage.gaussian_filter(np.minimum(dem, 0), 3.0), 0, 4000)
    depth = np.maximum(depth, np.clip(dist_km, 0, 400) * 3.0)
    t = np.clip(np.log1p(depth / 15) / math.log1p(3000 / 15), 0, 1)
    cs = sea_ramp(t)
    cs += (np.exp(-np.clip(dist_km, 0, 50) / 2.5) * 0.06)[..., None]
    cs *= (1 + 0.018 * ndimage.gaussian_filter(rng.standard_normal(dem.shape).astype(np.float32), 1.2))[..., None]
    sh = ndimage.gaussian_filter(ndimage.shift(land, (shadow_px, shadow_px), order=1, mode="nearest"), shadow_px * 0.9)
    edge = np.clip((ndimage.gaussian_filter(land, max(0.8, shadow_px / 8)) - land) * 2.2, 0, 1)
    cs *= (1 - 0.32 * sh - 0.30 * edge)[..., None]
    bev = ndimage.gaussian_filter(land, max(1.0, shadow_px / 5))
    by, bx = np.gradient(bev)
    rim = np.clip(-(bx * -0.7 + by * -0.7) * 6, -0.25, 0.25)
    cl += (rim * land)[..., None] * 0.35
    out = cs * (1 - land[..., None]) + cl * land[..., None]
    return np.clip(out, 0, 1)


def caspian_flat(dem, lonw, lat, land):
    """terrain tiles mix a flat -28 m SRTM surface with ETOPO sea-bed cells on the Caspian -> blocky; use coast distance only"""
    casp = (lonw > 46.0) & (lonw < 55.6) & (lat > 36.4) & (lat < 47.6) & (land < 0.5)
    dem[casp] = 0.0


def canvas_dist(mask_fn, x0, y0, x1, y1, k):
    """distance (km) from every water sample to the nearest land on the conformal canvas grid (k samples per canvas px)"""
    u = (np.arange(int((x1 - x0) * k)) + 0.5) / k + x0
    out = []
    for r0 in range(0, int((y1 - y0) * k), 1024):
        v = (np.arange(r0, min(r0 + 1024, int((y1 - y0) * k))) + 0.5) / k + y0
        X, Y = np.meshgrid(u, v); lon, lat = inv(X, Y)
        m = mask_fn(lon, lat); m[np.abs(lat) > 84.5] = 0
        out.append(m)
    m = np.concatenate(out, 0)
    return ndimage.distance_transform_edt(m < 128).astype(np.float32) * (MD.res / k / 1000.0)


def render(origin, k, w, h, src, margin=48, seed=0):
    """render a canvas region: origin canvas px (x0, y0), k px per canvas px, w x h output pixels"""
    x0, y0 = origin
    u = (np.arange(-margin, w + margin, dtype=np.float64) + 0.5) / k + x0
    v = (np.arange(-margin, h + margin, dtype=np.float64) + 0.5) / k + y0
    X, Y = np.meshgrid(u, v)
    lon, lat = inv(X, Y)
    lonw = wrap(lon)
    rgb = eq_sample(src["bm"], *src["bm_geo"], lon, lat).astype(np.float32) / 255
    dem = src["dem"].sample(lon, lat)[..., 0].astype(np.float32)
    land = eq_sample(src["mask"], *src["mask_geo"], lon, lat).astype(np.float32) / 255
    dx0, dy0, dk = src["dist_geo"]
    dist = ndimage.map_coordinates(src["dist"], [(Y - dy0) * dk - 0.5, (X - dx0) * dk - 0.5], order=1, mode="nearest").astype(np.float32)
    polar = np.abs(lat) > 84.5
    land[polar] = 0; dem[polar] = -3000
    caspian_flat(dem, lonw, lat, land)
    out = style(rgb, dem, land, dist, MD.res / k, src["ve"], src["shadow_px"], np.random.default_rng(seed))
    return (out[margin:margin + h, margin:margin + w] * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ Blue Marble 240 px/deg crops (any region)
def bm_crop(lo0, lo1, la0, la1):
    """Blue Marble (240 px/deg) over lon lo0..lo1 (continuous, may pass 180), lat la0..la1 -> ([r, g, b], (lon0, lat1, 240))"""
    la0, la1 = max(-89.99, la0), min(89.99, la1)
    c0, r0 = int(math.floor(lo0 * 240)), int(math.floor((90 - la1) * 240))
    c1, r1 = int(math.ceil(lo1 * 240)), int(math.ceil((90 - la0) * 240))
    out = np.zeros((r1 - r0, c1 - c0, 3), np.uint8)
    for name, (tw, tn) in BM_TILES.items():
        for sh in (-360, 0, 360):
            tc0, tr0 = (tw + sh) * 240, (90 - tn) * 240           # tile origin in global px
            ic0, ic1 = max(c0, tc0), min(c1, tc0 + 21600)
            ir0, ir1 = max(r0, tr0), min(r1, tr0 + 21600)
            if ic0 >= ic1 or ir0 >= ir1: continue
            p = f"cache/bm_{name}.jpg"
            get(BM_TILE.format(name), p)
            with Image.open(p) as im:
                a = np.asarray(im.crop((ic0 - tc0, ir0 - tr0, ic1 - tc0, ir1 - tr0)).convert("RGB"))
            out[ir0 - r0:ir1 - r0, ic0 - c0:ic1 - c0] = a
            print(f"  blue marble {name}: {a.shape[1]}x{a.shape[0]} px", flush=True)
    return [np.ascontiguousarray(out[..., c]) for c in range(3)], (c0 / 240, 90 - r0 / 240, 240)


def window_lonlat(x0, y0, x1, y1, step=8.0):
    gx, gy = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
    return inv(gx, gy)


# ------------------------------------------------------------------ 1) basemap (k = 1) + globe textures
def cmd_basemap(mdir):
    t0 = time.time()
    p = "cache/bm_world.jpg"; get(BM_WORLD, p)
    im = np.asarray(Image.open(p).convert("RGB"))
    BMW = [np.ascontiguousarray(im[..., c]) for c in range(3)]
    Image.fromarray(im).resize((4096, 2048), Image.LANCZOS).save(f"{mdir}/globe_day_4k.jpg", quality=90)
    del im
    glon, glat = window_lonlat(0, 0, MD.W, MD.H, 16.0)
    dem = Mosaic("dem", 7, glon, glat, threads=32)
    print(f"DEM z7: {dem.got} tiles", flush=True)
    MW = land_mask(-180, 90, 60, 21600, 10800)
    mask_w = lambda lon, lat: eq_sample(MW, -180, 90, 60, lon, lat, order=0)
    DW = canvas_dist(mask_w, 0, 0, MD.W, MD.H, 0.5)
    src = dict(bm=BMW, bm_geo=(-180, 90, 60), dem=dem, mask=MW, mask_geo=(-180, 90, 60), dist=DW, dist_geo=(0, 0, 0.5),
               ve=9.0, shadow_px=4.0)
    rows = []
    for y in range(0, MD.H, 1024):
        rows.append(render((0, y), 1, MD.W, min(1024, MD.H - y), src, margin=40, seed=y))
        print("basemap rows", y, flush=True)
    world = np.concatenate(rows, 0)
    Image.fromarray(world).save(f"{mdir}/basemap.jpg", quality=92)
    Image.fromarray(world).resize((MD.W // 2, MD.H // 2), Image.LANCZOS).save(f"{mdir}/basemap_half.jpg", quality=90)
    del BMW, dem, DW, src, rows
    mask_w = MW = None                                       # free the world mask before the night texture
    p = "cache/blackmarble.jpg"; get(BLACK_MARBLE, p)
    Image.open(p).convert("RGB").resize((4096, 2048), Image.LANCZOS).save(f"{mdir}/globe_night_4k.jpg", quality=90)
    print(f"basemap done {time.time() - t0:.0f}s", flush=True)


# ------------------------------------------------------------------ 2) HD cells (k = 4)
_SRC = {}


def hd_cell(c):
    i, j = c
    t1 = time.time()
    cx, cy = HD_X0 + i * HD_TILE, HD_Y0 + j * HD_TILE
    lon, lat = window_lonlat(cx - 40, cy - 40, cx + HD_TILE + 40, cy + HD_TILE + 40, 32.0)
    ref = float(np.median(lon))
    lon = (lon - ref + 180) % 360 - 180 + ref
    mlo0, mlo1, mla0, mla1 = float(lon.min()) - 0.3, float(lon.max()) + 0.3, float(lat.min()) - 0.3, float(lat.max()) + 0.3
    PPD = 400
    MH = land_mask(mlo0, mla1, PPD, int((mlo1 - mlo0) * PPD) + 1, int((mla1 - mla0) * PPD) + 1)
    MG = 600                                                  # water-distance window: cell +- 600 canvas px
    wl, wb = window_lonlat(cx - MG - 40, cy - MG - 40, cx + HD_TILE + MG + 40, cy + HD_TILE + MG + 40, 32.0)
    wl = (wl - ref + 180) % 360 - 180 + ref
    dlo0, dlo1, dla0, dla1 = float(wl.min()) - 0.5, float(wl.max()) + 0.5, max(-89.9, float(wb.min()) - 0.5), min(89.9, float(wb.max()) + 0.5)
    MDm = land_mask(dlo0, dla1, 200, int((dlo1 - dlo0) * 200) + 1, int((dla1 - dla0) * 200) + 1)
    DH = canvas_dist(lambda lo, la: eq_sample(MDm, dlo0, dla1, 200, lo, la, order=0), cx - MG, cy - MG, cx + HD_TILE + MG, cy + HD_TILE + MG, 2)
    slon, slat = window_lonlat(cx - 24, cy - 24, cx + HD_TILE + 24, cy + HD_TILE + 24, 4.0)
    dem = Mosaic("dem", 9, slon, slat, threads=8)
    src = dict(bm=_SRC["bm"], bm_geo=_SRC["bm_geo"], dem=dem, mask=MH, mask_geo=(mlo0, mla1, PPD), dist=DH,
               dist_geo=(cx - MG, cy - MG, 2), ve=4.0, shadow_px=11.0)
    a = render((cx, cy), HD_K, HD_TILE * HD_K, HD_TILE * HD_K, src, margin=48, seed=i * 100 + j)
    Image.fromarray(a).save(f"{_SRC['out']}/hd/t_{i}_{j}.jpg", quality=90)
    print(f"hd cell {i},{j} done {time.time() - t1:.0f}s", flush=True)
    return c


def cells_lonlat_box(boxes, pad):
    """lon/lat bounds of canvas boxes [(x0, y0, x1, y1)] (+ pad deg), lon continuous around the map's centre meridian"""
    los, las = [], []
    for x0, y0, x1, y1 in boxes:
        lo, la = window_lonlat(x0, y0, x1, y1, max(8.0, (x1 - x0) / 8))
        lo = (lo - MD.lon0 + 180) % 360 - 180 + MD.lon0
        los += [float(lo.min()), float(lo.max())]; las += [float(la.min()), float(la.max())]
    return min(los) - pad, max(los) + pad, min(las) - pad, max(las) + pad


def cmd_tiles(mdir, kind, items):
    items = [tuple(int(v) for v in t) for t in items]
    if not items: print(f"no {kind} tiles to build"); return
    os.makedirs(f"{mdir}/{kind}", exist_ok=True)
    if kind == "hd":
        boxes = [(HD_X0 + i * HD_TILE - 64, HD_Y0 + j * HD_TILE - 64, HD_X0 + (i + 1) * HD_TILE + 64, HD_Y0 + (j + 1) * HD_TILE + 64)
                 for i, j in items]
    else:
        boxes = [(x - 32, y - 32, x + UHD_TILE + 32, y + UHD_TILE + 32) for x, y in items]
    lo0, lo1, la0, la1 = cells_lonlat_box(boxes, 1.0)
    _SRC["bm"], _SRC["bm_geo"] = bm_crop(lo0, lo1, la0, la1)
    _SRC["out"] = mdir
    print(f"{kind}: {len(items)} tiles, colour crop lon {lo0:.1f}..{lo1:.1f} lat {la0:.1f}..{la1:.1f}", flush=True)
    ne_shapes()                                              # parse once before the workers fork
    t0 = time.time()
    fn = hd_cell if kind == "hd" else uhd_tile
    with cf.ProcessPoolExecutor(min(4, len(items)), mp_context=mp.get_context("fork")) as ex:
        for n, _ in enumerate(ex.map(fn, items)):
            if n % 10 == 0: print(f"{n + 1}/{len(items)} {kind} tiles, {time.time() - t0:.0f}s", flush=True)
    print(f"{kind} done: {len(items)} tiles {time.time() - t0:.0f}s", flush=True)


# ------------------------------------------------------------------ 3) UHD tiles (k = 8, Sentinel-2 detail)
def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def uhd_tile(t):
    tx, ty = t
    t1 = time.time()
    T3 = UHD_TILE
    glon, glat = window_lonlat(tx - 16, ty - 16, tx + T3 + 17, ty + T3 + 17, 4.0)
    ref = float(np.median(glon))
    glon = (glon - ref + 180) % 360 - 180 + ref
    lo0, lo1, la0, la1 = glon.min() - 0.15, glon.max() + 0.15, glat.min() - 0.15, glat.max() + 0.15
    ppd = 900
    mask = land_mask(lo0, la1, ppd, int((lo1 - lo0) * ppd) + 1, int((la1 - la0) * ppd) + 1)
    MG = 320
    wlon, wlat = window_lonlat(tx - MG, ty - MG, tx + T3 + MG + 1, ty + T3 + MG + 1, 16.0)
    wlon = (wlon - ref + 180) % 360 - 180 + ref
    blo0, blo1, bla0, bla1 = wlon.min() - 0.3, wlon.max() + 0.3, max(-89.9, wlat.min() - 0.3), min(89.9, wlat.max() + 0.3)
    mask2 = land_mask(blo0, bla1, 300, int((blo1 - blo0) * 300) + 1, int((bla1 - bla0) * 300) + 1)
    dist = canvas_dist(lambda lon, lat: eq_sample(mask2, blo0, bla1, 300, lon, lat, order=0), tx - MG, ty - MG, tx + T3 + MG, ty + T3 + MG, 2)
    dem = Mosaic("dem", 10, glon, glat, threads=8)
    s2 = Mosaic("s2", 10, glon, glat, threads=8)
    a = render_uhd(tx, ty, dem, s2, mask, (lo0, la1, ppd), dist, (tx - MG, ty - MG, 2), tx * 7 + ty)
    Image.fromarray(a).save(f"{_SRC['out']}/uhd/u_{tx}_{ty}.jpg", quality=91)
    print(f"uhd tile {tx},{ty} done {time.time() - t1:.0f}s", flush=True)
    return t


def render_uhd(tx, ty, dem, s2, mask, mask_geo, dist, dist_geo, seed, margin=64):
    w = h = UHD_TILE * UHD_K
    u = (np.arange(-margin, w + margin, dtype=np.float64) + 0.5) / UHD_K + tx
    v = (np.arange(-margin, h + margin, dtype=np.float64) + 0.5) / UHD_K + ty
    X, Y = np.meshgrid(u, v)
    lon, lat = inv(X, Y)
    lonw = wrap(lon)
    px_m = MD.res / UHD_K
    sig = 1500.0 / px_m                                           # detail band: everything finer than ~1.5 km
    rgb_bm = eq_sample(_SRC["bm"], *_SRC["bm_geo"], lon, lat).astype(np.float32) / 255
    rgb_lp = np.stack([ndimage.gaussian_filter(rgb_bm[..., c], sig) for c in range(3)], -1)
    s2rgb = s2.sample(lon, lat) / 255.0
    L = lum(s2rgb); Llp = ndimage.gaussian_filter(L, sig)
    ratio = np.clip((L + 0.02) / (Llp + 0.02), 0.5, 1.75) ** 0.85
    land = eq_sample(mask, *mask_geo, lon, lat).astype(np.float32) / 255
    landE = np.clip(ndimage.gaussian_filter(ndimage.minimum_filter(land, size=int(900 / px_m) * 2 + 1), 2.0), 0, 1)
    rgb = np.clip(rgb_lp * (1 + (ratio[..., None] - 1) * landE[..., None]), 0, 1)
    d = dem.sample(lon, lat)[..., 0]
    dx0, dy0, dk = dist_geo
    dd = ndimage.map_coordinates(dist, [(Y - dy0) * dk - 0.5, (X - dx0) * dk - 0.5], order=1, mode="nearest").astype(np.float32)
    caspian_flat(d, lonw, lat, land)
    out = style(rgb, d, land, dd, px_m, 3.0, 20.0, np.random.default_rng(seed))
    return (out[margin:margin + h, margin:margin + w] * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ 4) record sheet
def cmd_sheet(mdir):
    im = Image.open(f"{mdir}/basemap_half.jpg").convert("RGB")
    s = im.width / MD.W
    geo = f"{mdir}/geo.json"
    if os.path.exists(geo):
        g = json.load(open(geo)); dr = ImageDraw.Draw(im)
        for f in g.get("republics", []) + g.get("context", []):
            for seg in f["d"].split("Z"):
                pts = [tuple(float(v) * s for v in p.split(",")) for p in seg.replace("M", "").split("L") if "," in p]
                if len(pts) > 2: dr.line(pts + [pts[0]], fill=(255, 40, 40) if f in g["republics"] else (255, 255, 255), width=1)
    im.thumbnail((2400, 2400)); im.save(f"{mdir}/sheet.jpg", quality=86)


def main(a):
    global MD, HD_X0, HD_Y0
    if len(a) < 2: print(__doc__); sys.exit(1)
    cmd, mdir = a[0], a[1]
    MD = mapdef.load(os.path.join(mdir, "map.json"))
    HD_X0, HD_Y0 = (int(v) for v in MD.d.get("hd_origin", [0, 0]))
    if cmd == "basemap": cmd_basemap(mdir)
    elif cmd in ("hd", "uhd"): cmd_tiles(mdir, cmd, json.loads(a[2]) if len(a) > 2 else [])
    elif cmd == "sheet": cmd_sheet(mdir)
    else: print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
