#!/usr/bin/env python3
"""ORDER STORE - every picture an order uses (photos, document pages, signatures, extra flags, and later 3D models,
textures, HDRIs), the voice takes (keys vo_<paragraph id>, mp3 / wav / flac) and historical shapes (GeoJSON), fetched
with its licence and kept as an asset of the release "store_<order>" of this repository, listed in <orderDir>/store.json. The factory reads pictures only from there and never downloads them from a website.

usage:
  python factory/intake/store.py commons <orderDir> <key> "<Commons file name>" [--page N] [--replace]
  python factory/intake/store.py file    <orderDir> <key> <local file> --licence "<licence>" --author "<author>"
                                         --source <page url> [--title "<title>"] [--replace]
  python factory/intake/store.py verify  <orderDir> [--deep]     (every entry is in the release; --deep: sha256 too)
  python factory/intake/store.py list    <orderDir>
env: GH_TOKEN (contents: write)

licences: Public domain, CC0, CC BY, CC BY-SA only (NC, ND, fair use, all rights reserved = refused).
Wikimedia: identified user agent, standard thumbnail widths only (960, 1280, 1920, 3840), Retry-After honoured.
exit code 2 = refused (licence, missing file, wrong input) with the reason."""
import hashlib, html, io, json, mimetypes, os, re, sys, time, urllib.error, urllib.parse, urllib.request

REPO = "vidlgtm/videomaps"
API_GH = "https://api.github.com/repos/" + REPO
UPLOADS = "https://uploads.github.com/repos/" + REPO
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = "videomaps-intake-bot/1.0 (https://github.com/vidlgtm/videomaps)"
STD_W = (3840, 1920, 1280, 960)
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg",
       "image/tiff": "tif", "model/gltf-binary": "glb", "image/vnd.radiance": "hdr", "image/x-exr": "exr",
       "audio/mpeg": "mp3", "audio/wav": "wav", "audio/flac": "flac", "application/geo+json": "geojson"}


def die(msg):
    print("REFUSED:", msg, flush=True); sys.exit(2)


# ------------------------------------------------------------------ licence + author (same rules as the station)
def plain(v):
    s = re.sub(r"<[^>]+>", " ", str(v or "")); s = html.unescape(s); s = re.sub(r"\s+", " ", s).strip()
    m = re.fullmatch(r"(.+?)\s*\1", s)
    return m.group(1).strip() if m else s


def licence_check(short, nonfree=False):
    s = plain(short).lower().replace("_", " ")
    bad = nonfree or re.search(r"\bnc\b|-nc|non.?commercial|\bnd\b|-nd|no.?deriv|fair use|non.?free|all rights reserved|gfdl only", s)
    good = (s.startswith("public domain") or re.match(r"^pd(\b|-)", s) or "cc0" in s or "copyrighted free use" in s
            or re.match(r"^cc[ -]by(-sa)?([ -]\d(\.\d)?)?(\s|$)", s) or s in ("attribution", "attribution-sharealike", "no restrictions"))
    return bool(good and not bad)


def author_clean(a):
    a = plain(a)
    a = re.sub(r"^(photographer|photograph|photo|author|by)\s*[:.]?\s*", "", a, flags=re.I).strip(" .")
    if not a or re.match(r"unknown|anonymous|unidentified", a, re.I) or (re.search(r"\bunknown\b", a, re.I) and len(a) < 48): return "unknown author"
    a = re.sub(r"\s*\((life ?time|died|born|lived)[^)]*\)?.*$", "", a, flags=re.I).strip(" ,.")
    a = re.sub(r"^(.+?) from [A-Z][\w .,-]*$", r"\1", a)
    if re.search(r"see (the )?file history|see below|see source", a, re.I): return "unknown author"
    if len(a) > 40 and ". " in a: a = a.split(". ")[0].strip()
    if len(a) > 64:
        cut = re.split(r"[;(\[]| - |, (?:from|via|source)", a)[0].strip(" ,.")
        a = cut if 3 <= len(cut) <= 64 else a[:61].rstrip(" ,.") + "…"
    return a


# ------------------------------------------------------------------ http
def get(url, params=None, tries=6, headers=None):
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=180) as r: return r.read()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429 or e.code >= 500:
                wait = e.headers.get("Retry-After")
                time.sleep(min(120, int(wait)) if wait and wait.isdigit() else 5 + 10 * i); continue
            raise RuntimeError(f"{last} {url[:140]}")
        except Exception as e:
            last = str(e); time.sleep(5 + 10 * i)
    raise RuntimeError(f"{url[:140]}: {last}")


def gh(path, method="GET", data=None, body=None, ctype=None, base=API_GH):
    tok = os.environ.get("GH_TOKEN") or die("GH_TOKEN is not set")
    hdr = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": "videomaps"}
    if ctype: hdr["Content-Type"] = ctype
    payload = body if body is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(base + path, method=method, headers=hdr, data=payload)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            b = r.read(); return json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise RuntimeError(f"GitHub {method} {path}: HTTP {e.code} {e.read()[:300]!r}")


# ------------------------------------------------------------------ manifest + release
def slug_of(order): return os.path.basename(os.path.normpath(order))


def load_manifest(order):
    p = os.path.join(order, "store.json")
    if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    return {"release": "store_" + slug_of(order), "items": {}}


def save_manifest(order, m):
    m["items"] = dict(sorted(m["items"].items()))
    json.dump(m, open(os.path.join(order, "store.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(order, "store.json"), "a").write("\n")


def release(tag, create=True):
    r = gh(f"/releases/tags/{tag}")
    if r or not create: return r
    return gh("/releases", "POST", {"tag_name": tag, "name": tag, "body": "order store: pictures with their licences (store.json)",
                                     "target_commitish": "main", "draft": False, "prerelease": True})


def sniff(raw):
    """file type from the bytes (web addresses carry query strings, extensions lie)"""
    h = raw[:16]
    if h.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if h.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if h[:6] in (b"GIF87a", b"GIF89a"): return "image/gif"
    if h[:4] == b"RIFF" and raw[8:12] == b"WEBP": return "image/webp"
    if h[:4] in (b"II*\x00", b"MM\x00*"): return "image/tiff"
    if h[:4] == b"glTF": return "model/gltf-binary"
    if h.startswith(b"#?RADIANCE") or h.startswith(b"#?RGBE"): return "image/vnd.radiance"
    if h[:4] == b"\x76\x2f\x31\x01": return "image/x-exr"
    if h[:4] == b"RIFF" and raw[8:12] == b"WAVE": return "audio/wav"
    if h[:4] == b"fLaC": return "audio/flac"
    if h[:3] == b"ID3" or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0): return "audio/mpeg"
    head = raw[:2048].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head: return "image/svg+xml"
    if head.startswith(b"{"):
        try:
            j = json.loads(raw.decode("utf-8"))
            if isinstance(j, dict) and j.get("type") in ("FeatureCollection", "Feature", "Polygon", "MultiPolygon", "GeometryCollection"):
                return "application/geo+json"
        except (UnicodeDecodeError, ValueError):
            return None
    return None


def put(order, key, raw, mime, meta, replace):
    if not re.fullmatch(r"[a-z0-9_]+", key): die(f'key "{key}": lower-case letters, digits and _ only')
    m = load_manifest(order)
    if key in m["items"] and not replace: die(f'"{key}" is already in the store (use --replace to change it)')
    mime = sniff(raw) or mime
    ext = EXT.get(mime) or die(f"unsupported file type {mime}")
    name = f"{key}.{ext}"
    old = m["items"].get(key, {}).get("file")
    rel = release(m["release"])
    for a in rel.get("assets", []):
        if a["name"] == name or (replace and a["name"] == old):
            if not replace: die(f"{name} is already in the release (use --replace)")
            gh(f"/releases/assets/{a['id']}", "DELETE")
    gh(f"/releases/{rel['id']}/assets?name={urllib.parse.quote(name)}", "POST", body=raw, ctype=mime, base=UPLOADS)
    w = h = None
    if mime == "image/svg+xml":
        mm = re.search(rb'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', raw)
        if mm: w, h = float(mm.group(1)), float(mm.group(2))
    elif mime.startswith("image/") and ext not in ("hdr", "exr"):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(io.BytesIO(raw)) as im: w, h = im.size
    item = {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "mime": mime, "width": w, "height": h,
            **meta, "stored": time.strftime("%Y-%m-%d", time.gmtime())}
    m["items"][key] = item; save_manifest(order, m)
    print(f'stored {key}: {name} {len(raw):,} B {w}x{h} | {item["licence"]} | {item["author"]} | {item["source"]}', flush=True)


# ------------------------------------------------------------------ Wikimedia Commons
def commons_info(title, page=None, width=None):
    t = re.sub(r"^(File|Image):", "", title.strip(), flags=re.I)
    p = dict(action="query", format="json", redirects=1, titles="File:" + t, prop="imageinfo", iiprop="url|size|mime|extmetadata",
             iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|Credit|NonFree|ObjectName")
    if page: p.update(iiurlwidth=width or 1280, iiurlparam=f"page{int(page)}-{width or 1280}px")
    elif width: p.update(iiurlwidth=width)
    j = json.loads(get(COMMONS, p))
    pages = list(j.get("query", {}).get("pages", {}).values())
    if not pages or "imageinfo" not in pages[0]: die(f'no such file on Wikimedia Commons: "{t}"')
    ii = pages[0]["imageinfo"][0]; ii["title"] = pages[0]["title"]
    ii["page_url"] = "https://commons.wikimedia.org/wiki/" + pages[0]["title"].replace(" ", "_")
    return ii


def commons(order, key, title, page, replace):
    ii = commons_info(title, page)
    md = ii.get("extmetadata", {})
    short = plain(md.get("LicenseShortName", {}).get("value"))
    nonfree = plain(md.get("NonFree", {}).get("value")).lower() in ("true", "1", "yes")
    if not licence_check(short, nonfree): die(f'"{ii["title"][5:]}" has licence "{short or "none"}" - only Public domain, CC0, CC BY, CC BY-SA')
    who = author_clean(plain(md.get("Artist", {}).get("value")) or plain(md.get("Credit", {}).get("value")))
    mime = ii.get("mime")
    big = max(ii["width"], ii["height"])
    if page:                                                    # one page of a djvu / pdf / tif: its standard rendering
        url = ii["thumburl"]; mime = None
    elif mime in ("image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml") and ii.get("size", 0) <= 45e6 and big <= 9000:
        url = ii["url"]                                         # the original
    else:                                                       # huge or tif: the largest standard rendering
        url = None
        for W in STD_W:
            w = W if ii["width"] >= ii["height"] else max(320, round(W * ii["width"] / ii["height"]))
            j = commons_info(title, width=w)
            if j.get("thumburl") and j.get("thumbwidth", 0) >= min(ii["width"], 960): url = j["thumburl"]; break
        if not url: die(f"{title}: no usable rendering")
        mime = None
    raw = get(url)
    if not (sniff(raw) or mime): die(f"{title}: the download is not a picture")
    meta = {"licence": short, "author": who, "source": ii["page_url"], "title": ii["title"][5:], "page": page,
            "from": url}
    put(order, key, raw, mime, meta, replace)


def local_file(order, key, path, lic, who, src, title, replace):
    if not os.path.exists(path): die(f"{path} does not exist")
    if not lic or not who or not src: die("--licence, --author and --source are required")
    if not licence_check(lic): die(f'licence "{lic}" is not allowed - only Public domain, CC0, CC BY, CC BY-SA')
    mime = mimetypes.guess_type(path)[0] or ("model/gltf-binary" if path.endswith(".glb") else "application/octet-stream")
    if path.lower().endswith(".hdr"): mime = "image/vnd.radiance"
    if path.lower().endswith(".exr"): mime = "image/x-exr"
    raw = open(path, "rb").read()
    if not sniff(raw) and mime not in EXT: die(f"{path}: unsupported file type {mime}")
    put(order, key, raw, mime, {"licence": lic, "author": author_clean(who), "source": src, "title": title or os.path.basename(path),
                                "page": None, "from": "file"}, replace)


def verify(order, deep):
    m = load_manifest(order)
    rel = release(m["release"], create=False)
    if not rel: die(f'release {m["release"]} does not exist')
    have = {a["name"]: a for a in rel["assets"]}
    bad = 0
    for k, it in m["items"].items():
        a = have.get(it["file"])
        if not a or a["size"] != it["bytes"]: print("MISSING or wrong size:", k, it["file"]); bad += 1; continue
        if not licence_check(it.get("licence", "")): print("LICENCE not allowed:", k, it.get("licence")); bad += 1
        if deep:
            req = urllib.request.Request(a["browser_download_url"], headers={"User-Agent": "videomaps"})
            with urllib.request.urlopen(req, timeout=600) as r: d = r.read()
            if hashlib.sha256(d).hexdigest() != it["sha256"]: print("SHA256 differs:", k); bad += 1
    print(f'{len(m["items"])} items, {bad} problems'); sys.exit(2 if bad else 0)


def main(a):
    if len(a) < 2: print(__doc__); sys.exit(1)
    cmd, order = a[0], a[1]
    if not os.path.isdir(order): die(f"order folder {order} does not exist")
    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else d
    rep = "--replace" in a
    if cmd == "commons":
        if len(a) < 4: die("commons <orderDir> <key> <Commons file name> [--page N]")
        commons(order, a[2], a[3], int(opt("--page")) if opt("--page") else None, rep)
    elif cmd == "file":
        if len(a) < 4: die("file <orderDir> <key> <local file> --licence .. --author .. --source ..")
        local_file(order, a[2], a[3], opt("--licence"), opt("--author"), opt("--source"), opt("--title"), rep)
    elif cmd == "verify": verify(order, "--deep" in a)
    elif cmd == "list":
        for k, it in load_manifest(order)["items"].items():
            print(f'{k:16s} {it["file"]:28s} {it["bytes"]:>11,} {it["licence"]:16s} {it["author"][:40]}')
    else: print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
