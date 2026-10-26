"""Workshop template 'nest' - fetches the picture of every level (Wikimedia Commons file rendered to PNG by Commons,
or a direct PNG/JPG url) + its licence for the credits.  usage: python3 nest_prep.py <params.json> <out_dir>"""
import json, os, sys, time, io, re
import numpy as np, requests
from PIL import Image

P = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "videomaps-workshop/1.0 (map history films)"}


def get(url, **kw):
    for i in range(6):
        try:
            r = requests.get(url, timeout=60, headers=H, **kw); r.raise_for_status(); return r
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(url)


def fetch(img):
    meta = {}
    if img.get("commons"):
        t = img["commons"] if img["commons"].startswith("File:") else "File:" + img["commons"]
        d = get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "titles": t, "prop": "imageinfo",
                "iiprop": "url|size|extmetadata", "iiurlwidth": 2048, "format": "json"}).json()
        pg = next(iter(d["query"]["pages"].values()))
        if "imageinfo" not in pg: raise SystemExit(f"file not found on Wikimedia Commons: {t}")
        ii = pg["imageinfo"][0]; em = ii.get("extmetadata", {})
        lic = em.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"public domain|^pd|cc0|cc by(-sa)? ", lic.lower() + " "):
            raise SystemExit(f"licence not allowed for {t}: {lic}")
        art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip().split("\n")[0].strip()
        if len(art) > 60 or re.search(r"file history|unknown|see below", art.lower()): art = ""
        url = ii.get("thumburl") or ii["url"]
        meta = {"what": t[5:].rsplit(".", 1)[0], "author": art, "page": ii.get("descriptionurl", ""),
                "license": "Public domain" if "public domain" in lic.lower() or lic.lower().startswith("pd") else lic}
    else:
        url = img["url"]
    im = Image.open(io.BytesIO(get(url).content)).convert("RGB")
    if im.width < 1600: im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    return im, meta


levels, credits = {}, []
for lv in P["levels"]:
    k = lv["key"]
    im, meta = fetch(lv["image"])
    im.save(f"{OUT}/img_{k}.png")
    a = np.asarray(im, np.float32) / 255
    meta.update({"file": f"img_{k}.png", "aspect": im.width / im.height, "size": im.size,
                 "luma": round(float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean()), 4)})
    levels[k] = meta
    if meta.get("what"):
        credits.append(f"{meta['what']}: {meta['license']}" + (f", {meta['author']}" if meta.get("author") else "") + " (Wikimedia Commons)")
    print("level", k, im.size, meta.get("license", ""), flush=True)
json.dump({"levels": levels, "credits": sorted(set(credits), key=credits.index)}, open(f"{OUT}/meta.json", "w"))
