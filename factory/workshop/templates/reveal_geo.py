"""Workshop template 'reveal' - plain geometry and timing (no Blender): item sizes, the layout on the desk, the timeline
and the camera framing.  Units: the long side of an item of size 1 is 1."""
import math
import numpy as np

BORDER = 0.05                      # white margin of a print (share of its long side)
GAP = 0.24                         # free space between two items
TILT = (-2.5, 1.8, -1.2, 2.2)      # turn of each item on the desk (degrees)
SHIFT = (0.0, 0.035, -0.025, 0.03)  # small offsets along the depth of the desk
LEAD, ARR, REV, HOLD = 0.6, 1.2, 1.4, 1.6   # dark start, camera move to the next item, reveal, shortest hold (s)
AZ0, ORBIT = -7.0, 6.0             # camera azimuth at mid-clip and its slow drift over the clip (degrees)


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


def layout(ds):
    """items left to right, each turned a little, centred on x = 0; returns the items + the smallest gap between them"""
    its, x = [], 0.0
    for i, d in enumerate(ds):
        it = dict(d, rot=TILT[i % len(TILT)], y=SHIFT[i % len(SHIFT)] * max(d["w"], d["h"]), x=0.0)
        c = corners(it); half_l, half_r = -c[:, 0].min(), c[:, 0].max()
        if its:
            pc = corners(its[-1]); x = pc[:, 0].max() + GAP + half_l
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
