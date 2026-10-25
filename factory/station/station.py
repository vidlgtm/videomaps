#!/usr/bin/env python3
"""FACTORY - PROCESSING STATION (phase 2). The brain picks, the station makes them film-ready in our identity.

in : factory/orders/<order>/sources.json   (the brain's picks: Wikimedia Commons files + document texts, see ORDER_SPEC.txt)
out: out/pack/   archive/<id>.jpg (+ _depth.png, _fg.png, _cut.png), sig/, flags/, clips/ (Manim documents, made by the
                 workflow with doc_scene.py), pack.json (what the director reads), CREDITS.txt, station_report.txt, sheets/

photos     : Commons file (pages of djvu/pdf/tif via "page") -> licence gate (PD, CC0, CC BY, CC BY-SA only; anything else
             = ORDER ERROR) -> scan-border trim -> 4x super-resolution when small (Real-ESRGAN general x4v3, BSD) ->
             levels -> by use:
               banner / scene : depth map (Depth-Anything-V2-Small, Apache-2.0) + near layer <id>_fg.png (2.5D parallax)
                                + focus point (faces: YuNet; no face: the nearest region) so a crop never cuts the subject
               portrait       : cut-out <id>_cut.png (BiRefNet portrait -> general -> ISNet) with clean alpha
               document       : the page itself (no depth, no levels)
signatures : Commons SVG kept as drawn; PNG/JPG -> ink only (paper -> transparent), tight crop
flags      : extra flags (non-ISO, e.g. historical) from Commons SVG -> flags/<code>.svg + flags/4x3/<code>.svg + aspect
             (the ISO flags of the order's countries come from flag-icons in the workflow)
credits    : licence + author + page of every file from Commons -> pack.json "credits" (the director keeps the ones the
             film really shows: end card + CREDITS.txt for the YouTube description)

usage: python station.py process <orderDir> [--meta-only]      (meta-only: licence/metadata check, nothing downloaded)
       python station.py finish  <orderDir>                    (after the Manim documents: clip lengths, sheets, report)
exit code 2 = ORDER ERROR (every problem of the order is listed at once)."""
import html, io, json, os, re, sys, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.dirname(HERE)
REPO = os.path.dirname(FACTORY)
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "videomaps-factory/2.0 (https://github.com/vidlgtm/videomaps; history map films)"}
USES = {"banner", "scene", "portrait", "document"}
MAXS, SR_BELOW, LOW_RES = 2400, 1800, 700
OUT = "out/pack"
TMP = "out/station_tmp"
CACHE = os.path.join(HERE, "cache")
FIXED_CREDITS = [
    "Relief: AWS Terrain Tiles (SRTM, ETOPO1) · Imagery: NASA Blue Marble & Black Marble · "
    "Sentinel-2 cloudless 2016 by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2016), CC BY 4.0",
    "Boundaries: Natural Earth · Flags: flag-icons (MIT) · Narration: synthetic voice · Music: original score",
]
PHOTO_KEYS = {"commons", "page", "use", "what", "author", "note"}
DOC_KEYS = {"layout", "head", "title", "title_font", "body", "gloss", "underline", "seal", "hold", "what", "note"}
SIG_KEYS = {"commons", "what", "note"}
FLAG_KEYS = {"commons", "what", "note"}
TOP_KEYS = {"photos", "documents", "signatures", "flags", "credits_fixed", "note"}

errors, warnings = [], []


def err(msg): errors.append(msg); print("ORDER ERROR:", msg, flush=True)
def warn(msg): warnings.append(msg); print("warning:", msg, flush=True)


# ------------------------------------------------------------------ Commons
def http(url, params=None, tries=6):
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=180)
            if r.status_code == 429 or r.status_code >= 500: raise RuntimeError(f"HTTP {r.status_code}")
            if r.status_code >= 400: raise FileNotFoundError(f"HTTP {r.status_code} {url[:120]}")
            return r
        except FileNotFoundError: raise
        except Exception as e:
            last = e; time.sleep(3 + 6 * i)
    raise RuntimeError(f"{url[:120]}: {last}")


def plain(v):
    s = re.sub(r"<[^>]+>", " ", str(v or "")); s = html.unescape(s); s = re.sub(r"\s+", " ", s).strip()
    m = re.fullmatch(r"(.+?)\s*\1", s)          # Commons templates often print the author twice
    return m.group(1).strip() if m else s


def commons_info(title, page=None, width=None):
    t = re.sub(r"^(File|Image):", "", title.strip(), flags=re.I)
    p = dict(action="query", format="json", redirects=1, titles="File:" + t, prop="imageinfo",
             iiprop="url|size|mime|extmetadata",
             iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|NonFree|AttributionRequired|ObjectName")
    if page: p.update(iiurlwidth=width or 1280, iiurlparam=f"page{int(page)}-{width or 1280}px")
    elif width: p.update(iiurlwidth=width)
    j = http(API, p).json()
    pages = list(j.get("query", {}).get("pages", {}).values())
    if not pages or "imageinfo" not in pages[0]: raise FileNotFoundError(f'no such file on Wikimedia Commons: "{t}"')
    ii = pages[0]["imageinfo"][0]; ii["title"] = pages[0]["title"]
    ii["page_url"] = "https://commons.wikimedia.org/wiki/" + pages[0]["title"].replace(" ", "_")
    return ii


def licence(ii):
    m = ii.get("extmetadata", {})
    short = plain(m.get("LicenseShortName", {}).get("value"))
    nonfree = plain(m.get("NonFree", {}).get("value")).lower() in ("true", "1", "yes")
    s = short.lower().replace("_", " ")
    bad = nonfree or re.search(r"\bnc\b|-nc|non.?commercial|\bnd\b|-nd|no.?deriv|fair use|non.?free|all rights reserved|gfdl only", s)
    good = (s.startswith("public domain") or re.match(r"^pd(\b|-)", s) or "cc0" in s or "copyrighted free use" in s
            or re.match(r"^cc[ -]by(-sa)?([ -]\d(\.\d)?)?(\s|$)", s) or s in ("attribution", "attribution-sharealike", "no restrictions"))
    show = "Public domain" if (s.startswith("public domain") or re.match(r"^pd(\b|-)", s) or "cc0" in s or s == "no restrictions") else \
        re.sub(r"^cc", "CC", re.sub(r"\b(by|sa)\b", lambda x: x.group(1).upper(), short, flags=re.I), flags=re.I)
    return short, show, bool(good and not bad)


def author(ii, override=None):
    if override: return override
    m = ii.get("extmetadata", {})
    a = plain(m.get("Artist", {}).get("value")) or plain(m.get("Credit", {}).get("value"))
    a = re.sub(r"^(photographer|photograph|photo|author|by)\s*[:.]?\s*", "", a, flags=re.I).strip(" .")
    if not a or re.match(r"unknown|anonymous|unidentified", a, re.I) or (re.search(r"\bunknown\b", a, re.I) and len(a) < 48): return "unknown author"
    a = re.sub(r"\s*\((life ?time|died|born|lived)[^)]*\)?.*$", "", a, flags=re.I).strip(" ,.")   # painter's life dates
    a = re.sub(r"^(.+?) from [A-Z][\w .,-]*$", r"\1", a)                                       # Flickr "name from city"
    if len(a) > 40 and ". " in a: a = a.split(". ")[0].strip()
    if len(a) > 64:
        cut = re.split(r"[;(\[]| - |, (?:from|via|source)", a)[0].strip(" ,.")
        a = cut if 3 <= len(cut) <= 64 else a[:61].rstrip(" ,.") + "…"
    return a


# ------------------------------------------------------------------ order
def load_sources(order):
    p = os.path.join(order, "sources.json")
    if not os.path.exists(p): err(f"{p} is missing (the brain's picks: photos, documents, signatures, flags)"); return {}
    try: S = json.load(open(p))
    except Exception as e: err(f"sources.json is not valid JSON: {e}"); return {}
    for k in S:
        if k not in TOP_KEYS: err(f'sources.json: unknown key "{k}" (allowed: {", ".join(sorted(TOP_KEYS))})')
    seen = {}
    for sect, keys in (("photos", PHOTO_KEYS), ("documents", DOC_KEYS), ("signatures", SIG_KEYS), ("flags", FLAG_KEYS)):
        for i, v in (S.get(sect) or {}).items():
            if not re.fullmatch(r"[a-z0-9_]+", i): err(f'{sect} id "{i}": use lower-case letters, digits and _ only')
            if sect in ("photos", "documents"):
                if i in seen: err(f'id "{i}" is used twice ({seen[i]} and {sect})')
                seen[i] = sect
            if not isinstance(v, dict): err(f"{sect}.{i} must be an object"); continue
            for k in v:
                if k not in keys: err(f'{sect}.{i}: unknown key "{k}" (allowed: {", ".join(sorted(keys))})')
            if sect != "documents" and not v.get("commons"): err(f'{sect}.{i}: "commons" (the file name on Wikimedia Commons) is missing')
            if sect == "photos":
                uses = v.get("use") if isinstance(v.get("use"), list) else [v.get("use")]
                bad = [u for u in uses if u not in USES]
                if bad: err(f'photos.{i}: "use" must be {" | ".join(sorted(USES))} (or a list of them), not {bad}')
                if not v.get("what"): err(f'photos.{i}: "what" (short caption for the credits) is missing')
            if sect == "documents":
                lay = v.get("layout", "article")
                if lay not in ("article", "maxim"): err(f'documents.{i}: layout must be "article" or "maxim"')
                if not v.get("title"): err(f'documents.{i}: "title" is missing')
                if lay == "article" and not v.get("body"): err(f'documents.{i}: an article needs "body" (list of lines)')
                for k in ("body", "gloss"):
                    if k in v and not (isinstance(v[k], list) and all(isinstance(x, str) for x in v[k])): err(f'documents.{i}: "{k}" must be a list of lines')
                    if k in v and any(len(x) > 44 for x in v[k]): err(f'documents.{i}: a {k} line is longer than 44 characters (split it)')
                if len(v.get("body", [])) > 6: err(f"documents.{i}: at most 6 body lines")
    return S


# ------------------------------------------------------------------ image tools (loaded lazily)
def np_():
    import numpy as np
    return np


def trim_borders(img, frac=0.08):
    """scan / mount borders (uniform dark or light rows and columns at the edges) -> cut, at most 8 % per side"""
    np = np_()
    a = np.asarray(img.convert("L"), np.float32); h, w = a.shape
    def run(lines):
        n = 0
        for v in lines:
            if v.std() < 7 and (v.mean() < 40 or v.mean() > 222): n += 1
            else: break
        return n
    t = run(a[i] for i in range(int(h * frac))); b = run(a[h - 1 - i] for i in range(int(h * frac)))
    l = run(a[:, i] for i in range(int(w * frac))); r = run(a[:, w - 1 - i] for i in range(int(w * frac)))
    if max(t, b, l, r) < 3: return img, None
    pad = lambda n: n + 2 if n else 0
    return img.crop((pad(l), pad(t), w - pad(r), h - pad(b))), f"trim {l}/{t}/{r}/{b}px"


SR = None
def upscale(img):
    global SR
    import torch
    np = np_()
    if SR is None:
        from spandrel import ModelLoader
        wp = os.path.join(CACHE, "realesr-general-x4v3.pth"); os.makedirs(CACHE, exist_ok=True)
        if not os.path.exists(wp):
            open(wp, "wb").write(http("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth").content)
        SR = ModelLoader().load_from_file(wp).eval()
    x = torch.from_numpy(np.asarray(img, np.float32) / 255).permute(2, 0, 1)[None]
    h, w = x.shape[2:]; s = SR.scale
    out = torch.zeros(1, 3, h * s, w * s); T, P = 384, 16
    with torch.inference_mode():
        for y in range(0, h, T):
            for x0 in range(0, w, T):
                ya, yb, xa, xb = max(0, y - P), min(h, y + T + P), max(0, x0 - P), min(w, x0 + T + P)
                o = SR(x[:, :, ya:yb, xa:xb]).clamp(0, 1)
                oy, ox = (y - ya) * s, (x0 - xa) * s
                th, tw = (min(h, y + T) - y) * s, (min(w, x0 + T) - x0) * s
                out[:, :, y * s:y * s + th, x0 * s:x0 * s + tw] = o[:, :, oy:oy + th, ox:ox + tw]
    from PIL import Image
    return Image.fromarray((out[0].permute(1, 2, 0).numpy() * 255 + 0.5).astype(np.uint8))


def levels(img):
    """faded archive prints -> full tonal range (same map on the three channels, gentle, colours kept)"""
    np = np_()
    a = np.asarray(img, np.float32); L = a.mean(axis=2)
    lo, hi = np.percentile(L, 0.5), np.percentile(L, 99.5)
    if lo < 10 and hi > 244: return img, None
    k = min(1.6, 236.0 / max(hi - lo, 1.0))
    from PIL import Image
    return Image.fromarray(np.clip((a - lo) * k + 8, 0, 255).astype(np.uint8)), f"levels {lo:.0f}-{hi:.0f}"


DEPTH = None
def depth_map(img):
    global DEPTH
    from PIL import Image
    if DEPTH is None:
        from transformers import pipeline
        DEPTH = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
    small = img.copy(); small.thumbnail((1024, 1024), Image.LANCZOS)
    return DEPTH(small)["depth"].convert("L")


def near_layer(img, d):
    """the near layer of the photo cut by its depth map (the film moves it against the photo: 2.5D parallax)"""
    np = np_()
    from PIL import Image, ImageFilter
    im = img.copy()
    if im.width > 1100: im = im.resize((1100, round(im.height * 1100 / im.width)), Image.LANCZOS)
    dd = np.asarray(d.resize(im.size, Image.BICUBIC)).astype(np.float32)
    lo, hi = np.percentile(dd, 3), np.percentile(dd, 97)
    n = np.clip((dd - lo) / max(hi - lo, 1.0), 0, 1)
    a = np.clip((n - 0.55) / 0.25, 0, 1); a = a * a * (3 - 2 * a)
    im.putalpha(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)))
    return im


FACE = None
def faces(img):
    """faces as (cx, cy, w, h) fractions of the image - YuNet (OpenCV zoo, MIT), Haar cascade if YuNet is unavailable"""
    global FACE
    np = np_()
    import cv2
    small = img.copy(); small.thumbnail((1280, 1280))
    a = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2BGR); H, W = a.shape[:2]
    out = []
    try:
        if FACE is None:
            p = os.path.join(CACHE, "face_detection_yunet_2023mar.onnx")
            if not os.path.exists(p):
                os.makedirs(CACHE, exist_ok=True)
                open(p, "wb").write(http("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx").content)
            FACE = cv2.FaceDetectorYN.create(p, "", (320, 320), 0.6, 0.3, 5000)
        FACE.setInputSize((W, H)); _, f = FACE.detect(a)
        for r in ([] if f is None else f):
            x, y, w, h = [float(v) for v in r[:4]]
            out.append(((x + w / 2) / W, (y + h / 2) / H, w / W, h / H))
    except Exception as e:
        print("  YuNet unavailable, Haar cascade:", str(e)[:80])
        c = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        for x, y, w, h in c.detectMultiScale(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(24, 24)):
            out.append(((x + w / 2) / W, (y + h / 2) / H, w / W, h / H))
    return out


def focus_point(img, d):
    """where a crop must stay: the faces (size-weighted, a little below their centre = face + shoulders), else the
    nearest large region of the depth map, pulled towards the centre"""
    np = np_()
    fs = faces(img)
    if fs and max(f[2] for f in fs) >= 0.035:                    # tiny faces = background people, not the subject
        big = max(f[2] * f[3] for f in fs)
        fs = [f for f in fs if f[2] * f[3] >= 0.15 * big]
        wsum = sum(f[2] * f[3] for f in fs)
        fx = sum(f[0] * f[2] * f[3] for f in fs) / wsum
        fy = sum((f[1] + 0.3 * f[3]) * f[2] * f[3] for f in fs) / wsum
        return [round(float(min(0.88, max(0.12, fx))), 3), round(float(min(0.85, max(0.15, fy))), 3)], f"{len(fs)} face(s)"
    # no clear face: the nearest region only moves the crop sideways a little; vertically the centre is kept (the nearest
    # thing in buildings / landscapes is the ground, a lower crop would cut roofs and skylines)
    dd = np.asarray(d, np.float32); h, w = dd.shape
    ys, xs = np.nonzero(dd >= np.percentile(dd, 80))
    if not len(xs): return [0.5, 0.5], "centre"
    return [round(float(0.5 + 0.4 * (xs.mean() / w - 0.5)), 3), 0.5], "no face: nearest region sideways, centre height"


RB = None
def cutout(img):
    global RB
    np = np_()
    from PIL import Image
    from scipy import ndimage
    from rembg import remove, new_session
    if RB is None:
        for model in ("birefnet-portrait", "birefnet-general", "isnet-general-use"):
            try: RB = new_session(model); print("  matte model:", model, flush=True); break
            except Exception as e: print("  matte model failed:", model, str(e)[:80], flush=True)
    m = remove(img, session=RB, only_mask=True, post_process_mask=False)
    rgba = np.dstack([np.asarray(img), np.asarray(m.convert("L"))])
    a = rgba[..., 3].astype(np.float32) / 255; rgb = rgba[..., :3].astype(np.float32)
    a = np.clip((a - 0.10) / 0.85, 0, 1)                                   # haze -> 0 (no rectangular shadows)
    lab, n = ndimage.label(a > 0.5)                                        # the main body only
    if n > 1:
        sizes = ndimage.sum(np.ones_like(a), lab, range(1, n + 1))
        a *= ndimage.binary_dilation(np.isin(lab, 1 + np.where(sizes >= 0.04 * sizes.max())[0]), iterations=6)
    h, w = a.shape                                                         # figure cut by the photo frame -> soft fade
    hit = lambda v: (v > 0.5).mean() > 0.01
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); f = np.ones_like(a); fs, fb = 0.07 * min(w, h), 0.16 * h
    if hit(a[:, 0]): f *= np.clip(xx / fs, 0, 1) ** 1.6
    if hit(a[:, -1]): f *= np.clip((w - 1 - xx) / fs, 0, 1) ** 1.6
    if hit(a[-1, :]): f *= np.clip((h - 1 - yy) / fb, 0, 1) ** 1.4
    if hit(a[0, :]): f *= np.clip(yy / fs, 0, 1) ** 1.6
    a *= f
    core = (a > 0.92).astype(np.float32)                                   # edge colour without the old background
    num = np.stack([ndimage.gaussian_filter(rgb[..., c] * core, 6) for c in range(3)], -1)
    den = ndimage.gaussian_filter(core, 6)[..., None] + 1e-4
    conf = np.clip((a - 0.45) / 0.45, 0, 1)[..., None]
    rgb = np.where(den > 0.02, rgb * conf + (num / den) * (1 - conf), rgb)
    ys, xs = np.where(a > 0.01)
    if not len(xs): return None
    y0, y1, x0, x1 = max(0, ys.min() - 8), min(h, ys.max() + 9), max(0, xs.min() - 8), min(w, xs.max() + 9)
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)[y0:y1, x0:x1], "RGBA")
    im.thumbnail((1600, 1600), Image.LANCZOS)
    return im


def ink_png(raw):
    """signature scan -> dark ink on transparent paper, tight crop"""
    np = np_()
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(raw)); im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    L = np.asarray(im.convert("L"), np.float32)
    paper = np.percentile(L, 90)
    a = np.clip((paper - L) / max(paper - np.percentile(L, 1), 30), 0, 1)
    ys, xs = np.nonzero(a > 0.15)
    if not len(xs): return None
    out = np.zeros(L.shape + (4,), np.uint8); out[..., 0], out[..., 1], out[..., 2] = 22, 24, 40; out[..., 3] = (a * 255).astype(np.uint8)
    y0, y1, x0, x1 = max(0, ys.min() - 6), ys.max() + 7, max(0, xs.min() - 6), xs.max() + 7
    return Image.fromarray(out[y0:y1, x0:x1], "RGBA")


def svg_aspect(svg):
    m = re.search(rb'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    if m: return float(m.group(1)) / float(m.group(2))
    w = re.search(rb'<svg[^>]*\swidth\s*=\s*["\']([\d.]+)', svg); h = re.search(rb'<svg[^>]*\sheight\s*=\s*["\']([\d.]+)', svg)
    return float(w.group(1)) / float(h.group(1)) if w and h else 1.5


# ------------------------------------------------------------------ process
def raster_bytes(ii, title, page):
    """the picture itself: page render for multipage files, the original when it is a normal-size jpg/png, else a
    large rendering (tif, huge files)"""
    if page: return http(ii["thumburl"]).content, ii["thumburl"]
    big = max(ii["width"], ii["height"])
    if ii.get("mime") in ("image/jpeg", "image/png", "image/webp", "image/gif") and ii.get("size", 0) <= 45e6 and big <= 9000:
        return http(ii["url"]).content, ii["url"]
    for W in (3840, 2560, 1920, 1280):
        w = W if ii["width"] >= ii["height"] else max(320, round(W * ii["width"] / ii["height"]))
        try:
            j = commons_info(title, width=w)
            if j.get("thumburl"): return http(j["thumburl"]).content, j["thumburl"]
        except Exception as e: print("  rendering", W, "failed:", str(e)[:80])
    raise RuntimeError("no usable rendering")


def process(order, meta_only=False):
    S = load_sources(order)
    if errors: return finish_errors()
    for d in ("archive", "sig", "flags/4x3", "clips", "sheets"): os.makedirs(os.path.join(OUT, d), exist_ok=True)
    os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(TMP, "docs_json"), exist_ok=True)
    from PIL import Image, ImageOps
    pack = {"archive": {}, "cutouts": {}, "docs": {}, "sig": {}, "flags": {}, "credits": [], "credits_fixed": S.get("credits_fixed") or FIXED_CREDITS,
            "station": {"order": os.path.basename(os.path.normpath(order)), "made": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                        "sources_sha": hashlib.sha256(open(os.path.join(order, "sources.json"), "rb").read()).hexdigest()[:16]}}
    rows, rep = [], []
    # ---- photos
    for i, s in (S.get("photos") or {}).items():
        t0 = time.time(); uses = s["use"] if isinstance(s["use"], list) else [s["use"]]
        try: ii = commons_info(s["commons"], s.get("page"))
        except Exception as e: err(f'photos.{i}: {e}'); continue
        short, show, ok = licence(ii)
        if not ok: err(f'photos.{i}: "{ii["title"][5:]}" has licence "{short or "none"}" - only Public domain, CC0, CC BY, CC BY-SA are allowed; pick another file'); continue
        who = author(ii, s.get("author"))
        files = []
        line = f'{i:14s} {"+".join(uses):16s} {show:16s} {who[:40]:40s} {ii["width"]}x{ii["height"]}'
        if meta_only:
            rep.append(line); print(line, flush=True); continue
        try: raw, src = raster_bytes(ii, s["commons"], s.get("page"))
        except Exception as e: err(f'photos.{i}: download failed ({e})'); continue
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA"); bg = Image.new("RGBA", img.size, (255, 255, 255, 255)); bg.alpha_composite(img); img = bg
        img = img.convert("RGB"); orig = img.copy(); w0, h0 = img.size; steps = []
        if max(img.size) < LOW_RES: warn(f'photos.{i}: only {w0}x{h0} px on Commons - upscaled 4x, a larger file would look better')
        photo = any(u in ("banner", "scene", "portrait") for u in uses)
        if photo:
            img, st = trim_borders(img)
            if st: steps.append(st)
        if max(img.size) > 3200: img.thumbnail((3200, 3200), Image.LANCZOS)
        if max(img.size) < SR_BELOW: img = upscale(img); steps.append("4x super-resolution")
        if max(img.size) > MAXS:
            f = MAXS / max(img.size); img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
        if photo:
            img, st = levels(img)
            if st: steps.append(st)
        img.save(f"{OUT}/archive/{i}.jpg", quality=92); files.append(f"archive/{i}.jpg")
        aspect = round(img.width / img.height, 5)
        extra = {}
        if "banner" in uses or "scene" in uses:
            d = depth_map(img); d.resize((img.width // 2, img.height // 2)).save(f"{OUT}/archive/{i}_depth.png")
            near_layer(img, d).save(f"{OUT}/archive/{i}_fg.png", optimize=True)
            fp, how = focus_point(img, d); steps.append(f"depth + near layer, focus {fp} ({how})")
            pack["archive"][i] = {"file": f"archive/{i}.jpg", "aspect": aspect, "depth": True, "focus": fp}
            extra["depth"] = d; extra["focus"] = fp
        if "document" in uses:
            pack["docs"][i] = {"file": f"archive/{i}.jpg", "aspect": aspect}
        if "portrait" in uses:
            c = cutout(img)
            if c is None: err(f'photos.{i}: no person found for the cut-out - pick a clearer portrait')
            else:
                c.save(f"{OUT}/archive/{i}_cut.png"); files.append(f"archive/{i}_cut.png")
                pack["cutouts"][i] = {"file": f"archive/{i}_cut.png", "aspect": round(c.width / c.height, 5)}
                extra["cut"] = c; steps.append(f"cut-out {c.width}x{c.height}")
        pack["credits"].append({"id": i, "files": files, "what": s["what"], "author": who, "license": show, "page": ii["page_url"]})
        line += f' -> {img.width}x{img.height} | {"; ".join(steps) or "as is"} | {time.time() - t0:.0f}s'
        rep.append(line); print(line, flush=True)
        rows.append({"id": i, "uses": uses, "orig": orig, "final": img, "licence": show, "author": who, "size0": (w0, h0), **extra})
    # ---- signatures
    for i, s in (S.get("signatures") or {}).items():
        try: ii = commons_info(s["commons"])
        except Exception as e: err(f"signatures.{i}: {e}"); continue
        short, show, ok = licence(ii)
        if not ok: err(f'signatures.{i}: licence "{short}" is not allowed'); continue
        who = author(ii)
        rep.append(f"{i:14s} signature        {show:16s} {who[:40]}"); print(rep[-1], flush=True)
        if meta_only: continue
        raw = http(ii["url"]).content
        if ii.get("mime") == "image/svg+xml":
            open(f"{OUT}/sig/{i}.svg", "wb").write(raw); f = f"sig/{i}.svg"
        else:
            im = ink_png(raw)
            if im is None: err(f"signatures.{i}: no ink found in the image"); continue
            im.save(f"{OUT}/sig/{i}.png"); f = f"sig/{i}.png"
        pack["sig"][i] = f
        pack["credits"].append({"id": i, "files": [f], "what": s.get("what") or f"Signature ({i})", "author": who, "license": show, "page": ii["page_url"]})
    # ---- extra flags
    for c, s in (S.get("flags") or {}).items():
        try: ii = commons_info(s["commons"])
        except Exception as e: err(f"flags.{c}: {e}"); continue
        short, show, ok = licence(ii)
        if not ok: err(f'flags.{c}: licence "{short}" is not allowed'); continue
        rep.append(f"{c:14s} flag             {show:16s}"); print(rep[-1], flush=True)
        if meta_only: continue
        if ii.get("mime") != "image/svg+xml": err(f"flags.{c}: pick the SVG version of the flag"); continue
        raw = http(ii["url"]).content
        for p in (f"{OUT}/flags/{c}.svg", f"{OUT}/flags/4x3/{c}.svg"): open(p, "wb").write(raw)
        pack["flags"][c] = {"file": f"flags/4x3/{c}.svg", "aspect": round(svg_aspect(raw), 4)}
        pack["credits"].append({"id": c, "files": [f"flags/4x3/{c}.svg"], "what": s.get("what") or ii["title"][5:-4], "author": author(ii), "license": show, "page": ii["page_url"]})
    # ---- Manim documents: one JSON each for doc_scene.py (rendered by the workflow in the official Manim image)
    for i, s in (S.get("documents") or {}).items():
        spec = {k: v for k, v in s.items() if k not in ("what", "note")}
        spec.setdefault("layout", "article")
        json.dump(spec, open(os.path.join(TMP, "docs_json", f"{i}.json"), "w"), ensure_ascii=False, indent=1)
        pack["docs"][i] = {"clip": f"clips/{i}.mp4", "length": None}
        rep.append(f"{i:14s} manim document   {spec['layout']}: {s['title']}")
    if meta_only:
        print(f"\nMETA CHECK: {len(rep)} items, {len(errors)} order errors, {len(warnings)} warnings")
        return finish_errors()
    json.dump(pack, open(f"{OUT}/pack.json", "w"), ensure_ascii=False, indent=1)
    open(os.path.join(TMP, "report_lines.txt"), "w").write("\n".join(rep) + "\n")
    # thumbnails for the review sheets (finish step)
    for r in rows:
        k = r["id"]
        th = lambda im, n: (im.copy().convert("RGBA" if im.mode == "RGBA" else "RGB"), n)
        for im, n in (th(r["orig"], "orig"), th(r["final"], "final")):
            im.thumbnail((900, 900)); im.save(f"{TMP}/{k}_{n}.png")
        if "depth" in r: r["depth"].save(f"{TMP}/{k}_depthv.png")
        if "cut" in r: c = r["cut"].copy(); c.thumbnail((900, 900)); c.save(f"{TMP}/{k}_cutv.png")
        meta = {kk: r[kk] for kk in ("id", "uses", "licence", "author", "size0")}; meta["final"] = list(r["final"].size); meta["focus"] = r.get("focus")
        json.dump(meta, open(f"{TMP}/{k}_meta.json", "w"))
    return finish_errors()


def finish_errors():
    if errors:
        print(f"\n{len(errors)} ORDER ERROR(S) - the station stops. Fix sources.json:")
        for e in errors: print("  -", e)
        sys.exit(2)
    return 0


# ------------------------------------------------------------------ finish: clip lengths, sheets, report
def finish(order):
    import glob
    from PIL import Image, ImageDraw, ImageFont
    np = np_()
    pack = json.load(open(f"{OUT}/pack.json"))
    F = lambda s: ImageFont.truetype(os.path.join(REPO, "fonts/Inter.ttf"), s)
    docrows = []
    for i, d in pack["docs"].items():
        if "clip" not in d: continue
        p = f"{OUT}/{d['clip']}"
        if not os.path.exists(p): err(f"documents.{i}: the Manim render is missing ({p})"); continue
        import cv2
        cap = cv2.VideoCapture(p); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS) or 30
        d["length"] = round(n / fps, 3); frames = []
        for q in (0.3, 0.65, 0.999):
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * q) - 1)); ok, fr = cap.read()
            if ok: frames.append(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
        cap.release(); docrows.append((i, d["length"], frames))
    finish_errors()
    json.dump(pack, open(f"{OUT}/pack.json", "w"), ensure_ascii=False, indent=1)
    # review sheets: one row per item
    W, RH = 1920, 300
    def fit(im, w, h):
        im = im.copy(); im.thumbnail((w, h), Image.LANCZOS); return im
    def checker(w, h):
        c = Image.new("RGB", (w, h), (205, 200, 190)); d = ImageDraw.Draw(c)
        for y in range(0, h, 24):
            for x in range(0, w, 24):
                if (x // 24 + y // 24) % 2: d.rectangle((x, y, x + 23, y + 23), fill=(22, 30, 40))
        return c
    rows = []
    for mf in sorted(glob.glob(f"{TMP}/*_meta.json")):
        m = json.load(open(mf)); k = m["id"]
        row = Image.new("RGB", (W, RH), (14, 22, 30)); dr = ImageDraw.Draw(row); x = 16
        cols = [("COMMONS", Image.open(f"{TMP}/{k}_orig.png")), ("STATION", Image.open(f"{TMP}/{k}_final.png"))]
        if os.path.exists(f"{TMP}/{k}_depthv.png"): cols.append(("DEPTH", Image.open(f"{TMP}/{k}_depthv.png").convert("RGB")))
        if os.path.exists(f"{TMP}/{k}_cutv.png"): cols.append(("CUT-OUT", Image.open(f"{TMP}/{k}_cutv.png")))
        for name, im in cols:
            t = fit(im, 420, RH - 64)
            if name == "CUT-OUT":
                bg = checker(t.width, t.height); bg.paste(t, (0, 0), t); t = bg
            if name == "STATION" and m.get("focus"):
                t = t.convert("RGB"); d2 = ImageDraw.Draw(t); fx, fy = m["focus"][0] * t.width, m["focus"][1] * t.height
                d2.ellipse((fx - 9, fy - 9, fx + 9, fy + 9), outline=(255, 70, 70), width=3); d2.line((fx - 18, fy, fx + 18, fy), fill=(255, 70, 70), width=2); d2.line((fx, fy - 18, fx, fy + 18), fill=(255, 70, 70), width=2)
            row.paste(t.convert("RGB"), (x, 40)); dr.text((x, 12), name, font=F(17), fill=(226, 191, 106)); x += t.width + 18
        cap = f'{k}  ·  {"+".join(m["uses"])}  ·  {m["size0"][0]}x{m["size0"][1]} -> {m["final"][0]}x{m["final"][1]}  ·  {m["licence"]}  ·  {m["author"]}'
        dr.text((16, RH - 22), cap, font=F(17), fill=(244, 239, 230)); rows.append(row)
    for i, L, frames in docrows:
        row = Image.new("RGB", (W, RH), (14, 22, 30)); dr = ImageDraw.Draw(row); x = 16
        for q, fr in zip(("30 %", "65 %", "END"), frames):
            t = fit(fr, 440, RH - 64); row.paste(t, (x, 40)); dr.text((x, 12), f"MANIM DOCUMENT · {q}", font=F(17), fill=(226, 191, 106)); x += t.width + 18
        dr.text((16, RH - 22), f"{i}  ·  Manim document from the brain's text  ·  {L:.2f} s", font=F(17), fill=(244, 239, 230)); rows.append(row)
    sig = [(k, f"{OUT}/{v}") for k, v in pack["sig"].items()] + [(k, f"{OUT}/{v['file']}") for k, v in pack["flags"].items()]
    if sig:
        row = Image.new("RGB", (W, RH), (234, 222, 192)); dr = ImageDraw.Draw(row); x = 16
        for k, p in sig:
            try:
                if p.endswith(".svg"):
                    import cairosvg
                    im = Image.open(io.BytesIO(cairosvg.svg2png(url=p, output_height=180))).convert("RGBA")
                else: im = Image.open(p).convert("RGBA")
                t = fit(im, 380, RH - 80); row.paste(t, (x, 50), t)
            except Exception as e:
                dr.text((x, 120), f"(preview n/a: {str(e)[:30]})", font=F(15), fill=(90, 60, 30)); t = Image.new("RGBA", (300, 10))
            dr.text((x, 14), k, font=F(18), fill=(90, 60, 30)); x += max(t.width, 260) + 30
        rows.append(row)
    pages = []
    for s in range(0, len(rows), 5):
        pg = Image.new("RGB", (W, 64 + RH * 5), (8, 14, 20)); d = ImageDraw.Draw(pg)
        d.text((16, 16), f"FACTORY · PROCESSING STATION · order {pack['station']['order']} · page {s // 5 + 1}", font=F(26), fill=(244, 239, 230))
        for j, r in enumerate(rows[s:s + 5]): pg.paste(r, (0, 64 + j * RH))
        pg.save(f"{OUT}/sheets/station_{s // 5 + 1}.jpg", quality=88); pages.append(pg)
    if pages: pages[0].save(f"{OUT}/sheets/STATION_SHEET.pdf", save_all=True, append_images=pages[1:], resolution=110)
    # report + credits of everything processed (the director writes the film's own credits)
    rep = open(os.path.join(TMP, "report_lines.txt")).read()
    lines = [f"PROCESSING STATION REPORT - order {pack['station']['order']} - {pack['station']['made']}",
             f"photos {len([1 for c in pack['credits'] if c['files'] and c['files'][0].startswith('archive/')])} · banners/scenes {len(pack['archive'])} · "
             f"portraits {len(pack['cutouts'])} · documents {len(pack['docs'])} · signatures {len(pack['sig'])} · extra flags {len(pack['flags'])}",
             "", rep, "WARNINGS:", *(warnings or ["none"]), "", "MANIM DOCUMENTS:", *[f"  {i}: {L:.2f} s" for i, L, _ in docrows]]
    open(f"{OUT}/station_report.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("process", "finish"):
        print(__doc__); sys.exit(1)
    if sys.argv[1] == "process": process(sys.argv[2], "--meta-only" in sys.argv)
    else: finish(sys.argv[2])
