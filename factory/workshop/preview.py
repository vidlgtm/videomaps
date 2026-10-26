"""Evaluates the CPU preview a template wrote in --preview mode (check.json + 6 key frames + labels.json):
automatic checks -> preview.json, and the review sheet (3 x 2 key frames, label positions drawn, problem frames framed red).
checks: void (empty background where ground should be), low-detail ground close to the lens, exposure of the subject
against the template target, crushed shadows, blown highlights, plus the template's own errors and warnings."""
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fonts", "Inter.ttf")


def _mask(grid, codes, h, w):
    g = np.array([[c in codes for c in row] for row in grid], bool)
    return g[(np.arange(h) * g.shape[0]) // h][:, (np.arange(w) * g.shape[1]) // w]


def evaluate(odir, seconds):
    ck = json.load(open(os.path.join(odir, "check.json")))
    errors, warnings = list(ck.get("errors", [])), list(ck.get("warnings", []))
    bad_frames = set()
    for f, c in ck["counts"].items():
        tot = max(1, sum(c.values()))
        t = (int(f) - 1) / 30
        if c.get("v", 0):
            errors.append(f"empty space where ground should be at {t:.1f}s ({c['v'] / tot:.1%} of the frame)"); bad_frames.add(int(f))
        if c.get("x", 0) / tot > 0.005:
            errors.append(f"low-detail ground close to the lens at {t:.1f}s ({c['x'] / tot:.1%})"); bad_frames.add(int(f))
    lum, tiles = [], []
    for f in ck["key_frames"]:
        im = Image.open(os.path.join(odir, f"p_{f:04d}{ck.get('ext', '.jpg')}")).convert("RGBA")
        bg = Image.new("RGBA", im.size, (40, 44, 50, 255)); bg.alpha_composite(im); im = bg.convert("RGB").resize((640, 360), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255
        y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
        g = ck["grids"][str(f)]
        m = _mask(g, ck["subject"], 360, 640)
        if m.mean() < 0.08 and ck.get("subject_fallback"): m = _mask(g, ck["subject_fallback"], 360, 640)
        lum.append(float(y[m].mean()) if m.mean() > 0.02 else float(y.mean()))
        dark, blown = float((y < 0.06).mean()), float((y > 0.985).mean())
        if dark > ck.get("dark_max", 0.15): errors.append(f"too dark at {(f - 1) / 30:.1f}s: {dark:.0%} of the frame almost black"); bad_frames.add(f)
        if blown > 0.03: warnings.append(f"blown highlights at {(f - 1) / 30:.1f}s ({blown:.1%})")
        tiles.append((f, im))
    tgt, tol = ck["luma_target"], ck["luma_tol"]
    mean = float(np.mean(lum))
    if abs(mean - tgt) > tol: errors.append(f"exposure off: subject brightness {mean:.2f}, target {tgt:.2f} +/- {tol:.2f} (ev {ck['ev']:+.2f})")
    lab = None
    lp = os.path.join(odir, "labels.json")
    if os.path.exists(lp): lab = json.load(open(lp))
    sheet = Image.new("RGB", (1920, 720), (12, 18, 24))
    try: font = ImageFont.truetype(FONT, 15); small = ImageFont.truetype(FONT, 13)
    except Exception: font = small = ImageFont.load_default()
    for i, (f, im) in enumerate(tiles):
        d = ImageDraw.Draw(im)
        if lab:
            names = {n[0]: n for n in lab["names"]}
            for k, tr in lab["tracks"].items():
                x, yy, vis = tr[f - 1]
                if not vis: continue
                x, yy = x / 3, yy / 3
                hot = names.get(k, ["", "", ""])[2] == "hot"
                d.ellipse((x - 3, yy - 3, x + 3, yy + 3), fill=(255, 120, 90) if hot else (255, 240, 200))
                d.text((x + 6, yy - 9), names.get(k, [k, k])[1], font=font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(10, 16, 22))
        d.text((8, 340), f"{(f - 1) / 30:.1f}s", font=small, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        if f in bad_frames: d.rectangle((1, 1, 638, 358), outline=(230, 40, 40), width=4)
        sheet.paste(im, ((i % 3) * 640, (i // 3) * 360))
    res = {"ok": not errors, "ev": ck["ev"], "errors": errors, "warnings": warnings, "subject_luma": [round(v, 3) for v in lum],
           "luma_target": tgt, "calibration": ck.get("calibration"), "stats": ck.get("stats", {}),
           "cpu_s_per_frame": ck.get("cpu_s_per_frame"), "key_frames": ck["key_frames"], "labels": bool(lab)}
    return res, sheet
