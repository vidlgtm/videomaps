"""Smoke test of image helpers: rembg (background removal), Depth-Anything-V2-Small (depth for 2.5D parallax), Real-ESRGAN (x4 upscale)."""
import json, os, urllib.request, traceback
import numpy as np
from PIL import Image

OUT = "out/images"
os.makedirs(OUT, exist_ok=True)
SRC = f"{OUT}/input.png"
urllib.request.urlretrieve("https://raw.githubusercontent.com/VAST-AI-Research/TripoSR/main/examples/chair.png", SRC)
rep = {}

try:
    from rembg import remove
    remove(Image.open(SRC)).save(f"{OUT}/rembg.png"); rep["rembg"] = "ok"
except Exception as e:
    rep["rembg"] = repr(e)[:300]; traceback.print_exc(limit=1)

try:
    from transformers import pipeline
    pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
    pipe(Image.open(SRC).convert("RGB"))["depth"].save(f"{OUT}/depth.png"); rep["depth_anything_v2"] = "ok"
except Exception as e:
    rep["depth_anything_v2"] = repr(e)[:300]; traceback.print_exc(limit=1)

try:
    import cv2
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    up = RealESRGANer(scale=4, model_path="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                      model=model, tile=256, tile_pad=10, pre_pad=0, half=False, device="cpu")
    img = cv2.imread(SRC, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2))
    out, _ = up.enhance(img, outscale=4)
    cv2.imwrite(f"{OUT}/esrgan_x4.png", out); rep["real_esrgan"] = f"ok {img.shape[1]}x{img.shape[0]} -> {out.shape[1]}x{out.shape[0]}"
except Exception as e:
    rep["real_esrgan"] = repr(e)[:300]; traceback.print_exc(limit=1)

print("IMAGE-TOOLS", json.dumps(rep))
json.dump(rep, open(f"{OUT}/report.json", "w"), indent=1)
