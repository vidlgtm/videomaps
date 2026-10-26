"""Workshop template 'reveal' - plain geometry and timing (no Blender): item sizes, the paper curl, the layout on the desk,
the timeline, the camera path and its framing.  Units: the long side of an item of size 1 is 1."""
import math
import numpy as np

BORDER = 0.05                      # white margin of a print (share of its long side)
GAP = 0.24                         # free space between two items (the smallest one tried)
GAPS = (0.24, 0.32, 0.40, 0.50, 0.62)  # tried in turn until no revealed item shows as a thin sliver at the frame edge
SLIVER = 0.15                      # a visible part under this share of an item's width (or height) is a sliver
TILT = (-2.5, 1.8, -1.2, 2.2)      # turn of each item on the desk (degrees)
SHIFT = (0.0, 0.035, -0.025, 0.03)  # small offsets along the depth of the desk
LEAD, ARR, REV, HOLD = 0.6, 1.2, 1.4, 1.6   # dark start, camera move to the next item, reveal, shortest hold (s)
AZ0, ORBIT = -7.0, 6.0             # camera azimuth at mid-clip and its slow drift over the clip (degrees)
K0, K1 = 1.12, 1.07                # camera distance at the start of the first item / on arrival at the next, pushing to 1
SIGMA = 0.15                       # the camera path is smoothed by a Gaussian of this width (s)


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def curl(it, x, y):
    """height of the paper above the desk at (x, y) of the item: the edges lift a little, the corners most"""
    L_ = max(it["w"], it["h"]); doc = it["kind"] == "document"
    a, b = np.abs(2 * x / it["w"]), np.abs(2 * y / it["h"])
    return L_ * ((0.016 if doc else 0.010) * (0.7 * a ** 3 + 0.3 * b ** 3) + (0.012 if doc else 0.006) * (a * b) ** 4)


def thickness(it): return (0.004 if it["kind"] == "print" else 0.0025) * max(it["w"], it["h"])


def lift(it):
    """height of the highest point of the item above the desk"""
    return thickness(it) + 0.0008 + float(curl(it, it["w"] / 2, it["h"] / 2))


def dims(aspect, kind="print", size=1.0):
    """picture size (iw, ih) and item size (w, h): a print has a margin, a document is all picture"""
    b = BORDER * size if kind == "print" else 0.0
    if aspect >= 1: iw = size - 2 * b; ih = iw / aspect
    else: ih = size - 2 * b; iw = ih * aspect
    return {"iw": iw, "ih": ih, "w": iw + 2 * b, "h": ih + 2 * b, "b": b}


def corners(it):
    """corners of an item on the desk (world x, y)"""
    a = math.radians(it["rot"]); ca, sa = math.cos(a), math.sin(a)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = sx * it["w"] / 2, sy * it["h"] / 2
        out.append((it["x"] + ca * x - sa * y, it["y"] + sa * x + ca * y))
    return np.array(out)


def layout(ds, gap=GAP):
    """items left to right on a common baseline (their bottom edges in a row, so the band below the row stays free for
    the captions), each turned a little, centred on x = 0; returns the items + the smallest gap between them"""
    its, x = [], 0.0
    for i, d in enumerate(ds):
        it = dict(d, rot=TILT[i % len(TILT)], y=-0.5 + d["h"] / 2 + SHIFT[i % len(SHIFT)] * max(d["w"], d["h"]), x=0.0)
        c = corners(it); half_l = -c[:, 0].min()
        if its:
            pc = corners(its[-1]); x = pc[:, 0].max() + gap + half_l
        it["x"] = x; its.append(it)
    mid = 0.5 * (corners(its[0])[:, 0].min() + corners(its[-1])[:, 0].max())
    for it in its: it["x"] -= mid
    gaps = [corners(b)[:, 0].min() - corners(a)[:, 0].max() for a, b in zip(its, its[1:])]
    return its, (min(gaps) if gaps else None)


def timeline(T, n):
    """reveal start of every item, the start of the camera move to it, and the end of its hold"""
    need = LEAD + n * (REV + HOLD) + (n - 1) * ARR + 0.2
    hold = HOLD + max(0.0, T - need) / n
    t_rev, t_arr, t = [], [None], LEAD
    for i in range(n):
        if i: t_arr.append(t); t += ARR
        t_rev.append(t); t += REV + hold
    end = [t_arr[i + 1] if i + 1 < n else T for i in range(n)]
    return {"need": need, "hold": hold, "t_rev": t_rev, "t_arr": t_arr, "end": end}


def cam_dir(el_deg, az_deg):
    el, az = math.radians(el_deg), math.radians(az_deg)
    return np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])


def project(pts, cam, tgt, lens):
    """pinhole camera at cam looking at tgt (up = +z), sensor 36 mm wide, 16:9: returns (u, w) in [-1, 1] across the frame"""
    f = tgt - cam; f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); up = np.cross(r, f)
    v = np.asarray(pts, float) - cam; z = v @ f
    th = 18.0 / lens; tv = th * 9 / 16
    return np.column_stack([(v @ r) / (z * th), (v @ up) / (z * tv), z])


def fit(it, el_deg, az_deg, lens, fill, lift=0.0):
    """camera distance that holds the whole item within +-fill of the frame (both axes)"""
    c = corners(it); pts = np.column_stack([c, np.full(4, lift)])
    tgt = np.array([it["x"], it["y"], 0.0]); dr = cam_dir(el_deg, az_deg)
    lo, hi = 0.2, 40.0
    for _ in range(60):
        d = 0.5 * (lo + hi); p = project(pts, tgt + d * dr, tgt, lens)
        if np.all(p[:, 2] > 0) and max(np.abs(p[:, 0]).max(), np.abs(p[:, 1]).max()) <= fill: hi = d
        else: lo = d
    return hi


def camera_path(items, tl, T, el, lens, fill, fps=30):
    """camera target, distance and azimuth for every frame + the hold view of every item: holds push in slowly, moves to
    the next item ease in and out with a small rise; the whole path is smoothed by a Gaussian of SIGMA s"""
    n = len(items); frames = int(round(T * fps))
    view = [(np.array([it["x"], it["y"], 0.0]), fit(it, el, AZ0, lens, fill, lift=lift(it))) for it in items]
    ta, tr, te = tl["t_arr"], tl["t_rev"], tl["end"]

    def raw(t):
        for i in range(n):
            if i and ta[i] <= t < tr[i]:
                s = smooth((t - ta[i]) / ARR)
                tg = (1 - s) * view[i - 1][0] + s * view[i][0]
                return tg, ((1 - s) * view[i - 1][1] + s * view[i][1] * K1) * (1 + 0.10 * math.sin(math.pi * s))
            st = 0.0 if i == 0 else tr[i]
            if st <= t < te[i] or (i == n - 1 and t >= st):
                s = min(max((t - st) / max(te[i] - st, 1e-6), 0.0), 1.0)
                k0 = K0 if i == 0 else K1; e_ = 0.5 - 0.5 * math.cos(math.pi * s)
                return view[i][0], view[i][1] * (k0 + (1.0 - k0) * e_)
        return view[-1][0], view[-1][1]

    r = [raw(f / fps) for f in range(frames)]
    tg = np.array([x[0] for x in r]); dd = np.array([x[1] for x in r])
    sig = SIGMA * fps; kx = np.arange(-int(3 * sig), int(3 * sig) + 1); kern = np.exp(-0.5 * (kx / sig) ** 2); kern /= kern.sum()
    sm = lambda a: np.convolve(np.pad(a, len(kx) // 2, mode="edge"), kern, mode="valid")
    tg = np.column_stack([sm(tg[:, k]) for k in range(3)]); dd = sm(dd)
    az = np.array([AZ0 + ORBIT * ((f / fps) / max(T, 1e-6) - 0.5) for f in range(frames)])
    return tg, dd, az, view


def slivers(items, tl, path, el, lens, fps=30, step=3):
    """times when a revealed item shows only a thin sliver at the frame edge (camera moves excluded)"""
    tg, dd, az = path[:3]; n = len(items); out = {}
    for f in range(0, len(dd), step):
        t = f / fps
        if any(tl["t_arr"][j] is not None and tl["t_arr"][j] <= t < tl["t_rev"][j] for j in range(n)): continue
        cam = tg[f] + dd[f] * cam_dir(el, az[f])
        for i, it in enumerate(items):
            if t < tl["t_rev"][i] + 0.5 * REV: continue
            p = project(np.column_stack([corners(it), np.full(4, lift(it))]), cam, tg[f], lens)
            if (p[:, 2] <= 0).any(): continue
            x0, x1, y0, y1 = p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()
            fx = (min(x1, 1) - max(x0, -1)) / max(x1 - x0, 1e-9); fy = (min(y1, 1) - max(y0, -1)) / max(y1 - y0, 1e-9)
            if (0 < fx < SLIVER and fy > 0) or (0 < fy < SLIVER and fx > 0): out.setdefault(it["key"], []).append(round(t, 2))
    return out


def plan(ds, T, el, lens, fill, fps=30):
    """layout with the smallest gap of GAPS that leaves no sliver; returns items, smallest gap, gap used, slivers left"""
    tl = timeline(T, len(ds))
    for g in GAPS:
        items, mg = layout(ds, g)
        sl = slivers(items, tl, camera_path(items, tl, T, el, lens, fill, fps), el, lens, fps)
        if not sl: break
    return items, mg, g, sl
