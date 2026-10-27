"""Places and weather of the kit (Blender 4.5, Cycles): the wall of a gallery, the open sky, a real region seen from above
(terrain: relief + satellite colour to the horizon; sea: the same with the water in front), outdoor light (a sun and a
sky drawn for the mood, in known radiance, so exposure 0 is right), aerial haze, a hazy room, rain and snow, and the
shadow catcher of a piece laid over the map.
Units on a terrain or sea place: 1 = 1 km, heights exaggerated (ve from the scene data)."""
import json, math, os
import bpy, bmesh
import numpy as np
from mathutils import Vector
import common as C
import mats as M
import plan as P
import stage as ST
import terrain_mesh as TM

# sky of an outdoor mood: zenith, horizon, below the horizon (sRGB at exposure 0), sun azimuth / elevation (deg, camera
# at -90), sun colour, sun share of E_PAPER, sun angle (deg, softness of shadows)
SKY = {"dawn": ((0.40, 0.48, 0.62), (0.95, 0.76, 0.60), (0.64, 0.60, 0.60), -150, 7, (1.0, 0.78, 0.55), 0.62, 1.5),
       "noon": ((0.30, 0.48, 0.78), (0.80, 0.86, 0.92), (0.66, 0.70, 0.74), -120, 58, (1.0, 0.97, 0.92), 0.6, 0.8),
       "dusk": ((0.26, 0.30, 0.48), (0.98, 0.64, 0.40), (0.52, 0.44, 0.44), -160, 5, (1.0, 0.62, 0.36), 0.58, 1.8),
       "overcast": ((0.70, 0.72, 0.75), (0.83, 0.84, 0.85), (0.60, 0.61, 0.62), -110, 50, (0.9, 0.92, 1.0), 0.12, 15.0),
       "night": ((0.020, 0.030, 0.070), (0.09, 0.11, 0.17), (0.05, 0.06, 0.08), -140, 35, (0.62, 0.72, 1.0), 0.10, 0.6)}
FOG = {"clear": (0.25, 3.0, 0.55), "haze": (0.08, 1.6, 0.9), "rain": (0.05, 1.2, 0.93), "snow": (0.05, 1.1, 0.93)}  # start, depth (x span), max
NEAR_RING = 0.06              # coarse ground nearer than this share of the region to the lens shows its low detail


def lin(c): return M.lin3(c)


# ------------------------------------------------------------------ data of a terrain or sea place
def load_place(st):
    """reads the region of a terrain or sea place: heights, scale, ground sampler, lon/lat members -> sets st.unit,
    st.ground_fn, st.fixed, st.span"""
    D = json.load(open(os.path.join(st.data, "place.json")))
    Z = np.load(os.path.join(st.data, D["heights"]))
    st.place_d = D; st.hm = Z["h"].astype(np.float64); st.hr = Z["hr"].astype(np.float64)
    H, W = st.hm.shape; px = D["px_km"]; ve = D["ve"]
    st.span = max(W, H) * px; st.unit = P.UNIT_GEO * st.span

    def ground(x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        col = x / px + (W - 1) / 2; row = (H - 1) / 2 - y / px
        return np.maximum(bilinear(st.hm, row, col), 0.0) / 1000.0 * ve
    st.ground_fn = ground
    st.fixed = {}
    for n, xy in (D.get("points") or {}).items():
        st.fixed[n] = (xy[0], xy[1], float(ground([xy[0]], [xy[1]])[0]))
    return D


def bilinear(a, r, c):
    H, W = a.shape; r = np.clip(r, 0, H - 1.001); c = np.clip(c, 0, W - 1.001)
    r0, c0 = np.floor(r).astype(int), np.floor(c).astype(int); fr, fc = r - r0, c - c0
    return (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0 + 1, c0] * fr * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc + a[r0 + 1, c0 + 1] * fr * fc)


# ------------------------------------------------------------------ the sky (world and haze share one drawing)
def sky_group(mood):
    z, h, b, saz, sel, scol, _, _ = SKY.get(mood, SKY["noon"])
    ng = bpy.data.node_groups.new("sky", "ShaderNodeTree")
    ng.interface.new_socket(name="Vector", in_out="INPUT", socket_type="NodeSocketVector")
    ng.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    nv = N.new("ShaderNodeVectorMath"); nv.operation = "NORMALIZE"; L.new(gi.outputs[0], nv.inputs[0])
    sx = N.new("ShaderNodeSeparateXYZ"); L.new(nv.outputs[0], sx.inputs[0])

    def mth(op, a, bb=None, clamp=False):
        n = N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, x in enumerate((a, bb)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = float(x)
            else: L.new(x, n.inputs[i])
        return n.outputs[0]

    def mix(f, c1, c2):
        m = N.new("ShaderNodeMix"); m.data_type = "RGBA"
        L.new(f, m.inputs[0]) if not isinstance(f, (int, float)) else setattr(m.inputs[0], "default_value", f)
        for sock, c in ((m.inputs[6], c1), (m.inputs[7], c2)):
            if isinstance(c, tuple): sock.default_value = (*lin(c), 1)
            else: L.new(c, sock)
        return m.outputs[2]
    up = mth("POWER", mth("MAXIMUM", sx.outputs[2], 0.0), 0.55)
    down = mth("MINIMUM", mth("MULTIPLY", mth("MAXIMUM", mth("MULTIPLY", sx.outputs[2], -1.0), 0.0), 5.0), 1.0)
    col = mix(down, mix(up, h, z), b)
    sd = Vector(P.cam_dir(sel, saz))
    dv = N.new("ShaderNodeVectorMath"); dv.operation = "DOT_PRODUCT"; L.new(nv.outputs[0], dv.inputs[0]); dv.inputs[1].default_value = tuple(sd)
    dp = mth("MAXIMUM", dv.outputs["Value"], 0.0)
    glow = mth("ADD", mth("MULTIPLY", mth("POWER", dp, 900.0), 6.0), mth("MULTIPLY", mth("POWER", dp, 12.0), 0.22))
    em = N.new("ShaderNodeMix"); em.data_type = "RGBA"; em.blend_type = "ADD"; L.new(mth("MINIMUM", glow, 6.0), em.inputs[0])
    L.new(col, em.inputs[6]); em.inputs[7].default_value = (*lin(scol), 1)
    L.new(em.outputs[2], go.inputs[0])
    return ng


def world(st):
    """the sky as the world: seen by the camera and lighting the scene"""
    ng = sky_group(st.mood); st.sky = ng
    wd = st.sc.world; nt = wd.node_tree; bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord"); g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = ng
    nt.links.new(tc.outputs["Generated"], g.inputs[0]); nt.links.new(g.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0


def sun(st):
    """the sun of the mood; returns the exposure target of a surface of the given albedo lit by sun and sky"""
    z, h, b, saz, sel, scol, share, ang = SKY.get(st.mood, SKY["noon"])
    ld = bpy.data.lights.new("sun", "SUN"); ld.color = scol; ld.angle = math.radians(ang)
    ld.energy = share * ST.E_PAPER
    ob = bpy.data.objects.new("sun", ld); ST.link(ob); ob.location = Vector(P.cam_dir(sel, saz)) * 10.0; C.aim(ob, (0, 0, 0))
    st.key = ob; st.share = share
    e_sky = math.pi * (0.35 * np.mean(lin(z)) + 0.65 * np.mean(lin(h)))       # irradiance of the sky on flat ground (approx.)
    return share * ST.E_PAPER * math.sin(math.radians(max(sel, 3))) + e_sky


# ------------------------------------------------------------------ terrain / sea
def ground_material(st, D, x0, y0, x1, y1, fx0, fy0, fx1, fy1):
    """the region's own picture inside it, the coarse picture of the surroundings outside"""
    g = M.Graph("ground")
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(g.co, sx.inputs[0]); x, y = sx.outputs[0], sx.outputs[1]

    def tex(path, a0, b0, a1, b1):
        cv = g.node("ShaderNodeCombineXYZ")
        g.L.new(g.math("MULTIPLY_ADD", g.math("SUBTRACT", x, a0), 1.0 / (a1 - a0), 0.0), cv.inputs[0])
        g.L.new(g.math("MULTIPLY_ADD", g.math("SUBTRACT", y, b0), 1.0 / (b1 - b0), 0.0), cv.inputs[1])
        im = g.N.new("ShaderNodeTexImage"); im.image = bpy.data.images.load(path, check_existing=True)
        im.extension = "EXTEND"; im.interpolation = "Cubic"; g.L.new(cv.outputs[0], im.inputs[0])
        return im.outputs["Color"]
    inner = tex(os.path.join(st.data, D["image"]), x0, y0, x1, y1)
    outer = tex(os.path.join(st.data, D["ring_image"]), fx0, fy0, fx1, fy1)
    ins = g.math("MULTIPLY", g.math("MULTIPLY", g.math("GREATER_THAN", x, x0), g.math("LESS_THAN", x, x1)),
                 g.math("MULTIPLY", g.math("GREATER_THAN", y, y0), g.math("LESS_THAN", y, y1)))
    col = g.mix_rgb(ins, outer, inner)
    hs = g.node("ShaderNodeHueSaturation", Saturation=1.08); g.L.new(col, hs.inputs["Color"])
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.93); g.L.new(hs.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Specular IOR Level"].default_value = 0.2
    return g.finish(p.outputs[0], presence=False)


def terrain_place(st):
    D = st.place_d; H, W = st.hm.shape; px = D["px_km"]; ve = D["ve"]; R_ = D["ring"]
    hr = st.hr

    def h_main(X, Y): return np.asarray(bilinear(st.hm, Y, X))

    def h_far(X, Y): return np.asarray(bilinear(hr, (Y - R_["y0"]) / R_["sf"], (X - R_["x0"]) / R_["sf"]))
    co, quads, tris = TM.assemble(W, H, max(1, int(D.get("step", 1))), R_, R_["sf"], h_main, h_far)
    wc = np.stack([(co[:, 0] - (W - 1) / 2) * px, ((H - 1) / 2 - co[:, 1]) * px, co[:, 2] / 1000.0 * ve], -1)
    q_as_t = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]) if len(quads) else np.zeros((0, 3), np.int64)
    faces = TM.orient_up(wc, np.concatenate([q_as_t, tris]) if len(tris) else q_as_t)
    x0, x1 = -(W - 1) / 2 * px, (W - 1) / 2 * px; y0, y1 = -(H - 1) / 2 * px, (H - 1) / 2 * px
    fx0, fx1 = (R_["x0"] - (W - 1) / 2) * px, (R_["x1"] - (W - 1) / 2) * px
    fy0, fy1 = ((H - 1) / 2 - R_["y1"]) * px, ((H - 1) / 2 - R_["y0"]) * px
    gm = ground_material(st, D, x0, y0, x1, y1, fx0, fy0, fx1, fy1)
    ob = C.mesh_object("ground", wc, None, faces); ob.data.materials.append(gm); C.smooth_shade(ob)
    st.ground_obj = ob; st.region_box = (x0, y0, x1, y1); st.ground_mesh = (wc, faces)
    span = st.span; far = 6.0 * span
    wm = M.water("sea", 4.0 / max(px, 1e-3))
    hz = M.solid("horizon", "painted", color=tuple(D.get("ring_mean", (0.35, 0.36, 0.30))))
    disc = None
    if D.get("sea"): sea = ST.quad("sea", 2 * far, 2 * far, 0.0, None, wm)     # open water to the horizon
    else:                                                           # inland: water only inside the ring, flat land beyond it
        sea = ST.quad("sea", fx1 - fx0, fy1 - fy0, 0.0, None, wm, (fx0 + fx1) / 2, (fy0 + fy1) / 2)
        disc = ST.quad("land_beyond", 2 * far, 2 * far, -0.001, None, hz)
    fs, fd, fm = FOG.get(st.S["light"].get("weather", "clear"), FOG["clear"])
    for m_ in [gm, wm] + ([hz] if disc is not None else []):
        C.add_fog(m_, st.sky, fs * span, fd * span, 1.0, fm)
    st.sea_obj = sea
    return ob


def place(st):
    """builds the place of an outdoor scene (and the sky), or the wall of a gallery"""
    k = st.place
    if k in ("terrain", "sea", "sky"):
        world(st)
        if k in ("terrain", "sea"): terrain_place(st)
        st.surface = None; st.backdrop = None; st.albedo = None
        return
    if k == "wall": wall_place(st)


def wall_place(st):
    """a gallery: a wall behind the hung pieces (its surface from the scene, plaster by default), a dark wood floor"""
    wname = st.S["place"].get("surface") or "plaster"
    st.albedo = ST.ALBEDO.get(wname, 0.4)
    R = st.R; cx = st.center.x
    fl = ST.quad("floor", 2 * R, 2 * R, 0.0, None, M.surface("walnut"), cx, -R + 0.02)
    bm = bmesh.new()
    vs = [bm.verts.new((cx + sx * R, 0.0, z)) for sx, z in ((-1, 0.0), (1, 0.0), (1, 2 * R), (-1, 2 * R))]
    bm.faces.new(vs)
    wl = ST.bm_object("wall", bm, None, [M.surface(wname)])
    sk = ST.box("skirting", 2 * R, 0.02, 0.12, None, M.solid("skirting", "painted", color=(0.82, 0.8, 0.76)), x=cx, y=-0.01)
    st.surface, st.backdrop, st.wall = fl, None, (wl, sk)


# ------------------------------------------------------------------ light of the wall place and outdoor exposure
def outdoor_lights(st):
    e = sun(st)
    if st.place == "sky":
        st.target = 0.18; st.dark_max = 0.5; return
    alb = float(st.place_d.get("albedo", 0.1))
    st.albedo = alb; st.target = round(ST.srgb(alb * e / math.pi), 3); st.dark_max = 0.6 if st.mood != "night" else 0.97


# ------------------------------------------------------------------ over the map: shadows only
def catcher(st):
    q = ST.quad("shadow_catcher", 2 * st.R, 2 * st.R, 0.0, None, M.solid("catcher", "painted"), st.center.x, st.center.y)
    try: q.is_shadow_catcher = True
    except Exception as e: st.warnings.append(f"shadow catcher: {e}")


# ------------------------------------------------------------------ weather
def haze_room(st):
    """dust in the air of a room: the key light draws visible shafts"""
    g = M.Graph("haze"); g.N.remove(g.tc)
    pv = g.node("ShaderNodeVolumePrincipled"); pv.inputs["Density"].default_value = 0.035 / max(st.L0, 0.3)
    pv.inputs["Anisotropy"].default_value = 0.35; pv.inputs["Color"].default_value = (0.9, 0.88, 0.85, 1)
    g.L.new(pv.outputs[0], g.out.inputs["Volume"])
    b = ST.box("haze", 4 * st.L0, 4 * st.L0, 3 * st.L0, None, g.m, x=st.center.x, y=st.center.y)
    for vis in ("visible_shadow",):
        try: setattr(b, vis, False)
        except Exception: pass


def precip(st, kind):
    """rain streaks or snow flakes in a box in front of the camera that follows it: every flake moves in the world (true
    parallax) and wraps round the box out of sight; the box covers the near half of the view only (rain and snow are seen
    as streaks and flakes close to the eye, not as posts standing on far land) and none comes nearer the lens than 15 %
    of the camera distance (no blurred bars)"""
    rng = np.random.default_rng(7 if kind == "rain" else 11)
    N = 6000 if kind == "rain" else 4000
    base = rng.random((N, 3)); ph = rng.random(N) * 2 * np.pi
    plan = st.plan; fr = np.zeros((st.n, N, 3), np.float32)
    Dm = float(np.median(plan["dist"])); B = 0.9 * Dm
    v = np.array([0.08, 0.03, -1.6]) * Dm if kind == "rain" else np.array([0.03, 0.01, -0.12]) * Dm
    for fi in range(st.n):
        t = fi / P.FPS; cp = P.cam_pos(plan, fi); tg = plan["target"][fi]
        f = (tg - cp) / max(np.linalg.norm(tg - cp), 1e-9); c = cp + 0.5 * B * f
        p = base * B + v * t
        if kind == "snow": p = p + 0.04 * Dm * np.stack([np.sin(1.3 * t + ph), np.cos(0.9 * t + ph), np.zeros(N)], -1)
        p = c + ((p - c) % B) - B / 2
        near = np.linalg.norm(p - cp, axis=1) < 0.15 * plan["dist"][fi]
        p[near] = cp - 3.0 * Dm * f                                 # out of sight behind the camera
        fr[fi] = p
    os.makedirs(os.path.join(st.O.out, "_cache"), exist_ok=True)
    pc = os.path.join(st.O.out, "_cache", f"{kind}.pc2"); C.write_pc2(pc, fr)
    if kind == "rain":
        g = M.Graph("rain"); g.N.remove(g.tc)
        p_ = g.node("ShaderNodeBsdfPrincipled", Roughness=0.1); p_.inputs["Base Color"].default_value = (0.8, 0.84, 0.9, 1)
        tr = g.node("ShaderNodeBsdfTransparent"); mt = g.finish(g.mix_shader(0.72, p_.outputs[0], tr.outputs[0]), presence=False)
        r = np.full(N, 0.00035 * Dm)
        C.points_object("rain", fr[0], r, mt, cache=pc, streak=(28.0, (math.radians(6), 0.0, 0.0)))
    else:
        g = M.Graph("snow"); g.N.remove(g.tc)
        p_ = g.node("ShaderNodeBsdfPrincipled", Roughness=0.6); p_.inputs["Base Color"].default_value = (0.92, 0.93, 0.95, 1)
        mt = g.finish(p_.outputs[0], presence=False)
        C.points_object("snow", fr[0], 0.0007 * Dm * (0.6 + 0.8 * rng.random(N)), mt, cache=pc)


def weather(st):
    wx = st.S["light"].get("weather", "clear")
    if wx == "haze" and st.place not in P.OUTDOOR: haze_room(st)
    if wx in ("rain", "snow"): precip(st, wx)


# ------------------------------------------------------------------ what a ray that meets no cast member shows
def bg_code(st, o, d):
    """t = the region's ground, g = coarse ground far off, x = coarse ground close to the lens (low detail), w = water,
    s = sky, k = room, r/d = lit / dark surface (wall place: the wall too)"""
    if st.place in ("terrain", "sea"):
        hit = st.ground_tree.ray_cast(o, d) if getattr(st, "ground_tree", None) else (None,)
        tw = (-o.z / d.z) if d.z < -1e-9 else None
        if hit[0] is not None and (tw is None or (hit[0] - o).length <= tw + 1e-6) and hit[0].z > 1e-5:
            q = hit[0]; x0, y0, x1, y1 = st.region_box
            if x0 <= q.x <= x1 and y0 <= q.y <= y1: return "t"
            return "x" if (q - o).length < NEAR_RING * st.span else "g"
        if tw is not None: return "w"
        return "s"
    if st.place == "sky": return "s"
    return None
