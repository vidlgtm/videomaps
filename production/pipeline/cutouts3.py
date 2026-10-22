"""v3 cut-outs with clean alpha (no rectangle, no straight frame edge, no stray fragments).
lenin      : re-matted from the archival photo with BiRefNet (portrait model, rembg)
stalin/gorbachev : existing v2 cut-outs, cleaned the same way
cleaning   : 1) faint residual alpha (the haze that made drop-shadows rectangular) -> 0
             2) keep only the main body (drop disconnected fragments)
             3) where the figure is cut by the photo frame (sides / bottom) -> soft fade instead of a straight line
             4) colour decontamination of the edge (no dark halo from the old background)
             5) tight crop
in : archive/ (assets3 archive.zip)   out: out/cutouts/<id>_cut.png, cutouts_sheet.jpg"""
import os, sys, io
import numpy as np
from PIL import Image
from scipy import ndimage

A = sys.argv[1] if len(sys.argv) > 1 else "archive"
OUT = "out/cutouts"; os.makedirs(OUT, exist_ok=True)


def clean(rgba, fade_sides=0.07, fade_bottom=0.16):
    a = rgba[..., 3].astype(np.float32) / 255
    rgb = rgba[..., :3].astype(np.float32)
    a = np.clip((a - 0.10) / 0.85, 0, 1)                                   # 1) haze -> 0
    lab, n = ndimage.label(a > 0.5)                                        # 2) main body only
    if n > 1:
        sizes = ndimage.sum(np.ones_like(a), lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(sizes >= 0.04 * sizes.max())[0])
        keep = ndimage.binary_dilation(keep, iterations=6)
        a *= keep
    h, w = a.shape                                                         # 3) frame cuts -> soft fades
    edge_hit = lambda v: (v > 0.5).mean() > 0.01
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f = np.ones_like(a)
    fs, fb = fade_sides * min(w, h), fade_bottom * h
    if edge_hit(a[:, 0]): f *= np.clip(xx / fs, 0, 1) ** 1.6
    if edge_hit(a[:, -1]): f *= np.clip((w - 1 - xx) / fs, 0, 1) ** 1.6
    if edge_hit(a[-1, :]): f *= np.clip((h - 1 - yy) / fb, 0, 1) ** 1.4
    if edge_hit(a[0, :]): f *= np.clip(yy / fs, 0, 1) ** 1.6
    a *= f
    core = (a > 0.92).astype(np.float32)                                   # 4) decontaminate edge colour
    num = np.stack([ndimage.gaussian_filter(rgb[..., c] * core, 6) for c in range(3)], -1)
    den = ndimage.gaussian_filter(core, 6)[..., None] + 1e-4
    fg = num / den
    conf = np.clip((a - 0.45) / 0.45, 0, 1)[..., None]
    rgb = np.where(den > 0.02, rgb * conf + fg * (1 - conf), rgb)
    ys, xs = np.where(a > 0.01)                                            # 5) tight crop
    y0, y1, x0, x1 = max(0, ys.min() - 8), min(h, ys.max() + 9), max(0, xs.min() - 8), min(w, xs.max() + 9)
    out = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)[y0:y1, x0:x1]
    return Image.fromarray(out, "RGBA")


items = []
# Lenin: re-matte from the photo
from rembg import remove, new_session
src = Image.open(f"{A}/lenin.jpg").convert("RGB")
for model in ("birefnet-portrait", "birefnet-general", "isnet-general-use"):
    try:
        sess = new_session(model)
        m = remove(src, session=sess, only_mask=True, post_process_mask=False)
        print("lenin matte:", model, flush=True)
        break
    except Exception as e:
        print("model failed", model, e, flush=True)
rgba = np.dstack([np.asarray(src), np.asarray(m.convert("L"))])
im = clean(rgba); im.thumbnail((1600, 1600), Image.LANCZOS); im.save(f"{OUT}/lenin_cut.png"); items.append(("lenin", im))
for cid in ("stalin", "gorbachev"):
    rgba = np.asarray(Image.open(f"{A}/{cid}_cut.png").convert("RGBA"))
    im = clean(rgba); im.save(f"{OUT}/{cid}_cut.png"); items.append((cid, im))
    print(cid, im.size, flush=True)

# contact sheet on two backgrounds (map-dark and light) to show the alpha is clean
TH = 520
row = []
for cid, im in items:
    t = im.copy(); t.thumbnail((TH, TH))
    for bg in ((22, 30, 40), (205, 200, 190)):
        c = Image.new("RGB", (TH, TH), bg); c.paste(t, ((TH - t.width) // 2, TH - t.height), t); row.append(c)
sheet = Image.new("RGB", (TH * len(row), TH))
for i, c in enumerate(row): sheet.paste(c, (i * TH, 0))
sheet.save(f"{OUT}/cutouts_sheet.jpg", quality=88)
print("done")
