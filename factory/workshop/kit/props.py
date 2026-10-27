"""Builders of the kit's cast members that have parts or move inside themselves (Blender 4.5): book (its cover opens),
box (its lid opens), globe (the Earth turns on its tilted axis), cut-out figure, imported model (GLB), cloth (a flag that
waves on a pole, a banner, a cloth or sheet that unfolds), a free-standing wall, map tiles and terrain blocks (geometry from
the scene's data), pieces of a member that splits or assembles, writing that appears, routes drawn over a map.
Every builder appends its objects and materials to the stage and returns rigs: functions called once the motion of the
cast is known (plan.channels), which key the moving parts."""
import json, math, os
import bpy, bmesh
import numpy as np
from mathutils import Vector
import common as C
import mats as M
import plan as P
import stage as ST

TILT = 23.44                  # the Earth's axis on a desk globe


def data_json(st, name):
    p = os.path.join(st.data or "", name)
    return json.load(open(p)) if st.data and os.path.exists(p) else {}


def store_file(st, n):
    """the member's file in the scene data: an order-store picture or GLB, the cut-out of a figure, a model of the objects stage"""
    k, v = st.src(n)
    if k not in ("store", "obj"): return None
    key = "obj:" + v if k == "obj" else ("cut:" + v if st.cast[n]["is"] == "cutout" else v)
    it = st.items.get(key)
    return os.path.join(st.data, it["file"]) if it else None


def empty(name, parent, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None); ST.link(e, parent); e.location = loc
    return e


def rest_attr(ob, co):
    at = ob.data.attributes.new("rest", "FLOAT_VECTOR", "POINT"); at.data.foreach_set("vector", np.asarray(co, np.float32).ravel())


def grid(nx, ny):
    idx = np.arange((nx + 1) * (ny + 1)).reshape(ny + 1, nx + 1)
    return np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)


def bend(s, h, th, r):
    """a sheet folding over a round crease: s = distance from the crease on the folding side (>= 0), h = height of the
    layer, th = fold angle (0 flat, pi folded over), r = crease radius -> (along, up) of the point"""
    s = np.asarray(s, float); h = np.asarray(h, float); rr = np.maximum(r - h, 1e-6)
    arc = s <= r * th
    phi = np.where(arc, s / r, th)
    a = np.where(arc, -rr * np.sin(phi), -rr * np.sin(th) - (s - r * th) * np.cos(th))
    z = np.where(arc, r - rr * np.cos(phi), r - rr * np.cos(th) + (s - r * th) * np.sin(th))
    return a, z


def folded(X, Y, f, r):
    """rest coordinates of a flat sheet (centred) folded in four: f = 1 folded, 0 flat (first the second fold opens)"""
    th1 = np.pi * min(1.0, 2.0 * f); th2 = np.pi * max(0.0, 2.0 * f - 1.0)
    Z = np.zeros_like(X); Xo, Yo = X.copy(), Y.copy()
    m = X < 0
    if th1 > 1e-6:
        a, z = bend(-X[m], 0.0, th1, r); Xo[m] = -a; Z[m] = z               # the left half over the right half
    m2 = Yo < 0
    if th2 > 1e-6:
        a, z = bend(-Yo[m2], Z[m2], th2, 3 * r); Yo[m2] = -a; Z[m2] = z     # the lower half over the upper half
    return Xo, Yo, Z


def flag_shape(U, V, t, wind, L, H, wet=False):
    """a flag on its pole (hoist at x = 0, top at z = 0): travelling waves that grow toward the fly end, soft folds (no
    sharp crease squeezes the emblem), no stretching along a row; light air lets the fly end droop"""
    w = float(np.clip(wind, 0.05, 1.0)) * (0.6 if wet else 1.0)
    amp = L * (0.03 + 0.07 * w) * U ** 1.25
    k = 2 * np.pi * (1.0 + 0.5 * w) / L; c = (0.7 + 2.0 * w) * L
    ph = k * (U * L - c * t)
    Yd = amp * (np.sin(ph + 0.9 * V) + 0.3 * np.sin(1.9 * ph + 2.1 * V + 1.3))
    ds = L / (U.shape[1] - 1)
    dy = np.diff(Yd, axis=1); dx = np.sqrt(np.maximum(ds * ds - dy * dy, (0.2 * ds) ** 2))
    X = np.concatenate([np.zeros((U.shape[0], 1)), np.cumsum(dx, axis=1)], axis=1)
    droop = (1.0 - w) ** 2 * (0.22 if not wet else 0.32) * H
    Z = (V - 1.0) * H - droop * U ** 2
    return X, Yd, Z


# ------------------------------------------------------------------ book
def book(st, n, c, m, e):
    mat = c.get("material", "leather")
    cov = M.solid(f"{n}_cover", mat if mat in ("leather", "velvet", "cloth", "silk", "felt", "wood", "walnut", "oak", "bronze", "brass", "gold",
                                               "silver", "iron", "painted") else "leather",
                  color=(0.30, 0.09, 0.06) if mat in ("cloth", "silk", "felt") else None)
    pages = M.solid(f"{n}_pages", "paper")
    gold = M.solid(f"{n}_tooling", "gold")
    pw, ph, ov, t, pg = m["pw"], m["ph"], m["ov"], m["t"], m["pg"]
    cw, cd = pw + ov, ph + 2 * ov
    objs = [(ST.box(f"{n}_back", cw, cd, t, e, cov, x=cw / 2, bevel=0.3 * t), "o"),
            (ST.box(f"{n}_rpages", pw, ph, pg / 2, e, pages, z0=t, x=pw / 2 + 0.004 * ph), "o"),
            (ST.cylinder(f"{n}_spine", t + pg / 2, cd, e, cov, seg=24), "o")]
    sp = objs[-1][0]; sp.rotation_euler = (math.pi / 2, 0, 0); sp.location = (0, cd / 2, t + pg / 2); sp.scale = (0.35, 1.0, 1.0)
    pv = empty(f"{n}_pivot", e, (0, 0, t + pg / 2))
    objs += [(ST.box(f"{n}_lpages", pw, ph, pg / 2, pv, pages, x=pw / 2 + 0.004 * ph), "o"),
             (ST.box(f"{n}_front", cw, cd, t, pv, cov, z0=pg / 2, x=cw / 2, bevel=0.3 * t), "o")]
    b, wd, hh = 0.07 * ph, 0.006 * ph, 0.0012 * ph                  # gold tooling: a frame pressed into the front cover
    for i, (x, y, w, d) in enumerate(((cw / 2, -(cd / 2 - b), cw - 2 * b + wd, wd), (cw / 2, cd / 2 - b, cw - 2 * b + wd, wd),
                                      (b, 0, wd, cd - 2 * b), (cw - b, 0, wd, cd - 2 * b))):
        objs.append((ST.box(f"{n}_tool{i}", w, d, hh, pv, gold, z0=pg / 2 + t, x=x, y=y), "o"))
    mats = [cov, pages, gold]
    path = store_file(st, n)
    zt = t + pg / 2 + 0.0004 * ph
    if path:
        if m["spread"]:                                             # a wide picture over both pages of the open book
            pm, nd = M.picture(n, path, 2 * pw, ph, m["iw"], m["ih"], kind="paper")
            q = ST.quad(f"{n}_pr", pw, ph, 0.0, e, pm, cx=pw / 2 + 0.004 * ph); q.location.z = zt
            pm2, nd2 = M.picture(f"{n}_l", path, 2 * pw, ph, m["iw"], m["ih"], kind="paper")
            ql = ST.quad(f"{n}_pl", pw, ph, 0.0, pv, pm2, cx=-(pw / 2 + 0.004 * ph)); ql.rotation_euler = (0, math.pi, 0)
            ql.location.z = -0.0004 * ph
            st.pics += [{"member": n, "obj": q, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0},
                        {"member": n, "obj": ql, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0}]
            objs += [(q, "i"), (ql, "i")]; mats += [pm, pm2]; st.nodes.setdefault(n, []).extend([nd, nd2])
        else:                                                       # a picture on the right page, a blank page on the left
            ox = -(pw / 2 + 0.004 * ph)
            pm, nd = M.picture(n, path, pw, ph, m["iw"], m["ih"], kind="paper", ox=ox)
            q = ST.quad(f"{n}_pr", pw, ph, 0.0, e, pm, cx=-ox); q.location.z = zt
            bl, bnd = M.paper(f"{n}_left", "paper", pw, ph)
            ql = ST.quad(f"{n}_pl", pw, ph, 0.0, pv, bl, cx=ox); ql.rotation_euler = (0, math.pi, 0); ql.location.z = -0.0004 * ph
            st.pics.append({"member": n, "obj": q, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": ox, "oy": 0.0})
            objs += [(q, "i"), (ql, "o")]; mats += [pm, bl]; st.nodes.setdefault(n, []).extend([nd, bnd])
    st.objs[n] = objs; st.mats[n] = mats

    def rig(ch, ex):
        deg = ex["opens"].get(n, P.OPEN_DEG["book"])
        ST.keys(pv, "rotation_euler", np.stack([np.zeros(st.n), -np.radians(deg) * ch["open"], np.zeros(st.n)], -1))
    return [rig]


# ------------------------------------------------------------------ box
def chest(st, n, c, m, e):
    mat = c.get("material", "walnut")
    bm_ = M.solid(n, mat); lin_ = M.solid(f"{n}_lining", "velvet"); fit = M.solid(f"{n}_brass", "brass")
    w, d, h = m["w"], m["d"], m["h"]; wt = 0.06 * d; fl = m["floor"]; lh = 0.17 * h; bh = h - lh
    objs = [(ST.box(f"{n}_bottom", w, d, fl, e, bm_, bevel=0.2 * wt), "o"),
            (ST.box(f"{n}_wf", w, wt, bh, e, bm_, y=-(d - wt) / 2, bevel=0.15 * wt), "o"),
            (ST.box(f"{n}_wb", w, wt, bh, e, bm_, y=(d - wt) / 2, bevel=0.15 * wt), "o"),
            (ST.box(f"{n}_wl", wt, d - 2 * wt, bh, e, bm_, x=-(w - wt) / 2), "o"),
            (ST.box(f"{n}_wr", wt, d - 2 * wt, bh, e, bm_, x=(w - wt) / 2), "o"),
            (ST.quad(f"{n}_lin", w - 2 * wt, d - 2 * wt, fl + 0.0005, e, lin_), "o")]
    pv = empty(f"{n}_hinge", e, (0, d / 2, bh))
    lid = ST.box(f"{n}_lid", 1.02 * w, 1.02 * d, lh, pv, bm_, y=-d / 2, bevel=0.25 * wt)
    objs += [(lid, "o"), (ST.box(f"{n}_clasp", 0.08 * w, 0.012 * d, 0.22 * h, pv, fit, y=-1.02 * d, z0=-0.12 * h, bevel=0.002), "o")]
    mats = [bm_, lin_, fit]
    path = store_file(st, n)
    if path:                                                        # a picture set into the lid
        pm, nd = M.picture(n, path, m["iw"], m["ih"], m["iw"], m["ih"], kind="print", oy=d / 2)
        q = ST.quad(f"{n}_label", m["iw"], m["ih"], lh + 0.0006 * w, pv, pm, cy=-d / 2)
        st.pics.append({"member": n, "obj": q, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": d / 2})
        objs.append((q, "i")); mats.append(pm); st.nodes.setdefault(n, []).append(nd)
    st.objs[n] = objs; st.mats[n] = mats

    def rig(ch, ex):
        deg = ex["opens"].get(n, P.OPEN_DEG["box"])
        ST.keys(pv, "rotation_euler", np.stack([-np.radians(deg) * ch["open"], np.zeros(st.n), np.zeros(st.n)], -1))
    return [rig]


# ------------------------------------------------------------------ globe
def globe(st, n, c, m, e):
    L = m["L"]; r = L / 2
    wood = M.solid(f"{n}_base", c.get("material", "walnut")); brass = M.solid(f"{n}_brass", "brass")
    path = os.path.join(st.data, "earth.jpg") if st.data else ""
    if not os.path.exists(path): st.errors.append(f"cast {n}: the Earth picture of the globe is missing from the scene data"); return []
    ea = M.earth(n, path)
    cz = 1.42 * L - r - 0.03 * L
    objs = [(ST.cylinder(f"{n}_foot", 0.3 * L, 0.05 * L, e, wood, seg=64, bevel=0.01 * L), "o"),
            (ST.cylinder(f"{n}_stem", 0.022 * L, cz - r * 1.07, e, brass, z0=0.05 * L, seg=24), "o")]
    ax = empty(f"{n}_axis", e, (0, 0, cz)); ax.rotation_euler = (0, math.radians(TILT), 0)
    cu = bpy.data.curves.new(f"{n}_meridian", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.012 * r; cu.bevel_resolution = 3
    spl = cu.splines.new("POLY"); k = 96; spl.points.add(k - 1)
    for i in range(k):
        a = 2 * math.pi * i / k; spl.points[i].co = (1.07 * r * math.sin(a), 0.0, 1.07 * r * math.cos(a), 1.0)
    spl.use_cyclic_u = True
    mo = bpy.data.objects.new(f"{n}_meridian", cu); ST.link(mo, ax); cu.materials.append(brass)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=64, radius=r)
    sp = ST.bm_object(f"{n}_earth", bm, ax, [ea]); sp.data.polygons.foreach_set("use_smooth", [True] * len(sp.data.polygons))
    objs += [(mo, "o"), (sp, "o")]
    at = c.get("at")
    spin0 = math.radians(-90.0 - float(at[0])) if at else math.radians(-90.0 - 20.0)
    st.objs[n] = objs; st.mats[n] = [wood, brass, ea]
    st.globes[n] = {"sphere": sp, "axis": ax, "r": r, "spin0": spin0}

    def rig(ch, ex):                                                # "turn" spins the Earth, not the stand
        ST.keys(sp, "rotation_euler", np.stack([np.zeros(st.n), np.zeros(st.n), spin0 + ch["rz"]], -1))
    return [rig]


# ------------------------------------------------------------------ cut-out figure
def cutout(st, n, c, m, e):
    path = store_file(st, n)
    if not path: st.errors.append(f"cast {n}: a cut-out needs a picture from the order store"); return []
    w, h = m["w"], m["h"]; hb = 0.025 * h
    pm, nd = M.picture(n, path, w, h, w, h, kind="print", alpha=True, twosided=(0.55, 0.53, 0.5))
    q = ST.quad(f"{n}_card", w, h, 0.0, e, pm); q.rotation_euler = (math.pi / 2, 0, 0); q.location = (0, 0, hb + h / 2)
    wood = M.solid(f"{n}_foot", "walnut")
    foot = ST.box(f"{n}_foot", 0.6 * w, max(m["d"], 0.05 * h), hb, e, wood, bevel=0.2 * hb)
    st.pics.append({"member": n, "obj": q, "iw": w, "ih": h, "path": path, "ox": 0.0, "oy": 0.0, "alpha": True})
    st.objs[n] = [(q, "i"), (foot, "o")]; st.mats[n] = [pm, wood]; st.nodes.setdefault(n, []).append(nd)
    return []


# ------------------------------------------------------------------ imported model
def model_import(st, n, L):
    """imports the member's GLB, scaled so its longest side is L, standing on z = 0, centred; returns (holder, size)"""
    path = store_file(st, n)
    if not path or not path.lower().endswith(".glb"): st.errors.append(f"cast {n}: a model needs a GLB file"); return None, None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes: st.errors.append(f"cast {n}: the GLB has no mesh"); return None, None
    bpy.context.view_layer.update()
    pts = np.array([list(o.matrix_world @ Vector(cn)) for o in meshes for cn in o.bound_box])
    lo, hi = pts.min(0), pts.max(0); size = hi - lo; s = L / max(float(size.max()), 1e-6)
    holder = bpy.data.objects.new(f"{n}_model", None); ST.link(holder)
    for o in new:
        if o.parent is None or o.parent not in new:
            mw = o.matrix_world.copy(); o.parent = holder; o.matrix_world = mw
    holder.scale = (s, s, s); holder.location = (-(lo[0] + hi[0]) / 2 * s, -(lo[1] + hi[1]) / 2 * s, -lo[2] * s)
    st.model_parts[n] = meshes
    return holder, size * s


def model(st, n, c, m, e):
    holder = st.models.get(n)
    if holder is None: return []
    holder.parent = e
    mats = []
    for o in st.model_parts[n]:
        for ms in o.material_slots:
            if ms.material and ms.material not in mats: M.add_presence(ms.material); mats.append(ms.material)
    st.objs[n] = [(o, "o") for o in st.model_parts[n]]; st.mats[n] = mats
    return []


# ------------------------------------------------------------------ cloth
def cloth(st, n, c, m, e):
    L, H = m["fly"], m["hoist"]; flagged = bool(m.get("flag"))
    nx = 72; ny = max(12, int(round(nx * H / L)))
    U, V = np.meshgrid(np.linspace(0, 1, nx + 1), np.linspace(0, 1, ny + 1))
    X, Y = (U - 0.5) * L, (V - 0.5) * H
    rest = np.stack([X, Y, np.zeros_like(X)], -1).reshape(-1, 3)
    if flagged: co = np.stack([U * L, np.zeros_like(U), (V - 1.0) * H], -1).reshape(-1, 3)
    else: co = np.stack([X, Y, np.full_like(X, 0.002 * L)], -1).reshape(-1, 3)
    path = store_file(st, n)
    if path: mt, nd = M.picture(n, path, L, H, L, H, kind="print", rest=True); st.nodes.setdefault(n, []).append(nd)
    else: mt = M.solid(n, c.get("material", "cloth")); nd = None
    ob = C.mesh_object(n, co, grid(nx, ny)); ob.parent = e; ob.data.materials.append(mt); C.smooth_shade(ob)
    rest_attr(ob, rest)
    if path: st.pics.append({"member": n, "obj": ob, "iw": L, "ih": H, "path": path, "ox": 0.0, "oy": 0.0, "deforms": True})
    st.objs[n] = [(ob, "i" if path else "o")]; st.mats[n] = [mt]
    wet = st.S.get("light", {}).get("weather") == "rain"

    def rig(ch, ex):
        moving = np.ptp(ch["wind"]) > 1e-6 or np.ptp(ch["fold"]) > 1e-6 or flagged
        if not moving and ch["fold"][0] < 1e-6: return
        fr = np.zeros((st.n, len(co), 3), np.float32); t = np.arange(st.n) / P.FPS
        for i in range(st.n):
            if flagged:
                Xf, Yf, Zf = flag_shape(U, V, t[i], ch["wind"][i], L, H, wet)
            else:
                Xf, Yf, Zf = folded(X, Y, float(ch["fold"][i]), 0.012 * L)
                rip = max(0.0, float(ch["wind"][i]) - P.WIND0) * (1.0 - float(ch["fold"][i]))
                Zf = Zf + 0.002 * L + rip * 0.02 * L * np.sin(2 * np.pi * (U * 1.6 - 0.8 * t[i]) + 1.7 * V) * np.sin(np.pi * U)
            fr[i] = np.stack([Xf, Yf, Zf], -1).reshape(-1, 3)
        os.makedirs(os.path.join(st.O.out, "_cache"), exist_ok=True)
        pc = os.path.join(st.O.out, "_cache", f"{n}.pc2"); C.write_pc2(pc, fr); C.use_cache(ob, pc)
    return [rig]


def sheet_folding(st, n, c, m, e):
    """a sheet or print that unfolds or folds: a grid that keeps its picture printed on it (rest coordinates), paper on
    its back, crisp creases"""
    w, d = m["w"], m["d"]; nx = 64; ny = max(16, int(round(nx * d / w)))
    U, V = np.meshgrid(np.linspace(0, 1, nx + 1), np.linspace(0, 1, ny + 1))
    X, Y = (U - 0.5) * w, (V - 0.5) * d
    rest = np.stack([X, Y, np.zeros_like(X)], -1).reshape(-1, 3)
    pk = "parchment" if c.get("material") == "parchment" else "paper"
    path = store_file(st, n)
    if path:
        mt, nd = M.picture(n, path, w, d, m["iw"], m["ih"], kind=pk if m["noun"] == "sheet" else "print", rest=True,
                           twosided=M.PAPER[pk])
        st.pics.append({"member": n, "obj": None, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0, "deforms": True})
    else: mt, nd = M.paper(n, pk, w, d, rest=True)
    ob = C.mesh_object(n, np.stack([X, Y, np.full_like(X, 0.0015 * w)], -1).reshape(-1, 3), grid(nx, ny)); ob.parent = e
    ob.data.materials.append(mt); rest_attr(ob, rest)
    if path: st.pics[-1]["obj"] = ob
    st.objs[n] = [(ob, "i" if path else "o")]; st.mats[n] = [mt]; st.nodes.setdefault(n, []).append(nd)

    def rig(ch, ex):
        fr = np.zeros((st.n, len(rest), 3), np.float32)
        for i in range(st.n):
            Xf, Yf, Zf = folded(X, Y, float(ch["fold"][i]), 0.0035 * w); fr[i] = np.stack([Xf, Yf, Zf + 0.0015 * w], -1).reshape(-1, 3)
        os.makedirs(os.path.join(st.O.out, "_cache"), exist_ok=True)
        pc = os.path.join(st.O.out, "_cache", f"{n}.pc2"); C.write_pc2(pc, fr); C.use_cache(ob, pc)
    return [rig]


# ------------------------------------------------------------------ free-standing wall
def wall(st, n, c, m, e):
    mt = M.solid(n, c.get("material", "plaster"))
    st.objs[n] = [(ST.box(n, m["w"], m["d"], m["h"], e, mt, bevel=0.01 * m["L"]), "o")]; st.mats[n] = [mt]
    return []


# ------------------------------------------------------------------ slabs from polygons (map tiles, torn pieces)
def slab(name, verts, tris, rings, h, parent, top, side, z0=0.0):
    """a polygon (verts (k, 2), triangles, outline rings as vertex index loops) raised to a slab of height h:
    top faces material 0, bottom and walls material 1"""
    V = np.asarray(verts, float); k = len(V); T_ = np.asarray(tris, np.int64).reshape(-1, 3)
    co = np.vstack([np.c_[V, np.full(k, z0 + h)], np.c_[V, np.full(k, z0)]])
    quads = []
    for ring in rings:
        ring = list(ring)
        for a, b in zip(ring, ring[1:] + ring[:1]): quads.append((a, b, b + k, a + k))
    tris_all = np.vstack([T_, T_[:, ::-1] + k])
    ob = C.mesh_object(name, co, np.asarray(quads, np.int64) if quads else None, tris_all, link=True); ob.parent = parent
    ob.data.materials.append(top); ob.data.materials.append(side)
    nq = len(quads); mi = np.r_[np.ones(nq, np.int32), np.zeros(len(T_), np.int32), np.ones(len(T_), np.int32)]
    ob.data.polygons.foreach_set("material_index", mi)
    # winding: top up, bottom down, walls out (Blender recomputes normals from the winding)
    ob.data.polygons.foreach_set("use_smooth", [False] * len(ob.data.polygons))
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    return ob


def outline(name, verts, rings, z, parent, mat, radius):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = radius; cu.bevel_resolution = 2
    V = np.asarray(verts, float)
    for ring in rings:
        sp = cu.splines.new("POLY"); sp.points.add(len(ring) - 1)
        for i, j in enumerate(ring): sp.points[i].co = (V[j, 0], V[j, 1], z, 1.0)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu); ST.link(ob, parent); cu.materials.append(mat)
    return ob


def pieces_motion(st, n, parts, L, gap):
    """offsets of the pieces of a member that splits (split channel 0 -> 1) or assembles (1 -> 0): every piece moves
    away from the middle along the line to its own centre (the farthest by gap x L), with a small arc and turn"""
    cs = np.array([p["c"] for p in parts], float).reshape(-1, 2); mid = cs.mean(0) if len(cs) else np.zeros(2)
    v = cs - mid; r = max(float(np.linalg.norm(v, axis=1).max()) if len(v) else 0.0, 1e-6)
    out = []
    for i, p in enumerate(parts):
        dv = v[i] / r * gap * L if np.linalg.norm(v[i]) > 1e-9 else np.array([P.jitter(f"{n}{i}", "px", 1.0), P.jitter(f"{n}{i}", "py", 1.0)]) * 0.3 * gap * L
        out.append((dv, math.radians(P.jitter(f"{n}{i}", "spin", 7.0))))
    return out


def tiles(st, n, c, m, e):
    D = st.tiles.get(n)
    if not D: st.errors.append(f"cast {n}: its map piece is missing from the scene data"); return []
    S = st.tile_scale
    img = os.path.join(st.data, st.tile_meta["image"]); ex = [v * S for v in st.tile_meta["extent"]]
    iw, ih = ex[2] - ex[0], ex[3] - ex[1]; ecx, ecy = (ex[0] + ex[2]) / 2, (ex[1] + ex[3]) / 2
    h = m["h"]; L = max(m["w"], m["d"])
    scl = lambda pc: {"verts": np.asarray(pc["verts"], float) * S, "tris": pc["tris"], "rings": pc["rings"], "c": np.asarray(pc["c"], float) * S}
    side = M.solid(f"{n}_side", c.get("material", "slate") if c.get("material") not in (None, "painted") else "slate")
    border = M.line(f"{n}_border", (1.0, 0.97, 0.9), 1.0)
    split = n in st.split_members
    parts = [scl(pc) for pc in (D["pieces"] if split and D.get("pieces") else D["parts"])]
    objs, mats, holders = [], [side, border], []
    for i, pc in enumerate(parts):
        hold = empty(f"{n}_p{i}", e)
        top, nd = M.picture(f"{n}_{i}", img, iw, ih, iw, ih, kind="print", ox=D["cx"] * S - ecx, oy=D["cy"] * S - ecy)
        ob = slab(f"{n}_slab{i}", pc["verts"], pc["tris"], pc["rings"], h, hold, top, side)
        ol = outline(f"{n}_ol{i}", pc["verts"], pc["rings"], h + 0.0008 * L, hold, border, 0.0022 * L)
        objs += [(ob, "o"), (ol, "o")]; mats.append(top); st.nodes.setdefault(n, []).append(nd); holders.append(hold)
    st.objs[n] = objs; st.mats[n] = mats
    if not split: return []
    gap = st.extra_split.get(n, {}).get("gap", 0.35)
    mv = pieces_motion(st, n, parts, L, gap)

    def rig(ch, ex_):
        s = ch["split"]
        for hold, (dv, rot) in zip(holders, mv):
            ST.keys(hold, "location", np.stack([dv[0] * s, dv[1] * s, 0.12 * L * 4 * s * (1 - s)], -1))
            ST.keys(hold, "rotation_euler", np.stack([np.zeros(st.n), np.zeros(st.n), rot * s], -1))
    return [rig]


def torn(st, n, c, m, e):
    """a sheet or print that splits into pieces (jagged tears from the scene data) or assembles from them"""
    parts = st.pieces.get(n)
    if not parts: st.errors.append(f"cast {n}: its pieces are missing from the scene data"); return []
    pk = "parchment" if c.get("material") == "parchment" else "paper"
    path = store_file(st, n); w, d = m["w"], m["d"]; th = max(m["h"], 0.0008 * w)
    parts = [{"verts": np.asarray(pc["verts"], float) * [w, d], "tris": pc["tris"], "rings": pc["rings"],
              "c": np.asarray(pc["c"], float) * [w, d]} for pc in parts]
    if path:
        top, nd = M.picture(n, path, w, d, m["iw"], m["ih"], kind=pk if m["noun"] == "sheet" else "print")
        st.pics.append({"member": n, "obj": None, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0, "pieces": True})
    else: top, nd = M.paper(n, pk, w, d)
    back, bnd = M.paper(f"{n}_back", pk, w, d)
    objs, holders = [], []
    for i, pc in enumerate(parts):
        hold = empty(f"{n}_p{i}", e)
        ob = slab(f"{n}_piece{i}", pc["verts"], pc["tris"], pc["rings"], th, hold, top, back)
        objs.append((ob, "i" if path else "o")); holders.append(hold)
    st.objs[n] = objs; st.mats[n] = [top, back]; st.nodes.setdefault(n, []).extend([nd, bnd])
    gap = st.extra_split.get(n, {}).get("gap", 0.35)
    mv = pieces_motion(st, n, parts, max(w, d), gap)

    def rig(ch, ex_):
        s = ch["split"]
        for hold, (dv, rot) in zip(holders, mv):
            ST.keys(hold, "location", np.stack([dv[0] * s, dv[1] * s, 0.05 * max(w, d) * 4 * s * (1 - s)], -1))
            ST.keys(hold, "rotation_euler", np.stack([np.zeros(st.n), np.zeros(st.n), rot * s], -1))
    return [rig]


# ------------------------------------------------------------------ terrain block (a piece of land on the stage)
def terrain_block(st, n, c, m, e):
    D = st.terrains.get(n)
    if not D: st.errors.append(f"cast {n}: its terrain is missing from the scene data"); return []
    Hm = np.load(os.path.join(st.data, D["heights"]))["h"].astype(np.float64)
    ny, nx = Hm.shape; w, d = m["w"], m["d"]
    span_m = D["span_m"]; relief = max(float(Hm.max() - min(Hm.min(), 0.0)), 1.0)
    ve = float(np.clip(0.09 * span_m / relief, 1.0, D.get("ve_max", 12.0)))          # the relief about 9 % of the block
    zs = np.maximum(Hm, D.get("sea_floor", -60.0)) / span_m * w * ve
    z_low = min(float(zs.min()), 0.0); base = 0.03 * w; zs = zs - z_low + base; sea_z = base - z_low
    xs, ys = np.linspace(-w / 2, w / 2, nx), np.linspace(d / 2, -d / 2, ny)
    X, Y = np.meshgrid(xs, ys)
    top = np.stack([X, Y, zs], -1).reshape(-1, 3)
    idx = np.arange(nx * ny).reshape(ny, nx)
    q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
    edge = np.r_[idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]]       # the outline, round the block
    k = len(top); bot = top[edge].copy(); bot[:, 2] = 0.0
    co = np.vstack([top, bot]); kb = len(edge)
    walls = [(int(edge[i]), int(edge[(i + 1) % kb]), k + (i + 1) % kb, k + i) for i in range(kb)]
    gr = M.ground(n, os.path.join(st.data, D["image"]), -w / 2, -d / 2, w / 2, d / 2)
    earth_ = M.solid(f"{n}_earth", "painted", color=(0.24, 0.19, 0.14))
    ob = C.mesh_object(f"{n}_land", co, np.vstack([q, np.asarray(walls, np.int64)])); ob.parent = e
    ob.data.materials.append(gr); ob.data.materials.append(earth_)
    ob.data.polygons.foreach_set("material_index", np.r_[np.zeros(len(q), np.int32), np.ones(kb, np.int32)])
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    C.smooth_shade(ob)
    objs = [(ob, "o")]; mats = [gr, earth_]
    if Hm.min() < 0:                                                # the sea inside the block, flat and glossy
        wm = M.water(n, 60.0 / w); M.add_presence(wm)
        objs.append((ST.box(f"{n}_sea", w * 0.999, d * 0.999, sea_z, e, wm), "o")); mats.append(wm)
    st.objs[n] = objs; st.mats[n] = mats
    st.terrain_z[n] = (xs, ys, zs)
    return []


# ------------------------------------------------------------------ writing
def write(st, wr, i):
    """text written on a member's top surface, line by line, from the left (a script hand; gold on dark surfaces)"""
    n = wr["who"]; m = st.L[n]; e = st.root[n]
    noun = m["noun"]; mat = st.cast[n].get("material", ST.MATERIAL.get(noun, "painted"))
    dark = mat in ("walnut", "wood", "slate", "velvet", "leather", "iron", "bronze") or noun in ("box",)
    W = (m["pw"] if noun == "book" else m["w"]) * 0.8; Dp = m["d"] * 0.8
    words = wr["text"].split(); lines, cur = [], ""
    per = max(8, int(28 * min(1.0, W / max(Dp, 1e-6)) + 6))
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > per: lines.append(cur); cur = wd
        else: cur = (cur + " " + wd).strip()
    if cur: lines.append(cur)
    lines = lines[:8]
    size = min(Dp / (1.6 * max(1, len(lines))), W / (0.42 * max(len(x) for x in lines)))
    z = m["h"] + 0.0008 * max(m["w"], m["d"])
    cx = m.get("cx", 0.0) if noun == "book" else 0.0
    objs, keys = [], []
    for j, ln in enumerate(lines):
        cu = bpy.data.curves.new(f"{n}_w{i}_{j}", "FONT"); cu.body = ln
        try: cu.font = bpy.data.fonts.load(os.path.join(ST.FONTS, "GreatVibes-Regular.ttf"), check_existing=True)
        except Exception as ex: print("font:", ex, flush=True)
        cu.size = size; cu.align_x = "CENTER"; cu.align_y = "CENTER"; cu.extrude = 0.0
        ob = bpy.data.objects.new(f"{n}_w{i}_{j}", cu); ST.link(ob, e)
        ob.location = (cx, (len(lines) / 2 - j - 0.5) * 1.5 * size, z)
        lo, hi = ST.local_size([ob])
        mt, rv = M.ink(f"{n}_{i}_{j}", float(lo[0]) - ob.location.x, float(hi[0]) - ob.location.x, gold=dark)
        cu.materials.append(mt); objs.append(ob); keys.append(rv)
        st.mats.setdefault(n, []).append(mt)
    nl = len(lines); t = np.arange(st.n) / P.FPS
    for j, rv in enumerate(keys):
        a = wr["t0"] + wr["dur"] * j / nl; b = wr["t0"] + wr["dur"] * (j + 1) / nl
        ST.keys(rv.outputs[0], "default_value", np.clip((t - a) / max(b - a, 1e-3), 0, 1))
    st.objs[n] += [(o, "o") for o in objs]


# ------------------------------------------------------------------ routes
GLOW = {"warm": (1.0, 0.72, 0.40), "gold": (1.0, 0.80, 0.35), "red": (0.95, 0.18, 0.12), "blue": (0.35, 0.62, 1.0),
        "white": (1.0, 0.98, 0.94)}


def route(st, r, pts, parent, radius):
    """a line drawn along pts (k, 3) in the parent's frame over r["dur"] from r["t0"], a bright head at its tip"""
    col = GLOW.get(r["color"], GLOW["red"])
    mt = M.line(f"route{r['i']}", col, 1.0); hm = M.line(f"route{r['i']}_head", tuple(min(1.0, 0.4 + x) for x in col), 1.0)
    cu = bpy.data.curves.new(f"route{r['i']}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = radius; cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (float(p[0]), float(p[1]), float(p[2]), 1.0)
    try: cu.bevel_factor_mapping_end = "SPLINE"
    except Exception: pass
    ob = bpy.data.objects.new(f"route{r['i']}", cu); ST.link(ob, parent); cu.materials.append(mt)
    head = ST.sphere(f"route{r['i']}_head", 2.2 * radius, parent, hm)
    t = np.arange(st.n) / P.FPS; prog = P.smooth((t - r["t0"]) / max(r["dur"], 1e-3))
    ST.keys(cu, "bevel_factor_end", np.maximum(prog, 1e-4))
    P_ = np.asarray(pts, float); seg = np.linalg.norm(np.diff(P_, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]
    sv = prog * s[-1]; hp = np.stack([np.interp(sv, s, P_[:, k]) for k in range(3)], -1)
    ST.keys(head, "location", hp)
    ST.keys(head, "scale", np.repeat(np.where((prog > 1e-3) & (prog < 0.999), 1.0, 1e-3)[:, None], 3, 1))
    st.route_objs.append((ob, head, P_, prog, hp) if parent is None else (ob, head))
    return ob


SCREEN_LINE = 0.0032          # a route on the ground of a region: about 6 px wide in a 1920 px frame, near or far


def route_widths(st):
    """routes drawn on the ground of a terrain or sea place keep a steady width on screen (a fixed width in km is a band
    near the lens and a hair far off): each point's radius follows its distance to the camera from the moment the line
    reaches it, the bright head follows the camera every frame"""
    recs = [r for r in st.route_objs if len(r) == 5]
    if not recs: return
    cam = np.array([P.cam_pos(st.plan, fi) for fi in range(st.n)])
    k = 0.5 * SCREEN_LINE * 2 * math.atan(P.SENSOR / 2 / P.LENS)     # radius per unit of distance to the camera
    for ob, head, P_, prog, hp in recs:
        cu = ob.data; base = max(float(cu.bevel_depth), 1e-9)
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))]; frac = s / max(s[-1], 1e-9)
        sp = cu.splines[0]
        for i, p in enumerate(P_):
            f0 = int(min(st.n - 1, np.searchsorted(prog, frac[i] - 1e-6)))
            d = float(np.median(np.linalg.norm(cam[f0:] - p, axis=1)))
            sp.points[i].radius = max(0.02, k * d / base)
        dh = np.linalg.norm(cam - hp, axis=1); vis = (prog > 1e-3) & (prog < 0.999)
        ST.keys(head, "scale", np.repeat(np.where(vis, np.maximum(k * dh / base, 1e-3), 1e-3)[:, None], 3, 1))
