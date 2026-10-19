"""Image -> 3D mesh with Tencent Hunyuan3D-2 (public HF Space, /shape_generation).
Writes out/model/matryoshka.glb and out/model/meta.json (image crop box for UV projection).
Exit code 3 = Space unavailable (workflow then falls back to TripoSR on CPU)."""
import json, os, shutil, sys, time
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], "out/model"
os.makedirs(OUT, exist_ok=True)
im = Image.open(SRC).convert("RGB"); a = np.asarray(im).astype(int)
mask = (np.abs(a - 255).sum(-1) > 40)
ys, xs = np.where(mask)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
pad = int(0.06 * (y1 - y0))
side = max(x1 - x0, y1 - y0) + 2 * pad
cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
sq = Image.new("RGB", (side, side), (255, 255, 255))
sq.paste(im, (side // 2 - cx, side // 2 - cy))
sq = sq.resize((1024, 1024), Image.LANCZOS); sq.save(f"{OUT}/input_square.png")
json.dump({"img_w": im.width, "img_h": im.height, "bbox": [int(x0), int(y0), int(x1), int(y1)]}, open(f"{OUT}/meta.json", "w"))
shutil.copy(SRC, f"{OUT}/texture.png")

from gradio_client import Client, handle_file
for attempt in range(3):
    try:
        c = Client("tencent/Hunyuan3D-2", verbose=False)
        res = c.predict(caption=None, image=handle_file(f"{OUT}/input_square.png"), steps=30, guidance_scale=5.0,
                        seed=1234, octree_resolution=256, check_box_rembg=True, num_chunks=8000, randomize_seed=False,
                        api_name="/shape_generation")
        found = []
        def walk(x):
            if isinstance(x, str) and os.path.exists(x) and x.lower().endswith((".glb", ".obj", ".ply")): found.append(x)
            elif isinstance(x, dict): [walk(v) for v in x.values()]
            elif isinstance(x, (list, tuple)): [walk(v) for v in x]
        walk(res)
        if found:
            shutil.copy(found[0], f"{OUT}/matryoshka.glb")
            json.dump({"source": "Hunyuan3D-2", "attempt": attempt}, open(f"{OUT}/source.json", "w"))
            print("Hunyuan3D-2 OK", found[0]); sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print("attempt", attempt, repr(e)[:300]); time.sleep(30 + 30 * attempt)
sys.exit(3)
