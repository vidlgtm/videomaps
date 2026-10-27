"""Checks and review sheets of the order's 3D objects (numpy + Pillow + scipy; no Blender).
check_cut(info)                : the picture shows one whole object, big enough
check_views(views, cut, final) : every render - object present, centred, not cut by the frame, exposure, holes,
                                 colours close to the picture
sheet(...)                     : one review row per object: cut-out + every azimuth, the chosen one framed"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    try: return ImageFont.load_default(size=sz)
    except TypeError: return ImageFont.load_default()


def check_cut(info):
    errs, warns = [], []
    if info.get("empty"): return ["no object was found in the picture (the cut-out is empty)"], []
    if info["coverage"] < 0.02: errs.append(f"the object covers only {info['coverage']:.1%} of the picture: choose a closer picture")
    if min(info["object_px"]) < 160: errs.append(f"the object is only {info['object_px'][0]}x{info['object_px'][1]} px in the picture: choose a larger picture")
    touch = {k: v for k, v in info["border"].items() if v > 0.03}
    if len(touch) >= 2 or any(v > 0.15 for v in touch.values()):
        errs.append("the picture cuts the object at its edge (" + ", ".join(f"{k} {v:.0%}" for k, v in touch.items())
                    + "): choose a picture that shows the whole object")
    elif touch:
        warns.append("the object touches the picture edge at the " + ", ".join(touch) + " (check the cut-out)")
    if info.get("parts", 1) > 1: warns.append(f"the picture holds {info['parts']} separate objects; they become one 3D object")
    return errs, warns


def _lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _fg(png):
    a = np.asarray(Image.open(png).convert("RGBA")).astype(np.float32)
    return a, a[..., 3] > 128


def view_metrics(png):
    a, m = _fg(png)
    h, w = m.shape
    if m.sum() < 32: return {"empty": True}
    ys, xs = np.where(a[..., 3] > 8)
    box = [xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h]
    px = a[m][:, :3]
    luma = (0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]) / 255.0
    filled = ndimage.binary_fill_holes(m)
    mx, mn = px.max(1), px.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    return {"box": [round(float(v), 4) for v in box], "fill": round(float(max(box[2] - box[0], box[3] - box[1])), 4),
            "margin": round(float(min(box[0], box[1], 1 - box[2], 1 - box[3])), 4), "luma": round(float(luma.mean()), 4),
            "clipped": round(float((px.max(1) >= 254).mean()), 4), "crushed": round(float((px.max(1) <= 3).mean()), 4),
            "holes": round(float((filled & ~m).sum() / max(1, filled.sum())), 4), "sat": round(float(sat.mean()), 4),
            "lab": [round(float(v), 2) for v in _lab(px).mean(0)], "lstat": [round(float(_lab(px)[:, 0].mean()), 2), round(float(_lab(px)[:, 0].std()), 2)]}


def check_views(views, cut_png, final, mesh=None):
    """views {az: png}; cut_png = the picture's cut-out (colour reference); mesh = render.json of render_obj.py"""
    errs, warns, M = [], [], {}
    for az, png in views.items():
        if not os.path.exists(png): errs.append(f"a{az}: render missing"); continue
        v = M[az] = view_metrics(png)
        if v.get("empty"): errs.append(f"a{az}: the render is empty (no object)"); continue
        if v["margin"] < 0.015: errs.append(f"a{az}: the object touches the frame edge (margin {v['margin']:.1%})")
        if not 0.5 <= v["fill"] <= 0.93: errs.append(f"a{az}: the object fills {v['fill']:.0%} of the frame (expected 50-93 %)")
        if not 0.12 <= v["luma"] <= 0.88: errs.append(f"a{az}: exposure off (object brightness {v['luma']:.2f}, expected 0.12-0.88)")
        if v["clipped"] > 0.03: (errs if final else warns).append(f"a{az}: {v['clipped']:.1%} of the object is blown out")
        if v["crushed"] > 0.10: (errs if final else warns).append(f"a{az}: {v['crushed']:.1%} of the object is pure black")
        if v["holes"] > 0.06: warns.append(f"a{az}: holes in the object ({v['holes']:.1%} of its outline)")
    good = {az: v for az, v in M.items() if not v.get("empty")}
    if cut_png and os.path.exists(cut_png) and good:
        a, m = _fg(cut_png)
        px = a[m][:, :3]
        lr = _lab(px); ref = lr.mean(0); ref_l = (float(lr[:, 0].mean()), float(lr[:, 0].std()))
        mx, mn = px.max(1), px.min(1)
        ref_sat = float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0).mean())
        dE = {az: float(np.linalg.norm(np.array(v["lab"]) - ref)) for az, v in good.items()}
        dEm = float(np.median(list(dE.values())))                  # every azimuth counts, not only the best one
        dL = float(np.median([abs(v["lstat"][0] - ref_l[0]) for v in good.values()]))
        con = float(np.median([v["lstat"][1] for v in good.values()])) / max(ref_l[1], 1e-6)
        M["colour"] = {"ref_lab": [round(float(x), 2) for x in ref], "ref_sat": round(ref_sat, 4), "ref_l": [round(x, 2) for x in ref_l],
                       "dE": {k: round(x, 1) for k, x in dE.items()}, "dE_median": round(dEm, 1), "dL": round(dL, 1), "contrast": round(con, 3)}
        if dEm > 30: errs.append(f"the colours are far from the picture (mean colour difference {dEm:.0f} ΔE)")
        elif dEm > 18: warns.append(f"the colours differ from the picture (mean colour difference {dEm:.0f} ΔE)")
        if dL > 20: errs.append(f"the object is much brighter or darker than the picture ({dL:.0f} L*)")
        elif dL > 12: warns.append(f"the object's brightness differs from the picture ({dL:.0f} L*)")
        if ref_l[1] > 8 and con < 0.55: errs.append(f"the object lost the picture's light and dark ({con:.0%} of its contrast)")
        elif ref_l[1] > 8 and con < 0.75: warns.append(f"the object is flatter than the picture ({con:.0%} of its contrast)")
        if ref_sat > 0.15 and max(v["sat"] for v in good.values()) < 0.05: errs.append("the colours of the picture were lost (grey object)")
    if mesh:
        if mesh.get("colour") == "none": errs.append("the 3D object has no colours")
        d = sorted(mesh.get("dims", [1, 1, 1]))
        if d[0] < 0.015: errs.append(f"the object is flat ({d[0]:.3f} of its size): the picture was read as a flat card")
        elif d[0] < 0.04: warns.append(f"the object is very thin ({d[0]:.3f} of its size)")
        if mesh.get("faces", 0) < 500: errs.append(f"the mesh has only {mesh.get('faces')} faces")
    return errs, warns, M


def sheet(name, title, cut_png, views, chosen, ok, errs, warns, note=None, cell=300):
    azs = list(views)
    W = cell * (1 + len(azs)) + 20 * (2 + len(azs))
    lines = [(e, (255, 120, 110)) for e in errs] + [(w, (240, 200, 120)) for w in warns]
    if note: lines.append((note, (170, 190, 230)))
    H = 64 + cell + 34 + 22 * len(lines) + 16
    im = Image.new("RGB", (W, H), (34, 37, 44))
    d = ImageDraw.Draw(im)
    d.text((20, 14), f"{name} · {title}", font=font(22), fill=(240, 240, 240))
    d.text((W - 110, 14), "PASS" if ok else "FAIL", font=font(22), fill=(120, 220, 140) if ok else (255, 110, 100))
    tiles = [("picture", cut_png)] + [(f"a{az}", views[az]) for az in azs]
    for i, (lab, p) in enumerate(tiles):
        x0, y0 = 20 + i * (cell + 20), 56
        ck = Image.new("RGB", (cell, cell), (92, 96, 104))
        cd = ImageDraw.Draw(ck)
        for yy in range(0, cell, 20):
            for xx in range(0, cell, 20):
                if (xx // 20 + yy // 20) % 2: cd.rectangle([xx, yy, xx + 19, yy + 19], fill=(104, 108, 116))
        if p and os.path.exists(p):
            t = Image.open(p).convert("RGBA"); t.thumbnail((cell, cell), Image.LANCZOS)
            ck.paste(t, ((cell - t.width) // 2, (cell - t.height) // 2), t)
        im.paste(ck, (x0, y0))
        if lab == f"a{chosen}": d.rectangle([x0 - 4, y0 - 4, x0 + cell + 3, y0 + cell + 3], outline=(240, 196, 70), width=4)
        d.text((x0 + 4, y0 + cell + 6), lab + ("  (chosen)" if lab == f"a{chosen}" else ""), font=font(17), fill=(220, 220, 220))
    y = 56 + cell + 34
    for t, col in lines:
        d.text((20, y), t[:200], font=font(16), fill=col); y += 22
    return im


if __name__ == "__main__":
    print(__doc__)
