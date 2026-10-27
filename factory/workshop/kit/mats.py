"""Materials of the workshop kit (Blender 4.5, Cycles). Surfaces and props are ordinary physical materials; pictures
(photos, documents, maps, paintings) keep their exact colours: the camera sees an emission at 2^-exposure (Standard view),
every other ray sees a painted surface, so the room answers the picture without changing it.
Every material carries a presence value (0 = invisible, 1 = there) so any cast member can appear or vanish."""
import bpy, math, os

PAPER = {"paper": (0.93, 0.91, 0.86), "parchment": (0.86, 0.78, 0.60), "print": (0.94, 0.93, 0.90)}
METALS = {"bronze": (0.55, 0.36, 0.19), "brass": (0.78, 0.60, 0.30), "gold": (0.95, 0.74, 0.34), "silver": (0.90, 0.90, 0.88),
          "iron": (0.42, 0.42, 0.43)}
EXACT = []            # value nodes = 2^-exposure (set by the frame handler in build.py)


def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin3(c): return tuple(srgb2lin(x) for x in c)


class Graph:
    """small helper around a material node tree"""
    def __init__(self, name, rest=False):
        """rest: texture coordinates from the mesh attribute "rest" (the undeformed positions of a cloth or a folding sheet,
        so a picture stays printed on the surface while it moves) instead of the object coordinates"""
        self.m = bpy.data.materials.new(name); self.m.use_nodes = True
        self.nt = self.m.node_tree; self.N, self.L = self.nt.nodes, self.nt.links
        self.N.clear(); self.out = self.N.new("ShaderNodeOutputMaterial")
        self.tc = self.N.new("ShaderNodeTexCoord")
        self.co = self.tc.outputs["Object"]
        if rest:
            at = self.N.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = "rest"
            self.co = at.outputs["Vector"]; self.m["rest"] = 1

    def node(self, kind, **inputs):
        n = self.N.new(kind)
        for k, v in inputs.items(): self.set(n.inputs[k], v)
        return n

    def set(self, sock, v):
        if hasattr(v, "is_output") or hasattr(v, "links"): self.L.new(v, sock)
        elif isinstance(v, (tuple, list)):
            sock.default_value = tuple(v) + ((1.0,) if len(v) == 3 and len(sock.default_value) == 4 else ())
        else: sock.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = float(v)
            else: self.L.new(v, n.inputs[i])
        return n.outputs[0]

    def value(self, v=0.0):
        n = self.N.new("ShaderNodeValue"); n.outputs[0].default_value = v; return n

    def mix_shader(self, fac, a, b):
        m = self.N.new("ShaderNodeMixShader"); self.set(m.inputs[0], fac); self.L.new(a, m.inputs[1]); self.L.new(b, m.inputs[2])
        return m.outputs[0]

    def mix_rgb(self, fac, a, b):
        m = self.N.new("ShaderNodeMix"); m.data_type = "RGBA"; self.set(m.inputs[0], fac); self.set(m.inputs[6], a); self.set(m.inputs[7], b)
        return m.outputs[2]

    def scale(self, vec, s):
        n = self.N.new("ShaderNodeVectorMath"); n.operation = "SCALE"; self.set(n.inputs[0], vec); self.set(n.inputs["Scale"], s)
        return n.outputs[0]

    def finish(self, shader, presence=True):
        """presence: a value node; 0 = transparent (the object is not there)"""
        p = None
        if presence:
            p = self.value(1.0); tr = self.node("ShaderNodeBsdfTransparent")
            shader = self.mix_shader(p.outputs[0], tr.outputs[0], shader)
        self.L.new(shader, self.out.inputs["Surface"])
        self.m["presence_node"] = p.name if p else ""
        return self.m


def presence_node(m):
    n = m.get("presence_node")
    return m.node_tree.nodes.get(n) if n else None


# ------------------------------------------------------------------ surfaces
def wood(kind="walnut", presence=False):
    """polished wood veneer: fine grain along x (lines about 6 mm apart, warped), slow colour drift, pores, clear coat"""
    g = Graph(f"wood_{kind}")
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.42)
    p.inputs["Coat Weight"].default_value = 0.3; p.inputs["Coat Roughness"].default_value = 0.22
    co = g.co
    wn = g.node("ShaderNodeTexNoise", Scale=2.2, Detail=3.0); g.L.new(co, wn.inputs["Vector"])
    wc = g.N.new("ShaderNodeVectorMath"); wc.operation = "SUBTRACT"; g.L.new(wn.outputs["Color"], wc.inputs[0]); wc.inputs[1].default_value = (0.5, 0.5, 0.5)
    wa = g.N.new("ShaderNodeVectorMath"); wa.operation = "ADD"; g.L.new(co, wa.inputs[0]); g.L.new(g.scale(wc.outputs[0], 0.06), wa.inputs[1])
    mp = g.node("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (5.0, 160.0, 1.0); g.L.new(wa.outputs[0], mp.inputs["Vector"])
    wv = g.N.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"
    try: wv.bands_direction = "Y"
    except Exception: pass
    wv.inputs["Scale"].default_value = 1.0; wv.inputs["Distortion"].default_value = 3.5; wv.inputs["Detail"].default_value = 2.5
    wv.inputs["Detail Scale"].default_value = 0.6
    g.L.new(mp.outputs[0], wv.inputs["Vector"])
    gr = g.math("POWER", wv.outputs["Fac"], 1.8)                         # thin dark latewood lines on lighter wood
    mp2 = g.node("ShaderNodeMapping"); mp2.inputs["Scale"].default_value = (12.0, 420.0, 1.0); g.L.new(co, mp2.inputs["Vector"])
    po = g.node("ShaderNodeTexNoise", Scale=1.0, Detail=1.0); g.L.new(mp2.outputs[0], po.inputs["Vector"])
    pores = g.math("GREATER_THAN", po.outputs["Fac"], 0.68)
    f = g.math("SUBTRACT", g.math("MULTIPLY_ADD", gr, -0.55, 1.0), g.math("MULTIPLY", pores, 0.18))
    cr = g.N.new("ShaderNodeValToRGB"); g.L.new(f, cr.inputs[0])
    lo, hi = {"walnut": ((0.030, 0.014, 0.006), (0.105, 0.050, 0.021)), "oak": ((0.17, 0.095, 0.042), (0.42, 0.26, 0.13))}.get(kind, ((0.030, 0.014, 0.006), (0.105, 0.050, 0.021)))
    cr.color_ramp.elements[0].color = (*lo, 1); cr.color_ramp.elements[1].color = (*hi, 1)
    ln = g.node("ShaderNodeTexNoise", Scale=0.9, Detail=2.0); g.L.new(co, ln.inputs["Vector"])
    g.L.new(g.scale(cr.outputs[0], g.math("MULTIPLY_ADD", ln.outputs["Fac"], 0.36, 0.82)), p.inputs["Base Color"])
    bp = g.node("ShaderNodeBump", Strength=0.035, Distance=0.0008); g.L.new(f, bp.inputs["Height"]); g.L.new(bp.outputs[0], p.inputs["Normal"])
    return g.finish(p.outputs[0], presence=presence)


def stone(kind="stone", presence=False):
    """stone, marble, slate, sand, plaster: procedural, low gloss, fine relief"""
    base = {"stone": ((0.40, 0.385, 0.36), (0.66, 0.64, 0.60), 0.6), "marble": ((0.70, 0.69, 0.66), (0.86, 0.85, 0.82), 0.25),
            "slate": ((0.07, 0.075, 0.08), (0.13, 0.135, 0.14), 0.55), "sand": ((0.55, 0.45, 0.31), (0.68, 0.57, 0.40), 0.95),
            "plaster": ((0.70, 0.67, 0.61), (0.80, 0.77, 0.71), 0.9)}[kind]
    g = Graph(f"surface_{kind}")
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=base[2])
    nz = g.node("ShaderNodeTexNoise", Scale=3.5 if kind != "sand" else 40.0, Detail=8.0, Roughness=0.62)
    g.L.new(g.co, nz.inputs["Vector"])
    f = nz.outputs["Fac"]
    if kind in ("stone", "slate"):                             # crystals: dark and light specks over the base tone
        sp = g.node("ShaderNodeTexVoronoi", Scale=380.0 if kind == "stone" else 240.0); g.L.new(g.co, sp.inputs["Vector"])
        sc_ = g.N.new("ShaderNodeSeparateColor"); g.L.new(sp.outputs["Color"], sc_.inputs[0])
        dk = g.math("LESS_THAN", sc_.outputs[0], 0.24); lt = g.math("GREATER_THAN", sc_.outputs[1], 0.88)
        f = g.math("ADD", g.math("MULTIPLY_ADD", dk, -0.4, nz.outputs["Fac"]), g.math("MULTIPLY", lt, 0.35))
    if kind == "marble":                                       # soft veins
        wv = g.N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 5.0; wv.inputs["Distortion"].default_value = 14.0
        wv.inputs["Detail"].default_value = 8.0; wv.inputs["Detail Roughness"].default_value = 0.6
        g.L.new(g.co, wv.inputs["Vector"])
        f = g.math("MULTIPLY_ADD", g.math("POWER", wv.outputs["Fac"], 10.0), -0.22, g.math("MULTIPLY_ADD", nz.outputs["Fac"], 0.3, 0.68))
    cr = g.N.new("ShaderNodeValToRGB"); g.L.new(f, cr.inputs[0])
    cr.color_ramp.elements[0].color = (*lin3(base[0]), 1); cr.color_ramp.elements[1].color = (*lin3(base[1]), 1)
    g.L.new(cr.outputs[0], p.inputs["Base Color"])
    bp = g.node("ShaderNodeBump", Strength=0.08 if kind != "marble" else 0.02, Distance=0.003); g.L.new(nz.outputs["Fac"], bp.inputs["Height"])
    g.L.new(bp.outputs[0], p.inputs["Normal"])
    return g.finish(p.outputs[0], presence=presence)


def velvet(presence=False):
    g = Graph("velvet")
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=1.0)
    p.inputs["Base Color"].default_value = (0.011, 0.011, 0.013, 1); p.inputs["Specular IOR Level"].default_value = 0.1
    try: p.inputs["Sheen Weight"].default_value = 0.8; p.inputs["Sheen Roughness"].default_value = 0.4
    except Exception: pass
    return g.finish(p.outputs[0], presence=presence)


def surface(name):
    if name in ("walnut", "oak", "wood"): return wood("oak" if name == "oak" else "walnut")
    if name == "velvet": return velvet()
    if name in ("stone", "marble", "slate", "sand", "plaster"): return stone(name)
    return stone("stone")


# ------------------------------------------------------------------ props
def solid(name, kind, color=None):
    """physical material for props and cast members without a picture"""
    g = Graph(f"{name}_{kind}")
    p = g.node("ShaderNodeBsdfPrincipled")
    if kind in METALS:
        p.inputs["Base Color"].default_value = (*lin3(METALS[kind]), 1); p.inputs["Metallic"].default_value = 1.0
        p.inputs["Roughness"].default_value = 0.32 if kind in ("gold", "silver", "brass") else 0.45
        nz = g.node("ShaderNodeTexNoise", Scale=60.0, Detail=4.0); g.L.new(g.co, nz.inputs["Vector"])
        g.L.new(g.math("MULTIPLY_ADD", nz.outputs["Fac"], 0.18, 0.26), p.inputs["Roughness"])
    elif kind == "wax":
        p.inputs["Base Color"].default_value = (*lin3(color or (0.62, 0.05, 0.04)), 1); p.inputs["Roughness"].default_value = 0.2
        try:
            p.inputs["Subsurface Weight"].default_value = 0.25; p.inputs["Subsurface Radius"].default_value = (0.004, 0.001, 0.001)
        except Exception: pass
    elif kind == "glass":
        p.inputs["Transmission Weight"].default_value = 1.0; p.inputs["Roughness"].default_value = 0.02
    elif kind in ("walnut", "oak", "wood"):
        bpy.data.materials.remove(g.m); return wood("oak" if kind == "oak" else "walnut", presence=True)
    elif kind in ("stone", "marble", "slate", "sand", "plaster"):
        bpy.data.materials.remove(g.m); return stone(kind, presence=True)
    elif kind == "velvet":
        bpy.data.materials.remove(g.m); return velvet(presence=True)
    elif kind in ("paper", "parchment"):
        p.inputs["Base Color"].default_value = (*lin3(PAPER[kind]), 1); p.inputs["Roughness"].default_value = 0.7
    elif kind == "leather":
        p.inputs["Base Color"].default_value = (*lin3((0.24, 0.13, 0.07)), 1); p.inputs["Roughness"].default_value = 0.55
    elif kind in ("cloth", "silk", "felt"):
        p.inputs["Base Color"].default_value = (*lin3(color or (0.45, 0.08, 0.07)), 1); p.inputs["Roughness"].default_value = 0.8
        try: p.inputs["Sheen Weight"].default_value = 0.5
        except Exception: pass
    else:                                                      # painted
        p.inputs["Base Color"].default_value = (*lin3(color or (0.6, 0.58, 0.54)), 1); p.inputs["Roughness"].default_value = 0.5
    return g.finish(p.outputs[0])


def add_glow(m, color=(1.0, 0.75, 0.3)):
    """an emission added to a material, driven by a value node (0 = off); returns the node"""
    nt = m.node_tree; out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    v = nt.nodes.new("ShaderNodeValue"); v.outputs[0].default_value = 0.0
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*lin3(color), 1)
    nt.links.new(v.outputs[0], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader"); nt.links.new(src, add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return v


# ------------------------------------------------------------------ pictures
def burn_mask(g, x, y, w, h, burn, burn_from="left"):
    """an edge of fire crossing a sheet of w x h from one side (burn value node: 0 = whole, 1 = gone)
    returns sockets: gone (1 behind the front), char (dark band ahead of it), ember (glowing rim)"""
    bn = g.node("ShaderNodeTexNoise", Scale=9.0, Detail=6.0, Roughness=0.6); g.L.new(g.co, bn.inputs["Vector"])
    side = {"left": (x, 1.0 / w), "right": (x, -1.0 / w), "bottom": (y, 1.0 / h), "top": (y, -1.0 / h)}.get(burn_from, (x, 1.0 / w))
    edge = g.math("MULTIPLY_ADD", side[0], side[1], 0.5)                # 0 at the edge the fire starts from, 1 at the other
    front = g.math("SUBTRACT", g.math("MULTIPLY_ADD", bn.outputs["Fac"], 0.35, g.math("MULTIPLY", edge, 0.82)), g.math("MULTIPLY_ADD", burn.outputs[0], 1.4, -0.18))
    on = g.math("GREATER_THAN", burn.outputs[0], 0.001)
    gone = g.math("LESS_THAN", front, 0.0)
    char = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("DIVIDE", front, 0.06, clamp=True)), on)
    ember = g.math("MULTIPLY", g.math("POWER", g.math("SUBTRACT", 1.0, g.math("DIVIDE", front, 0.018, clamp=True)), 2.0), on)
    return gone, char, ember


def paper(name, kind="paper", w=0.3, h=0.42, burn_from="left", rest=False):
    """blank paper or parchment: mottling, fibres, darker aged edges; shown like a picture of itself (the camera sees its
    exact colours, as it sees every document and photo next to it); burn, glow and presence like a picture
    returns (material, nodes)"""
    g = Graph(f"paper_{name}", rest)
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(g.co, sx.inputs[0]); x, y = sx.outputs[0], sx.outputs[1]
    parch = kind == "parchment"
    mo = g.node("ShaderNodeTexNoise", Scale=30.0, Detail=8.0, Roughness=0.65); g.L.new(g.co, mo.inputs["Vector"])
    mpf = g.node("ShaderNodeMapping"); mpf.inputs["Scale"].default_value = (90.0, 900.0, 1.0); g.L.new(g.co, mpf.inputs["Vector"])
    fb = g.node("ShaderNodeTexNoise", Scale=1.0, Detail=2.0); g.L.new(mpf.outputs[0], fb.inputs["Vector"])
    ex_ = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("MULTIPLY", x, 2.0 / w)))
    ey_ = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("MULTIPLY", y, 2.0 / h)))
    age = g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("MINIMUM", ex_, ey_), 0.14, clamp=True))
    tone = g.math("MULTIPLY", g.math("MULTIPLY_ADD", mo.outputs["Fac"], 0.22 if parch else 0.08, 0.89 if parch else 0.96),
                  g.math("MULTIPLY_ADD", fb.outputs["Fac"], 0.06, 0.97))
    tone = g.math("MULTIPLY", tone, g.math("MULTIPLY_ADD", g.math("POWER", age, 2.0), -0.45 if parch else -0.12, 1.0))
    pap = g.node("ShaderNodeCombineXYZ")
    for i, c in enumerate(PAPER.get(kind, PAPER["paper"])): pap.inputs[i].default_value = srgb2lin(c)
    col = g.scale(pap.outputs[0], tone)
    burn = g.value(0.0); glow = g.value(0.0)
    gone, char, ember = burn_mask(g, x, y, w, h, burn, burn_from)
    col = g.mix_rgb(g.math("MULTIPLY", char, 0.85), col, (0.012, 0.008, 0.005))
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.62 if parch else 0.75); g.L.new(col, p.inputs["Base Color"])
    try: p.inputs["Sheen Weight"].default_value = 0.25
    except Exception: pass
    bp = g.node("ShaderNodeBump", Strength=0.04, Distance=0.0005); g.L.new(mo.outputs["Fac"], bp.inputs["Height"]); g.L.new(bp.outputs[0], p.inputs["Normal"])
    ex = g.value(1.0); EXACT.append(ex)
    lw = g.node("ShaderNodeLayerWeight", Blend=0.5)
    shade = g.math("MULTIPLY_ADD", g.math("POWER", lw.outputs["Facing"], 2.0), -0.3, 1.0)
    lift = g.math("MULTIPLY_ADD", glow.outputs[0], 0.8, 1.0)
    em = g.node("ShaderNodeEmission", Strength=1.0)
    g.L.new(g.scale(col, g.math("MULTIPLY", g.math("MULTIPLY", ex.outputs[0], shade), lift)), em.inputs["Color"])
    lp = g.node("ShaderNodeLightPath")
    surf = g.mix_shader(lp.outputs["Is Camera Ray"], p.outputs[0], em.outputs[0])
    fire = g.node("ShaderNodeEmission", Color=(1.0, 0.36, 0.06)); g.L.new(g.math("MULTIPLY", ember, g.math("MULTIPLY", ex.outputs[0], 6.0)), fire.inputs["Strength"])
    a1 = g.node("ShaderNodeAddShader"); g.L.new(surf, a1.inputs[0]); g.L.new(fire.outputs[0], a1.inputs[1])
    tr = g.node("ShaderNodeBsdfTransparent")
    m = g.finish(g.mix_shader(gone, a1.outputs[0], tr.outputs[0]))
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m, {"reveal": None, "burn": burn, "glow": glow, "presence": presence_node(m)}


def picture(name, path, w, h, iw, ih, kind="paper", sheen=False, burn_from="left", ox=0.0, oy=0.0, alpha=False, rest=False,
            twosided=None):
    """a picture of iw x ih (object units, centred at -ox, -oy) on a sheet of w x h whose margin is paper of the given kind.
    alpha: the picture's own transparency cuts the surface out (a cut-out figure); rest: see Graph;
    twosided: colour of the back of a single surface (paper, card) - otherwise the back shows the picture (a flag)
    returns (material, nodes) - nodes: reveal (DARK..1), burn (0..1), glow (0..1), presence (value nodes)"""
    g = Graph(f"pic_{name}", rest)
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(g.co, sx.inputs[0])
    x, y = sx.outputs[0], sx.outputs[1]
    u = g.math("MULTIPLY_ADD", g.math("ADD", x, ox), 1.0 / iw, 0.5); v = g.math("MULTIPLY_ADD", g.math("ADD", y, oy), 1.0 / ih, 0.5)
    cv = g.node("ShaderNodeCombineXYZ"); g.L.new(u, cv.inputs[0]); g.L.new(v, cv.inputs[1])
    img = g.N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(path, check_existing=True)
    img.extension = "EXTEND"; img.interpolation = "Cubic"; g.L.new(cv.outputs[0], img.inputs[0])
    du, dv = g.math("ABSOLUTE", g.math("SUBTRACT", u, 0.5)), g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5))
    inside = g.math("MULTIPLY", g.math("LESS_THAN", du, 0.5), g.math("LESS_THAN", dv, 0.5))
    nz = g.node("ShaderNodeTexNoise", Scale=220.0, Detail=4.0); g.L.new(g.co, nz.inputs["Vector"])
    grain = g.math("MULTIPLY_ADD", nz.outputs["Fac"], 0.05, 0.975)
    pap = g.node("ShaderNodeCombineXYZ")
    for i, c in enumerate(PAPER.get(kind, PAPER["paper"])): pap.inputs[i].default_value = srgb2lin(c)
    col = g.mix_rgb(inside, g.scale(pap.outputs[0], grain), img.outputs["Color"])
    # burn: an edge of fire crosses the sheet from one side (value 0 = whole, 1 = gone)
    burn = g.value(0.0)
    gone, char, ember = burn_mask(g, x, y, w, h, burn, burn_from)
    col = g.mix_rgb(g.math("MULTIPLY", char, 0.85), col, (0.012, 0.008, 0.005))
    # reveal: before its light comes on, a picture is almost dark (driven by the light verb; 1 = lit)
    rev = g.value(1.0); glow = g.value(0.0)
    ex = g.value(1.0); EXACT.append(ex)
    lw = g.node("ShaderNodeLayerWeight", Blend=0.5)
    shade = g.math("MULTIPLY_ADD", g.math("POWER", lw.outputs["Facing"], 2.0), -0.3, 1.0)
    em = g.node("ShaderNodeEmission", Strength=1.0)
    lift = g.math("MULTIPLY_ADD", glow.outputs[0], 0.8, 1.0)            # the glow verb brightens the picture itself
    g.L.new(g.scale(col, g.math("MULTIPLY", g.math("MULTIPLY", g.math("MULTIPLY", ex.outputs[0], rev.outputs[0]), shade), lift)), em.inputs["Color"])
    top = em.outputs[0]
    if sheen:                                                           # satin photo paper
        gl = g.node("ShaderNodeBsdfGlossy", Roughness=0.22); fr = g.node("ShaderNodeFresnel", IOR=1.5)
        blk = g.node("ShaderNodeEmission", Strength=0.0)
        coat = g.mix_shader(g.math("MULTIPLY", fr.outputs[0], 0.5), blk.outputs[0], gl.outputs[0])
        add = g.node("ShaderNodeAddShader"); g.L.new(top, add.inputs[0]); g.L.new(coat, add.inputs[1]); top = add.outputs[0]
    paint = g.node("ShaderNodeBsdfPrincipled", Roughness=0.6); g.L.new(col, paint.inputs["Base Color"])
    lp = g.node("ShaderNodeLightPath")
    surf = g.mix_shader(lp.outputs["Is Camera Ray"], paint.outputs[0], top)
    fire = g.node("ShaderNodeEmission", Color=(1.0, 0.36, 0.06)); g.L.new(g.math("MULTIPLY", ember, g.math("MULTIPLY", ex.outputs[0], 6.0)), fire.inputs["Strength"])
    add2 = g.node("ShaderNodeAddShader"); g.L.new(surf, add2.inputs[0]); g.L.new(fire.outputs[0], add2.inputs[1])
    tr = g.node("ShaderNodeBsdfTransparent")
    surf = g.mix_shader(gone, add2.outputs[0], tr.outputs[0])
    if twosided is not None:                                            # the back of a sheet or card is plain
        bk = g.node("ShaderNodeBsdfPrincipled", Roughness=0.8); bk.inputs["Base Color"].default_value = (*lin3(twosided), 1)
        geo = g.node("ShaderNodeNewGeometry"); surf = g.mix_shader(geo.outputs["Backfacing"], surf, bk.outputs[0])
    if alpha:                                                           # the figure only, its background cut away
        a_ = g.math("GREATER_THAN", img.outputs["Alpha"], 0.5)
        surf = g.mix_shader(a_, g.node("ShaderNodeBsdfTransparent").outputs[0], surf)
    m = g.finish(surf)
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m, {"reveal": rev, "burn": burn, "glow": glow, "presence": presence_node(m)}


def flame(name="flame"):
    g = Graph(name)
    em = g.node("ShaderNodeEmission", Color=(1.0, 0.62, 0.22), Strength=18.0)
    m = g.finish(em.outputs[0])
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m


def image_size(path):
    im = bpy.data.images.load(path, check_existing=True)
    return im.size[0], im.size[1]


def file_in(data, name): return os.path.join(data, name)


# ------------------------------------------------------------------ added tools: presence on any material, dissolve, ink,
# the Earth of a globe, water, terrain colour, lines (borders, routes)
def add_presence(m):
    """a presence value (1 = there, 0 = gone) on a material made elsewhere (an imported model); returns the value node"""
    if m.get("presence_node"): return presence_node(m)
    nt = m.node_tree; out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None or not out.inputs["Surface"].links: return None
    src = out.inputs["Surface"].links[0].from_socket
    v = nt.nodes.new("ShaderNodeValue"); v.outputs[0].default_value = 1.0
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(v.outputs[0], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(src, mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"]); m["presence_node"] = v.name
    return v


def add_dissolve(m, scale, rim=(1.0, 0.86, 0.62)):
    """the material eaten away by a noisy front (value 0 = whole, 1 = gone) with a faint bright rim; returns the value node
    scale: noise scale in object units (about 6 / size of the member)"""
    nt = m.node_tree; N, L = nt.nodes, nt.links
    out = next((n for n in N if n.type == "OUTPUT_MATERIAL"), None)
    if out is None or not out.inputs["Surface"].links: return None
    src = out.inputs["Surface"].links[0].from_socket
    if m.get("rest"):
        co = N.new("ShaderNodeAttribute"); co.attribute_type = "GEOMETRY"; co.attribute_name = "rest"; co = co.outputs["Vector"]
    else: co = N.new("ShaderNodeTexCoord").outputs["Object"]
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 6.0
    L.new(co, nz.inputs["Vector"])
    v = N.new("ShaderNodeValue"); v.outputs[0].default_value = 0.0

    def mth(op, a, b, clamp=False):
        n = N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)): n.inputs[i].default_value = float(x)
            else: L.new(x, n.inputs[i])
        return n.outputs[0]
    front = mth("SUBTRACT", nz.outputs["Fac"], mth("SUBTRACT", mth("MULTIPLY", v.outputs[0], 1.3), 0.15))
    gone = mth("LESS_THAN", front, 0.0)
    on = mth("GREATER_THAN", v.outputs[0], 0.001)
    edge = mth("MULTIPLY", mth("SUBTRACT", 1.0, mth("DIVIDE", front, 0.035, True)), on)
    em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*lin3(rim), 1); L.new(mth("MULTIPLY", edge, 3.0), em.inputs["Strength"])
    add = N.new("ShaderNodeAddShader"); L.new(src, add.inputs[0]); L.new(em.outputs[0], add.inputs[1])
    tr = N.new("ShaderNodeBsdfTransparent"); mx = N.new("ShaderNodeMixShader")
    L.new(gone, mx.inputs[0]); L.new(add.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])
    return v


def ink(name, x0, x1, gold=False):
    """handwriting on a surface: dark ink (gold leaf on a dark surface) shown from the left edge x0 to x1 as the reveal
    value goes 0 -> 1 (a soft, slightly slanted front, as a pen moves); returns (material, reveal value node)"""
    g = Graph(f"ink_{name}")
    p = g.node("ShaderNodeBsdfPrincipled")
    if gold:
        p.inputs["Base Color"].default_value = (*lin3(METALS["gold"]), 1); p.inputs["Metallic"].default_value = 1.0; p.inputs["Roughness"].default_value = 0.3
    else:
        p.inputs["Base Color"].default_value = (*lin3((0.07, 0.055, 0.05)), 1); p.inputs["Roughness"].default_value = 0.38
    rv = g.value(0.0)
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(g.co, sx.inputs[0])
    u = g.math("MULTIPLY_ADD", g.math("SUBTRACT", sx.outputs[0], x0), 1.0 / max(x1 - x0, 1e-6), g.math("MULTIPLY", sx.outputs[1], 0.25 / max(x1 - x0, 1e-6)))
    show = g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("SUBTRACT", u, g.math("MULTIPLY_ADD", rv.outputs[0], 1.04, -0.02)), 0.02, clamp=True))
    tr = g.node("ShaderNodeBsdfTransparent")
    return g.finish(g.mix_shader(show, tr.outputs[0], p.outputs[0])), rv


def earth(name, path):
    """the Earth on a sphere of radius 1 (object coordinates, north = +z, longitude 0 on +x): equirectangular picture,
    varnished like a desk globe"""
    g = Graph(f"earth_{name}")
    nv = g.N.new("ShaderNodeVectorMath"); nv.operation = "NORMALIZE"; g.L.new(g.co, nv.inputs[0])
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(nv.outputs[0], sx.inputs[0])
    lon = g.math("ARCTAN2", sx.outputs[1], sx.outputs[0]); lat = g.math("ARCSINE", sx.outputs[2])
    cv = g.node("ShaderNodeCombineXYZ")
    g.L.new(g.math("MULTIPLY_ADD", lon, 0.5 / math.pi, 0.5), cv.inputs[0]); g.L.new(g.math("MULTIPLY_ADD", lat, 1.0 / math.pi, 0.5), cv.inputs[1])
    img = g.N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(path, check_existing=True)
    img.extension = "REPEAT"; img.interpolation = "Linear"; g.L.new(cv.outputs[0], img.inputs[0])
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.42); g.L.new(img.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Coat Weight"].default_value = 0.35; p.inputs["Coat Roughness"].default_value = 0.12
    return g.finish(p.outputs[0])


def water(name, scale):
    """open water: deep blue-green, glossy, small waves (normal only; scale = waves per object unit)"""
    g = Graph(f"water_{name}")
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.07)
    p.inputs["Base Color"].default_value = (*lin3((0.03, 0.10, 0.14)), 1); p.inputs["IOR"].default_value = 1.333
    nz = g.node("ShaderNodeTexNoise", Scale=scale, Detail=8.0, Roughness=0.55); g.L.new(g.co, nz.inputs["Vector"])
    bp = g.node("ShaderNodeBump", Strength=0.18, Distance=0.02); g.L.new(nz.outputs["Fac"], bp.inputs["Height"]); g.L.new(bp.outputs[0], p.inputs["Normal"])
    return g.finish(p.outputs[0], presence=False)


def ground(name, path, x0, y0, x1, y1, sat=1.08):
    """land coloured by a satellite picture over x0..x1, y0..y1 (object units; the picture's top row at y1), lit by the scene"""
    g = Graph(f"ground_{name}")
    sx = g.node("ShaderNodeSeparateXYZ"); g.L.new(g.co, sx.inputs[0])
    cv = g.node("ShaderNodeCombineXYZ")
    g.L.new(g.math("MULTIPLY_ADD", g.math("SUBTRACT", sx.outputs[0], x0), 1.0 / (x1 - x0), 0.0), cv.inputs[0])
    g.L.new(g.math("MULTIPLY_ADD", g.math("SUBTRACT", sx.outputs[1], y0), 1.0 / (y1 - y0), 0.0), cv.inputs[1])
    img = g.N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(path, check_existing=True)
    img.extension = "EXTEND"; img.interpolation = "Cubic"; g.L.new(cv.outputs[0], img.inputs[0])
    hs = g.node("ShaderNodeHueSaturation", Saturation=sat); g.L.new(img.outputs["Color"], hs.inputs["Color"])
    p = g.node("ShaderNodeBsdfPrincipled", Roughness=0.92); g.L.new(hs.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Specular IOR Level"].default_value = 0.2
    return g.finish(p.outputs[0], presence=False)


def line(name, color, strength=1.0):
    """a drawn line (border, route): an emission seen by the camera only, so it reads the same in any light"""
    g = Graph(f"line_{name}")
    em = g.node("ShaderNodeEmission", Color=(*lin3(color), 1), Strength=strength)
    ex = g.value(1.0); EXACT.append(ex)
    g.L.new(g.math("MULTIPLY", ex.outputs[0], strength), em.inputs["Strength"])
    lp = g.node("ShaderNodeLightPath"); tr = g.node("ShaderNodeBsdfTransparent")
    m = g.finish(g.mix_shader(lp.outputs["Is Camera Ray"], tr.outputs[0], em.outputs[0]))
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m
