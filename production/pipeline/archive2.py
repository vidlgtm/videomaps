"""Archival photos for the banners / living photographs.
download (Wikimedia Commons, PD / CC licences listed in production/archive_manifest.json)
-> Real-ESRGAN (realesr-general-x4v3, via spandrel) for small originals
-> Depth-Anything-V2-Small depth maps (2.5D parallax)  -> rembg cut-outs for portraits
outputs: out/archive/<id>.jpg, <id>_depth.png, <id>_cut.png, credits.json, archive_sheet.jpg"""
import io, json, os, time
import numpy as np, requests, torch
from PIL import Image, ImageOps, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "out/archive"; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "videomaps-ci/2.0 (https://github.com/vidlgtm/videomaps)"}
M = json.load(open(f"{ROOT}/archive_manifest.json"))
M.append(dict(id="sovflag", title="Flag of the Soviet Union.svg", license="Public domain", artist="",
              url="https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Flag_of_the_Soviet_Union.svg&width=2400",
              page="https://commons.wikimedia.org/wiki/File:Flag_of_the_Soviet_Union.svg"))
CUT = {"lenin", "stalin1918", "stalin", "gorbachev"}
NO_DEPTH = {"sovflag", "treaty1922", "const1936", "crimea1954", "ukr_ref"}
MAXS = 2400
torch.set_num_threads(4)


def get(url):
    for i in range(6):
        try:
            r = requests.get(url, headers=UA, timeout=120); r.raise_for_status(); return r.content
        except Exception as e:
            print("retry", url[:80], e); time.sleep(3 + 5 * i)
    raise RuntimeError(url)


# ---------- super-resolution ----------
from spandrel import ModelLoader
wp = "cache/realesr-general-x4v3.pth"; os.makedirs("cache", exist_ok=True)
if not os.path.exists(wp):
    open(wp, "wb").write(get("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"))
SR = ModelLoader().load_from_file(wp).eval()
print("SR model:", SR.architecture.name if hasattr(SR, "architecture") else type(SR), "scale", SR.scale)


def upscale(img):
    x = torch.from_numpy(np.asarray(img, np.float32) / 255).permute(2, 0, 1)[None]
    h, w = x.shape[2:]
    out = torch.zeros(1, 3, h * SR.scale, w * SR.scale)
    T, P = 384, 16   # tiles with overlap
    with torch.inference_mode():
        for y in range(0, h, T):
            for x0 in range(0, w, T):
                ya, yb, xa, xb = max(0, y - P), min(h, y + T + P), max(0, x0 - P), min(w, x0 + T + P)
                o = SR(x[:, :, ya:yb, xa:xb]).clamp(0, 1)
                s = SR.scale
                oy, ox = (y - ya) * s, (x0 - xa) * s
                th, tw = (min(h, y + T) - y) * s, (min(w, x0 + T) - x0) * s
                out[:, :, y * s:y * s + th, x0 * s:x0 * s + tw] = o[:, :, oy:oy + th, ox:ox + tw]
    return Image.fromarray((out[0].permute(1, 2, 0).numpy() * 255 + 0.5).astype(np.uint8))


# ---------- depth ----------
from transformers import pipeline
DEPTH = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
# ---------- cut-outs ----------
from rembg import remove, new_session
RB = new_session("isnet-general-use")

credits, thumbs = [], []
for m in M:
    t0 = time.time()
    raw = Image.open(io.BytesIO(get(m["url"])))
    raw = ImageOps.exif_transpose(raw)
    if raw.mode in ("RGBA", "LA", "P"):
        raw = raw.convert("RGBA"); bg = Image.new("RGBA", raw.size, (255, 255, 255, 255)); bg.alpha_composite(raw); raw = bg
    img = raw.convert("RGB")
    w, h = img.size
    if max(w, h) < 1800 and m["id"] != "sovflag":
        img = upscale(img)
        print(f"  {m['id']}: SR {w}x{h} -> {img.size}")
    if max(img.size) > MAXS:
        f = MAXS / max(img.size); img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
    img.save(f"{OUT}/{m['id']}.jpg", quality=92)
    th = [img.copy()]
    if m["id"] not in NO_DEPTH:
        small = img.copy(); small.thumbnail((1024, 1024), Image.LANCZOS)
        d = DEPTH(small)["depth"].convert("L").resize((img.width // 2, img.height // 2), Image.BICUBIC)
        d.save(f"{OUT}/{m['id']}_depth.png"); th.append(d.convert("RGB"))
    if m["id"] in CUT:
        c = remove(img, session=RB); c.thumbnail((1600, 1600), Image.LANCZOS); c.save(f"{OUT}/{m['id']}_cut.png")
        bgc = Image.new("RGB", c.size, (40, 120, 60)); bgc.paste(c, mask=c.split()[3]); th.append(bgc)
    credits.append({k: m.get(k, "") for k in ("id", "title", "artist", "license", "page", "date")})
    thumbs.append((m["id"], th))
    print(f"{m['id']}: {img.size} {time.time() - t0:.0f}s", flush=True)

json.dump(credits, open(f"{OUT}/credits.json", "w"), ensure_ascii=False, indent=1)
# contact sheet: one row per item (image | depth | cut-out)
H = 200; rows = []
for id_, th in thumbs:
    row = Image.new("RGB", (1500, H + 24), (24, 24, 24)); x = 0
    for im in th:
        im = im.copy(); im.thumbnail((480, H)); row.paste(im, (x, 0)); x += im.width + 8
    ImageDraw.Draw(row).text((4, H + 6), id_, fill=(255, 220, 120))
    rows.append(row)
for k in range(0, len(rows), 8):
    sheet = Image.new("RGB", (1500, (H + 24) * 8), (10, 10, 10))
    for i, r in enumerate(rows[k:k + 8]): sheet.paste(r, (0, i * (H + 24)))
    sheet.save(f"{OUT}/archive_sheet_{k // 8 + 1}.jpg", quality=85)
print("done")
