"""Profile, nesting fit and timeline of the 'nest' template (python + numpy only: used by the template and the preflight).
All lengths are relative to the height of the level (every level is the same turned shape, scaled)."""
import math
import numpy as np

# control points (z, r) from the foot to the top, seam height, panel centre height
PRESETS = {
    "doll":    {"pts": [(0, .255), (.015, .285), (.06, .31), (.16, .335), (.28, .345), (.40, .335), (.50, .31), (.58, .285),
                        (.66, .27), (.76, .265), (.86, .24), (.93, .19), (.975, .12), (1, 0)], "seam": .52, "panel": .29},
    "egg":     {"pts": [(0, .16), (.03, .24), (.10, .31), (.22, .355), (.35, .37), (.48, .36), (.62, .325), (.75, .27),
                        (.86, .20), (.94, .12), (.985, .05), (1, 0)], "seam": .44, "panel": .25},
    "capsule": {"pts": [(0, .29), (.02, .315), (.08, .32), (.62, .32), (.75, .31), (.86, .27), (.94, .19), (.985, .09), (1, 0)],
                "seam": .62, "panel": .33},
    "barrel":  {"pts": [(0, .27), (.02, .29), (.25, .322), (.5, .335), (.75, .322), (.98, .29), (1, .27)], "seam": .5, "panel": .27},
}
TW, CL, LIP, GAP = 0.022, 0.010, 0.035, 0.004       # wall, clearance between levels, lip height, seam gap
REST = TW + 0.004                                    # an inner level rests just above the cavity floor (no touching faces)
BANDS_BASE = [(0.030, 0.042)]                        # gold bands (relative height); seam bands added from the seam
D_OPEN, H_FIRST, H_MID, H_LAST = 2.7, 1.4, 1.1, 1.8  # seconds: one opening, first hold, hold between, last hold
# phases of one opening (seconds from its start)
PH = {"twist": (0.0, 0.5), "clear": (0.5, 0.85), "exit": (0.85, 1.35), "rise": (0.85, 1.55), "away": (1.5, 2.25),
      "down": (1.8, 2.6), "lid_hide": 1.45, "base_hide": 2.35}


def _catmull(Q, per=80):
    Q = np.vstack([2 * Q[0] - Q[1], Q, 2 * Q[-1] - Q[-2]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0; t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5; t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5; t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5
        ts = np.linspace(t1, t2, per, endpoint=False)[:, None]
        a1 = (t1 - ts) / (t1 - t0) * p0 + (ts - t0) / (t1 - t0) * p1
        a2 = (t2 - ts) / (t2 - t1) * p1 + (ts - t1) / (t2 - t1) * p2
        a3 = (t3 - ts) / (t3 - t2) * p2 + (ts - t2) / (t3 - t2) * p3
        b1 = (t2 - ts) / (t2 - t0) * a1 + (ts - t0) / (t2 - t0) * a2
        b2 = (t3 - ts) / (t3 - t1) * a2 + (ts - t1) / (t3 - t1) * a3
        out.append((t2 - ts) / (t2 - t1) * b1 + (ts - t1) / (t2 - t1) * b2)
    out.append(Q[-2][None])
    return np.vstack(out)


def _resample(c, n):
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
    s = np.linspace(0, L[-1], n)
    return np.column_stack([np.interp(s, L, c[:, 0]), np.interp(s, L, c[:, 1])])


def profile(spec):
    """spec: preset name or {"profile": [[z, r], ...], "seam": z, "panel": z}; returns the outer profile + its inner wall"""
    if isinstance(spec, str):
        pr = PRESETS[spec]; pts, seam, pz = pr["pts"], pr["seam"], pr["panel"]
    else:
        pts, seam, pz = spec["profile"], spec["seam"], spec.get("panel", spec["seam"] * 0.55)
    zr = np.asarray(pts, float)
    c = _catmull(np.column_stack([zr[:, 1], zr[:, 0]]))          # (r, z)
    c[:, 0] = np.maximum(c[:, 0], 0); c[:, 1] = np.clip(np.maximum.accumulate(c[:, 1]), 0, 1)
    c = _resample(c, 160)
    flat_top = c[-1, 0] > 1e-4
    # inner wall: the outer curve moved inwards along its normal by the wall thickness
    tg = np.gradient(c, axis=0); tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)
    off = c + TW * np.column_stack([-tg[:, 1], tg[:, 0]])
    off[:, 1] = np.maximum.accumulate(off[:, 1])
    top = 1 - TW
    keep = (off[:, 1] >= TW) & (off[:, 1] <= top) & (off[:, 0] > 0)
    inner = off[keep]
    if inner[0, 1] > TW + 1e-6:                                    # start the wall exactly on the cavity floor
        inner = np.vstack([[np.interp(TW, off[:, 1], off[:, 0]), TW], inner])
    if flat_top or inner[-1, 0] > 1e-3:                            # close at the ceiling (flat) or at the axis (dome)
        zc = min(top, inner[-1, 1]) if not flat_top else top
        inner = np.vstack([inner, [[np.interp(zc, off[:, 1], off[:, 0]), zc]] if flat_top else [[0.0, inner[-1, 1]]]])
    g = {"outer": c, "inner": inner, "seam": float(seam), "panel_z": float(pz), "flat_top": bool(flat_top)}
    zs = np.linspace(0, 1, 2001)
    g["Rz"] = zs; g["R"] = np.interp(zs, c[:, 1], c[:, 0])
    g["RS"] = float(np.interp(seam, c[:, 1], c[:, 0])); g["Rmax"] = float(c[:, 0].max())
    g["cav_seam"] = float(np.interp(seam, inner[:, 1], inner[:, 0]))
    g["RL"] = (g["RS"] + g["cav_seam"]) / 2                        # lip outer radius (half the wall)
    g["RR"] = g["RL"] + GAP                                       # lid rebate radius
    g["ceil"] = float(inner[-1, 1])
    return g


def R(g, z): return np.interp(z, g["Rz"], g["R"])


def cavity(g, z, part):
    """free radius inside the closed level at height z: base (floor .. lip top) or lid (seam .. ceiling)"""
    inner = g["inner"]; zs = g["seam"]
    r = np.interp(z, inner[:, 1], inner[:, 0], left=0.0, right=0.0)
    if part == "base":
        r = np.where(z > zs, g["cav_seam"], r)                   # inside the lip
        return np.where((z < TW) | (z > zs + LIP), np.inf, r)
    r = np.where(z < zs + LIP + GAP, g["RR"], r)                 # the rebate that takes the lip
    return np.where(z < zs, np.inf, r)


def fit(g, k):
    """can a level scaled by k rest inside, be lifted out of the base and have the lid lifted off it?"""
    zi = np.linspace(0, 1, 401); ri = k * R(g, zi); h = REST + k * zi
    if h[-1] > g["ceil"] - CL: return False
    full = np.minimum(cavity(g, h, "base"), cavity(g, h, "lid"))
    if np.any(ri + CL > full): return False
    grid = np.linspace(0, 1, 1601)
    cb = cavity(g, grid, "base"); cl = cavity(g, grid, "lid")
    suf = np.minimum.accumulate(cb[::-1])[::-1]                     # min of the base opening above each height
    pre = np.minimum.accumulate(np.where(grid >= g["seam"], cl, np.inf))   # min of the lid opening below each height
    ib = np.clip(np.searchsorted(grid, h), 0, len(grid) - 1)
    if np.any(ri + CL > suf[ib]): return False
    above = h >= g["seam"]
    if np.any((ri + CL > pre[ib]) & above): return False
    return True


def solve_k(g):
    for k in np.arange(0.92, 0.449, -0.005):
        if fit(g, float(k)): return round(float(k), 3)
    return None


def timeline(seconds, nl):
    no = nl - 1
    need = H_FIRST + no * D_OPEN + max(no - 1, 0) * H_MID + H_LAST
    extra = max(0.0, seconds - need)
    if no > 1: hf, hm, hl = H_FIRST + 0.3 * extra, H_MID + 0.4 * extra / (no - 1), H_LAST + 0.3 * extra
    else: hf, hm, hl = H_FIRST + 0.5 * extra, H_MID, H_LAST + 0.5 * extra
    t_open = [hf + i * (D_OPEN + hm) for i in range(no)]
    settle = [0.0] + [t + D_OPEN for t in t_open]
    return {"need": round(need, 2), "t_open": t_open, "settle": settle, "end_motion": settle[-1], "holds": [hf, hm, hl]}


def panel(g, aspect):
    """panel centre height + arc width and height (relative units) for a picture of this aspect ratio"""
    zs = g["seam"]
    lo, hi = 0.075, zs - 0.045
    zc = min(max(g["panel_z"], lo + 0.06), hi - 0.06)
    rc = float(R(g, zc))
    hmax = min(0.30, 2 * min(zc - lo, hi - zc))
    hp = min(hmax, 1.25 * rc / aspect)
    return {"zc": zc, "rc": rc, "w": hp * aspect, "h": hp}


def ease(x): x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def ease_in(x): x = min(max(x, 0.0), 1.0); return x * x


def ph(t, ab, f=ease): a, b = ab; return f((t - a) / (b - a))


# ------------------------------------------------------------------ turned parts (cross-section runs -> revolved mesh)
def _dedupe(p, eps=1e-5):
    p = np.asarray(p, float); keep = [0]
    for i in range(1, len(p)):
        if np.linalg.norm(p[i] - p[keep[-1]]) > eps: keep.append(i)
    return p[keep]


def runs(g, part):
    """smooth runs of the cross-section (r, z), counter-clockwise around the solid, with material 0 lacquer / 1 wood.
    part: base | lid | solid (the innermost level)"""
    zs, RS, RL, RR, cs = g["seam"], g["RS"], g["RL"], g["RR"], g["cav_seam"]
    out, inn = g["outer"], g["inner"]; r0 = out[0, 0]
    zr = zs + LIP + 2 * GAP                                        # rebate ceiling of the lid
    top_runs = [] if not g["flat_top"] else [(np.array([[out[-1, 0], 1.0], [0.0, 1.0]]), 0)]
    if part == "solid":
        return [(np.array([[0.0, 0.0], [r0, 0.0]]), 1), (_dedupe(out), 0)] + top_runs
    if part == "base":
        ob = np.vstack([out[out[:, 1] < zs], [[RS, zs]]])
        ib = inn[inn[:, 1] < zs][::-1]
        wall = _dedupe(np.vstack([[[cs, zs + LIP], [cs, zs]], ib]))
        return [(np.array([[0.0, 0.0], [r0, 0.0]]), 1), (_dedupe(ob), 0), (np.array([[RS, zs], [RL, zs]]), 1),
                (np.array([[RL, zs], [RL, zs + LIP]]), 1), (np.array([[RL, zs + LIP], [cs, zs + LIP]]), 1),
                (wall, 1), (np.array([[wall[-1, 0], wall[-1, 1]], [0.0, wall[-1, 1]]]), 1)]
    zb = zs + GAP
    ol = np.vstack([[[float(np.interp(zb, out[:, 1], out[:, 0])), zb]], out[out[:, 1] > zb]])
    il = inn[inn[:, 1] > zr][::-1]                                 # ceiling (axis) down to the rebate ceiling
    rc_ = float(np.interp(zr, inn[:, 1], inn[:, 0]))
    cav = _dedupe(np.vstack([il, [[rc_, zr]]]))
    res = [(np.array([[RR, zb], [ol[0, 0], zb]]), 1), (_dedupe(ol), 0)] + top_runs
    if g["flat_top"]: res.append((np.array([[0.0, g["ceil"]], [cav[0, 0], g["ceil"]]]), 1))
    res += [(cav, 1), (np.array([[rc_, zr], [RR, zr]]), 1), (np.array([[RR, zr], [RR, zb]]), 1)]
    return res


def revolve(rs, S=128):
    """revolve the runs around z (angle 0 = front = -y). returns verts (N,3), quads (Q,4), tris (T,3), quad/tri materials"""
    th = (np.arange(S) + 0.0) * 2 * np.pi / S; sn, cs = np.sin(th), -np.cos(th)
    V, Q, Tr, MQ, MT = [], [], [], [], []
    nv = 0
    for pts, mi in rs:
        pts = np.asarray(pts, float); ids = []
        for r, z in pts:
            if r < 1e-6:
                V.append(np.array([[0.0, 0.0, z]])); ids.append(np.full(S, nv)); nv += 1
            else:
                V.append(np.column_stack([r * sn, r * cs, np.full(S, z)])); ids.append(nv + np.arange(S)); nv += S
        q_run, t_run = [], []
        for a in range(len(pts) - 1):
            A, B = ids[a], ids[a + 1]; A1, B1 = np.roll(A, -1), np.roll(B, -1)
            pa, pb = pts[a][0] < 1e-6, pts[a + 1][0] < 1e-6
            if pa and pb: continue
            if pa: t_run.append(np.column_stack([A, B, B1]))
            elif pb: t_run.append(np.column_stack([A, B, A1]))
            else: q_run.append(np.column_stack([A, B, B1, A1]))
        # orientation: the face normal must point to the right of the walking direction (outside the solid)
        VV = np.vstack(V)
        d = pts[1] - pts[0]; nr, nz = d[1], -d[0]
        f = (q_run or t_run)[0][0]
        p = VV[f]; nrm = np.cross(p[1] - p[0], p[2] - p[0]) if np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])) > 1e-12 else np.cross(p[2] - p[1], p[-1] - p[1])
        m = (2 * np.pi / S) / 2 if not (pts[0][0] < 1e-6 and len(f) == 3) else (2 * np.pi / S) / 2
        exp = np.array([nr * np.sin(m), -nr * np.cos(m), nz])
        flip = float(np.dot(nrm, exp)) < 0
        for x in q_run:
            Q.append(x[:, ::-1] if flip else x); MQ.append(np.full(len(x), mi))
        for x in t_run:
            Tr.append(x[:, ::-1] if flip else x); MT.append(np.full(len(x), mi))
    VV = np.vstack(V)
    return (VV, np.vstack(Q) if Q else np.zeros((0, 4), int), np.vstack(Tr) if Tr else np.zeros((0, 3), int),
            np.concatenate(MQ) if MQ else np.zeros(0, int), np.concatenate(MT) if MT else np.zeros(0, int))
