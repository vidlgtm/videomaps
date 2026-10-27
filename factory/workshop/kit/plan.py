"""Pure geometry of a described 3D scene (numpy only, no Blender): sizes of the cast, layout on the place, the motion of
every cast member from the beats, the camera path from the camera entries, key frames. Units: metres, z up, the place's
surface at z = 0, the camera at azimuth -90 looks along +y."""
import hashlib, math
import numpy as np

FPS = 30
SIZE = {"sheet": 0.42, "print": 0.24, "canvas": 0.55, "cutout": 0.5, "cloth": 0.9, "tile": 1.2, "block": 0.30, "book": 0.26,
        "box": 0.30, "disc": 0.06, "globe": 0.36, "model": 0.30, "text": 0.07, "pole": 1.8, "table": 1.4, "plinth": 1.0,
        "frame": 0.50, "wall": 3.0, "candle": 0.16, "terrain": 1.0}
OUTDOOR = {"terrain", "sea", "sky"}
UNIT_GEO = 0.03 / 1.8         # on a terrain or sea place a pole of size M stands 3 % of the region high (about half the
                              # height a flight keeps over the ground, so it is seen from above): every size alike
HUNG = {"sheet", "print", "canvas", "frame", "cloth", "text"}    # what hangs on the wall of a "wall" place
WALL_C = 1.45                 # height of the centre of the hung row (m)
FLAT = {"sheet", "print", "canvas", "frame", "block", "text"}
SML = {"S": 0.6, "M": 1.0, "L": 1.6}
BORDER = 0.05                 # white margin of a print (share of its long side)
GAP = 0.22                    # free space between two cast members side by side (share of the larger one)
ELEV = {"desk": 52.0, "museum": 48.0, "floor": 38.0, "wall": 8.0, "void": 30.0, "sky": 12.0, "terrain": 35.0, "sea": 20.0}
LENS, SENSOR, ASPECT = 50.0, 36.0, 16 / 9
DRIFT = 0.012                 # the camera never stops: a slow push-in of 1.2 % of the distance per 5 s while it holds
SAFE = (0.03, 0.97, 0.05, 0.96)   # safe area of the frame (u0, u1, v0, v1; v up): held things stay inside it or wholly out
BUILT = {"nouns": {"sheet", "print", "canvas", "disc", "block", "text", "pole", "plinth", "table", "frame", "candle", "book", "box",
                   "globe", "cutout", "model", "cloth", "tile", "terrain", "wall"},
         "verbs": {"appear", "vanish", "drop", "rise", "slide", "turn", "flip", "stamp", "light", "label", "glow", "burn", "open",
                   "close", "unfold", "fold", "wave", "split", "assemble", "dissolve", "write", "route", "scatter", "stack"},
         "moves": {"wide", "close", "top", "low", "push", "pull", "orbit", "crane", "dolly", "tilt", "hold", "rack", "track", "fly"},
         "places": {"desk", "museum", "floor", "void", "wall", "terrain", "sea", "sky"}, "weather": {"clear", "haze", "rain", "snow"},
         "output": {"film", "over_map"}}


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = np.clip(x, 0.0, 1.0)
    return 1 - (1 - x) ** 3


def jitter(name, k, amp):
    """small deterministic variation per cast member (natural layout without randomness between runs)"""
    h = int(hashlib.sha1(f"{name}:{k}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return (2 * h - 1) * amp


# ------------------------------------------------------------------ sizes
def fit_pic(a, w, d):
    """largest picture of aspect a inside w x d"""
    return (w, w / a) if a >= w / d else (d * a, d)


def dims(c, aspect=None, unit=1.0):
    """footprint (w along x, d along y), height h, picture size (iw, ih) of a cast member lying on the place
    unit: scale of every size (1 = metres; a terrain or sea place sets it from its region)"""
    noun = c["is"]; s = c.get("size", "M")
    L = (float(s) if isinstance(s, (int, float)) else SIZE[noun] * SML.get(s, 1.0)) * unit
    if noun == "book":                       # closed book on the right half of its footprint (the open cover needs the left)
        ph = L; sp = bool(aspect and aspect >= 1.2)
        pw = float(np.clip(ph * aspect / 2 * 1.08 if sp else ph * (aspect or 0.66) * 1.14, 0.55 * ph, 0.9 * ph))
        iw, ih = fit_pic(aspect or 1.0, (2 * pw if sp else pw) * 0.86, 0.86 * ph)
        ov, t, pg = 0.03 * ph, 0.012 * ph, 0.075 * ph
        return {"w": 2 * (pw + ov), "d": ph + 2 * ov, "h": 2 * t + pg, "L": L, "iw": iw, "ih": ih, "pw": pw, "ph": ph, "spread": sp,
                "t": t, "pg": pg, "ov": ov, "cx": (pw + ov) / 2}
    if noun == "box":
        w, d, h = L, 0.68 * L, 0.42 * L; iw, ih = fit_pic(aspect or 1.0, 0.8 * w, 0.8 * d)
        return {"w": w, "d": d, "h": h, "L": L, "iw": iw, "ih": ih, "floor": 0.07 * h, "h_open": 0.95 * d}
    if noun == "globe": return {"w": 1.16 * L, "d": 1.16 * L, "h": 1.42 * L, "L": L}
    if noun == "cutout":
        a = aspect or 0.45; return {"w": L * a, "d": max(0.14 * L * a, 0.05 * L), "h": L, "L": L, "iw": L * a, "ih": L}
    if noun == "cloth":
        a = aspect or 1.5; return {"w": L, "d": L / a, "h": 0.004 * L, "L": L, "iw": L, "ih": L / a, "fly": L, "hoist": L / a}
    if noun == "wall": return {"w": L, "d": 0.08 * L, "h": 0.55 * L, "L": L}
    if noun == "terrain":
        a = aspect or 1.4; return {"w": L, "d": L / a, "h": 0.12 * L, "L": L}
    a = aspect or (2 ** -0.5 if noun == "sheet" else 1.0)          # a blank sheet is portrait paper (A sizes)
    if noun in ("sheet", "print", "canvas", "frame"):
        b = BORDER * L if noun == "print" else (0.07 * L if noun in ("canvas", "frame") else 0.0)
        if a >= 1: iw = L - 2 * b; ih = iw / a
        else: ih = L - 2 * b; iw = ih * a
        w, d = iw + 2 * b, ih + 2 * b
        h = {"sheet": 0.0025, "print": 0.004}.get(noun, 0.035) * max(w, d)
        return {"w": w, "d": d, "h": h, "iw": iw, "ih": ih, "L": L}
    if noun == "disc": return {"w": L, "d": L, "h": 0.17 * L, "L": L}
    if noun == "block":
        fw, fd = 0.86 * L, 0.86 * 0.62 * L
        iw, ih = (fw, fw / a) if a >= fw / fd else (fd * a, fd)
        return {"w": L, "d": 0.62 * L, "h": 0.42 * L, "L": L, "iw": iw, "ih": ih}
    if noun == "text": return {"w": L * 0.62 * max(1, len(str(c.get("from", "text:x"))[5:])), "d": L, "h": 0.12 * L, "L": L}
    if noun == "pole": return {"w": 0.033 * L, "d": 0.033 * L, "h": L, "L": L}
    if noun == "plinth": return {"w": 0.5 * L, "d": 0.5 * L, "h": L, "L": L}
    if noun == "table": return {"w": L, "d": 0.58 * L, "h": 0.536 * L, "L": L}
    if noun == "candle": return {"w": 0.31 * L, "d": 0.31 * L, "h": L, "L": L}
    return {"w": L, "d": L, "h": L, "L": L}


# ------------------------------------------------------------------ layout
def footprint(m, x=None, y=None, rot=None):
    x = m["x"] if x is None else x; y = m["y"] if y is None else y; a = math.radians(m["rot"] if rot is None else rot)
    ca, sa = math.cos(a), math.sin(a); out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        px, py = sx * m["w"] / 2, sy * m["d"] / 2
        out.append((x + ca * px - sa * py, y + sa * px + ca * py))
    return np.array(out)


def overlap(p, q):
    """separating axis test of two convex polygons (2D)"""
    for P in (p, q):
        for i in range(len(P)):
            e = P[(i + 1) % len(P)] - P[i]; n = np.array([-e[1], e[0]])
            a, b = p @ n, q @ n
            if a.max() <= b.min() + 1e-9 or b.max() <= a.min() + 1e-9: return False
    return True


def hang(m):
    """a flat member hung on a wall: its face turns to the camera (x 90 deg), its box becomes upright"""
    m["w0"], m["d0"], m["h0"] = m["w"], m["d"], m["h"]                     # the member is built lying, then stood up
    m["d"], m["h"] = max(m["h"], 0.004), m["d"]; m["rx0"] = 90.0; m["oz"] = m["h"] / 2; m["rot"] = 0.0; m["upright"] = True


def row_place(M, names, y_front=None, groups=None):
    """members in one row along x (bottom edges aligned); members of a group (map tiles) keep their relative places"""
    groups = groups or {}
    blocks, seen = [], set()
    for n in names:
        if n in seen: continue
        if n in groups:
            g = [k for k in names if k in groups]; seen.update(g)
            xs = [groups[k][0] + s * M[k]["w"] / 2 for k in g for s in (-1, 1)]; ys = [groups[k][1] + s * M[k]["d"] / 2 for k in g for s in (-1, 1)]
            blocks.append({"names": g, "w": max(xs) - min(xs), "d": max(ys) - min(ys), "cx": (max(xs) + min(xs)) / 2, "cy": (max(ys) + min(ys)) / 2})
        else:
            seen.add(n); blocks.append({"names": [n], "w": M[n]["w"], "d": M[n]["d"]})
    if not blocks: return
    gap = GAP * max(b["w"] for b in blocks)
    total = sum(b["w"] for b in blocks) + gap * (len(blocks) - 1)
    x = -total / 2; dmax = max(b["d"] for b in blocks)
    y0 = -dmax / 2 if y_front is None else y_front
    for b in blocks:
        bx = x + b["w"] / 2; by = y0 + b["d"] / 2
        if len(b["names"]) == 1 and b["names"][0] not in groups:
            m = M[b["names"][0]]; m["x"] = bx; m["y"] = by + (0.0 if m.get("upright") else jitter(m["name"], "y", 0.02 * dmax))
        else:
            for k in b["names"]:
                M[k]["x"] = bx + groups[k][0] - b["cx"]; M[k]["y"] = by + groups[k][1] - b["cy"]; M[k]["rot"] = 0.0
        for k in b["names"]: M[k]["placed"] = True
        x += b["w"] + gap


def layout(cast, aspects, sizes=None, place="desk", unit=1.0, fixed=None, groups=None):
    """positions of the cast: 'where' relations first, the rest in a row on the place (bottom edges aligned)
    sizes : measured sizes that replace the estimates (text, models, map tiles, terrain blocks)
    place : on a "wall" place the flat members hang in a row on the wall, the others stand in a row in front of it
    unit  : scale of every size (a terrain or sea place sets it from its region)
    fixed : {name: (x, y, z)} members already placed (a lon/lat on a terrain); groups: {name: (gx, gy)} members that keep
            their places relative to each other (the tiles of one map) and move in the row as one block"""
    M = {}
    for n, c in cast.items():
        d = dims(c, aspects.get(n), unit); d.update((sizes or {}).get(n, {}))
        d.update(name=n, noun=c["is"], z=0.0, x=0.0, y=0.0, rot=0.0, placed=False)
        d.setdefault("rx0", 0.0); d.setdefault("ox", 0.0); d.setdefault("oz", 0.0)
        if c["is"] in FLAT: d["rot"] = jitter(n, "rot", 2.2)
        M[n] = d
    for n, xyz in (fixed or {}).items():
        if n in M: M[n]["x"], M[n]["y"], M[n]["z"] = map(float, xyz); M[n]["placed"] = True
    row = [n for n, c in cast.items() if (not c.get("where") or c["where"][1] == "place") and not M[n]["placed"]]
    rel = [n for n in cast if n not in row and not M[n]["placed"]]
    if place == "wall":
        hung = [n for n in row if cast[n]["is"] in HUNG]
        for n in hung: hang(M[n])
        if hung:
            row_place(M, hung, y_front=-max(M[n]["d"] for n in hung) - 0.004)
            hc = max(WALL_C, 0.5 * max(M[n]["h"] for n in hung) + 0.35)
            for n in hung: M[n]["z"] = hc - M[n]["h"] / 2
        stand = [n for n in row if n not in hung]
        dmax = max([M[n]["d"] for n in stand] or [0.0])
        row_place(M, stand, y_front=-(0.45 + dmax + max([M[n]["d"] for n in hung] or [0.0])), groups=groups)
    else:
        row_place(M, row, groups=groups)
    for _ in range(len(rel) + 1):
        for n in rel:
            m = M[n]
            if m["placed"]: continue
            r, ref = cast[n]["where"]
            R = M.get(ref)
            if R is None or not R["placed"]: continue
            g = GAP * max(m["w"], R["w"])
            if place == "wall" and r not in ("on", "in", "around"):
                if cast[n]["is"] in HUNG and r != "in_front_of":        # a flat thing beside a hung one hangs on the wall too
                    if not m.get("upright"): hang(m)
                    m["y"] = R["y"] - R["d"] / 2 + m["d"] / 2 if R.get("upright") else -m["d"] / 2 - 0.004
                    zc = R["z"] + R["h"] / 2 if R.get("upright") else WALL_C
                    if r in ("left_of", "right_of", "beside", "behind", "against"):
                        sgn = -1 if r == "left_of" else 1
                        m["x"] = R["x"] + sgn * (R["w"] / 2 + g + m["w"] / 2); m["z"] = zc - m["h"] / 2
                    elif r == "above":
                        m["x"] = R["x"]; m["z"] = (R["z"] + R["h"] if R.get("upright") else WALL_C) + g
                    else:                                                # under
                        m["x"] = R["x"]; m["z"] = max(0.3, (R["z"] if R.get("upright") else WALL_C) - g - m["h"])
                    m["placed"] = True; continue
                if R.get("upright"):                                     # a standing thing next to a hung one: on the floor
                    sgn = -1 if r == "left_of" else (1 if r in ("right_of", "beside") else 0)
                    m["x"] = R["x"] + sgn * (R["w"] / 2 + g + m["w"] / 2)
                    m["y"] = R["y"] - R["d"] / 2 - 0.45 - m["d"] / 2; m["z"] = 0.0
                    m["placed"] = True; continue
            if r in ("on", "in"):
                sib = [x for x in rel if cast[x]["where"] in (["on", ref], ["in", ref])]
                cnt = len(sib); idx = sib.index(n)
                if cnt == 1: lx, ly = (0.18 * R["w"], -0.24 * R["d"]) if m["noun"] == "disc" else (0.0, 0.0)
                else:                                           # several things on one support: rows across its lower part
                    cell = 1.3 * max(max(M[x]["w"], M[x]["d"]) for x in sib)
                    cols = max(1, min(cnt, int(0.86 * R["w"] // cell))); rows = -(-cnt // cols)
                    r_, c_ = divmod(idx, cols); in_row = cols if r_ < rows - 1 else cnt - cols * (rows - 1)
                    span = max(min(0.86 * R["w"], max(0.62 * R["w"], in_row * cell)), in_row * cell)
                    lx, ly = ((c_ + 0.5) / in_row - 0.5) * span, -0.24 * R["d"] + r_ * cell
                lx += R.get("cx", 0.0)                                  # a closed book lies on the right half of its place
                a = math.radians(R["rot"])
                m["x"] = R["x"] + math.cos(a) * lx - math.sin(a) * ly; m["y"] = R["y"] + math.sin(a) * lx + math.cos(a) * ly
                m["z"] = R["z"] + (R.get("floor", R["h"]) if r == "in" else R["h"]); m["rot"] = R["rot"] + jitter(n, "rot", 4.0)
                if m["noun"] == "cloth" and R["noun"] == "pole":         # a flag: its hoist on the pole, flying along +x
                    m["d"] = 0.12 * m["fly"]; m["h"] = m["hoist"]; m["x"] = R["x"] + 0.011 * R["L"] + m["fly"] / 2; m["y"] = R["y"]
                    m["z"] = R["z"] + R["h"] - 0.017 * R["L"] - m["hoist"]; m["ox"] = -m["fly"] / 2; m["oz"] = m["hoist"]; m["rot"] = 0.0
                    m["flag"] = True
            elif r in ("left_of", "right_of", "beside"):
                sgn = -1 if r == "left_of" else 1
                m["x"] = R["x"] + sgn * (R["w"] / 2 + g + m["w"] / 2); m["y"] = R["y"] - R["d"] / 2 + m["d"] / 2; m["z"] = R["z"]
            elif r in ("behind", "in_front_of", "against"):
                sgn = 1 if r in ("behind", "against") else -1
                m["y"] = R["y"] + sgn * (R["d"] / 2 + g + m["d"] / 2); m["x"] = R["x"]; m["z"] = R["z"]
            elif r == "above":
                m["x"], m["y"], m["z"] = R["x"], R["y"], R["z"] + R["h"] + 0.3 * max(m["L"], 0.1)
            elif r == "under":
                m["x"], m["y"], m["z"] = R["x"], R["y"], 0.0
            elif r == "around":
                sib = [x for x in rel if cast[x]["where"] == ["around", ref]]; idx = sib.index(n); cnt = len(sib)
                rad = 0.5 * math.hypot(R["w"], R["d"]) + g + 0.5 * max(m["w"], m["d"])
                a = math.pi * (1.25 + 1.5 * idx / max(1, cnt - 1 if cnt > 1 else 1)) if cnt > 1 else -math.pi / 2
                m["x"], m["y"], m["z"] = R["x"] + rad * math.cos(a), R["y"] + rad * math.sin(a), R["z"]
            m["placed"] = True
    errs = [f'cast {n}: its "where" refers to a cast member that is never placed' for n in M if not M[n]["placed"]]
    for n, c in cast.items():                                       # what lies in a box must fit inside its walls
        wh = c.get("where") or []
        if len(wh) == 2 and wh[0] == "in" and wh[1] in M and M[wh[1]]["noun"] == "box":
            B = M[wh[1]]
            if max(M[n]["w"], M[n]["d"]) > 0.88 * max(B["w"], B["d"]) or min(M[n]["w"], M[n]["d"]) > 0.88 * min(B["w"], B["d"]):
                errs.append(f"cast {n} is larger than the inside of the box {wh[1]} (make it smaller or the box larger)")
    names = list(M)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = M[a], M[b]
            if abs(A["z"] - B["z"]) > 1e-6 or (a in (groups or {}) and b in (groups or {})): continue
            if overlap(footprint(A), footprint(B)): errs.append(f"cast {a} and {b} overlap on the place")
    return M, errs


# ------------------------------------------------------------------ motion of the cast (channels per frame)
CH = ("dx", "dy", "dz", "rx", "ry", "rz", "sx", "sy", "sz", "presence", "reveal", "burn", "glow", "open", "fold", "wind", "dissolve",
      "split")
OPEN_DEG = {"book": 172.0, "box": 105.0}
WIND0 = 0.22                  # a cloth always moves a little (light air) before a "wave" beat raises the wind
DARK = 0.008                  # what shows of a picture before its light comes on (linear)


def ramp(arr, t, t0, dur, target, shape=None):
    """from the value the channel has at t0 to target over dur (smooth), the earlier part untouched"""
    i0 = int(min(max(round(t0 * FPS), 0), len(arr) - 1)); v0 = arr[i0]
    s = (shape or smooth)((t - t0) / max(dur, 1e-3))
    return np.where(t >= t0, v0 + (target - v0) * s, arr)


def channels(M, beats, T):
    """motion of every member from the beats -> (channels, light spots, labels, errors, extra)
    extra: opens {who: deg}, splits {who: {into, gap}}, writes [..], routes [..]"""
    n = int(round(T * FPS)); t = np.arange(n) / FPS
    C = {k: {c: np.zeros(n) for c in CH} for k in M}
    for k in M:
        for c in ("sx", "sy", "sz", "presence", "reveal"): C[k][c][:] = 1.0
        C[k]["wind"][:] = WIND0
    spots, labels, errs = {}, [], []
    extra = {"opens": {}, "splits": {}, "writes": [], "routes": []}
    cx = float(np.mean([m["x"] for m in M.values()])) if M else 0.0; cy = float(np.mean([m["y"] for m in M.values()])) if M else 0.0
    for who in M:                                                   # the state a member starts in, from its first beat
        mine = [b for b in beats if b["who"] == who]
        f = next((b["do"] for b in mine if b["do"] in ("open", "close")), None)
        if f == "close": C[who]["open"][:] = 1.0
        f = next((b["do"] for b in mine if b["do"] in ("fold", "unfold")), None)
        if f == "unfold": C[who]["fold"][:] = 1.0
        f = next((b["do"] for b in mine if b["do"] in ("split", "assemble")), None)
        if f == "assemble": C[who]["split"][:] = 1.0
    rix = {id(b): k for k, b in enumerate([b for b in beats if b["do"] == "route"])}     # routes numbered in beat order
    for b in beats:                                                 # a route drawn on the ground of a terrain or sea place
        if b["who"] == "place" and b["do"] == "route":
            extra["routes"].append({"who": "place", "path": b["path"], "color": b.get("color", "red"), "t0": float(b["t"]),
                                    "dur": float(b.get("dur", 2.6)), "i": rix[id(b)]})
    by = {}
    for b in beats: by.setdefault(b["who"], []).append(b)
    for who, bs in by.items():
        if who not in M: continue
        ch, m = C[who], M[who]
        L = max(m["L"], 0.05)
        first_in = min((b["t"] for b in bs if b["do"] in ("appear", "drop", "stamp", "slide_in")), default=None)
        if first_in is not None: ch["presence"][t < first_in] = 0.0
        for b in bs:
            v, t0 = b["do"], float(b["t"]); dur = float(b.get("dur", {"appear": 0.8, "vanish": 0.8, "drop": 0.75, "rise": 1.1, "slide": 1.3,
                                                                     "turn": 1.3, "flip": 1.1, "stamp": 0.65, "light": 1.4, "glow": 1.6,
                                                                     "burn": 3.2, "label": T - t0, "open": 1.6, "close": 1.3,
                                                                     "unfold": 2.2, "fold": 1.8, "wave": 1.5, "split": 2.0,
                                                                     "assemble": 2.0, "dissolve": 2.4, "write": 2.5, "route": 2.6,
                                                                     "scatter": 1.2, "stack": 1.3}.get(v, 1.0)))
            x = (t - t0) / max(dur, 1e-3); s = smooth(x); after = t >= t0
            if v == "appear":
                if b.get("how", "fade") == "scale":
                    k_ = ease_out(x) * (1 + 0.05 * np.sin(np.pi * np.clip(x, 0, 1)))
                    for c in ("sx", "sy", "sz"): ch[c] = ch[c] * np.where(after, np.maximum(k_, 1e-3), 1e-3)
                    ch["presence"][after] = 1.0
                else:
                    ch["presence"] = np.where(after, np.maximum(ch["presence"], s), ch["presence"])
            elif v == "vanish":
                ch["presence"] = np.where(after, ch["presence"] * (1 - s), ch["presence"])
            elif v == "drop":
                h0 = float(b.get("from_h", max(0.35, 2.5 * L)))
                fall = np.clip(x / 0.78, 0, 1); z = h0 * (1 - fall ** 2)
                bounce = np.where((x > 0.78) & (x < 1.0), 0.035 * h0 * np.sin(np.pi * (x - 0.78) / 0.22), 0.0)
                ch["dz"] = np.where(after, ch["dz"] + z + bounce, ch["dz"] + h0)
                ch["rz"] = ch["rz"] + np.where(after, jitter(who, "drop", 6.0) * (1 - fall), jitter(who, "drop", 6.0))
                ch["presence"][after] = 1.0
            elif v == "rise":
                ch["dz"] = ch["dz"] + float(b.get("h", 0.12 * L + 0.02)) * s
            elif v == "slide":
                to = b.get("to", [0.25, 0.0])
                if isinstance(to, str) and to in M:
                    R = M[to]; gx = R["x"] + (R["w"] / 2 + GAP * max(m["w"], R["w"]) + m["w"] / 2) - m["x"]; gy = R["y"] - m["y"]
                else: gx, gy = float(to[0]), float(to[1])
                ch["dx"] = ch["dx"] + gx * s; ch["dy"] = ch["dy"] + gy * s
            elif v == "turn":
                ax = {"x": "rx", "y": "ry"}.get(b.get("axis", "z"), "rz")
                ch[ax] = ch[ax] + math.radians(float(b.get("deg", 90))) * s
            elif v == "flip":
                ax = "rx" if b.get("axis", "y") == "x" else "ry"
                ch[ax] = ch[ax] + math.pi * s
                ch["dz"] = ch["dz"] + 0.5 * max(m["w"], m["d"]) * np.sin(np.pi * np.clip(x, 0, 1))
            elif v == "stamp":
                h0 = 0.22 + 2 * L
                desc = np.clip(x / 0.5, 0, 1); z = h0 * (1 - desc ** 2.2)
                sq = np.where((x >= 0.5) & (x <= 1.0), np.sin(np.pi * (x - 0.5) / 0.5), 0.0)
                ch["dz"] = np.where(after, ch["dz"] + z, ch["dz"] + h0)
                ch["sz"] = ch["sz"] * (1 - 0.16 * sq); ch["sx"] = ch["sx"] * (1 + 0.07 * sq); ch["sy"] = ch["sy"] * (1 + 0.07 * sq)
                ch["presence"][after] = 1.0
            elif v == "light":
                lv = smooth((t - t0) / (0.85 * dur)) ** 2.2
                ch["reveal"] = np.where(after, np.maximum(DARK, lv), DARK)
                spots[who] = {"t0": t0, "dur": dur, "how": b.get("how", "spot"), "level": np.where(after, lv, 0.0)}
            elif v == "glow":
                ch["glow"] = np.maximum(ch["glow"], s)
            elif v == "burn":
                ch["burn"] = np.maximum(ch["burn"], np.where(after, 0.3 * smooth(x) + 0.7 * np.clip(x, 0, 1), 0.0))
            elif v == "label":
                labels.append({"who": who, "text": b["text"], "t0": t0 + 0.15, "t1": min(T, t0 + dur)})
            elif v in ("open", "close"):
                if v == "open": extra["opens"][who] = max(extra["opens"].get(who, 0.0), float(b.get("deg", OPEN_DEG.get(m["noun"], 120.0))))
                ch["open"] = ramp(ch["open"], t, t0, dur, 1.0 if v == "open" else 0.0)
            elif v in ("unfold", "fold"):
                ch["fold"] = ramp(ch["fold"], t, t0, dur, 0.0 if v == "unfold" else 1.0)
            elif v == "wave":
                ch["wind"] = ramp(ch["wind"], t, t0, dur, float(np.clip(b.get("wind", 0.7), 0.1, 1.0)))
            elif v in ("split", "assemble"):
                sp = extra["splits"].setdefault(who, {"into": None, "gap": 0.35})
                if b.get("into") is not None: sp["into"] = b["into"]
                if b.get("gap") is not None: sp["gap"] = float(np.clip(b["gap"], 0.05, 1.5))
                ch["split"] = ramp(ch["split"], t, t0, dur, 1.0 if v == "split" else 0.0)
            elif v == "dissolve":
                ch["dissolve"] = ramp(ch["dissolve"], t, t0, dur, 1.0, lambda x: np.clip(x, 0, 1))
                ch["presence"] = np.where(t >= t0 + dur, 0.0, ch["presence"])
            elif v == "write":
                extra["writes"].append({"who": who, "text": str(b["text"]), "t0": t0, "dur": dur})
            elif v == "route":
                extra["routes"].append({"who": who, "path": b["path"], "color": b.get("color", "red"), "t0": t0, "dur": dur,
                                        "i": rix[id(b)]})
            elif v == "scatter":                                         # away from the middle of the cast, with a spin
                vx, vy = m["x"] - cx, m["y"] - cy; r = math.hypot(vx, vy)
                if r < 1e-6: a_ = jitter(who, "scatter", math.pi); vx, vy, r = math.cos(a_), math.sin(a_), 1.0
                k_ = 0.45 * L / r
                ch["dx"] = ch["dx"] + vx * k_ * s; ch["dy"] = ch["dy"] + vy * k_ * s
                ch["rz"] = ch["rz"] + math.radians(jitter(who, "spin", 28.0)) * s
                ch["dz"] = ch["dz"] + 0.12 * L * np.sin(np.pi * np.clip(x, 0, 1))
            elif v == "stack":                                           # onto another member, in an arc
                R = M.get(b.get("on"))
                if R is None: errs.append(f'beat stack on {who}: "on" must name another cast member'); continue
                gz = R["z"] + R["h"] + 0.002 - m["z"]
                ch["dx"] = ch["dx"] + (R["x"] - m["x"]) * s; ch["dy"] = ch["dy"] + (R["y"] - m["y"]) * s
                ch["dz"] = ch["dz"] + gz * s + (0.35 * L + max(gz, 0.0)) * np.sin(np.pi * np.clip(x, 0, 1))
                ch["rz"] = ch["rz"] + math.radians(R["rot"] - m["rot"] + jitter(who, "stack", 3.0)) * s
            else:
                errs.append(f'beat "{v}" on {who}: this tool is not built yet in the workshop')
    return C, spots, labels, errs, extra


# ------------------------------------------------------------------ camera
def cam_dir(el, az):
    e, a = math.radians(el), math.radians(az)
    return np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])


def project(pts, pos, tgt, lens=LENS):
    """normalized image coordinates (u right, v up, 0..1) and depth of world points for a camera at pos looking at tgt"""
    f = tgt - pos; f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0]); r = r / max(np.linalg.norm(r), 1e-9) if np.linalg.norm(r) > 1e-6 else np.array([1.0, 0, 0])
    u = np.cross(r, f)
    q = np.asarray(pts, float) - pos
    z = q @ f; x = q @ r; y = q @ u
    sw = SENSOR / lens; sh = sw / ASPECT
    return np.stack([0.5 + x / np.maximum(z, 1e-6) / sw, 0.5 + y / np.maximum(z, 1e-6) / sh], -1), z


def box_points(m, C=None, fr=None):
    """corners of a cast member (its box), at rest or at a frame of its motion (pieces moving apart, an open lid)"""
    dx = dy = dz = 0.0; k = 1.0; up = 0.0
    if C is not None and fr is not None:
        dx, dy, dz = C["dx"][fr], C["dy"][fr], C["dz"][fr]
        if C["split"][fr] > 1e-4: k = 1.0 + 1.4 * m.get("gap", 0.35) * C["split"][fr]; up = 0.15 * m["L"] * C["split"][fr]
        up += m.get("h_open", 0.0) * C["open"][fr]
    fp = footprint(dict(m, w=m["w"] * k, d=m["d"] * k), m["x"] + dx, m["y"] + dy)
    z0 = m["z"] + dz; z1 = z0 + max(m["h"], 0.002) + up
    return np.array([[x, y, z] for x, y in fp for z in (z0, z1)])


def fit(pts, tgt, el, az, margin=0.08, lens=LENS):
    """distance at which all points are inside the frame with the margin"""
    lo, hi = 0.05, 400.0
    d = cam_dir(el, az)
    for _ in range(48):
        mid = math.sqrt(lo * hi); uv, z = project(pts, tgt + mid * d, tgt, lens)
        ok = (z > 0.02).all() and (uv >= margin).all() and (uv <= 1 - margin).all()
        hi, lo = (mid, lo) if ok else (hi, mid)
    return hi


def catmull(P, k=24):
    """centripetal Catmull-Rom through the points P (m, 2|3) -> dense polyline"""
    P = np.asarray(P, float)
    if len(P) < 2: return P
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]]); out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0; t1 = t0 + max(np.linalg.norm(p1 - p0) ** 0.5, 1e-6); t2 = t1 + max(np.linalg.norm(p2 - p1) ** 0.5, 1e-6)
        t3 = t2 + max(np.linalg.norm(p3 - p2) ** 0.5, 1e-6)
        for tt in np.linspace(t1, t2, k, endpoint=False):
            a1 = (t1 - tt) / (t1 - t0) * p0 + (tt - t0) / (t1 - t0) * p1; a2 = (t2 - tt) / (t2 - t1) * p1 + (tt - t1) / (t2 - t1) * p2
            a3 = (t3 - tt) / (t3 - t2) * p2 + (tt - t2) / (t3 - t2) * p3
            b1 = (t2 - tt) / (t2 - t0) * a1 + (tt - t0) / (t2 - t0) * a2; b2 = (t3 - tt) / (t3 - t1) * a2 + (tt - t1) / (t3 - t1) * a3
            out.append((t2 - tt) / (t2 - t1) * b1 + (tt - t1) / (t2 - t1) * b2)
    out.append(P[-1])
    return np.array(out)


def fly_path(pts, ground, span):
    """a flight over a terrain along ground points (x, y) in order: the camera keeps a clear height over the ground ahead
    and looks at the path a little ahead of it. ground(x, y) -> height (vectorised). returns f(u) -> (position, target)"""
    xy = catmull(np.asarray(pts, float)[:, :2]); seg = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]; total = max(s[-1], 1e-6)
    look, alt = 0.16 * span, 0.055 * span
    d_end = (xy[-1] - xy[-2]) / max(np.linalg.norm(xy[-1] - xy[-2]), 1e-9)
    def at(sv):
        sv = np.atleast_1d(sv); p = np.stack([np.interp(sv, s, xy[:, 0]), np.interp(sv, s, xy[:, 1])], -1)
        over = np.maximum(sv - total, 0.0)[:, None]
        return p + over * d_end
    ss = np.linspace(0, total, 240)
    gz = np.array([ground(*at(np.linspace(v, v + look, 9)).T).max() for v in ss])       # the ground ahead of the camera
    cz = np.convolve(np.pad(gz, 12, mode="edge"), np.ones(25) / 25, mode="valid") + alt
    def f(u):
        sv = float(np.clip(u, 0, 1)) * total; p2 = at(sv)[0]; t2 = at(sv + look)[0]
        return np.array([p2[0], p2[1], float(np.interp(sv, ss, cz))]), np.array([t2[0], t2[1], float(ground(t2[:1], t2[1:])[0])])
    return f


def camera(entries, M, C, T, place, labels=(), fly=None, extra_pts=None):
    """per-frame camera: target, distance, azimuth, elevation, focus point, f-stop
    labels: cast members that carry a label (the framing keeps room for it under them)
    fly: {entry index: f(u) -> (position, target)} for "fly" entries (fly_path); extra_pts: what to frame when there is no cast"""
    n = int(round(T * FPS)); t = np.arange(n) / FPS
    names = list(M)
    E0 = ELEV.get(place, 40.0); A0 = -90.0 + jitter("camera", place, 7.0)

    def pts_of(name, w=None):
        """every place the member(s) will be while on their support during the frames w = (f0, f1) of a shot (the whole
        scene when w is None; falling in from above the frame is not framed)"""
        out = []
        f0, f1 = (0, n - 1) if w is None else (max(0, min(n - 1, w[0])), max(0, min(n - 1, w[1])))
        for k in ([name] if name else names):
            ch, m = C[k], M[k]
            frs = [fi for fi in list(range(f0, f1 + 1, 15)) + [f1] if ch["presence"][fi] >= 0.5 and abs(ch["dz"][fi]) < 0.05 + 0.2 * m["h"]]
            if not frs and w is not None:                            # not there in this shot: where it is in the scene
                frs = [fi for fi in list(range(0, n, 15)) + [n - 1] if ch["presence"][fi] >= 0.5 and abs(ch["dz"][fi]) < 0.05 + 0.2 * m["h"]]
            out += [box_points(m, ch, fi) for fi in frs] or [box_points(m)]
            if k in labels:                                         # the label sits under the member's front edge
                q = box_points(m); q[:, 1] -= 0.18 * max(m["d"], 0.1); out.append(q)
        return np.concatenate(out) if out else np.asarray(extra_pts, float)

    def center(p): return 0.5 * (p.min(0) + p.max(0))

    def frame_state(kind, name, st, w=None):
        p = pts_of(name, w); c = center(p)
        el = {"top": 86.0, "low": 14.0}.get(kind, st["E"] if st else E0)
        az = st["A"] if st else A0
        marg = 0.12 if kind == "close" else 0.08
        return {"T": c, "A": az, "E": el, "D": fit(p, c, el, az, marg), "focus": name, "fstop": 5.6, "pts": name}

    def offset(name, tt):
        fi = int(min(max(round(tt * FPS), 0), n - 1)); cc = C[name]
        return np.array([cc["dx"][fi], cc["dy"][fi], cc["dz"][fi]])

    es = sorted(entries, key=lambda e: e["t"])
    first = es[0]
    win = lambda t0_, t1_: (int(round(t0_ * FPS)), int(round(min(t1_, T) * FPS)) - 1)
    st = frame_state(first["move"] if first["move"] in ("wide", "close", "top", "low") else "wide", first.get("to"), None,
                     win(0.0, es[1]["t"] if len(es) > 1 else T))
    if first["move"] == "fly" and fly and 0 in fly:                 # a flight from the first frame: it starts on its path
        p0, t0_ = fly[0](0.0); v = p0 - t0_; dd = float(np.linalg.norm(v))
        st = dict(st, T=t0_, D=dd, A=math.degrees(math.atan2(v[1], v[0])), E=math.degrees(math.asin(np.clip(v[2] / dd, -1, 1))))
        p1, t1 = fly[0](1.0); v = p1 - t1; dd = float(np.linalg.norm(v))
        g0 = dict(st, T=t1, D=dd, A=math.degrees(math.atan2(v[1], v[0])), E=math.degrees(math.asin(np.clip(v[2] / dd, -1, 1))),
                  fly=fly[0], pts=None)
        nxt = es[1]["t"] if len(es) > 1 else T
        first = dict(first, _fly0=(float(first.get("dur", nxt)), g0))
    states = [(0.0, 0.0, st, st)]                                   # (start, duration, from, to)
    cur = st
    if first.get("_fly0"):
        states = [(0.0, first["_fly0"][0], st, first["_fly0"][1])]; cur = first["_fly0"][1]
    for i, e in enumerate(es[1:], 1):
        mv, nm = e["move"], e.get("to")
        nxt = es[i + 1]["t"] if i + 1 < len(es) else T
        dur = float(e.get("dur", max(0.8, min(nxt - e["t"], 2.6))))
        if cur.get("track") and mv != "track":                         # leave a tracking shot from where it got to
            cur = dict(cur, T=cur["T"] + offset(cur["track"], e["t"]), track=None)
        g = dict(cur); g.pop("rack_from", None)
        w = win(float(e["t"]), nxt)                                    # what this shot shows: from its start to the next one
        if mv in ("wide", "close", "top", "low"): g = frame_state(mv, nm, cur, w)
        elif mv == "push":                                             # always closer than before
            if nm: g = frame_state("close", nm, cur, w); g["D"] = min(g["D"], 0.8 * cur["D"])
            else: g["D"] = cur["D"] * 0.62
        elif mv == "pull":
            g = frame_state("wide", None, cur, w) if not nm else frame_state("wide", nm, cur, w); g["D"] = max(g["D"], cur["D"] * 1.5)
        elif mv in ("orbit", "crane", "tilt"):
            p_ = pts_of(nm if nm else g.get("pts"), w)
            g["T"] = center(p_)                                        # the move ends framed on what is there by then
            if nm: g["pts"] = nm
            if mv == "orbit": g["A"] = cur["A"] + float(e.get("deg", 35))
            elif mv == "crane": g["E"] = min(86.0, cur["E"] + float(e.get("h", 0.3)) * 50.0)
            else: g["E"] = float(np.clip(cur["E"] + float(e.get("deg", -15)), 6.0, 88.0))
            g["D"] = fit(p_, g["T"], g["E"], g["A"], 0.08)
        elif mv == "dolly":
            a = math.radians(cur["A"] + 90.0); sd = float(e.get("side", 1.0))
            g["T"] = cur["T"] + sd * 0.28 * cur["D"] * np.array([math.cos(a), math.sin(a), 0.0])
        elif mv == "rack":
            g["focus"] = nm; g["fstop"] = 2.8; g["rack_from"] = e.get("from", cur["focus"])
        elif mv == "track":
            g["track"] = nm
        elif mv == "fly" and fly and i in fly:
            p1, t1 = fly[i](1.0); v = p1 - t1; dd = float(np.linalg.norm(v))
            g.update(T=t1, D=dd, A=math.degrees(math.atan2(v[1], v[0])), E=math.degrees(math.asin(np.clip(v[2] / dd, -1, 1))),
                     fly=fly[i], pts=None)
        if nm and mv not in ("rack",): g["focus"] = nm
        states.append((float(e["t"]), dur, cur, g)); cur = g
    # a clean frame while the camera holds: the subject whole, and every small thing either whole in the frame or out of it
    # (the distance of the hold is moved as little as possible until that is true)
    def framed(st, fi, D_):
        pos = st["T"] + D_ * cam_dir(st["E"], st["A"]); bad = 0
        for k in names:
            if C[k]["presence"][fi] < 0.5: continue
            uv, z = project(box_points(M[k], C[k], fi), pos, st["T"])
            if (z <= 0.02).any(): return False
            safe = ((uv[:, 0] >= SAFE[0]) & (uv[:, 0] <= SAFE[1]) & (uv[:, 1] >= SAFE[2]) & (uv[:, 1] <= SAFE[3])).all()
            if st.get("pts") in (None, k):
                if not safe: return False
                continue
            seen = ((uv >= 0) & (uv <= 1)).all(1).any() or not (uv[:, 0].max() < 0 or uv[:, 0].min() > 1 or uv[:, 1].max() < 0 or uv[:, 1].min() > 1)
            span = uv.max(0) - uv.min(0)
            if seen and not safe and (span < 0.5).all(): bad += 1
        return bad == 0

    for i, (t0, dur, a, b) in enumerate(states):
        h0 = t0 + dur; h1 = states[i + 1][0] if i + 1 < len(states) else T
        if h1 - h0 <= 1e-6 or b.get("track") or b.get("fly"): continue          # even a short hold at the end is clean
        f0, f1 = int(min(n - 1, round(h0 * FPS))), int(min(n - 1, round(h1 * FPS)))
        shrink = 1 - DRIFT * (h1 - h0) / 5.0
        for f in [1.0] + sorted(np.geomspace(0.7, 1.8, 41), key=lambda x: abs(math.log(x))):
            if framed(b, f0, b["D"] * f) and framed(b, f1, b["D"] * f * shrink):
                if abs(f - 1) > 1e-9: b["D"] *= f; b["cleaned"] = round(float(f), 3)
                break

    TG = np.zeros((n, 3)); D = np.zeros(n); A = np.zeros(n); E = np.zeros(n); FS = np.zeros(n); FOC = [None] * n
    SUBJ, STEADY = [None] * n, np.zeros(n, bool)
    for fi in range(n):
        tt = t[fi]
        k = max(i for i, s in enumerate(states) if s[0] <= tt + 1e-9)
        t0, dur, a, b = states[k]
        x = float(smooth((tt - t0) / dur)) if dur > 0 else 1.0
        if b.get("fly"):                                           # on the flight path (joined smoothly from the shot before)
            u = float(np.clip((tt - t0) / dur, 0, 1)) if dur > 0 else 1.0
            u = u * u * (3 - 2 * u) if len(states) == 1 or k == 0 else u ** 1.6 / (u ** 1.6 + (1 - u) ** 1.6)
            p_, tg_ = b["fly"](u)
            if a is not b and not a.get("fly") and k > 0:
                w_ = float(smooth(u / 0.25)); p_ = cam_pos_state(a) * (1 - w_) + p_ * w_; tg_ = a["T"] * (1 - w_) + tg_ * w_
            v = p_ - tg_; dd = max(float(np.linalg.norm(v)), 1e-6)
            hold = max(0.0, tt - (t0 + dur)); dd *= 1 - DRIFT * hold / 5.0
            TG[fi] = tg_; D[fi] = dd; A[fi] = math.degrees(math.atan2(v[1], v[0])); E[fi] = math.degrees(math.asin(np.clip(v[2] / dd, -1, 1)))
            FS[fi] = 8.0; SUBJ[fi] = None; STEADY[fi] = False; FOC[fi] = (None, None, 1.0)
            continue
        tg = a["T"] * (1 - x) + b["T"] * x
        if b.get("track") and b["track"] in C:
            cc = C[b["track"]]; tg = tg + np.array([cc["dx"][fi], cc["dy"][fi], cc["dz"][fi]]) * x
        d = math.exp(math.log(a["D"]) * (1 - x) + math.log(b["D"]) * x)
        hold = max(0.0, tt - (t0 + dur))
        d *= 1 - DRIFT * hold / 5.0
        TG[fi] = tg; D[fi] = d; A[fi] = a["A"] * (1 - x) + b["A"] * x; E[fi] = a["E"] * (1 - x) + b["E"] * x
        FS[fi] = b.get("fstop") or 5.6
        SUBJ[fi] = b.get("pts"); STEADY[fi] = x >= 1.0
        FOC[fi] = (b.get("rack_from"), b.get("focus"), x) if b.get("rack_from") else (None, b.get("focus"), 1.0)
    return {"target": TG, "dist": D, "az": A, "el": E, "fstop": FS, "focus": FOC, "states": states, "subject": SUBJ, "steady": STEADY}


def cam_pos(cam, fi): return cam["target"][fi] + cam["dist"][fi] * cam_dir(cam["el"][fi], cam["az"][fi])


def cam_pos_state(st): return st["T"] + st["D"] * cam_dir(st["E"], st["A"])


def key_frames(beats, entries, T, k=6):
    n = int(round(T * FPS)); cand = []
    for b in beats:
        d = float(b.get("dur", 1.0)) if b["do"] != "label" else 1.0
        cand.append(b["t"] + 0.6 * min(d, 2.0))
    for e in entries[1:]: cand.append(e["t"] + 0.5 * float(e.get("dur", 1.6)))
    cand.append(T - 0.3)
    fr = sorted({int(min(max(round(c * FPS) + 1, 1), n)) for c in cand})
    out = []
    for f in fr:
        if all(abs(f - g) >= 6 for g in out): out.append(f)
    while len(out) > k:                                            # keep the most spread
        gaps = [(out[i + 1] - out[i - 1], i) for i in range(1, len(out) - 1)]
        out.pop(min(gaps)[1])
    for f in np.linspace(1, n, k + 2)[1:-1].round().astype(int):
        if len(out) >= k: break
        if all(abs(f - g) >= 6 for g in out): out.append(int(f))
    return sorted(out)[:k]
