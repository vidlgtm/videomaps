"""Map data for the film, all projected ONCE here so raster and vectors align perfectly.
Projection: Lambert Conformal Conic centred on the USSR (the classic Soviet-atlas look).
Sources: Natural Earth 10m vectors + Natural Earth HYP_HR_SR_OB_DR raster (public domain),
historical-basemaps world_1938 (only to cut pre-1939 Soviet borders in the west/east).
Historical traps handled: Crimea -> Ukraine only from 1954; 1991 Ukraine includes Crimea;
pre-1936 Uzbek SSR without Karakalpakstan (+Tajik ASSR until 1929); Transcaucasian SFSR;
Karelo-Finnish SSR (1940-56); USSR 1938 outline without Baltics, W. Ukraine/Belarus,
Bessarabia, East Prussia, S. Sakhalin, Tuva."""
import json, os, re, sys, zipfile, math
import numpy as np, requests
import geopandas as gpd, warnings
warnings.filterwarnings('ignore')
from shapely.geometry import box, Point, Polygon, MultiPolygon, LineString, MultiLineString
from shapely.ops import unary_union, transform
from shapely.ops import polylabel
from pyproj import Transformer, CRS
from PIL import Image
import cv2

Image.MAX_IMAGE_PIXELS = None
OUT = "out/geo"; os.makedirs(OUT, exist_ok=True); os.makedirs("cache", exist_ok=True)
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
LON0, LAT0, LAT1, LAT2 = 90.0, 55.0, 45.0, 62.0
PROJ = f"+proj=lcc +lat_1={LAT1} +lat_2={LAT2} +lat_0={LAT0} +lon_0={LON0} +R=6371000 +units=m +no_defs"
W = 8192
fw = Transformer.from_crs("EPSG:4326", CRS.from_proj4(PROJ), always_xy=True)
inv = Transformer.from_crs(CRS.from_proj4(PROJ), "EPSG:4326", always_xy=True)
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s); log.append(s)


def fetch(url, name):
    p = f"cache/{name}"
    if not os.path.exists(p):
        r = requests.get(url, timeout=600, stream=True); r.raise_for_status()
        with open(p, "wb") as fh:
            for ch in r.iter_content(1 << 20): fh.write(ch)
    return p


rd = lambda n: gpd.read_file(fetch(NE + n, n))
adm0 = rd("ne_10m_admin_0_countries_lakes.geojson")
adm1 = rd("ne_10m_admin_1_states_provinces_lakes.geojson")
brk = rd("ne_10m_admin_0_disputed_areas.geojson")
rivers = rd("ne_10m_rivers_lake_centerlines.geojson")
hist = gpd.read_file(fetch("https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1938.geojson", "world_1938.geojson"))

A0 = lambda iso: unary_union(adm0[adm0["ADM0_A3"] == iso].geometry.values)
USSR = ["RUS", "UKR", "BLR", "KAZ", "UZB", "TKM", "KGZ", "TJK", "GEO", "ARM", "AZE", "MDA", "EST", "LVA", "LTU"]
NAMES = {"RUS": "Russia", "UKR": "Ukraine", "BLR": "Belarus", "KAZ": "Kazakhstan", "UZB": "Uzbekistan", "TKM": "Turkmenistan",
         "KGZ": "Kyrgyzstan", "TJK": "Tajikistan", "GEO": "Georgia", "ARM": "Armenia", "AZE": "Azerbaijan", "MDA": "Moldova",
         "EST": "Estonia", "LVA": "Latvia", "LTU": "Lithuania"}
G = {iso: A0(iso) for iso in USSR}

# --- Crimea: NE default puts it in RUS as a separate polygon part (incl. Sevastopol)
cbox = box(32.3, 44.2, 36.65, 46.3)
rparts = list(G["RUS"].geoms)
crimea = unary_union([p for p in rparts if cbox.contains(p.representative_point())])
say("Crimea parts area(deg2):", round(crimea.area, 3))
assert 2.0 < crimea.area < 4.0, "Crimea extraction failed"
RUS_NE = G["RUS"]                                     # Russia incl. Crimea (= RSFSR 1945-1954 + Crimea)
G["RUS"] = MultiPolygon([p for p in rparts if not cbox.contains(p.representative_point())])
UKR_noC = G["UKR"]
G["UKR"] = unary_union([UKR_noC, crimea])             # 1991 Ukraine

# --- admin-1 pieces
def a1(country, pattern):
    sel = adm1[(adm1["adm0_a3"] == country) & adm1["name"].fillna("").str.contains(pattern, case=False, regex=True)]
    if len(sel) == 0: say("WARN admin-1 not found:", country, pattern); return None
    return unary_union(sel.geometry.values)

karak = a1("UZB", r"Karakalpak")
karelia = a1("RUS", r"^Karel")
RREP = {"Tatarstan": r"^Tatarstan", "Bashkortostan": r"^Bashkortostan", "Chuvashia": r"^Chuvash", "Mari El": r"^Mariy|^Mari",
        "Udmurtia": r"^Udmurt", "Mordovia": r"^Mordov", "Chechnya": r"^Chechnya|^Chechen", "Ingushetia": r"^Ingush",
        "Dagestan": r"^Dagestan", "North Ossetia": r"North Ossetia", "Kabardino-Balkaria": r"^Kabardin",
        "Karachay-Cherkessia": r"^Karachay", "Adygea": r"^Adyge", "Kalmykia": r"^Kalmyk", "Karelia": r"^Karel",
        "Komi": r"^Komi$", "Sakha (Yakutia)": r"Sakha|Yakut", "Buryatia": r"^Buryat", "Tuva": r"^Tuva",
        "Khakassia": r"^Khakas", "Altai Republic": r"^Gorno-Altay|^Altay$"}
rrep = {k: a1("RUS", v) for k, v in RREP.items()}

# --- breakaway regions
def brk_find(pattern):
    for col in brk.columns:                    # pandas 3 uses a string dtype (not object): test every non-geometry column
        if col == "geometry": continue
        m = brk[brk[col].astype(str).str.contains(pattern, case=False, regex=True, na=False)]
        if len(m): return unary_union(m.geometry.values)
    say("WARN breakaway not found:", pattern); return None
BRK = {"Abkhazia": brk_find(r"Abkhaz"), "South Ossetia": brk_find(r"South Ossetia"),
       "Transnistria": brk_find(r"Transnist|Pridnestrov"), "Nagorno-Karabakh": brk_find(r"Karabakh|Artsakh")}

# --- 1938 neighbours from historical-basemaps (to cut pre-1939 Soviet borders)
hn = next(c for c in ["NAME", "name", "ABBREVN"] if c in hist.columns)
near = hist[hist.intersects(box(10, 30, 180, 82))]
say("world_1938 names near USSR:", sorted(set(near[hn].dropna().astype(str)))[:80])
def H(pattern):
    m = hist[hist[hn].fillna("").astype(str).str.contains(pattern, case=False, regex=True)]
    if len(m) == 0: say("WARN 1938 polity not found:", pattern); return None
    return unary_union(m.geometry.values).buffer(0)
NOT_USSR_1938 = [g for g in [H(r"^Poland"), H(r"Romania"), H(r"Finland"), H(r"Estonia"), H(r"Latvia"), H(r"Lithuania"),
                             H(r"German"), H(r"Japan"), H(r"Tuva|Tannu"), H(r"Czech"), H(r"Hungar"), H(r"Manchu")] if g is not None]
if rrep.get("Tuva") is not None: NOT_USSR_1938.append(rrep["Tuva"])   # Tuvan People's Republic joined only in 1944
cut38 = unary_union(NOT_USSR_1938) if NOT_USSR_1938 else None
def pre39(g):
    if cut38 is None: return g
    return g.difference(cut38).buffer(-0.02).buffer(0.02)   # opening removes dataset-mismatch slivers

S = {}  # historical shapes
S["ussr_1991"] = unary_union(list(G.values()))
S["ussr_1938"] = pre39(unary_union([RUS_NE, UKR_noC, G["BLR"], G["KAZ"], G["UZB"], G["TKM"], G["KGZ"], G["TJK"],
                                     G["GEO"], G["ARM"], G["AZE"]] + ([BRK["Transnistria"]] if BRK["Transnistria"] is not None else [])))
S["rsfsr_1922"] = pre39(unary_union([RUS_NE, G["KAZ"], G["KGZ"], G["UZB"], G["TKM"], G["TJK"]]))
S["ukr_1936"] = pre39(unary_union([UKR_noC] + ([BRK["Transnistria"]] if BRK["Transnistria"] is not None else [])))
S["blr_1936"] = pre39(G["BLR"])
S["tsfsr"] = unary_union([G["GEO"], G["ARM"], G["AZE"]])
S["uzb_1924"] = unary_union([G["UZB"], G["TJK"]]).difference(karak).buffer(0) if karak is not None else unary_union([G["UZB"], G["TJK"]])
S["uzb_1929"] = G["UZB"].difference(karak).buffer(0) if karak is not None else G["UZB"]
S["rsfsr_1936"] = pre39(RUS_NE)
S["ukr_1945"] = UKR_noC
S["rsfsr_1954"] = RUS_NE
S["kfssr"] = karelia
S["karakalpakstan"] = karak
S["crimea"] = crimea
_open = lambda g: g.buffer(-0.01).buffer(0.01)
S["rsfsr_1924"] = _open(S["rsfsr_1922"].difference(unary_union([S["uzb_1924"], G["TKM"]])))
S["rsfsr_1929"] = _open(S["rsfsr_1922"].difference(unary_union([S["uzb_1929"], G["TKM"], G["TJK"]])))
S["rsfsr_1940"] = _open(RUS_NE.difference(karelia)) if karelia is not None else RUS_NE

# --- extent: USSR 1991 + margin
X = transform(lambda x, y: fw.transform(x, y), S["ussr_1991"])
minx, miny, maxx, maxy = X.bounds
mx, my = (maxx - minx) * 0.07, (maxy - miny) * 0.10
minx, maxx, miny, maxy = minx - mx, maxx + mx, miny - my, maxy + my
RES = (maxx - minx) / W
H_ = int(math.ceil((maxy - miny) / RES))
say("canvas", W, "x", H_, "res km/px", round(RES / 1000, 3))
n_cone = math.log(math.cos(math.radians(LAT1)) / math.cos(math.radians(LAT2))) / math.log(
    math.tan(math.pi / 4 + math.radians(LAT2) / 2) / math.tan(math.pi / 4 + math.radians(LAT1) / 2))


def to_px(g):
    g = transform(lambda x, y: fw.transform(x, y), g)
    return transform(lambda x, y: ((np.asarray(x) - minx) / RES, (maxy - np.asarray(y)) / RES), g)


def pxy(lon, lat):
    x, y = fw.transform(lon, lat); return [round((x - minx) / RES, 1), round((maxy - y) / RES, 1)]


def path_d(g, tol=0.4, min_area=1.5):
    if g is None or g.is_empty: return ""
    polys = [g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))
    out = []
    for p in polys:
        if not isinstance(p, Polygon) or p.area < min_area: continue
        p = p.simplify(tol, preserve_topology=True)
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords)
            if len(c) < 4: continue
            out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in c[:-1]) + "Z")
    return "".join(out)


def line_d(g, tol=0.6):
    if g is None or g.is_empty: return ""
    lines = [g] if isinstance(g, LineString) else list(getattr(g, "geoms", []))
    out = []
    for l in lines:
        if not isinstance(l, LineString): continue
        c = np.asarray(l.simplify(tol).coords)
        if len(c) >= 2: out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in c))
    return "".join(out)


def label_pt(gpx):
    polys = [gpx] if isinstance(gpx, Polygon) else list(gpx.geoms)
    big = max(polys, key=lambda p: p.area)
    pt = polylabel(big, tolerance=1.0)
    return [round(pt.x, 1), round(pt.y, 1)]


def feat(name, g, extra=None, tol=0.4):
    if g is None or g.is_empty: return None
    gp = to_px(g)
    if name == "RUS" or name.startswith("ussr") or name.startswith("rsfsr"):
        gp = gp.buffer(0.35).buffer(-0.35)   # weld the antimeridian seam
    b = gp.bounds
    f = {"id": name, "d": path_d(gp, tol), "label": label_pt(gp), "bbox": [round(v, 1) for v in b],
         "area_px": round(gp.area)}
    if extra: f.update(extra)
    return f


geo = {"width": W, "height": H_, "proj": PROJ, "res_m": RES, "minx": minx, "maxy": maxy, "lon0": LON0, "cone_n": n_cone,
       "republics": [], "shapes": {}, "rus_republics": [], "breakaway": [], "context": [], "rivers": [], "cities": {}}
for iso in USSR:
    geo["republics"].append(feat(iso, G[iso], {"name": NAMES[iso]}))
for k, g in S.items():
    f = feat(k, g)
    if f: geo["shapes"][k] = f
for k, g in rrep.items():
    f = feat(k, g, {"name": k})
    if f: geo["rus_republics"].append(f)
for k, g in BRK.items():
    f = feat(k, g, {"name": k})
    if f: geo["breakaway"].append(f)

# context countries inside the canvas (clipped)
canvas_ll = None
corners = [inv.transform(minx + (maxx - minx) * i / 40, maxy - (maxy - miny) * j / 40) for i in range(41) for j in range(41)]
lons = [c[0] for c in corners]; lats = [c[1] for c in corners]
ctx_box = box(max(-180, min(lons) - 5), max(-85, min(lats) - 5), 180, min(85, max(lats) + 5))
frame = box(-200, -200, W + 200, H_ + 200)
for _, r in adm0.iterrows():
    iso = r["ADM0_A3"]
    if iso in USSR or not r.geometry.intersects(ctx_box): continue
    try:
        gp = to_px(r.geometry.intersection(ctx_box)).intersection(frame)
    except Exception:
        continue
    if gp.is_empty or gp.area < 30: continue
    geo["context"].append({"id": iso, "name": r.get("NAME_EN") or r.get("NAME"), "d": path_d(gp, 0.6, 3), "label": label_pt(gp)})

# outer frontier of the USSR (1991) - glowing perimeter for Stalin's first rule
U = to_px(S["ussr_1991"]).buffer(0.35).buffer(-0.35)
polys = [U] if isinstance(U, Polygon) else sorted(U.geoms, key=lambda p: -p.area)
geo["shapes"]["ussr_frontier"] = {"id": "ussr_frontier", "d": line_d(MultiLineString([p.exterior for p in polys if p.area > 400]), 1.0)}

# rivers (Volga & Kama for the Tatarstan scene, plus a few majors)
for nm in ["Volga", "Kama", "Dnieper|Dnipro", "Don", "Amu.?Dar.*", "Syr.?Dar.*", "Ural", "Ob", "Yenisey|Yenisei", "Lena"]:
    m = rivers[rivers["name"].fillna("").str.fullmatch(nm, case=False) | rivers.get("name_en", rivers["name"]).fillna("").str.fullmatch(nm, case=False)]
    if len(m) == 0: say("WARN river not found", nm); continue
    gp = to_px(unary_union(m.geometry.values)).intersection(frame)
    geo["rivers"].append({"id": nm.split("|")[0], "d": line_d(gp, 0.8)})

CITIES = {"Moscow": (37.62, 55.75), "Kazan": (49.11, 55.79), "Ufa": (55.96, 54.74), "Cheboksary": (47.25, 56.13),
          "Grozny": (45.69, 43.32), "Tallinn": (24.75, 59.44), "Riga": (24.11, 56.95), "Vilnius": (25.28, 54.69),
          "Kyiv": (30.52, 50.45), "Kharkiv": (36.23, 49.99), "Minsk": (27.56, 53.90), "Chisinau": (28.86, 47.01),
          "Tbilisi": (44.79, 41.72), "Yerevan": (44.51, 40.18), "Baku": (49.87, 40.41), "Tashkent": (69.24, 41.30),
          "Ashgabat": (58.38, 37.95), "Dushanbe": (68.79, 38.56), "Bishkek": (74.59, 42.87), "Almaty": (76.95, 43.24),
          "Simferopol": (34.10, 44.95), "Sevastopol": (33.52, 44.62), "Petrozavodsk": (34.35, 61.79),
          "Viskuli": (23.84, 52.63), "Sukhumi": (41.02, 43.00), "Tskhinvali": (43.96, 42.23), "Tiraspol": (29.63, 46.84),
          "Stepanakert": (46.75, 39.82), "Leningrad": (30.32, 59.94), "Kaliningrad": (20.51, 54.71),
          "Vladivostok": (131.89, 43.12), "Helsinki": (24.94, 60.17), "Warsaw": (21.01, 52.23), "Bucharest": (26.10, 44.43)}
geo["cities"] = {k: {"lonlat": v, "px": pxy(*v)} for k, v in CITIES.items()}
json.dump(geo, open(f"{OUT}/geo.json", "w"), separators=(",", ":"))
say("geo.json MB", round(os.path.getsize(f"{OUT}/geo.json") / 1e6, 2))

# ---------------- raster basemap (reprojected + graded) ----------------
if os.environ.get("NORASTER"):
    open(f"{OUT}/log.txt", "w").write("\n".join(log)); sys.exit(0)
zp = fetch("https://naciscdn.org/naturalearth/10m/raster/HYP_HR_SR_OB_DR.zip", "HYP_HR_SR_OB_DR.zip")
with zipfile.ZipFile(zp) as z:
    tif = next(n for n in z.namelist() if n.lower().endswith(".tif"))
    z.extract(tif, "cache")
src = np.asarray(Image.open(f"cache/{tif}").convert("RGB"))
SH, SW = src.shape[:2]
say("source raster", SW, SH)


def grade(img):
    f = img.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    water = np.clip(((b - r) - 0.04) / 0.10, 0, 1)[..., None]
    lum = (0.3 * r + 0.59 * g + 0.11 * b)[..., None]
    deep, shallow = np.array([0.07, 0.22, 0.32]), np.array([0.38, 0.62, 0.68])
    wcol = deep + (shallow - deep) * np.clip((lum - 0.45) / 0.45, 0, 1) ** 1.3
    grey = lum.repeat(3, -1)
    land = np.clip((grey + (f - grey) * 0.82 - 0.5) * 1.08 + 0.5, 0, 1) * np.array([1.02, 1.0, 0.95])
    out = land * (1 - water) + wcol * water
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


ys, xs = np.mgrid[0:H_, 0:W].astype(np.float64)
PX = minx + (xs + 0.5) * RES; PY = maxy - (ys + 0.5) * RES
lon, lat = inv.transform(PX, PY)
del PX, PY, xs, ys
mapx = (((lon + 180.0) % 360.0) / 360.0 * SW - 0.5).astype(np.float32)
mapy = ((90.0 - lat) / 180.0 * SH - 0.5).astype(np.float32)
del lon, lat
base = cv2.remap(src, mapx, mapy, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_WRAP)
del mapx, mapy
base = grade(base)
Image.fromarray(base).save(f"{OUT}/basemap.jpg", quality=88, optimize=True)
Image.fromarray(base).resize((W // 2, H_ // 2), Image.LANCZOS).save(f"{OUT}/basemap_half.jpg", quality=86)
Image.fromarray(base).resize((2048, int(2048 * H_ / W)), Image.LANCZOS).save(f"{OUT}/preview_basemap.jpg", quality=80)
glob = grade(np.asarray(Image.fromarray(src).resize((8192, 4096), Image.LANCZOS)))
Image.fromarray(glob).save(f"{OUT}/globe.jpg", quality=88)

# quick vector-over-raster check image
from PIL import ImageDraw
chk = Image.fromarray(base).resize((2048, int(2048 * H_ / W)))
dr = ImageDraw.Draw(chk); s = 2048 / W
for f in geo["republics"]:
    for seg in f["d"].split("Z"):
        pts = [tuple(float(v) * s for v in p.split(",")) for p in seg.replace("M", "").split("L") if "," in p]
        if len(pts) > 2: dr.line(pts + [pts[0]], fill=(255, 40, 40), width=1)
    dr.text((f["label"][0] * s, f["label"][1] * s), f["id"], fill=(0, 0, 0))
chk.save(f"{OUT}/check_overlay.jpg", quality=82)
open(f"{OUT}/log.txt", "w").write("\n".join(log))
print("done")
