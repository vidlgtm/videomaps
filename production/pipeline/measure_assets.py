"""Measure the project's images so the layout engine sizes them exactly (no guessing):
src/data/aspect.json     : width/height of every public/archive image   (documents, cut-outs, banners)
src/data/icon_boxes.json : visible-content box (alpha > 8) of every public/icons/<name>_a<az>.png, as fractions
usage (from production/remotion): python ../pipeline/measure_assets.py"""
import glob, json, os
import numpy as np
from PIL import Image
asp = {}
for f in sorted(glob.glob("public/archive/*")):
    if f.lower().endswith((".jpg", ".jpeg", ".png")):
        with Image.open(f) as im: asp["archive/" + os.path.basename(f)] = round(im.width / im.height, 5)
boxes = {}
for f in sorted(glob.glob("public/icons/*.png")):
    a = np.asarray(Image.open(f).convert("RGBA"))[..., 3]
    ys, xs = np.where(a > 8)
    if len(xs):
        h, w = a.shape
        boxes[os.path.basename(f)[:-4]] = [round(xs.min() / w, 3), round(ys.min() / h, 3), round((xs.max() + 1) / w, 3), round((ys.max() + 1) / h, 3)]
json.dump(asp, open("src/data/aspect.json", "w"), indent=0)
json.dump(boxes, open("src/data/icon_boxes.json", "w"), indent=0)
print(f"aspect: {len(asp)} images; icon boxes: {len(boxes)} renders")
