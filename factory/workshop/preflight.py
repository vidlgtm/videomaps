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
            "sun", "lens", "samples", "haze", "saturation"}


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
    c.number("samples", 16, 256); c.number("haze", 0.2, 1.0); c.number("saturation", 0.6, 1.6)
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


CHECKS = {"fly": check_fly, "cloth": check_cloth}


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
