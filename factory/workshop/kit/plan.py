"""Pure geometry of a described 3D scene (numpy only, no Blender): sizes of the cast, layout on the place, the motion of
every cast member from the beats, the camera path from the camera entries, key frames. Units: metres, z up, the place's
surface at z = 0, the camera at azimuth -90 looks along +y."""
import hashlib, math
import numpy as np

FPS = 30
SIZE = {"sheet": 0.42, "print": 0.24, "canvas": 0.55, "cutout": 0.5, "cloth": 0.9, "tile": 0.5, "block": 0.30, "book": 0.28,
        "box": 0.30, "disc": 0.06, "globe": 0.40, "model": 0.30, "text": 0.07, "pole": 1.8, "table": 1.4, "plinth": 1.0,
        "frame": 0.50, "wall": 3.0, "candle": 0.16}
SML = {"S": 0.6, "M": 1.0, "L": 1.6}
BORDER = 0.05                 # white margin of a print (share of its long side)
GAP = 0.22                    # free space between two cast members side by side (share of the larger one)
ELEV = {"desk": 52.0, "museum": 48.0, "floor": 38.0, "wall": 8.0, "void": 30.0, "sky": 12.0, "terrain": 35.0, "sea": 20.0}
LENS, SENSOR, ASPECT = 50.0, 36.0, 16 / 9
DRIFT = 0.012                 # the camera never stops: a slow push-in of 1.2 % of the distance per 5 s while it holds
BUILT = {"nouns": {"sheet", "print", "canvas", "disc", "block", "text", "pole", "plinth", "table", "frame", "candle"},
         "verbs": {"appear", "vanish", "drop", "rise", "slide", "turn", "flip", "stamp", "light", "label", "glow", "burn"},
         "moves": {"wide", "close", "top", "low", "push", "pull", "orbit", "crane", "dolly", "tilt", "hold", "rack", "track"},
         "places": {"desk", "museum", "floor", "void"}, "weather": {"clear"}, "output": {"film"}}


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
def dims(c, aspect=None):
    """footprint (w along x, d along y), height h, picture size (iw, ih) of a cast member lying on the place"""
    noun = c["is"]; s = c.get("size", "M")
    L = float(s) if isinstance(s, (int, float)) else SIZE[noun] * SML.get(s, 1.0)
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
    if noun == "pole": return {"w": 0.06, "d": 0.06, "h": L, "L": L}
    if noun == "plinth": return {"w": 0.5 * L, "d": 0.5 * L, "h": L, "L": L}
    if noun == "table": return {"w": L, "d": 0.58 * L, "h": 0.75, "L": L}
    if noun == "candle": return {"w": 0.05, "d": 0.05, "h": L, "L": L}
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


def layout(cast, aspects, sizes=None):
    """positions of the cast: 'where' relations first, the rest in a row on the place (bottom edges aligned)
    sizes: measured sizes that replace the estimates (text)"""
    M = {}
    for n, c in cast.items():
        d = dims(c, aspects.get(n)); d.update((sizes or {}).get(n, {}))
        d.update(name=n, noun=c["is"], z=0.0, x=0.0, y=0.0, rot=0.0, placed=False)
        if c["is"] in ("sheet", "print", "canvas", "frame", "block", "text"): d["rot"] = jitter(n, "rot", 2.2)
        M[n] = d
    row = [n for n, c in cast.items() if not c.get("where") or c["where"][1] == "place"]
    rel = [n for n in cast if n not in row]
    if row:
        gap = GAP * max(M[n]["w"] for n in row)
        total = sum(M[n]["w"] for n in row) + gap * (len(row) - 1)
        x = -total / 2; dmax = max(M[n]["d"] for n in row)
        for n in row:
            m = M[n]; m["x"] = x + m["w"] / 2; m["y"] = -dmax / 2 + m["d"] / 2 + jitter(n, "y", 0.02 * dmax); x += m["w"] + gap
            m["placed"] = True
    for _ in range(len(rel) + 1):
        for n in rel:
            m = M[n]
            if m["placed"]: continue
            r, ref = cast[n]["where"]
            R = M.get(ref)
            if R is None or not R["placed"]: continue
            g = GAP * max(m["w"], R["w"])
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
                a = math.radians(R["rot"])
                m["x"] = R["x"] + math.cos(a) * lx - math.sin(a) * ly; m["y"] = R["y"] + math.sin(a) * lx + math.cos(a) * ly
                m["z"] = R["z"] + R["h"]; m["rot"] = R["rot"] + jitter(n, "rot", 4.0)
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
    names = list(M)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = M[a], M[b]
            if abs(A["z"] - B["z"]) > 1e-6: continue
            if overlap(footprint(A), footprint(B)): errs.append(f"cast {a} and {b} overlap on the place")
    return M, errs


# ------------------------------------------------------------------ motion of the cast (channels per frame)
CH = ("dx", "dy", "dz", "rx", "ry", "rz", "sx", "sy", "sz", "presence", "reveal", "burn", "glow")
DARK = 0.008                  # what shows of a picture before its light comes on (linear)


def channels(M, beats, T):
    n = int(round(T * FPS)); t = np.arange(n) / FPS
    C = {k: {c: np.zeros(n) for c in CH} for k in M}
    for k in M:
        for c in ("sx", "sy", "sz", "presence", "reveal"): C[k][c][:] = 1.0
    spots, labels, errs = {}, [], []
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
                                                                     "burn": 3.2, "label": T - t0}.get(v, 1.0)))
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
            else:
                errs.append(f'beat "{v}" on {who}: this tool is not built yet in the workshop')
    return C, spots, labels, errs


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
    """corners of a cast member (its box), at rest or at a frame of its motion"""
    dx = dy = dz = 0.0
    if C is not None and fr is not None: dx, dy, dz = C["dx"][fr], C["dy"][fr], C["dz"][fr]
    fp = footprint(m, m["x"] + dx, m["y"] + dy)
    z0 = m["z"] + dz; z1 = z0 + max(m["h"], 0.002)
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


def camera(entries, M, C, T, place):
    """per-frame camera: target, distance, azimuth, elevation, focus point, f-stop"""
    n = int(round(T * FPS)); t = np.arange(n) / FPS
    names = list(M)
    E0 = ELEV.get(place, 40.0); A0 = -90.0 + jitter("camera", place, 7.0)

    def pts_of(name):
        """every place the member(s) will be while on their support (falling in from above the frame is not framed)"""
        out = []
        for k in ([name] if name else names):
            ch, m = C[k], M[k]
            frs = [fi for fi in list(range(0, n, 15)) + [n - 1] if ch["presence"][fi] >= 0.5 and abs(ch["dz"][fi]) < 0.05 + 0.2 * m["h"]]
            out += [box_points(m, ch, fi) for fi in frs] or [box_points(m)]
        return np.concatenate(out)

    def center(p): return 0.5 * (p.min(0) + p.max(0))

    def frame_state(kind, name, st):
        p = pts_of(name); c = center(p)
        el = {"top": 86.0, "low": 14.0}.get(kind, st["E"] if st else E0)
        az = st["A"] if st else A0
        marg = 0.12 if kind == "close" else 0.08
        return {"T": c, "A": az, "E": el, "D": fit(p, c, el, az, marg), "focus": name, "fstop": 5.6, "pts": name}

    def offset(name, tt):
        fi = int(min(max(round(tt * FPS), 0), n - 1)); cc = C[name]
        return np.array([cc["dx"][fi], cc["dy"][fi], cc["dz"][fi]])

    es = sorted(entries, key=lambda e: e["t"])
    first = es[0]
    st = frame_state(first["move"] if first["move"] in ("wide", "close", "top", "low") else "wide", first.get("to"), None)
    states = [(0.0, 0.0, st, st)]                                   # (start, duration, from, to)
    cur = st
    for i, e in enumerate(es[1:], 1):
        mv, nm = e["move"], e.get("to")
        nxt = es[i + 1]["t"] if i + 1 < len(es) else T
        dur = float(e.get("dur", max(0.8, min(nxt - e["t"], 2.6))))
        if cur.get("track") and mv != "track":                         # leave a tracking shot from where it got to
            cur = dict(cur, T=cur["T"] + offset(cur["track"], e["t"]), track=None)
        g = dict(cur); g.pop("rack_from", None)
        if mv in ("wide", "close", "top", "low"): g = frame_state(mv, nm, cur)
        elif mv == "push":                                             # always closer than before
            if nm: g = frame_state("close", nm, cur); g["D"] = min(g["D"], 0.8 * cur["D"])
            else: g["D"] = cur["D"] * 0.62
        elif mv == "pull":
            g = frame_state("wide", None, cur) if not nm else frame_state("wide", nm, cur); g["D"] = max(g["D"], cur["D"] * 1.5)
        elif mv in ("orbit", "crane", "tilt"):
            if nm: g["T"] = center(pts_of(nm)); g["pts"] = nm               # the move ends framed on that member
            if mv == "orbit": g["A"] = cur["A"] + float(e.get("deg", 35))
            elif mv == "crane": g["E"] = min(86.0, cur["E"] + float(e.get("h", 0.3)) * 50.0)
            else: g["E"] = float(np.clip(cur["E"] + float(e.get("deg", -15)), 6.0, 88.0))
            g["D"] = fit(pts_of(g["pts"]), g["T"], g["E"], g["A"], 0.08)
        elif mv == "dolly":
            a = math.radians(cur["A"] + 90.0); sd = float(e.get("side", 1.0))
            g["T"] = cur["T"] + sd * 0.28 * cur["D"] * np.array([math.cos(a), math.sin(a), 0.0])
        elif mv == "rack":
            g["focus"] = nm; g["fstop"] = 2.8; g["rack_from"] = e.get("from", cur["focus"])
        elif mv == "track":
            g["track"] = nm
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
            subject = st.get("pts") in (None, k)
            if subject:
                if (uv < 0.03).any() or (uv > 0.97).any(): return False
                continue
            inside = ((uv >= 0) & (uv <= 1)).all(1)
            span = uv.max(0) - uv.min(0)
            if inside.any() and not inside.all() and (span < 0.5).all(): bad += 1
        return bad == 0

    for i, (t0, dur, a, b) in enumerate(states):
        h0 = t0 + dur; h1 = states[i + 1][0] if i + 1 < len(states) else T
        if h1 - h0 < 0.3 or b.get("track"): continue
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
