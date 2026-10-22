"""v5: HD terrain cells (k = 4, 512 canvas px -> 2048 px) that the camera path still needed but terrain2 skipped because they
reach outside its Blue Marble source window (north-west Europe, Kola, the Barents coast). Rendered with exactly the terrain2
recipe - same render()/style(), Blue Marble C1 colour, terrarium z9 relief, Natural Earth 10m land at 400 px/deg, the
canvas-grid water-distance sea ramp and the same per-tile seed (i * 100 + j) - so they join the existing HD tiles seamlessly.
env HD_CELLS='[[i, j], ...]' (HD grid: x0 = 0, y0 = 1024, tile 512).  output: out/hd5/hd/t_<i>_<j>.jpg"""
import os, json, math, time
import concurrent.futures as cf
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
src_txt = open(f"{HERE}/terrain2.py").read()
exec(compile(src_txt.split("# ======================= 1) world basemap")[0], "terrain2_head", "exec"))  # helpers only

OUT5 = "out/hd5"; os.makedirs(f"{OUT5}/hd", exist_ok=True)
HD = json.load(open(f"{ROOT}/remotion/src/data/hd_index.json"))
X0, Y0, TILE, K = HD["x0"], HD["y0"], HD["tile"], HD["k"]
CELLS = [tuple(c) for c in json.loads(os.environ["HD_CELLS"])]
MG = 600                                     # water-distance window: cell +- 700 km (terrain2: whole HD grid + 220 px)
PPD = 400

# Blue Marble C1 (0..90E, 90N..0N, 240 px/deg) cropped to the cells (+ margin)
def cell_lonlat(i, j, pad):
    cx, cy = X0 + i * TILE, Y0 + j * TILE
    bx, by = np.meshgrid(np.linspace(cx - pad, cx + TILE + pad, 17), np.linspace(cy - pad, cy + TILE + pad, 17))
    return inv(bx, by)
ll = [cell_lonlat(i, j, 64) for i, j in CELLS]      # colour is only sampled inside the cell (+ render margin)
LO0 = max(0.0, min(float(a.min()) for a, _ in ll) - 1.0); LO1 = min(90.0, max(float(a.max()) for a, _ in ll) + 1.0)
LA0 = max(0.0, min(float(b.min()) for _, b in ll) - 1.0); LA1 = min(89.9, max(float(b.max()) for _, b in ll) + 1.0)
bm_c1 = "cache/bm_c1.jpg"
if not os.path.exists(bm_c1):
    get("https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x21600x21600.C1.jpg", bm_c1)
C1 = Image.open(bm_c1)
r0, r1, c0_, c1_ = int((90 - LA1) * 240), int((90 - LA0) * 240), int(LO0 * 240), int(LO1 * 240)
_im = np.asarray(C1.crop((c0_, r0, c1_, r1)).convert("RGB")); del C1
BMC = [np.ascontiguousarray(_im[..., c]) for c in range(3)]; del _im
BM_GEO = (c0_ / 240, 90 - r0 / 240, 240)
print(f"BM crop lon {LO0:.1f}..{LO1:.1f} lat {LA0:.1f}..{LA1:.1f}: {BMC[0].shape}", flush=True)


def do_cell(c):
    i, j = c
    t1 = time.time()
    cx, cy = X0 + i * TILE, Y0 + j * TILE
    # land mask at the terrain2 HD resolution over the cell (+ render margin)
    lon, lat = cell_lonlat(i, j, 40)
    mlo0, mlo1, mla0, mla1 = float(lon.min()) - 0.3, float(lon.max()) + 0.3, float(lat.min()) - 0.3, float(lat.max()) + 0.3
    MH = land_mask(mlo0, mla1, PPD, int((mlo1 - mlo0) * PPD) + 1, int((mla1 - mla0) * PPD) + 1)
    # coarser mask over the water-distance window
    wl, wb = cell_lonlat(i, j, MG + 40)
    dlo0, dlo1, dla0, dla1 = float(wl.min()) - 0.5, float(wl.max()) + 0.5, float(wb.min()) - 0.5, min(89.9, float(wb.max()) + 0.5)
    MD = land_mask(dlo0, dla1, 200, int((dlo1 - dlo0) * 200) + 1, int((dla1 - dla0) * 200) + 1)
    DH = canvas_dist(lambda lo, la: eq_sample(MD, dlo0, dla1, 200, lo, la, order=0), cx - MG, cy - MG, cx + TILE + MG, cy + TILE + MG, 2)
    sx, sy = np.meshgrid(np.arange(cx - 24, cx + TILE + 25, 4.0), np.arange(cy - 24, cy + TILE + 25, 4.0))
    slon, slat = inv(sx, sy)
    dem = Dem(9, slon, slat)
    src = dict(bm=BMC, bm_geo=BM_GEO, dem=dem, mask=MH, mask_geo=(mlo0, mla1, PPD), dist=DH, dist_geo=(cx - MG, cy - MG, 2),
               ve=4.0, shadow_px=11.0)
    a = render((cx, cy), K, TILE * K, TILE * K, src, margin=48, seed=i * 100 + j)
    Image.fromarray(a).save(f"{OUT5}/hd/t_{i}_{j}.jpg", quality=90)
    print(f"cell {i},{j} done {time.time() - t1:.0f}s", flush=True)
    return c


t0 = time.time()
with cf.ProcessPoolExecutor(min(4, len(CELLS))) as ex:
    done = list(ex.map(do_cell, CELLS))
print(f"HD5 done: {len(done)} cells, {time.time() - t0:.0f}s", flush=True)
