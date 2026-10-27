#!/usr/bin/env python3
"""Data of the 3D scenes that is not an order-store picture as it is (made here, outside Blender, into DIR/geo.json and
files next to it):
  map tiles   : Natural Earth 10 m countries or the order's own shapes (order.json "shapes" / "regions" / "disputed", the
                same resolver as the map library), projected with the map library's formulas (mapdef.py), simplified and
                triangulated; all tiles of a scene form one map (units: the map's long side = 1) with one satellite
                picture on top (Sentinel-2 cloudless 2016, EOX IT Services, CC BY 4.0, shaded with the AWS terrarium relief)
  pieces      : what a member splits into - the listed countries / shapes of a tile, or jagged tears (bounded Voronoi
                cells with torn edges) of a tile, sheet or print (units: the member's footprint = 1 x 1 for sheets)
  terrains    : a terrain block (cast "region"): relief + colour of the region; a terrain or sea place (place.region):
                the region at full detail and a coarse ring around it out to the horizon (place.json); open sea is
                forced below the water (flat 0 m patches of the relief would show as pale slabs)
  routes, fly : route paths and flight paths (lon/lat) densified along great circles and projected onto what they are
                drawn on (tile map, terrain block, globe, the place); cast "at" points on a terrain or sea place
  globe       : earth.jpg - NASA Blue Marble (equirectangular, 8192 px) with the land borders drawn
  models      : GLB files from the order store or from the objects stage (release objects_cache, objects.json collected)
  cut-outs    : the figure of an order-store picture (its own transparency, otherwise rembg), cropped to the figure
Sources: base-map sources only (factory/rules/hermetic.py); heavy libraries are imported only when a scene needs them."""
import hashlib, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPO = os.environ.get("GITHUB_REPOSITORY", "vidlgtm/videomaps")
VERSION = "geo v1"
TILE_IMG, PLACE_IMG, BLOCK_IMG, RING_IMG = 4096, 4096, 2048, 1024
BLOCK_N, PLACE_N = 360, 560   # relief samples across a terrain block / a terrain place
EOX = "Sentinel-2 cloudless 2016 by EOX IT Services GmbH (CC BY 4.0)"
RELIEF = "Relief: AWS Terrain Tiles (Mapzen terrarium)"
NE_CREDIT = "Borders: Natural Earth (public domain)"
BM_CREDIT = "Earth: NASA Blue Marble (NASA Earth Observatory)"


def _maps():
    sys.path.insert(0, os.path.join(ROOT, "factory", "maps"))
    import mapdef, terrain, geo_build
    return mapdef, terrain, geo_build


def seed_of(s): return int(hashlib.sha1(str(s).encode()).hexdigest()[:8], 16)


def route_beats(sc): return [b for b in (sc.get("beats") or []) if b.get("do") == "route"]


def needs(sc):
    """what data a scene needs (also the part of the data key that is not a store file)"""
    cast = sc.get("cast") or {}; beats = sc.get("beats") or []; pl = sc.get("place") or {}
    splits = {}
    for b in beats:
        if b.get("do") in ("split", "assemble"):
            sp = splits.setdefault(b["who"], {"into": None})
            if b.get("into") is not None: sp["into"] = b["into"]
    cams = sorted(sc.get("camera") or [], key=lambda e: e.get("t", 0))
    return {"version": VERSION,
            "tiles": {n: str(c["from"])[4:] for n, c in cast.items() if c.get("is") == "tile"},
            "tile_sizes": {n: c.get("size", "M") for n, c in cast.items() if c.get("is") == "tile"},
            "splits": {n: sp for n, sp in splits.items() if n in cast and cast[n].get("is") in ("tile", "sheet", "print")},
            "terrains": {n: c.get("region") for n, c in cast.items() if c.get("is") == "terrain"},
            "place": pl.get("region") if pl.get("kind") in ("terrain", "sea") else None, "kind": pl.get("kind"),
            "at": {n: c["at"] for n, c in cast.items() if c.get("at") is not None and c.get("is") != "globe"},
            "routes": [{"who": b["who"], "path": b["path"]} for b in route_beats(sc)],
            "fly": {str(i): e.get("path") for i, e in enumerate(cams) if e.get("move") == "fly"},
            "globe": any(c.get("is") == "globe" for c in cast.values()),
            "models": {n: str(c.get("from")) for n, c in cast.items() if c.get("is") == "model"},
            "cutouts": {n: str(c.get("from"))[6:] for n, c in cast.items() if c.get("is") == "cutout" and str(c.get("from", "")).startswith("store:")}}


# ------------------------------------------------------------------ geometry helpers
def densify(path, step=0.5):
    """lon/lat points joined along great circles, a point every <= step degrees"""
    P = np.radians(np.asarray(path, float)); out = []
    for (lo1, la1), (lo2, la2) in zip(P[:-1], P[1:]):
        a = np.array([math.cos(la1) * math.cos(lo1), math.cos(la1) * math.sin(lo1), math.sin(la1)])
        b = np.array([math.cos(la2) * math.cos(lo2), math.cos(la2) * math.sin(lo2), math.sin(la2)])
        om = math.acos(float(np.clip(a @ b, -1, 1))); k = max(1, int(math.degrees(om) / step))
        for t in np.linspace(0, 1, k, endpoint=False):
            v = a if om < 1e-9 else (math.sin((1 - t) * om) * a + math.sin(t * om) * b) / math.sin(om)
            out.append((math.degrees(math.atan2(v[1], v[0])), math.degrees(math.asin(np.clip(v[2], -1, 1)))))
    out.append(tuple(np.degrees(P[-1])))
    o = np.array(out); o[:, 0] = np.degrees(np.unwrap(np.radians(o[:, 0])))           # continuous across 180
    return o


def mesh(g):
    """polygon(s) -> verts (k, 2), triangles, outline rings (index loops); exterior counter-clockwise"""
    import mapbox_earcut as earcut
    from shapely.geometry.polygon import orient
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    V, T, R = [], [], []
    for p in polys:
        p = orient(p)
        rings = [np.asarray(p.exterior.coords)[:-1]] + [np.asarray(i.coords)[:-1] for i in p.interiors]
        rings = [r for r in rings if len(r) >= 3]
        if not rings: continue
        vs = np.vstack(rings); ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
        t = np.asarray(earcut.triangulate_float64(vs.astype(np.float64), ends), np.int64).reshape(-1, 3)
        b = sum(len(x) for x in V); V.append(vs); T.append(t + b)
        s0 = 0
        for e in ends: R.append(list(range(b + s0, b + int(e)))); s0 = int(e)
    if not V: return None
    return {"verts": np.vstack(V), "tris": np.vstack(T), "rings": R}


def keep_big(g, frac=0.0015, most=40):
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    if not polys: return g
    from shapely.geometry import MultiPolygon
    big = max(p.area for p in polys); polys = sorted([p for p in polys if p.area >= frac * big], key=lambda p: -p.area)[:most]
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def part(g, cx, cy, nd=5):
    m = mesh(g)
    if m is None: return None
    c = g.centroid
    return {"verts": np.round(m["verts"] - [cx, cy], nd).tolist(), "tris": m["tris"].tolist(), "rings": m["rings"],
            "c": [round(c.x - cx, nd), round(c.y - cy, nd)]}


def jagged(g, N, seed, amp=0.022):
    """g cut into N pieces: bounded Voronoi cells of well spread seeds, every cut line torn (smooth random wobble that
    is zero at its ends, so neighbouring pieces still fit exactly)"""
    from scipy.spatial import Voronoi
    from shapely.geometry import LineString, Point
    from shapely.ops import polygonize, unary_union
    rng = np.random.default_rng(seed_of(seed)); x0, y0, x1, y1 = g.bounds
    dmin = 0.55 * math.sqrt(g.area / max(N, 1)); pts = []
    for _ in range(4000):
        if len(pts) >= N: break
        p = (rng.uniform(x0, x1), rng.uniform(y0, y1))
        if g.contains(Point(p)) and all(math.hypot(p[0] - q[0], p[1] - q[1]) > dmin for q in pts): pts.append(p)
    if len(pts) < 2: return [g]
    S = np.array(pts); allp = [S]
    for ax, v in ((0, x0), (0, x1), (1, y0), (1, y1)):
        m_ = S.copy(); m_[:, ax] = 2 * v - m_[:, ax]; allp.append(m_)
    vor = Voronoi(np.vstack(allp)); n = len(S); lines = []
    for (a, b), rv in zip(vor.ridge_points, vor.ridge_vertices):
        if a >= n or b >= n or -1 in rv: continue                    # cut lines only between two real seeds
        p, q = vor.vertices[rv[0]].copy(), vor.vertices[rv[1]].copy(); L = float(np.linalg.norm(q - p))
        if L < 1e-9: continue
        u_ = (q - p) / L; sz = max(x1 - x0, y1 - y0)
        edge = lambda v: min(abs(v[0] - x0), abs(v[0] - x1), abs(v[1] - y0), abs(v[1] - y1)) < 1e-6 * sz
        if edge(p): p = p - u_ * 1e-3 * sz                          # a cut that ends on the frame crosses it (closed pieces)
        if edge(q): q = q + u_ * 1e-3 * sz
        L = float(np.linalg.norm(q - p))
        k = max(8, int(40 * L / max(x1 - x0, y1 - y0))); t = np.linspace(0, 1, k + 1)
        nrm = np.array([-(q - p)[1], (q - p)[0]]) / L; ph = rng.random(3) * 2 * np.pi
        off = amp * max(x1 - x0, y1 - y0) * np.sin(np.pi * t) * (0.6 * np.sin(5 * t + ph[0]) + 0.3 * np.sin(13 * t + ph[1]) + 0.15 * np.sin(29 * t + ph[2]))
        pl = p + np.outer(t, q - p) + np.outer(off, nrm); pl[0], pl[-1] = p, q   # ends exactly on the shared corners
        lines.append(LineString(pl))
    cells = list(polygonize(unary_union(lines + [g.boundary])))
    out = [c.intersection(g) for c in cells]
    out = [c for c in out if not c.is_empty and c.area > 1e-3 * g.area]
    return out or [g]


# ------------------------------------------------------------------ pictures of the ground
def zoom_for(mpp, lat): return int(np.clip(round(math.log2(156543.03 * math.cos(math.radians(lat)) / max(mpp, 1e-3))), 2, 13))


def shade(dem, px_m, ve=2.0):
    gy, gx = np.gradient(dem * ve, px_m)
    az, alt = math.radians(315), math.radians(45)
    sl = np.arctan(np.hypot(gx, gy)); asp = np.arctan2(-gx, gy)
    s = np.sin(alt) * np.cos(sl) + np.cos(alt) * np.sin(sl) * np.cos(az - asp)
    return np.clip(0.78 + 0.55 * (s - np.sin(alt)), 0.6, 1.25)


def ground_picture(terrain, lon, lat, mpp, with_shade=True):
    """Sentinel-2 cloudless colour at the sample points (lon, lat (h, w)), shaded with the relief"""
    from scipy import ndimage
    latm = float(np.nanmean(lat)); z = zoom_for(mpp, latm)
    rgb = terrain.Mosaic("s2", z, lon, lat).sample(lon, lat)
    if with_shade:
        h, w = lon.shape; k = max(1, int(round(max(h, w) / 1024)))
        lo2, la2 = lon[::k, ::k], lat[::k, ::k]
        dem = terrain.Mosaic("dem", max(2, min(12, zoom_for(mpp * k, latm))), lo2, la2).sample(lo2, la2)[..., 0]
        sh = shade(dem, mpp * k)
        sh = ndimage.zoom(sh, (h / sh.shape[0], w / sh.shape[1]), order=1)[:h, :w]
        rgb = rgb * sh[..., None]
    rgb = 255.0 * (np.clip(rgb, 0, 255) / 255.0) ** 0.85             # Sentinel-2 shadows and seas lifted (lesson 9)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def save_jpg(a, path):
    from PIL import Image
    Image.fromarray(a).save(path, quality=92)


def srgb_lin(a):
    a = np.asarray(a, float) / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


# ------------------------------------------------------------------ map tiles
def geo_resolver(order, store_dir):
    mapdef, terrain, gb = _maps()
    op = os.path.join(order, "order.json")
    o = json.load(open(op, encoding="utf-8")) if os.path.exists(op) else {}
    o["_dir"] = order
    G = gb.Geo.__new__(gb.Geo); G.o = o; G.store_dir = store_dir; G.md = None
    G.adm0 = gb.fetch("ne_10m_admin_0_countries_lakes.geojson"); G._adm1 = None; G._brk = None; G.cache = {}
    shapes, regions = o.get("shapes") or {}, o.get("regions") or {}

    def ref(r):
        from shapely.ops import unary_union
        gs = [G.resolve(x, shapes, regions) for x in r.split("+")]
        gs = [main_body(unwrap_lon(g)) if g is not None and not g.is_empty else g for g in gs]
        gs = [g for g in gs if g is not None and not g.is_empty]
        return unary_union(gs) if gs else None
    return ref, gb


def main_body(g):
    """the shape without far-off small territories (overseas departments, distant islands): a part stays if it is big
    (a quarter of the largest) or near the largest (within half its size)"""
    from shapely.ops import unary_union
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    if len(polys) < 2: return g
    main = max(polys, key=lambda p: p.area); x0, y0, x1, y1 = main.bounds; diag = math.hypot(x1 - x0, y1 - y0)
    keep = [p for p in polys if p.area >= 0.25 * main.area or p.distance(main) <= 0.5 * diag]
    return unary_union(keep)


def unwrap_lon(g):
    """geometries that cross 180: western longitudes moved by +360 so the shape is continuous"""
    from shapely.ops import transform
    x0, _, x1, _ = g.bounds
    if x1 - x0 < 300: return g
    return transform(lambda x, y: (np.where(np.asarray(x) < 0, np.asarray(x) + 360.0, x), y), g)


def tiles(order, nd, out, store_dir, errs):
    mapdef, terrain, gb0 = _maps()
    from shapely.ops import transform, unary_union
    ref, gb = geo_resolver(order, store_dir)
    G = {}
    for n, r in nd["tiles"].items():
        g = ref(r)
        if g is None: errs.append(f'map tile {n}: "map:{r}" did not resolve to a shape')
        else: G[n] = main_body(unwrap_lon(g))
    errs += [e for e in gb.ERR if e not in errs]
    if errs or not G: return None
    allg = unary_union(list(G.values())); lo0, la0, lo1, la1 = allg.bounds
    md = mapdef.define([lo0, la0, lo1, la1])
    prj = lambda g: transform(lambda x, y: md.fwd(np.asarray(x), np.asarray(y)), g)
    PX = {n: prj(g).buffer(0) for n, g in G.items()}
    X0, Y0, X1, Y1 = unary_union(list(PX.values())).bounds; k = 1.0 / max(X1 - X0, Y1 - Y0); cxp, cyp = (X0 + X1) / 2, (Y0 + Y1) / 2
    to_n = lambda g: transform(lambda x, y: ((np.asarray(x) - cxp) * k, -(np.asarray(y) - cyp) * k), g)
    members = {}; NG = {}
    for n, g in PX.items():
        gn = keep_big(to_n(g)).simplify(0.0012, preserve_topology=True).buffer(-0.0006).buffer(0)
        if gn.is_empty: errs.append(f"map tile {n}: too small on this map"); continue
        NG[n] = gn; x0, y0, x1, y1 = gn.bounds; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        members[n] = {"w": round(x1 - x0, 5), "d": round(y1 - y0, 5), "cx": round(cx, 5), "cy": round(cy, 5), "parts": [part(gn, cx, cy)]}
        sp = nd["splits"].get(n)
        if sp is not None:
            into = sp.get("into")
            if isinstance(into, list) and into and all(str(x).startswith("map:") for x in into):
                pcs = []
                for r in into:
                    pg = ref(str(r)[4:])
                    if pg is None: errs.append(f"map tile {n}: piece {r} did not resolve"); continue
                    q = to_n(prj(unwrap_lon(pg)).buffer(0)).intersection(gn)
                    if q.area > 1e-4 * gn.area: pcs.append(q)
                if pcs:
                    rest = gn.difference(unary_union(pcs))
                    if rest.area > 0.01 * gn.area: pcs.append(rest)
            else:
                cnt = int(into[0]) if isinstance(into, list) and into else int(into or 5)
                pcs = jagged(gn, max(2, min(12, cnt)), n, amp=0.012)
            members[n]["pieces"] = [p_ for p_ in (part(keep_big(q.buffer(-0.0008).buffer(0)), cx, cy) for q in pcs) if p_]
    if errs: return None
    U = unary_union(list(NG.values())); ex = U.bounds; mg = 0.02 * max(ex[2] - ex[0], ex[3] - ex[1])
    ex = [ex[0] - mg, ex[1] - mg, ex[2] + mg, ex[3] + mg]
    wn, hn = ex[2] - ex[0], ex[3] - ex[1]
    Wi = TILE_IMG if wn >= hn else max(64, int(round(TILE_IMG * wn / hn))); Hi = TILE_IMG if hn > wn else max(64, int(round(TILE_IMG * hn / wn)))
    u = ex[0] + (np.arange(Wi) + 0.5) / Wi * wn; v = ex[3] - (np.arange(Hi) + 0.5) / Hi * hn
    U_, V_ = np.meshgrid(u, v); lon, lat = md.inv(U_ / k + cxp, -V_ / k + cyp)
    mpp = wn / k * md.res / Wi
    save_jpg(ground_picture(terrain, lon, lat, mpp), os.path.join(out, "tiles.jpg"))
    return {"image": "tiles.jpg", "extent": [round(x, 5) for x in ex], "members": members,
            "proj": {"md": md.d, "k": k, "cx": cxp, "cy": cyp}}


def project_tiles(T, path):
    mapdef, _, _ = _maps()
    md = mapdef.MapDef(T["proj"]["md"]); p = densify(path)
    X, Y = md.fwd(p[:, 0], p[:, 1]); k = T["proj"]["k"]
    return np.stack([(X - T["proj"]["cx"]) * k, -(Y - T["proj"]["cy"]) * k], -1)


# ------------------------------------------------------------------ terrain (block or place)
def region_grid(md, nx):
    ny = max(8, int(round(nx * md.H / md.W)))
    X, Y = np.meshgrid(np.linspace(0, md.W, nx), np.linspace(0, md.H, ny))
    return X, Y, nx, ny


def heights(terrain, lon, lat, mpp, sea_floor):
    latm = float(np.nanmean(lat))
    dem = terrain.Mosaic("dem", max(2, min(12, zoom_for(mpp, latm))), lon, lat).sample(lon, lat)[..., 0].astype(np.float64)
    lo0, lo1 = float(np.nanmin(lon)) - 0.5, float(np.nanmax(lon)) + 0.5; la0, la1 = float(np.nanmin(lat)) - 0.5, float(np.nanmax(lat)) + 0.5
    ppd = float(np.clip(lon.shape[1] / max(lo1 - lo0, 1e-3) * 1.5, 20, 240))
    w, h = int((lo1 - lo0) * ppd) + 1, int((la1 - la0) * ppd) + 1
    mask = terrain.land_mask(lo0, la1, ppd, w, h).astype(np.float32)
    land = terrain.eq_sample(mask, lo0, la1, ppd, lon, lat) > 127
    sea = (~land) & (dem < 5.0)
    dem[sea] = np.minimum(dem[sea], sea_floor)                       # open sea well below the water
    return dem, float(sea.mean())


def terrain_block(region, name, out):
    mapdef, terrain, _ = _maps()
    lo0, la0, lo1, la1 = region; md = mapdef.define([lo0, la0, lo1, la1])
    X, Y, nx, ny = region_grid(md, BLOCK_N); lon, lat = md.inv(X, Y)
    span_m = md.W * md.res; dem, sea = heights(terrain, lon, lat, span_m / (nx - 1), -60.0)
    np.savez_compressed(os.path.join(out, f"terrain_{name}.npz"), h=dem.astype(np.float32))
    Wi = BLOCK_IMG; Hi = max(64, int(round(Wi * md.H / md.W)))
    Xi, Yi = np.meshgrid((np.arange(Wi) + 0.5) / Wi * md.W, (np.arange(Hi) + 0.5) / Hi * md.H); li, ai = md.inv(Xi, Yi)
    save_jpg(ground_picture(terrain, li, ai, span_m / Wi), os.path.join(out, f"terrain_{name}.jpg"))
    return {"heights": f"terrain_{name}.npz", "image": f"terrain_{name}.jpg", "aspect": md.W / md.H, "span_m": span_m,
            "sea_floor": -60.0, "ve_max": 12.0, "sea": round(sea, 3), "md": md.d}


def project_block(Tb, path):
    mapdef, _, _ = _maps()
    md = mapdef.MapDef(Tb["md"]); p = densify(path); X, Y = md.fwd(p[:, 0], p[:, 1])
    return np.stack([X / md.W - 0.5, 0.5 - Y / md.H], -1)


def terrain_place(region, kind, nd, out):
    mapdef, terrain, _ = _maps()
    lo0, la0, lo1, la1 = region; md = mapdef.define([lo0, la0, lo1, la1])
    X, Y, nx, ny = region_grid(md, PLACE_N); lon, lat = md.inv(X, Y)
    span_m = md.W * md.res; px_m = span_m / (nx - 1)
    dem, sea = heights(terrain, lon, lat, px_m, -50.0)
    sf = 6; ext = 1.5                                                # the coarse ring: 1.5 regions on every side
    far = {"x0": -ext * (nx - 1), "x1": (1 + ext) * (nx - 1), "y0": -ext * (ny - 1), "y1": (1 + ext) * (ny - 1), "sf": sf}
    fxs = far["x0"] + sf * np.arange(int((far["x1"] - far["x0"]) // sf) + 1); fys = far["y0"] + sf * np.arange(int((far["y1"] - far["y0"]) // sf) + 1)
    FX, FY = np.meshgrid(fxs, fys)
    rl, ra = md.inv(FX / (nx - 1) * md.W, FY / (ny - 1) * md.H)
    ra = np.clip(ra, -85.0, 85.0)
    hr, _ = heights(terrain, rl, ra, px_m * sf, -50.0)
    ii, jj = np.meshgrid(np.arange(hr.shape[1]), np.arange(hr.shape[0]))   # the ring's land sinks to sea level at its outer
    edge = np.minimum(np.minimum(ii, hr.shape[1] - 1 - ii) / max(1, 0.2 * hr.shape[1]),       # edge, where the flat land
                      np.minimum(jj, hr.shape[0] - 1 - jj) / max(1, 0.2 * hr.shape[0]))       # beyond meets it
    hr = np.where(hr > 0, hr * np.clip(edge, 0, 1), hr)
    np.savez_compressed(os.path.join(out, "place_h.npz"), h=dem.astype(np.float32), hr=hr.astype(np.float32))
    Wi = PLACE_IMG; Hi = max(64, int(round(Wi * md.H / md.W)))
    Xi, Yi = np.meshgrid((np.arange(Wi) + 0.5) / Wi * md.W, (np.arange(Hi) + 0.5) / Hi * md.H); li, ai = md.inv(Xi, Yi)
    img = ground_picture(terrain, li, ai, span_m / Wi); save_jpg(img, os.path.join(out, "place.jpg"))
    Wr = RING_IMG; Hr = max(64, int(round(Wr * (far["y1"] - far["y0"]) / (far["x1"] - far["x0"]))))
    gx = far["x0"] + (np.arange(Wr) + 0.5) / Wr * (far["x1"] - far["x0"]); gy = far["y0"] + (np.arange(Hr) + 0.5) / Hr * (far["y1"] - far["y0"])
    GX, GY = np.meshgrid(gx, gy); rl2, ra2 = md.inv(GX / (nx - 1) * md.W, GY / (ny - 1) * md.H)
    ring = ground_picture(terrain, rl2, np.clip(ra2, -85, 85), span_m * (1 + 2 * ext) / Wr, with_shade=False)
    save_jpg(ring, os.path.join(out, "ring.jpg"))
    lum = srgb_lin(img) @ np.array([0.2126, 0.7152, 0.0722])
    span_km = span_m / 1000.0; ve = float(np.clip(1.6 * (span_km / 300.0) ** 0.3, 1.2, 4.0))
    px_km = px_m / 1000.0

    def km(path, dense=True):
        p = densify(path) if dense else np.asarray(path, float)
        Xp, Yp = md.fwd(p[:, 0], p[:, 1])
        col, row = Xp / md.W * (nx - 1), Yp / md.H * (ny - 1)
        return np.stack([(col - (nx - 1) / 2) * px_km, ((ny - 1) / 2 - row) * px_km], -1)
    D = {"region": region, "kind": kind, "heights": "place_h.npz", "image": "place.jpg", "ring_image": "ring.jpg",
         "px_km": px_km, "ve": ve, "step": 1, "ring": far, "albedo": round(float(lum.mean()), 4),
         "ring_mean": [round(float(x) / 255, 3) for x in ring.reshape(-1, 3).mean(0)], "sea": bool(kind == "sea" or sea > 0.3),
         "points": {n: [round(float(v), 4) for v in km([at], dense=False)[0]] for n, at in nd["at"].items()}}
    json.dump(D, open(os.path.join(out, "place.json"), "w"))
    return D, km


# ------------------------------------------------------------------ globe, models, cut-outs
def earth(out):
    from PIL import Image, ImageDraw
    mapdef, terrain, gb = _maps()
    Image.MAX_IMAGE_PIXELS = None
    terrain.get(terrain.BM_WORLD, "cache/bm_world.jpg")
    im = Image.open("cache/bm_world.jpg"); im.draft("RGB", (im.size[0] // 2, im.size[1] // 2))
    im = im.convert("RGB").resize((8192, 4096), Image.LANCZOS)
    ov = Image.new("L", im.size, 0); dr = ImageDraw.Draw(ov)
    for f in gb.fetch("ne_10m_admin_0_boundary_lines_land.geojson"):
        g = f.get("geometry") or {}
        lines = g.get("coordinates", []) if g.get("type") == "MultiLineString" else [g.get("coordinates", [])]
        for ln in lines:
            if len(ln) < 2: continue
            pts = [((x + 180) / 360 * 8192, (90 - y) / 180 * 4096) for x, y in ln]
            dr.line(pts, fill=255, width=3)
    a = np.asarray(im).astype(np.float32); m = np.asarray(ov).astype(np.float32)[..., None] / 255 * 0.62
    a = a * (1 - m) + np.array([238, 232, 214], np.float32) * m
    save_jpg(np.clip(a, 0, 255).astype(np.uint8), os.path.join(out, "earth.jpg"))


def model_file(order, src, store, store_dir, out, errs, credits):
    """a model's GLB into DIR: from the order store (store:<key>, checked by sha256) or from the objects stage (obj:<name>)"""
    import shutil
    kind, _, key = src.partition(":")
    if kind == "store":
        it = store.get(key)
        if not it: errs.append(f"model {src}: not in store.json"); return None
        p = os.path.join(store_dir, it["file"])
        if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != it["sha256"]:
            errs.append(f"model {src}: file missing or different from store.json"); return None
        if open(p, "rb").read(4) != b"glTF": errs.append(f"model {src}: not a GLB file"); return None
        shutil.copy(p, os.path.join(out, f"model_{key}.glb"))
        credits.append({"what": it.get("title") or key, "license": it.get("licence"), "author": it.get("author"), "page": it.get("source")})
        return {"file": f"model_{key}.glb"}
    if kind == "obj":
        op = os.path.join(order, "out", "objects.json")
        if not os.path.exists(op): errs.append(f"model {src}: the objects stage has not collected the order's objects (out/objects.json)"); return None
        mo = (json.load(open(op)).get("models") or {}).get(key)
        if not mo or not mo.get("glb"): errs.append(f"model {src}: not made by the objects stage yet"); return None
        rel = json.load(open(op)).get("release", "objects_cache")
        import requests
        r = requests.get(f"https://github.com/{REPO}/releases/download/{rel}/{mo['glb']}", timeout=300)
        if r.status_code != 200 or r.content[:4] != b"glTF": errs.append(f"model {src}: could not download {mo['glb']} ({r.status_code})"); return None
        open(os.path.join(out, f"obj_{key}.glb"), "wb").write(r.content)
        cr = mo.get("credit")
        if isinstance(cr, dict): credits.append(cr)
        if mo.get("engine") == "hunyuan":                               # the licence's notice travels with every use
            credits.append({"what": "3D model made with Tencent Hunyuan 3D 2.0", "license": "Tencent Hunyuan 3D 2.0 Community License",
                            "author": "Tencent", "page": None})
        return {"file": f"obj_{key}.glb"}
    errs.append(f"model {src}: from store:<key> or obj:<name>"); return None


def cut_figure(src_path, out_path):
    """the figure of a picture on transparency, cropped to it (feet on the bottom edge); returns its aspect"""
    from PIL import Image
    im = Image.open(src_path); im.load()
    own = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA")
    if not (own and im.getextrema()[3][0] < 255):
        import rembg
        im = rembg.remove(im.convert("RGB")).convert("RGBA")
    a = np.asarray(im)[..., 3]; ys, xs = np.nonzero(a > 128)
    if len(xs) < 64: return None
    pad = int(0.01 * max(im.size))
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.size[0], xs.max() + pad + 1), ys.max() + 1)
    c = im.crop(box); c.save(out_path)
    return c.size[0] / c.size[1]


# ------------------------------------------------------------------ everything a scene needs
def build(order, sc, out, items, store, store_dir, credits, errs):
    """writes DIR/geo.json and its files; adds models and cut-outs to items (keys obj:<name>, cut:<store key>)"""
    nd = needs(sc); geo = {}
    used_map = bool(nd["tiles"] or nd["terrains"] or nd["place"] or nd["globe"])
    if nd["tiles"]:
        T = tiles(order, nd, out, store_dir, errs)
        if T: geo["tiles"] = T; credits += [{"what": EOX}, {"what": NE_CREDIT}]
    sheets = {n: sp for n, sp in nd["splits"].items() if (sc["cast"][n]["is"] in ("sheet", "print"))}
    if sheets:
        from shapely.geometry import box as sbox
        geo["pieces"] = {}
        for n, sp in sheets.items():
            into = sp.get("into")
            if isinstance(into, list): cnt = int(into[0]) if into and str(into[0]).isdigit() else 4
            else: cnt = int(into) if into is not None else 4
            sq = sbox(-0.5, -0.5, 0.5, 0.5)
            geo["pieces"][n] = [p_ for p_ in (part(q, 0.0, 0.0) for q in jagged(sq, max(2, min(8, cnt)), n)) if p_]
    if nd["terrains"]:
        geo["terrains"] = {}
        for n, rg in nd["terrains"].items():
            if not (isinstance(rg, list) and len(rg) == 4): errs.append(f"terrain {n}: needs \"region\": [lon0, lat0, lon1, lat1]"); continue
            geo["terrains"][n] = terrain_block(rg, n, out)
        credits += [{"what": EOX}, {"what": RELIEF}]
    km = None
    if nd["place"]:
        D, km = terrain_place(nd["place"], nd["kind"], nd, out); credits += [{"what": EOX}, {"what": RELIEF}]
        geo["fly"] = {i: np.round(km(p), 4).tolist() for i, p in nd["fly"].items() if p}
    if nd["globe"]:
        earth(out); credits += [{"what": BM_CREDIT}, {"what": NE_CREDIT}]
    routes = {}
    cast = sc.get("cast") or {}
    for i, r in enumerate(nd["routes"]):
        who, path = r["who"], r["path"]
        if not (isinstance(path, list) and len(path) >= 2): errs.append(f"route {i + 1}: path needs 2+ [lon, lat] points"); continue
        if who == "place" and km is not None: routes[str(i)] = np.round(km(path), 4).tolist()
        elif who in cast and cast[who]["is"] == "tile" and geo.get("tiles"): routes[str(i)] = np.round(project_tiles(geo["tiles"], path), 5).tolist()
        elif who in cast and cast[who]["is"] == "terrain" and who in geo.get("terrains", {}): routes[str(i)] = np.round(project_block(geo["terrains"][who], path), 5).tolist()
        elif who in cast and cast[who]["is"] == "globe": routes[str(i)] = np.round(densify(path, 1.0), 4).tolist()
        else: errs.append(f"route {i + 1}: drawn on a map tile, a terrain, a globe or the place of a terrain / sea scene")
    if routes: geo["routes"] = routes
    for n, src in nd["models"].items():
        mf = model_file(order, src, store, store_dir, out, errs, credits)
        if mf: items["obj:" + src.partition(":")[2] if src.startswith("obj:") else src.partition(":")[2]] = mf
    for n, key in nd["cutouts"].items():
        it = items.get(key)
        if not it: continue
        asp = cut_figure(os.path.join(out, it["file"]), os.path.join(out, f"cut_{key}.png"))
        if asp is None: errs.append(f"cutout {n}: no figure found in {key}"); continue
        items["cut:" + key] = dict(it, file=f"cut_{key}.png", aspect=asp)
    if geo or used_map: json.dump(geo, open(os.path.join(out, "geo.json"), "w"))
    seen, uniq = set(), []
    for c in credits:
        k = json.dumps(c, sort_keys=True)
        if k not in seen: seen.add(k); uniq.append(c)
    credits[:] = uniq
    return geo
