"""Archive images of a project (projects/<P>/archive/<id>.jpg, licences in projects/<P>/archive/credits.json):
- depth map <id>_depth.png (Depth-Anything-V2-Small) for every id in project.json "archive" that has none yet
  (the film cuts a near layer from it -> 2.5D parallax on banners/documents, see DEPTH_IDS in src/v2.ts)
- cut-out <id>_cut.png (rembg BiRefNet-portrait -> BiRefNet-general -> ISNet; haze removal, main body only, soft frame
  fades, edge colour decontamination, tight crop) for every id in project.json "cutouts"
- optional 4x super-resolution (Real-ESRGAN general x4v3 via spandrel) for ids in project.json "upscale" (< 1100 px wide)
env PROJECT. output: out/archive/"""
import json, os, time
import numpy as np, requests
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.environ.get("PROJECT", "example_baltic")
PJ = json.load(open(f"{ROOT}/projects/{P}/project.json"))
A = f"{ROOT}/projects/{P}/archive"; OUT = "out/archive"; os.makedirs(OUT, exist_ok=True)
ids, cuts, ups = PJ.get("archive", []), PJ.get("cutouts", []), PJ.get("upscale", [])


def src(i):
    for e in (".jpg", ".jpeg", ".png"):
        if os.path.exists(f"{A}/{i}{e}"): return f"{A}/{i}{e}"
    raise SystemExit(f"missing archive image {A}/{i}.jpg")


import torch
torch.set_num_threads(4)
if ups:
    from spandrel import ModelLoader
    wp = "realesr-general-x4v3.pth"
    if not os.path.exists(wp):
        open(wp, "wb").write(requests.get("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth", timeout=300).content)
    SR = ModelLoader().load_from_file(wp).eval()
    for i in ups:
        img = Image.open(src(i)).convert("RGB")
        if img.width >= 1100: continue
        x = torch.from_numpy(np.asarray(img, np.float32) / 255).permute(2, 0, 1)[None]
        with torch.inference_mode(): y = SR(x).clamp(0, 1)
        Image.fromarray((y[0].permute(1, 2, 0).numpy() * 255 + 0.5).astype(np.uint8)).save(f"{OUT}/{i}.jpg", quality=92)
        print("upscaled", i, flush=True)
need_depth = [i for i in ids if not os.path.exists(f"{A}/{i}_depth.png")]
if need_depth:
    from transformers import pipeline
    DEPTH = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
    for i in need_depth:
        img = Image.open(f"{OUT}/{i}.jpg" if os.path.exists(f"{OUT}/{i}.jpg") else src(i)).convert("RGB")
        small = img.copy(); small.thumbnail((1024, 1024))
        d = DEPTH(small)["depth"].convert("L").resize((img.width // 2, img.height // 2), Image.BICUBIC)
        d.save(f"{OUT}/{i}_depth.png"); print("depth", i, flush=True)


def clean(rgba, fade_sides=0.07, fade_bottom=0.16):
    a = rgba[..., 3].astype(np.float32) / 255
    rgb = rgba[..., :3].astype(np.float32)
    a = np.clip((a - 0.10) / 0.85, 0, 1)
    lab, n = ndimage.label(a > 0.5)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(a), lab, range(1, n + 1))
        keep = ndimage.binary_dilation(np.isin(lab, 1 + np.where(sizes >= 0.04 * sizes.max())[0]), iterations=6)
        a *= keep
    h, w = a.shape
    hit = lambda v: (v > 0.5).mean() > 0.01
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f = np.ones_like(a); fs, fb = fade_sides * min(w, h), fade_bottom * h
    if hit(a[:, 0]): f *= np.clip(xx / fs, 0, 1) ** 1.6
    if hit(a[:, -1]): f *= np.clip((w - 1 - xx) / fs, 0, 1) ** 1.6
    if hit(a[-1, :]): f *= np.clip((h - 1 - yy) / fb, 0, 1) ** 1.4
    if hit(a[0, :]): f *= np.clip(yy / fs, 0, 1) ** 1.6
    a *= f
    core = (a > 0.92).astype(np.float32)
    num = np.stack([ndimage.gaussian_filter(rgb[..., c] * core, 6) for c in range(3)], -1)
    den = ndimage.gaussian_filter(core, 6)[..., None] + 1e-4
    conf = np.clip((a - 0.45) / 0.45, 0, 1)[..., None]
    rgb = np.where(den > 0.02, rgb * conf + (num / den) * (1 - conf), rgb)
    ys, xs = np.where(a > 0.01)
    y0, y1, x0, x1 = max(0, ys.min() - 8), min(h, ys.max() + 9), max(0, xs.min() - 8), min(w, xs.max() + 9)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)[y0:y1, x0:x1], "RGBA")


if cuts:
    from rembg import remove, new_session
    sess = None
    for model in ("birefnet-portrait", "birefnet-general", "isnet-general-use"):
        try: sess = new_session(model); print("matte model:", model, flush=True); break
        except Exception as e: print("matte model failed:", model, e, flush=True)
    for i in cuts:
        img = Image.open(src(i)).convert("RGB")
        m = remove(img, session=sess, only_mask=True, post_process_mask=False)
        rgba = np.dstack([np.asarray(img), np.asarray(m.convert("L"))])
        im = clean(rgba); im.thumbnail((1600, 1600), Image.LANCZOS); im.save(f"{OUT}/{i}_cut.png"); print("cut-out", i, flush=True)
print("archive done:", sorted(os.listdir(OUT)))
