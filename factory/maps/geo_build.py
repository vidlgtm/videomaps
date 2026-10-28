#!/usr/bin/env python3
"""GEOGRAPHY of one order on a library map -> geo.json for the director and the engine (same format as the v5 film).
Sources: Natural Earth 10 m (countries with lakes, admin-1 regions, disputed areas, rivers, populated places) and the
order store (historical shapes the order brings as GeoJSON, with their licence). Everything is projected with the map's
own formulas (mapdef.py), so borders sit exactly on the terrain.
Worldview: Natural Earth draws borders de facto (who holds the land: Crimea inside Russia). Countries are drawn in the
de jure view of the United States (Natural Earth point of view "usa": Crimea in Ukraine, Abkhazia and South Ossetia in
Georgia, Baikonur in Kazakhstan, Northern Cyprus in Cyprus), with the boundary lakes cut out as in the drawing data.

ids written (the places of order.json / storyboard.json):
  rep:<ISO3>      the film's countries (order.json "countries")          republics
  ctx:<ISO3>      every other country on the canvas (names for the era sets)   context
  shape:<id>      historical shapes (order.json "shapes") + shape:frontier (outline of the film's countries)
  rr:<name>       admin-1 regions (order.json "regions": {"Name": ["ISO3", "name regex"]})
  brk:<name>      disputed areas (order.json "disputed": {"Name": "name regex"})
  river:<name>    rivers on the canvas (Natural Earth scalerank <= 6 + order.json "rivers")
  cities          capitals + large cities on the canvas + the order's capitals and point places
order.json "shapes": {"<id>": {"store": "<store key of a GeoJSON>", "where": {"<property>": "regex"}}
                             | {"union": ["ISO3" | "shape:<id>" | "rr:<name>" | "brk:<name>", ...], "minus": [...]}
                             | {"admin1": ["ISO3", "name regex"]}}
usage: python factory/maps/geo_build.py <mapDir> <orderDir> <storeDir|-> <out geo.json>
exit code 2 = the order names a country, region or shape that does not exist (all problems listed)."""
import json, os, re, sys, time
import numpy as np
import requests
from shapely.geometry import shape as to_shape, box, Polygon, LineString, MultiLineString, Point
from shapely.ops import transform, unary_union, polylabel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapdef

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
UA = {"User-Agent": "videomaps-geo/1.0 (https://github.com/vidlgtm/videomaps)"}
os.makedirs("cache", exist_ok=True)
ERR = []
WORLDVIEW = "usa"                        # Natural Earth point-of-view file ne_10m_admin_0_countries_<WORLDVIEW>
WORLDVIEW_FCLASS = "fclass_us"           # the same view in the boundary-line data
HIDDEN_LINES = ("Unrecognized", "Admin-1 boundary", "Claim boundary")   # lines that view does not draw as borders


def fetch(name):
    p = f"cache/{name}"
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        for i in range(6):
            try:
                r = requests.get(NE + name, timeout=600, headers=UA); r.raise_for_status()
                open(p + ".part", "wb").write(r.content); os.replace(p + ".part", p); break
            except Exception:
                if i == 5: raise
                time.sleep(3 + 4 * i)
    return json.load(open(p, encoding="utf-8"))["features"]


def big_parts(g, min_area=2e-4):
    """the polygons of g larger than min_area square degrees (about 2 km2): drops slivers where two files digitise the
    same border slightly differently; None when nothing is left"""
    if g is None or g.is_empty: return None
    polys = [g] if g.geom_type == "Polygon" else [q for q in getattr(g, "geoms", []) if q.geom_type == "Polygon"]
    keep = [q for q in polys if q.area >= min_area]
    return unary_union(keep) if keep else None


def props(f):
    return {k.lower(): v for k, v in (f.get("properties") or {}).items()}


def geom(f):
    try:
        g = to_shape(f["geometry"])
        return g if g.is_valid else g.buffer(0)
    except Exception:
        return None


class Geo:
    def __init__(self, md, order, store_dir):
        self.md, self.o, self.store_dir = md, order, store_dir
        lb = md.lonlat_box()
        self.llbox = box(max(-180, lb[0] - 3), max(-89.5, lb[1] - 3), min(180, lb[2] + 3), min(89.5, lb[3] + 3))
        self.frame = box(-300, -300, md.W + 300, md.H + 300)
        self.init_countries()
        self._adm1 = None; self._brk = None
        self.cache = {}

    def init_countries(self):
        """admin-0 sources: countries with boundary lakes (the drawing), the worldview file and the default file (their
        difference is the land the worldview gives to another country than the de facto data)"""
        self.adm0 = fetch("ne_10m_admin_0_countries_lakes.geojson")
        self.pov = fetch(f"ne_10m_admin_0_countries_{WORLDVIEW}.geojson")
        self.dflt = fetch("ne_10m_admin_0_countries.geojson")
        index = lambda fs: [({props(f).get("adm0_a3"), props(f).get("iso_a3"), props(f).get("iso_a3_eh")}, f) for f in fs]
        self.ix = {"lakes": index(self.adm0), "pov": index(self.pov), "dflt": index(self.dflt)}
        self.delta, self.gcache = {}, {}

    # ---------------------------------------------------------------- projection helpers (as the v5 geodata)
    def to_px(self, g):
        g = g.intersection(self.llbox)
        if g.is_empty: return g
        g = transform(lambda x, y: self.md.fwd(np.asarray(x), np.asarray(y)), g)
        g = g if g.is_valid else g.buffer(0)
        return g.intersection(self.frame)

    def pxy(self, lon, lat):
        x, y = self.md.fwd(lon, lat); return [round(float(x), 1), round(float(y), 1)]

    @staticmethod
    def path_d(g, tol=0.4, min_area=1.5):
        if g is None or g.is_empty: return ""
        polys = [g] if isinstance(g, Polygon) else [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
        out = []
        for p in polys:
            if p.area < min_area: continue
            p = p.simplify(tol, preserve_topology=True)
            for ring in [p.exterior] + list(p.interiors):
                c = np.asarray(ring.coords)
                if len(c) < 4: continue
                out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in c[:-1]) + "Z")
        return "".join(out)

    @staticmethod
    def line_d(g, tol=0.6):
        if g is None or g.is_empty: return ""
        lines = [g] if isinstance(g, LineString) else [l for l in getattr(g, "geoms", []) if isinstance(l, LineString)]
        out = []
        for l in lines:
            c = np.asarray(l.simplify(tol).coords)
            if len(c) >= 2: out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in c))
        return "".join(out)

    @staticmethod
    def label_pt(gp):
        polys = [gp] if isinstance(gp, Polygon) else [p for p in gp.geoms if isinstance(p, Polygon)]
        big = max(polys, key=lambda p: p.area)
        pt = polylabel(big, tolerance=1.0)
        return [round(pt.x, 1), round(pt.y, 1)]

    def feat(self, fid, g, extra=None, tol=0.4):
        if g is None or g.is_empty: return None
        gp = self.to_px(g)
        if gp.is_empty or gp.area < 2: return None
        gp = gp.buffer(0.35).buffer(-0.35)                     # weld slivers between source parts
        f = {"id": fid, "d": self.path_d(gp, tol), "label": self.label_pt(gp), "bbox": [round(v, 1) for v in gp.bounds],
             "area_px": round(gp.area)}
        if extra: f.update(extra)
        return f

    # ---------------------------------------------------------------- sources
    def hits(self, which, iso):
        """features of one admin-0 file that belong to country iso (its own code, ISO code or 'equivalent' code)"""
        return [f for cs, f in self.ix[which] if iso in cs]

    def _others(self, which, iso, area):
        """union of the features of one admin-0 file that belong to another country than iso and touch area"""
        gs = []
        for cs, f in self.ix[which]:
            if iso in cs: continue
            k = (which, id(f))
            if k not in self.gcache: self.gcache[k] = geom(f)
            g = self.gcache[k]
            if g is not None and g.intersects(area): gs.append(g)
        return unary_union(gs) if gs else None

    def _delta(self, iso):
        """(gained, lost): land the worldview gives to iso / gives to another country, compared with the de facto data.
        Only a change of owner counts: land missing from one file (the 'usa' file has no Adjara) is a hole, not a change."""
        if iso not in self.delta:
            hp, hd = self.hits("pov", iso), self.hits("dflt", iso)
            gained = lost = None
            if [f["geometry"] for f in hp] != [f["geometry"] for f in hd]:
                gp = unary_union([g for g in map(geom, hp) if g is not None]) if hp else None
                gd = unary_union([g for g in map(geom, hd) if g is not None]) if hd else None
                gained = big_parts(gp.difference(gd) if gp is not None and gd is not None else gp)
                lost = big_parts(gd.difference(gp) if gp is not None and gd is not None else gd)
                if gained is not None:                    # held by another country in the de facto data
                    o = self._others("dflt", iso, gained); gained = big_parts(gained.intersection(o)) if o is not None else None
                if lost is not None:                      # given to another country by the worldview
                    o = self._others("pov", iso, lost); lost = big_parts(lost.intersection(o)) if o is not None else None
            self.delta[iso] = (gained, lost)
        return self.delta[iso]

    def land(self, iso):
        """country iso as the worldview draws it, boundary lakes cut out; None when Natural Earth has no land for it"""
        key = "l:" + iso
        if key not in self.cache:
            hl = self.hits("lakes", iso)
            g = unary_union([x for x in map(geom, hl) if x is not None]) if hl else None
            gained, lost = self._delta(iso)
            if gained is not None: g = gained if g is None else g.union(gained)
            if lost is not None and g is not None: g = g.difference(lost)
            if g is not None and not g.is_empty and not g.is_valid: g = g.buffer(0)
            self.cache[key] = g if g is not None and not g.is_empty else None
        return self.cache[key]

    def country(self, iso):
        key = "c:" + iso
        if key in self.cache: return self.cache[key]
        g = self.land(iso)
        hits = self.hits("pov", iso) or self.hits("lakes", iso)
        if g is None or not hits:
            ERR.append(f'country "{iso}" is not in Natural Earth (use its ADM0_A3 code)'); self.cache[key] = None; return None
        p = props(next((f for f in hits if props(f).get("adm0_a3") == iso), hits[0]))
        self.cache[key] = g
        self.cache["n:" + iso] = p.get("name_en") or p.get("name") or iso
        iso2 = str(p.get("iso_a2_eh") or p.get("iso_a2") or "").lower()
        self.cache["i2:" + iso] = iso2 if re.fullmatch(r"[a-z]{2}", iso2) else None
        return g

    def adm1(self):
        if self._adm1 is None: self._adm1 = fetch("ne_10m_admin_1_states_provinces_lakes.geojson")
        return self._adm1

    def admin1(self, iso, pattern):
        """admin-1 regions of iso whose name matches pattern, in the worldview: Natural Earth files them under the country that
        holds them (Crimea under RUS), so a region inside land the worldview gives to iso counts for iso, and one inside land
        it gives away does not"""
        gained, lost = self._delta(iso)
        sel, away = [], []
        for f in self.adm1():
            p = props(f)
            if not re.search(pattern, str(p.get("name") or ""), re.I): continue
            mine = p.get("adm0_a3") == iso
            if not mine and gained is None: continue
            g = geom(f)
            if g is None: continue
            pt = g.representative_point()
            if mine and lost is not None and lost.contains(pt): away.append(str(p.get("name"))); continue
            if mine or gained.contains(pt): sel.append(g)
        if not sel:
            ERR.append(f'admin-1 region "{pattern}" not found in {iso}' +
                       (f' ({", ".join(away)}: not part of {iso} in the worldview "{WORLDVIEW}")' if away else '')); return None
        return unary_union(sel)

    def disputed(self, pattern):
        if self._brk is None: self._brk = fetch("ne_10m_admin_0_disputed_areas.geojson")
        for f in self._brk:
            if any(isinstance(v, str) and re.search(pattern, v, re.I) for v in props(f).values()):
                return geom(f)
        ERR.append(f'disputed area "{pattern}" not found'); return None

    def store_geojson(self, key, where):
        sj = os.path.join(self.o["_dir"], "store.json")
        items = json.load(open(sj))["items"] if os.path.exists(sj) else {}
        it = items.get(key)
        if not it: ERR.append(f'shape store key "{key}" is not in store.json'); return None
        p = os.path.join(self.store_dir, it["file"]) if self.store_dir != "-" else None
        if not p or not os.path.exists(p): ERR.append(f"store file {it['file']} is missing"); return None
        fs = json.load(open(p, encoding="utf-8"))
        fs = fs["features"] if fs.get("type") == "FeatureCollection" else [fs]
        if where:
            fs = [f for f in fs if all(re.search(rx, str(props(f).get(k.lower(), "")), re.I) for k, rx in where.items())]
        gs = [geom(f) for f in fs]
        gs = [g for g in gs if g is not None and not g.is_empty]
        if not gs: ERR.append(f'shape "{key}": no feature matches {where}'); return None
        return unary_union(gs)

    def resolve(self, ref, shapes_spec, regions, depth=0):
        """'ISO3' | 'rep:ISO3' | 'ctx:ISO3' | 'shape:<id>' | 'rr:<name>' | 'brk:<name>' -> lon/lat geometry"""
        if depth > 12: ERR.append(f"shape {ref}: circular definition"); return None
        if ref.startswith("shape:"): return self.shape(ref[6:], shapes_spec, regions, depth + 1)
        if ref.startswith("rr:"):
            r = regions.get(ref[3:])
            if not r: ERR.append(f'region "{ref}" is not in order.json "regions"'); return None
            return self.admin1(r[0], r[1])
        if ref.startswith("brk:"):
            rx = (self.o.get("disputed") or {}).get(ref[4:])
            if not rx: ERR.append(f'disputed area "{ref}" is not in order.json "disputed"'); return None
            return self.disputed(rx)
        iso = ref.split(":", 1)[1] if ref.startswith(("rep:", "ctx:")) else ref
        return self.country(iso)

    def shape(self, sid, spec, regions, depth=0):
        key = "s:" + sid
        if key in self.cache: return self.cache[key]
        s = spec.get(sid)
        if s is None: ERR.append(f'shape "{sid}" is not in order.json "shapes"'); return None
        g = None
        if "store" in s: g = self.store_geojson(s["store"], s.get("where"))
        elif "admin1" in s: g = self.admin1(s["admin1"][0], s["admin1"][1])
        elif "union" in s:
            parts = [self.resolve(r, spec, regions, depth + 1) for r in s["union"]]
            parts = [p for p in parts if p is not None]
            g = unary_union(parts) if parts else None
        else: ERR.append(f'shape "{sid}": needs "store", "union" or "admin1"')
        if g is not None and s.get("minus"):
            cut = [self.resolve(r, spec, regions, depth + 1) for r in s["minus"]]
            cut = [c for c in cut if c is not None]
            if cut: g = g.difference(unary_union(cut)).buffer(-0.01).buffer(0.01)   # opening removes dataset-mismatch slivers
        self.cache[key] = g
        return g


def main(a):
    if len(a) < 4: print(__doc__); sys.exit(1)
    mdir, odir, sdir, out = a
    md = mapdef.load(os.path.join(mdir, "map.json"))
    o = json.load(open(os.path.join(odir, "order.json"), encoding="utf-8")); o["_dir"] = odir
    G = Geo(md, o, sdir)
    geo = {**md.geo_header(), "republics": [], "shapes": {}, "rus_republics": [], "breakaway": [], "context": [], "rivers": [], "cities": {}}
    film = list(o.get("countries") or [])
    for iso in film:
        g = G.country(iso)
        f = G.feat(iso, g, {"name": G.cache.get("n:" + iso, iso), "iso2": G.cache.get("i2:" + iso)})
        if f: geo["republics"].append(f)
        elif g is not None: ERR.append(f"country {iso} is outside the map canvas")
    regions = o.get("regions") or {}
    for name, (iso, rx) in regions.items():
        f = G.feat(name, G.admin1(iso, rx), {"name": name})
        if f: geo["rus_republics"].append(f)
    for name, rx in (o.get("disputed") or {}).items():
        f = G.feat(name, G.disputed(rx), {"name": name})
        if f: geo["breakaway"].append(f)
    spec = o.get("shapes") or {}
    for sid in spec:
        f = G.feat(sid, G.shape(sid, spec, regions))
        if f: geo["shapes"][sid] = f
        else: ERR.append(f'shape "{sid}" is empty or outside the map canvas')
    # outline of the film's countries (border "frontier")
    U = [G.to_px(G.cache["c:" + i]) for i in film if G.cache.get("c:" + i) is not None]
    if U:
        U = unary_union(U).buffer(0.35).buffer(-0.35)
        polys = [U] if isinstance(U, Polygon) else sorted([p for p in U.geoms if isinstance(p, Polygon)], key=lambda p: -p.area)
        geo["shapes"]["frontier"] = {"id": "frontier", "d": G.line_d(MultiLineString([p.exterior for p in polys if p.area > 400]), 1.0)}
    # every other country on the canvas, as the worldview draws it (a piece of another country is not a neighbour of its
    # own: Baikonur is Kazakhstan, Abkhazia and South Ossetia are Georgia)
    seen = set(film)
    adm = {props(f).get("adm0_a3") for f in G.pov}
    for f in G.pov:
        p = props(f); iso = p.get("adm0_a3")
        if not iso or iso in seen: continue
        eh = p.get("iso_a3_eh")
        if eh and eh != iso and (eh in adm or eh in film): continue
        g0 = geom(f)
        if g0 is None or not g0.intersects(G.llbox): continue
        g = G.land(iso)
        if g is None: continue
        try: gp = G.to_px(g)
        except Exception: continue
        if gp.is_empty or gp.area < 30: continue
        seen.add(iso)
        iso2 = str(p.get("iso_a2_eh") or p.get("iso_a2") or "").lower()
        geo["context"].append({"id": iso, "name": p.get("name_en") or p.get("name"), "d": G.path_d(gp, 0.6, 3), "label": G.label_pt(gp),
                               "iso2": iso2 if re.fullmatch(r"[a-z]{2}", iso2) else None})
    # rivers
    want = [str(r).lower() for r in (o.get("rivers") or [])]
    by = {}
    for f in fetch("ne_10m_rivers_lake_centerlines.geojson"):
        p = props(f); nm = p.get("name_en") or p.get("name")
        if not nm: continue
        rank = p.get("scalerank") if p.get("scalerank") is not None else 9
        if rank > 6 and nm.lower() not in want: continue
        g = geom(f)
        if g is None or not g.intersects(G.llbox): continue
        by.setdefault(nm, []).append(g)
    for nm, gs in sorted(by.items()):
        gp = G.to_px(unary_union(gs))
        if gp.is_empty or gp.length < 60: continue
        geo["rivers"].append({"id": nm, "d": G.line_d(gp, 0.8)})
    for r in want:
        if not any(x["id"].lower() == r for x in geo["rivers"]): ERR.append(f'river "{r}" not found on the canvas')
    # cities: capitals + large cities on the canvas, then the order's own points
    for f in fetch("ne_10m_populated_places_simple.geojson"):
        p = props(f)
        rank = p.get("scalerank") if p.get("scalerank") is not None else 10
        if not (p.get("adm0cap") in (1, 1.0) or rank <= 3): continue
        lon, lat = float(p.get("longitude")), float(p.get("latitude"))
        if not G.llbox.contains(Point(lon, lat)): continue
        xy = G.pxy(lon, lat)
        if 0 <= xy[0] <= md.W and 0 <= xy[1] <= md.H:
            geo["cities"][p.get("name")] = {"lonlat": [lon, lat], "px": xy}
    for iso, c in (o.get("capitals") or {}).items():        # capitals given as a name must be a known city
        if isinstance(c, str) and c not in geo["cities"] and c not in (o.get("places") or {}):
            ERR.append(f'capital "{c}" of {iso}: not a Natural Earth city on the canvas - give [lon, lat] or add it to "places"')
    if ERR:
        print("GEOGRAPHY ERROR - the order names things the map cannot draw:")
        for e in ERR: print("  -", e)
        sys.exit(2)
    json.dump(geo, open(out, "w"), separators=(",", ":"))
    print(f"geo.json {os.path.getsize(out) / 1e6:.2f} MB: {len(geo['republics'])} countries, {len(geo['context'])} neighbours, "
          f"{len(geo['shapes'])} shapes, {len(geo['rus_republics'])} regions, {len(geo['breakaway'])} disputed, {len(geo['rivers'])} rivers, "
          f"{len(geo['cities'])} cities | map {md.kind} {md.W}x{md.H} {md.res / 1000:.3f} km/px | worldview {WORLDVIEW}")


if __name__ == "__main__":
    main(sys.argv[1:])
