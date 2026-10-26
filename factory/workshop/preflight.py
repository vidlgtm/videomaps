"""Workshop preflight: strict check and normalisation of every piece of an order before anything is downloaded or
rendered. All problems are reported at once; nothing runs while one is left.
- unknown parameters, wrong types, values out of range, inconsistent combinations -> error
- fly: the camera must stay inside the region; ground the camera sees nearby that lies outside the region extends the
  region automatically (noted), so no low-detail ground shows up close to the lens
- every piece gets a time budget for the GPU render (seconds x template rate, or budget_min)"""
import copy, math

FPS = 30


class Report:
    def __init__(self): self.errors, self.notes = [], []


def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class Piece:
    def __init__(self, rep, pid, params):
        self.rep, self.pid, self.p = rep, pid, params

    def bad(self, msg): self.rep.errors.append(f"{self.pid}: {msg}")
    def note(self, msg): self.rep.notes.append(f"{self.pid}: {msg}")

    def known(self, allowed):
        extra = sorted(set(self.p) - set(allowed))
        if extra: self.bad(f"unknown parameter(s) {', '.join(extra)} (allowed: {', '.join(sorted(allowed))})")

    def number(self, k, lo, hi, required=False, src=None):
        src = self.p if src is None else src
        if k not in src:
            if required: self.bad(f"'{k}' is required")
            return None
        v = src[k]
        if not _num(v) or not lo <= v <= hi:
            self.bad(f"'{k}' must be a number in [{lo}, {hi}] (got {v!r})"); return None
        return v

    def choice(self, k, opts, required=False):
        if k not in self.p:
            if required: self.bad(f"'{k}' is required ({' | '.join(opts)})")
            return None
        if self.p[k] not in opts: self.bad(f"'{k}' must be one of {' | '.join(opts)} (got {self.p[k]!r})"); return None
        return self.p[k]


# ------------------------------------------------------------------ web mercator helpers
def merc(Z):
    N = 256 * 2 ** Z
    mx = lambda lon: (lon + 180) / 360 * N
    my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
    ilon = lambda x: x / N * 360 - 180
    ilat = lambda y: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / N))))
    return N, mx, my, ilon, ilat


def auto_zoom(lon0, lon1): return max(6, min(12, math.floor(math.log2(9000 * 360 / (256 * (lon1 - lon0))))))


def _cr(p0, p1, p2, p3, s):
    return tuple(0.5 * ((2 * b) + (-a + c) * s + (2 * a - 5 * b + 4 * c - d) * s * s + (-a + 3 * b - 3 * c + d) * s ** 3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def _interp(keys, t, idx):
    ts = [k[0] for k in keys]
    if t <= ts[0]: return keys[0][idx]
    if t >= ts[-1]: return keys[-1][idx]
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    s = (t - ts[i]) / (ts[i + 1] - ts[i])
    g = lambda j: keys[min(max(j, 0), len(keys) - 1)][idx]
    return _cr(g(i - 1), g(i), g(i + 1), g(i + 2), s)


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / n for x in v)


def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def fly_footprint(p, sec):
    """extends the bbox until every ground point the camera sees closer than the ring-detail limit lies inside it
    (10 % margin over the preview check for the difference between this spline and Blender's)"""
    notes = []
    for _ in range(4):
        lon0, lon1, lat0, lat1 = p["bbox"]
        Z = int(p.get("zoom") or auto_zoom(lon0, lon1)); N, mx, my, ilon, ilat = merc(Z)
        x0, x1, y0, y1 = mx(lon0), mx(lon1), my(lat1), my(lat0); W, H = x1 - x0, y1 - y0
        mpp = 40075016.686 * math.cos(math.radians((lat0 + lat1) / 2)) / N
        ex = float(p.get("exaggeration", 2.6))
        P3 = lambda lon, lat, alt: (mx(lon) - x0, -(my(lat) - y0), alt * 1000 * ex / mpp)
        keys = [(float(k["t"]), P3(*k["cam"]), P3(*k["look"])) for k in p["path"]]
        thx = 18.0 / float(p.get("lens", 30)); thy = thx * 1080 / 1920
        # the ring is 2 zoom levels coarser (texel = 4 region px): ground closer than where a ring texel covers
        # 2 screen pixels must be region ground (the preview check uses the same limit)
        near, m = 4.0 / (2 * (36.0 / float(p.get("lens", 30))) / 1920) * 1.1, 0.02 * max(W, H)
        out = []
        for i in range(int(sec * 4) + 1):
            t = min(sec, i / 4)
            c, l = _interp(keys, t, 1), _interp(keys, t, 2)
            f = _norm(tuple(b - a for a, b in zip(c, l))); r = _norm(_cross(f, (0, 0, 1))); u = _cross(r, f)
            for a, b in [(-1 + i_ / 4, -1 + j_ / 10) for i_ in range(9) for j_ in range(21)]:
                d = _norm(tuple(f[k] + r[k] * a * thx + u[k] * b * thy for k in range(3)))
                if d[2] >= -1e-6: continue
                s = -c[2] / d[2]
                if s > near: continue
                hx, hy = c[0] + s * d[0], c[1] + s * d[1]
                if not (m <= hx <= W - m and -H + m <= hy <= -m): out.append((hx, hy))
        if not out: return notes
        xs = [0.0, W] + [h[0] for h in out]; ys = [0.0, -H] + [h[1] for h in out]
        pad = 0.05 * max(W, H)
        nx0, nx1 = min(xs) - pad * (min(xs) < m), max(xs) + pad * (max(xs) > W - m)
        ny0, ny1 = min(ys) - pad * (min(ys) < -H + m), max(ys) + pad * (max(ys) > -m)
        nb = [round(ilon(x0 + nx0), 3), round(ilon(x0 + nx1), 3), round(ilat(y0 - ny0), 3), round(ilat(y0 - ny1), 3)]
        notes.append(f"region extended {p['bbox']} -> {nb}: the camera sees nearby ground outside it")
        p["bbox"] = nb
    return notes


# ------------------------------------------------------------------ templates
PRESETS = {"gold", "red", "orange", "white", "blue"}
FLY_KEYS = {"bbox", "zoom", "sea", "borders", "highlight", "styles", "places", "labels", "path", "exaggeration", "snow",
            "sun", "lens", "samples", "haze", "saturation", "look"}


def check_fly(c, sec):
    p = c.p
    c.known(FLY_KEYS)
    bb = p.get("bbox")
    if not (isinstance(bb, list) and len(bb) == 4 and all(_num(v) for v in bb)):
        c.bad("'bbox' must be [lon0, lon1, lat0, lat1]"); return
    lon0, lon1, lat0, lat1 = bb
    if not (-180 <= lon0 < lon1 <= 180 and -75 <= lat0 < lat1 <= 75): c.bad("bbox: lon0 < lon1, lat0 < lat1, |lat| <= 75"); return
    if lon1 - lon0 > 16 or lat1 - lat0 > 12: c.bad("bbox too large for one fly-over (max 16 x 12 degrees)")
    if lon1 - lon0 < 0.5 or lat1 - lat0 < 0.4: c.bad("bbox too small (min 0.5 x 0.4 degrees)")
    c.number("zoom", 6, 12); c.number("sea", -50, 50); c.number("exaggeration", 1, 5); c.number("lens", 18, 85)
    c.number("samples", 16, 256); c.number("haze", 0.2, 1.0); c.number("saturation", 0.6, 1.6); c.choice("look", ("punchy", "base"))
    sun = p.get("sun", {})
    if not isinstance(sun, dict) or set(sun) - {"elevation", "azimuth"}: c.bad("'sun' must be {elevation, azimuth}")
    else: c.number("elevation", 10, 70, src=sun); c.number("azimuth", 0, 360, src=sun)
    if "snow" in p and not (isinstance(p["snow"], list) and len(p["snow"]) == 2 and all(_num(v) for v in p["snow"]) and 0 <= p["snow"][0] < p["snow"][1] <= 9000):
        c.bad("'snow' must be [m0, m1] with 0 <= m0 < m1 <= 9000")
    cs = p.get("borders", {}).get("countries", []) if isinstance(p.get("borders", {}), dict) else None
    if cs is None or not all(isinstance(x, str) and len(x) == 3 and x.isupper() for x in cs): c.bad("'borders' must be {countries: [ISO3, ...]}")
    hk = []
    for h in p.get("highlight", []):
        if not isinstance(h, dict) or not isinstance(h.get("key"), str): c.bad("each highlight needs a 'key'"); continue
        hk.append(h["key"])
        kinds = [k for k in ("admin0", "admin1", "disputed") if k in h]
        if len(kinds) != 1: c.bad(f"highlight {h['key']}: exactly one of admin0 | admin1 (+ country) | disputed"); continue
        if kinds[0] == "admin1" and not (isinstance(h["admin1"], list) and isinstance(h.get("country"), str)): c.bad(f"highlight {h['key']}: admin1 is a list of names + 'country' ISO3")
        if set(h) - {"key", "admin0", "admin1", "country", "disputed"}: c.bad(f"highlight {h['key']}: unknown fields")
    if len(set(hk)) != len(hk): c.bad("highlight keys must be unique")
    for k, s in p.get("styles", {}).items():
        if k not in hk and k != "intl": c.bad(f"style for unknown line '{k}' (lines: intl, {', '.join(hk) or '-'})")
        if not (s in PRESETS or (isinstance(s, list) and len(s) == 5 and all(_num(v) for v in s))):
            c.bad(f"style '{k}' must be one of {', '.join(sorted(PRESETS))} or [r, g, b, strength, width]")
    places = p.get("places", {})
    for k, v in places.items():
        if not (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)): c.bad(f"place {k}: [lon, lat]"); continue
        if not (lon0 <= v[0] <= lon1 and lat0 <= v[1] <= lat1): c.bad(f"place {k} lies outside the bbox")
    for e in p.get("labels", []):
        if not (isinstance(e, list) and 1 <= len(e) <= 3 and all(isinstance(x, str) for x in e)): c.bad(f"label {e!r}: [place, display, style]"); continue
        if e[0] not in places: c.bad(f"label {e[0]}: not in places")
        if len(e) > 2 and e[2] not in ("", "hot", "sea"): c.bad(f"label {e[0]}: style must be '', 'hot' or 'sea'")
    path = p.get("path")
    if not (isinstance(path, list) and len(path) >= 2): c.bad("'path' needs at least 2 keys"); return
    ts = []
    for k in path:
        ok = isinstance(k, dict) and set(k) == {"t", "cam", "look"} and _num(k.get("t")) and all(
            isinstance(k.get(x), list) and len(k[x]) == 3 and all(_num(v) for v in k[x]) for x in ("cam", "look"))
        if not ok: c.bad(f"path key {k!r}: {{t, cam: [lon, lat, alt_km], look: [lon, lat, alt_km]}}"); return
        ts.append(k["t"])
        if not (lon0 <= k["cam"][0] <= lon1 and lat0 <= k["cam"][1] <= lat1): c.bad(f"path t={k['t']}: the camera must stay inside the bbox")
        if not 2 <= k["cam"][2] <= 80: c.bad(f"path t={k['t']}: camera altitude 2..80 km")
        if not 0 <= k["look"][2] <= 20: c.bad(f"path t={k['t']}: look altitude 0..20 km")
    if ts[0] != 0 or any(b <= a for a, b in zip(ts, ts[1:])) or abs(ts[-1] - sec) > 0.05:
        c.bad(f"path times must start at 0, increase, and end at seconds ({sec})")
    if c.rep.errors and any(e.startswith(c.pid + ":") for e in c.rep.errors): return
    for n in fly_footprint(p, sec): c.note(n)
    p["zoom"] = int(p.get("zoom") or auto_zoom(p["bbox"][0], p["bbox"][1]))


CLOTH_KEYS = {"flag", "action", "sky", "weather", "camera", "wind", "background", "finial", "focus_uv", "seed", "samples"}


def check_cloth(c, sec):
    p = c.p
    c.known(CLOTH_KEYS)
    f = p.get("flag")
    if not (isinstance(f, dict) and len(f) == 1 and (isinstance(f.get("commons"), str) or str(f.get("url", "")).startswith("http"))):
        c.bad("'flag' must be {commons: 'File:...'} or {url: 'https://...'}")
    act = c.choice("action", ("wave", "lower", "raise", "half"))
    sky = c.choice("sky", ("day", "dawn", "dusk", "night", "storm", "overcast"))
    wx = c.choice("weather", ("none", "snow", "rain", "embers", "dust"))
    c.choice("camera", ("pull", "push", "orbit", "low"))
    c.choice("background", ("city", "hills", "transparent"), required=True)
    c.choice("finial", ("ball", "spear"))
    c.number("wind", 0, 1); c.number("samples", 16, 256); c.number("seed", 0, 10 ** 6)
    fu = p.get("focus_uv")
    if fu is not None and not (isinstance(fu, list) and len(fu) == 2 and all(_num(v) and 0 <= v <= 1 for v in fu)): c.bad("'focus_uv' must be [u, v] in 0..1")
    if act in ("lower", "raise", "half") and sec < 6: c.bad(f"action {act} needs at least 6 seconds")
    if wx == "embers" and sky in ("day", "dawn", "overcast"): c.bad("embers glow only at dusk, night or in a storm")
    if wx == "dust" and sky in ("night", "storm"): c.bad("dust needs daylight (day, dawn or dusk)")
    if wx in ("rain", "snow") and sky in ("day", "dawn", "dusk"): c.note(f"{wx}: rendered under an overcast {sky} sky (no sun)")


def auto_zoom_base(lon0, lon1, lat0, lat1):
    """base map zoom: about 7000 px across, never more than 8192 px on either side"""
    z = max(3, min(10, math.floor(math.log2(7000 * 360 / (256 * (lon1 - lon0))))))
    while z > 3:
        N, mx, my, _, _ = merc(z)
        if mx(lon1) - mx(lon0) <= 8192 and my(lat0) - my(lat1) <= 8192: break
        z -= 1
    return z


def _lerp2(v, e): return v[0] + (v[1] - v[0]) * e


def shatter_footprint(p, sec):
    """extends the bbox until the ground the camera sees (frame corners and edges, sampled over the clip) lies inside
    the base map; returns notes, or raises ValueError when the view cannot be covered"""
    import shatter_time as ST
    notes = []
    cam = p["camera"]
    lens = float(p.get("lens", 45)); thx = 18.0 / lens; thy = thx * 1080 / 1920
    for _ in range(5):
        lon0, lon1, lat0, lat1 = p["bbox"]
        Z = int(p.get("zoom") or auto_zoom_base(lon0, lon1, lat0, lat1)); N, mx, my, ilon, ilat = merc(Z)
        x0, x1, y0, y1 = mx(lon0), mx(lon1), my(lat1), my(lat0); W, H = x1 - x0, y1 - y0
        lt, la = cam["target"]
        mpp = 40075016.686 * math.cos(math.radians(la)) / N
        T = (mx(lt) - x0, -(my(la) - y0), 0.0)
        out = []
        for i in range(13):
            e = ST.smooth(i / 12)
            span = _lerp2(cam["span"], e) * 1000 / mpp
            hd = math.radians(_lerp2(cam.get("heading", [0, 0]), e)); tl = math.radians(_lerp2(cam.get("tilt", [35, 40]), e))
            d = span / (2 * thx)
            f = (math.sin(tl) * math.sin(hd), math.sin(tl) * math.cos(hd), -math.cos(tl))
            c = tuple(T[k] - d * f[k] for k in range(3))
            r = _norm(_cross(f, (math.sin(hd), math.cos(hd), 0.0))); u = _cross(r, f)
            for a in (-1, -0.5, 0, 0.5, 1):
                for b in (-1, -0.5, 0, 0.5, 1):
                    v = _norm(tuple(f[k] + r[k] * a * thx + u[k] * b * thy for k in range(3)))
                    if v[2] > -0.05: raise ValueError("the camera sees the horizon - lower the tilt")
                    s = -c[2] / v[2]
                    hx, hy = c[0] + s * v[0], c[1] + s * v[1]
                    if not (0 <= hx <= W and -H <= hy <= 0): out.append((hx, hy))
        if not out:
            p["zoom"] = Z
            return notes
        xs = [0.0, W] + [h[0] for h in out]; ys = [0.0, -H] + [h[1] for h in out]
        pad = 0.04 * max(W, H)
        nb = [round(ilon(x0 + min(xs) - pad * (min(xs) < 0)), 3), round(ilon(x0 + max(xs) + pad * (max(xs) > W)), 3),
              round(ilat(y0 - (min(ys) - pad * (min(ys) < -H))), 3), round(ilat(y0 - (max(ys) + pad * (max(ys) > 0))), 3)]
        nb = [max(-179.9, nb[0]), min(179.9, nb[1]), max(-80.0, nb[2]), min(80.0, nb[3])]
        if nb[1] - nb[0] > 80 or nb[3] - nb[2] > 55: raise ValueError(f"the camera sees too much ground ({nb}) - reduce span or tilt")
        notes.append(f"base map extended {p['bbox']} -> {nb}: the camera sees ground outside it")
        p["bbox"] = nb; p.pop("zoom", None)
    raise ValueError("the camera view could not be covered by the base map")


SHATTER_KEYS = {"bbox", "zoom", "base", "base_borders", "base_dim", "base_luma", "pieces", "union", "action", "order", "camera", "thickness",
                "lift", "spread", "rim", "labels", "sun", "samples", "lens", "timing"}
PIECE_KEYS = {"key", "admin0", "admin1", "country", "disputed", "flag", "fit", "focus"}
ISO3 = lambda x: isinstance(x, str) and len(x) == 3 and x.isupper()


def _flag_ok(f): return isinstance(f, dict) and len(f) == 1 and (isinstance(f.get("commons"), str) or str(f.get("url", "")).startswith("http"))


def check_shatter(c, sec):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
    import shatter_time as ST
    p = c.p
    c.known(SHATTER_KEYS)
    bb = p.get("bbox")
    if not (isinstance(bb, list) and len(bb) == 4 and all(_num(v) for v in bb)): c.bad("'bbox' must be [lon0, lon1, lat0, lat1]"); return
    lon0, lon1, lat0, lat1 = bb
    if not (-180 <= lon0 < lon1 <= 180 and -80 <= lat0 < lat1 <= 80): c.bad("bbox: lon0 < lon1, lat0 < lat1, |lat| <= 80"); return
    if lon1 - lon0 > 80 or lat1 - lat0 > 55: c.bad("bbox too large (max 80 x 55 degrees)")
    if lon1 - lon0 < 0.5 or lat1 - lat0 < 0.4: c.bad("bbox too small (min 0.5 x 0.4 degrees)")
    c.number("zoom", 3, 10); c.number("base_dim", 0.3, 1.0); c.number("base_luma", 0.06, 0.45)
    c.choice("base", ("satellite", "dark"), required=True)
    act = c.choice("action", ("break", "rise", "drop"), required=True)
    bbo = p.get("base_borders", True)
    if not (isinstance(bbo, bool) or (isinstance(bbo, list) and bbo and all(ISO3(x) or (isinstance(x, list) and x and all(ISO3(y) for y in x)) for x in bbo))):
        c.bad("'base_borders' must be true, false or a list of ISO3 codes / lists of ISO3 codes (merged groups)")
    pcs = p.get("pieces")
    if not (isinstance(pcs, list) and 1 <= len(pcs) <= 20): c.bad("'pieces' must be a list of 1..20 pieces"); return
    keys = []
    for i, pc in enumerate(pcs):
        if not isinstance(pc, dict): c.bad(f"piece {i}: must be an object"); continue
        k = pc.get("key")
        if not (isinstance(k, str) and k and set(k) <= set("abcdefghijklmnopqrstuvwxyz0123456789_")): c.bad(f"piece {i}: 'key' must be lowercase letters, digits, _"); continue
        keys.append(k)
        if set(pc) - PIECE_KEYS: c.bad(f"piece {k}: unknown field(s) {', '.join(sorted(set(pc) - PIECE_KEYS))}")
        kinds = [x for x in ("admin0", "admin1", "disputed") if x in pc]
        if len(kinds) != 1: c.bad(f"piece {k}: exactly one of admin0 | admin1 (+ country) | disputed"); continue
        if kinds[0] == "admin0" and not (ISO3(pc["admin0"]) or (isinstance(pc["admin0"], list) and pc["admin0"] and all(ISO3(x) for x in pc["admin0"]))):
            c.bad(f"piece {k}: admin0 is an ISO3 code or a list of ISO3 codes (merged)")
        if kinds[0] == "admin1" and not (isinstance(pc["admin1"], list) and pc["admin1"] and all(isinstance(x, str) for x in pc["admin1"]) and ISO3(pc.get("country"))):
            c.bad(f"piece {k}: admin1 is a list of province names + 'country' ISO3")
        if "country" in pc and kinds[0] != "admin1": c.bad(f"piece {k}: 'country' only goes with admin1")
        if kinds[0] == "disputed" and not isinstance(pc["disputed"], str): c.bad(f"piece {k}: disputed is a name")
        if not _flag_ok(pc.get("flag")): c.bad(f"piece {k}: 'flag' must be {{commons: 'File:...'}} or {{url: 'https://...'}}")
        if pc.get("fit", "cover") not in ("cover", "contain"): c.bad(f"piece {k}: fit must be cover or contain")
        fo = pc.get("focus")
        if fo is not None and not (isinstance(fo, list) and len(fo) == 2 and all(_num(v) and 0 <= v <= 1 for v in fo)): c.bad(f"piece {k}: focus must be [u, v] in 0..1")
    if len(set(keys)) != len(keys): c.bad("piece keys must be unique")
    un = p.get("union")
    if act == "break":
        if not (isinstance(un, dict) and _flag_ok(un.get("flag")) and not set(un) - {"flag", "fit", "focus"}):
            c.bad("action break needs 'union': {flag, fit, focus} - the flag that spans all pieces before they split")
        elif un.get("fit", "cover") not in ("cover", "contain"): c.bad("union: fit must be cover or contain")
        if len(keys) < 2: c.bad("action break needs at least 2 pieces")
    elif un is not None: c.bad(f"'union' is only used by action break (not {act})")
    od = p.get("order")
    if od is not None and not (isinstance(od, list) and sorted(od) == sorted(keys)): c.bad("'order' must list every piece key exactly once")
    cam = p.get("camera")
    if not isinstance(cam, dict): c.bad("'camera' is required: {target: [lon, lat], span: [km start, km end], heading: [deg, deg], tilt: [deg, deg]}"); return
    if set(cam) - {"target", "span", "heading", "tilt"}: c.bad(f"camera: unknown field(s) {', '.join(sorted(set(cam) - {'target', 'span', 'heading', 'tilt'}))}")
    tg = cam.get("target")
    if not (isinstance(tg, list) and len(tg) == 2 and all(_num(v) for v in tg) and lon0 <= tg[0] <= lon1 and lat0 <= tg[1] <= lat1):
        c.bad("camera.target must be [lon, lat] inside the bbox")
    pair = lambda k, lo, hi, d: cam.get(k, d) if (isinstance(cam.get(k, d), list) and len(cam.get(k, d)) == 2 and all(_num(v) and lo <= v <= hi for v in cam.get(k, d))) else None
    if pair("span", 20, 9000, None) is None: c.bad("camera.span must be [km at the start, km at the end], each 20..9000")
    if pair("heading", -180, 360, [0, 0]) is None: c.bad("camera.heading must be [deg, deg]")
    if pair("tilt", 0, 55, [35, 40]) is None: c.bad("camera.tilt must be [deg, deg], each 0..55 (0 = straight down)")
    c.number("thickness", 0.003, 0.06); c.number("lift", 0, 0.35); c.number("spread", 0, 0.35); c.number("rim", 0, 10)
    c.number("lens", 20, 85); c.number("samples", 16, 256)
    if act != "break" and "spread" in p: c.bad("'spread' is only used by action break")
    if act == "drop" and "lift" in p: c.bad("'lift' is not used by action drop")
    sun = p.get("sun", {})
    if not isinstance(sun, dict) or set(sun) - {"elevation", "azimuth"}: c.bad("'sun' must be {elevation, azimuth} (azimuth relative to the frame: 0 = from the top, 270 = from the left)")
    else: c.number("elevation", 15, 75, src=sun); c.number("azimuth", 0, 360, src=sun)
    for e in p.get("labels", []):
        if not (isinstance(e, list) and 2 <= len(e) <= 3 and all(isinstance(x, str) for x in e)): c.bad(f"label {e!r}: [piece key, display, style]"); continue
        if e[0] not in keys: c.bad(f"label {e[0]}: not a piece key")
        if len(e) > 2 and e[2] not in ("", "hot"): c.bad(f"label {e[0]}: style must be '' or 'hot'")
    tm = p.get("timing")
    if tm is not None and not (isinstance(tm, dict) and all(_num(v) and 0 <= v <= sec for v in tm.values())): c.bad("'timing' values must be seconds inside the clip")
    if any(e.startswith(c.pid + ":") for e in c.rep.errors): return
    try:
        ST.schedule(act, sec, len(keys), tm)
    except ValueError as e:
        c.bad(str(e)); return
    try:
        for n in shatter_footprint(p, sec): c.note(n)
    except ValueError as e:
        c.bad(str(e)); return
    lon0, lon1, lat0, lat1 = p["bbox"]
    p["zoom"] = int(p.get("zoom") or auto_zoom_base(lon0, lon1, lat0, lat1))


NEST_KEYS = {"shape", "profile", "seam", "panel", "levels", "ratio", "background", "camera", "labels", "samples"}
HEX6 = lambda s: isinstance(s, str) and len(s) == 7 and s[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in s[1:])


def check_nest(c, sec):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
    import nest_geo as NG
    p = c.p; n0 = len(c.rep.errors)
    c.known(NEST_KEYS)
    if "profile" in p:
        pr = p["profile"]
        if "shape" in p: c.bad("give 'shape' or 'profile', not both")
        if not (isinstance(pr, list) and 4 <= len(pr) <= 40 and all(isinstance(q, list) and len(q) == 2 and all(_num(v) for v in q) for q in pr)):
            c.bad("'profile' must be a list of 4..40 [z, r] points"); return
        zs, rs = [q[0] for q in pr], [q[1] for q in pr]
        if abs(zs[0]) > 1e-9 or abs(zs[-1] - 1) > 1e-9 or any(b <= a for a, b in zip(zs, zs[1:])): c.bad("profile: z must rise strictly from 0 to 1")
        if any(not 0 <= r <= 0.6 for r in rs) or rs[0] < 0.08: c.bad("profile: r in [0, 0.6], and a foot (r at z = 0) of at least 0.08")
        c.number("seam", 0.3, 0.75, required=True); c.number("panel", 0.1, 0.6)
        spec = {"profile": pr, "seam": p.get("seam", 0.5), "panel": p.get("panel")}
    else:
        spec = c.choice("shape", tuple(NG.PRESETS)) or "doll"
        for k in ("seam", "panel"):
            if k in p: c.bad(f"'{k}' only goes with a custom 'profile'")
    lv = p.get("levels")
    if not (isinstance(lv, list) and 2 <= len(lv) <= 6): c.bad("'levels' must be a list of 2..6 levels (outermost first)"); return
    keys = []
    for i, e in enumerate(lv):
        if not isinstance(e, dict): c.bad(f"level {i}: must be an object"); continue
        if set(e) - {"key", "image", "color"}: c.bad(f"level {i}: unknown field(s) {sorted(set(e) - {'key', 'image', 'color'})}")
        k = e.get("key")
        if not (isinstance(k, str) and k and set(k) <= set("abcdefghijklmnopqrstuvwxyz0123456789_")): c.bad(f"level {i}: key must be lowercase letters, digits, _")
        elif k in keys: c.bad(f"level {i}: duplicate key {k}")
        else: keys.append(k)
        if not _flag_ok(e.get("image")): c.bad(f"level {i}: 'image' must be {{commons: File:...}} or {{url: https://...}}")
        if "color" in e and not HEX6(e["color"]): c.bad(f"level {i}: color must be #RRGGBB")
    c.number("ratio", 0.55, 0.85); c.choice("background", ("studio", "transparent")); c.number("samples", 16, 256)
    cam = p.get("camera", {})
    if not isinstance(cam, dict) or set(cam) - {"elevation", "lens", "orbit", "fill"}: c.bad("'camera' takes elevation, lens, orbit, fill")
    else:
        c.number("elevation", 0, 30, src=cam); c.number("lens", 35, 135, src=cam); c.number("orbit", 0, 20, src=cam); c.number("fill", 0.4, 0.75, src=cam)
    lab = p.get("labels", [])
    if not (isinstance(lab, list) and all(isinstance(e, list) and 1 <= len(e) <= 3 and all(isinstance(x, str) for x in e) for e in lab)):
        c.bad("'labels' must be [[key, display, style], ...]")
    else:
        for e in lab:
            if e[0] not in keys: c.bad(f"label {e[0]!r} is not a level key")
    if len(c.rep.errors) > n0: return
    try: g = NG.profile(spec)
    except Exception as ex: c.bad(f"the profile cannot be built: {ex}"); return
    k = NG.solve_k(g)
    if k is None: c.bad("this profile cannot nest: no size step lets a level rest inside and pass through the opening"); return
    if p.get("ratio") and p["ratio"] > k: c.bad(f"ratio {p['ratio']} is larger than this shape allows ({k})")
    need = NG.timeline(sec, len(lv))["need"]
    if sec < need: c.bad(f"{len(lv)} levels need at least {need:.1f} s (got {sec:g})")
    kk = min(k, p.get("ratio", 0.8)); inner = kk ** (len(lv) - 1)
    if inner < 0.25: c.bad(f"the innermost level would be {inner:.0%} of the outer one - fewer levels or a bigger ratio")
    c.note(f"size step {kk} (fit {k}); the innermost level is {inner:.0%} of the outer one; opens at "
           f"{', '.join(f'{x:.1f}' for x in NG.timeline(sec, len(lv))['t_open'])} s")


CHECKS = {"fly": check_fly, "cloth": check_cloth, "shatter": check_shatter, "nest": check_nest}


def check(spec, reg):
    rep = Report()
    pieces = spec.get("pieces")
    if not isinstance(pieces, list) or not pieces: rep.errors.append("workshop.json has no pieces"); return [], rep
    out, ids = [], set()
    for i, pc in enumerate(pieces):
        pid = pc.get("id") if isinstance(pc, dict) else None
        if not (isinstance(pid, str) and pid and set(pid) <= set("abcdefghijklmnopqrstuvwxyz0123456789_")):
            rep.errors.append(f"piece {i}: id must be lowercase letters, digits, _"); continue
        if pid in ids: rep.errors.append(f"{pid}: duplicate id"); continue
        ids.add(pid)
        if set(pc) - {"id", "template", "seconds", "params", "budget_min", "note"}: rep.errors.append(f"{pid}: unknown fields {sorted(set(pc) - {'id', 'template', 'seconds', 'params', 'budget_min', 'note'})}")
        t = pc.get("template")
        if t not in reg or t not in CHECKS: rep.errors.append(f"{pid}: unknown template {t!r} (known: {', '.join(k for k in reg if k in CHECKS)})"); continue
        sec = pc.get("seconds")
        if not (_num(sec) and 2 <= sec <= 40): rep.errors.append(f"{pid}: seconds must be 2..40"); continue
        prm = copy.deepcopy(pc.get("params", {}))
        if not isinstance(prm, dict): rep.errors.append(f"{pid}: params must be an object"); continue
        c = Piece(rep, pid, prm)
        CHECKS[t](c, float(sec))
        rate = float(reg[t].get("budget_min_per_s", 2.5))
        b = pc.get("budget_min", min(40.0, max(8.0, round(rate * float(sec), 1))))
        if not (_num(b) and 5 <= b <= 45): rep.errors.append(f"{pid}: budget_min must be 5..45"); continue
        out.append({"id": pid, "template": t, "seconds": float(sec), "params": prm, "budget_min": float(b)})
    return out, rep
