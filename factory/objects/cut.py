"""Cut-out of an order-store picture for image-to-3D (its own key: changing a check never changes a 3D object).
cut_out(src, out_png, session) : the object on a transparent square - the picture's own transparency when it has one,
                                 otherwise rembg (u2net) - centred at 0.85 of the side (TripoSR's own input framing),
                                 1024 px; returns facts for check_cut (coverage, border contact, separate parts)
grey_input(cut_png, out_png)   : the cut-out over 50 % grey (what TripoSR feeds its model)"""
import numpy as np
from PIL import Image
from scipy import ndimage

SIDE = 1024


def cut_out(src, out_png, session=None):
    im = Image.open(src)
    im.load()
    own = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA")
    if own and im.getextrema()[3][0] < 255:
        rgba, how = im, "own transparency"
    else:
        import rembg
        rgba, how = rembg.remove(im.convert("RGB"), session=session).convert("RGBA"), "rembg"
    A = np.asarray(rgba)[..., 3]
    m = A > 128
    h, w = A.shape
    info = {"how": how, "src_size": [w, h], "coverage": round(float(m.mean()), 4)}
    if m.sum() < 64:
        info["empty"] = True; return info
    border = {"top": float(m[0].mean()), "bottom": float(m[-1].mean()), "left": float(m[:, 0].mean()), "right": float(m[:, -1].mean())}
    info["border"] = {k: round(v, 3) for k, v in border.items()}
    lab, n = ndimage.label(m)
    sizes = np.sort(ndimage.sum(m, lab, range(1, n + 1)))[::-1] if n else np.array([0])
    info["parts"] = int((sizes > 0.1 * sizes[0]).sum())
    ys, xs = np.where(A > 0)
    fg = np.asarray(rgba)[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = max(fg.shape[0], fg.shape[1])
    sq = np.zeros((s, s, 4), np.uint8)
    oy, ox = (s - fg.shape[0]) // 2, (s - fg.shape[1]) // 2
    sq[oy:oy + fg.shape[0], ox:ox + fg.shape[1]] = fg
    n2 = int(s / 0.85)
    out = np.zeros((n2, n2, 4), np.uint8)
    o2 = (n2 - s) // 2
    out[o2:o2 + s, o2:o2 + s] = sq
    Image.fromarray(out).resize((SIDE, SIDE), Image.LANCZOS).save(out_png)
    info["object_px"] = [int(fg.shape[1]), int(fg.shape[0])]
    return info


def grey_input(cut_png, out_png):
    """TripoSR input: the cut-out over 50 % grey (what TripoSR itself feeds the model)"""
    a = np.asarray(Image.open(cut_png).convert("RGBA")).astype(np.float32) / 255.0
    rgb = a[..., :3] * a[..., 3:4] + (1 - a[..., 3:4]) * 0.5
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(out_png)
