"""Map definitions of the factory's map library: one conformal canvas (projection + extent + pixel grid) per region.
kind "lcc"  : Lambert conformal conic (regions of the northern hemisphere away from the equator - the classic atlas look)
kind "merc" : Mercator, the n = 0 limit of the same family (regions near or south of the equator)
Every raster and vector of a map is projected with these formulas only (numpy here, TypeScript in
factory/engine/src/lib/proj.ts), so terrain tiles, borders, labels and the camera align exactly.
A map is defined once from the extent it must show and never changes afterwards (its key is a hash of the definition):
films that fit inside an existing map reuse its terrain; a new region is added to the library once."""
import hashlib, json, math
import numpy as np

R = 6371000.0
D = math.pi / 180
STYLE = "v5"                 # the terrain look (terrain.py); a new style gives new map keys
W_MAX = 8192                 # longest side of a canvas (px)
MARGIN = (0.07, 0.10)        # extra canvas around the extent (share of its projected width, height)


class MapDef:
    def __init__(self, d):
        self.d = dict(d)
        self.kind = d["kind"]
        self.lon0 = float(d["lon0"])
        self.res = float(d["res_m"]); self.minx = float(d["minx"]); self.maxy = float(d["maxy"])
        self.W = int(d["width"]); self.H = int(d["height"])
        self.lat0 = float(d.get("lat0", 0.0)); self.lat1 = float(d.get("lat1", 0.0)); self.lat2 = float(d.get("lat2", 0.0))
        if self.kind == "lcc":
            p1, p2 = self.lat1 * D, self.lat2 * D
            if abs(p1 - p2) > 1e-9:
                self.n = math.log(math.cos(p1) / math.cos(p2)) / math.log(math.tan(math.pi / 4 + p2 / 2) / math.tan(math.pi / 4 + p1 / 2))
            else:
                self.n = math.sin(p1)
            self.F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** self.n / self.n
            self.rho0 = R * self.F / math.tan(math.pi / 4 + self.lat0 * D / 2) ** self.n
        elif self.kind == "merc":
            self.n = 0.0; self.F = 0.0; self.rho0 = 0.0
        else:
            raise ValueError(f"unknown map kind {self.kind}")

    # ---------------------------------------------------------------- projection
    def fwd_m(self, lon, lat):
        """lon, lat (deg) -> projected metres"""
        dl = (np.asarray(lon, np.float64) - self.lon0 + 180.0) % 360.0 - 180.0
        lat = np.asarray(lat, np.float64)
        if self.kind == "lcc":
            th = self.n * dl * D
            rho = R * self.F / np.tan(math.pi / 4 + np.clip(lat, -89.9, 89.9) * D / 2) ** self.n
            return rho * np.sin(th), self.rho0 - rho * np.cos(th)
        la = np.clip(lat, -85.0, 85.0) * D
        return R * dl * D, R * np.log(np.tan(math.pi / 4 + la / 2))

    def fwd(self, lon, lat):
        """lon, lat (deg) -> canvas px (x right, y down)"""
        x, y = self.fwd_m(lon, lat)
        return (x - self.minx) / self.res, (self.maxy - y) / self.res

    def inv(self, X, Y):
        """canvas px -> lon (deg, continuous across the canvas: may leave -180..180), lat (deg)"""
        x = self.minx + np.asarray(X, np.float64) * self.res
        y = self.maxy - np.asarray(Y, np.float64) * self.res
        if self.kind == "lcc":
            dy = self.rho0 - y
            rho = np.sqrt(x * x + dy * dy); th = np.arctan2(x, dy)
            lon = self.lon0 + th / self.n / D
            lat = (2 * np.arctan((R * self.F / np.maximum(rho, 1.0)) ** (1 / self.n)) - math.pi / 2) / D
            return lon, lat
        return self.lon0 + x / R / D, (2 * np.arctan(np.exp(y / R)) - math.pi / 2) / D

    def proj4(self):
        if self.kind == "lcc":
            return f"+proj=lcc +lat_1={self.lat1} +lat_2={self.lat2} +lat_0={self.lat0} +lon_0={self.lon0} +R=6371000 +units=m +no_defs"
        return f"+proj=merc +lon_0={self.lon0} +R=6371000 +units=m +no_defs"

    def geo_header(self):
        """the projection keys of geo.json (read by factory/engine/src/lib/proj.ts)"""
        return {"width": self.W, "height": self.H, "proj": self.proj4(), "kind": self.kind, "res_m": self.res, "minx": self.minx,
                "maxy": self.maxy, "lon0": self.lon0, "lat0": self.lat0, "lat1": self.lat1, "lat2": self.lat2, "cone_n": self.n}

    def key(self):
        core = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in self.d.items() if k not in ("name", "key", "extent")}
        return hashlib.sha1(json.dumps([core, STYLE], sort_keys=True).encode()).hexdigest()[:10]

    def margin_of(self, lon, lat):
        """smallest distance of the points to the canvas edge, as a share of the canvas size (negative = outside)"""
        X, Y = self.fwd(lon, lat)
        X, Y = np.asarray(X), np.asarray(Y)
        return float(min((X / self.W).min(), (1 - X / self.W).min(), (Y / self.H).min(), (1 - Y / self.H).min()))

    def lonlat_box(self, step=32):
        """lon/lat bounds of the whole canvas (sampled along a grid)"""
        X, Y = np.meshgrid(np.linspace(0, self.W, step + 1), np.linspace(0, self.H, step + 1))
        lon, lat = self.inv(X, Y)
        return [float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())]


def extent_points(ext, n=41):
    lo0, la0, lo1, la1 = ext
    L, B = np.meshgrid(np.linspace(lo0, lo1, n), np.linspace(la0, la1, n))
    return L.ravel(), B.ravel()


def define(ext, name=""):
    """a new canvas for an extent [lon0, lat0, lon1, lat1] (deg; lon1 may exceed 180 when the extent crosses the antimeridian)"""
    lo0, la0, lo1, la1 = map(float, ext)
    if lo1 <= lo0: raise ValueError("extent: lon1 must be east of lon0")
    if lo1 - lo0 > 200 or la1 - la0 > 120: raise ValueError("extent too large for one conformal canvas (max 200 x 120 deg)")
    if lo0 < -180 or lo1 > 180: raise ValueError("maps crossing the antimeridian are not supported by the terrain sources")
    clon, clat = (lo0 + lo1) / 2, (la0 + la1) / 2
    if la0 >= 12 and clat >= 25:                                  # northern mid/high latitudes: conic
        span = la1 - la0
        d = {"kind": "lcc", "lon0": round(clon, 1), "lat0": round(clat * 2) / 2,
             "lat1": round((la0 + span / 6) * 2) / 2, "lat2": round((la1 - span / 6) * 2) / 2}
        if d["lat2"] - d["lat1"] < 1: d["lat1"], d["lat2"] = d["lat0"] - 0.5, d["lat0"] + 0.5
    else:
        d = {"kind": "merc", "lon0": round(clon, 1)}
    tmp = MapDef({**d, "res_m": 1.0, "minx": 0.0, "maxy": 0.0, "width": 1, "height": 1})
    L, B = extent_points(ext)
    x, y = tmp.fwd_m(L, B)
    minx, maxx, miny, maxy = float(x.min()), float(x.max()), float(y.min()), float(y.max())
    mx, my = (maxx - minx) * MARGIN[0], (maxy - miny) * MARGIN[1]
    minx, maxx, miny, maxy = minx - mx, maxx + mx, miny - my, maxy + my
    res = max(maxx - minx, maxy - miny) / W_MAX
    W, H = int(math.ceil((maxx - minx) / res)), int(math.ceil((maxy - miny) / res))
    d.update(res_m=res, minx=minx, maxy=maxy, width=W, height=H)
    d["name"] = name
    md = MapDef(d)
    d["key"] = md.key(); d["extent"] = [round(v, 3) for v in ext]
    return MapDef(d)


def load(path):
    return MapDef(json.load(open(path)))


def save(md, path):
    json.dump(md.d, open(path, "w"), indent=1)
