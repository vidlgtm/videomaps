#!/usr/bin/env python3
"""One review file for the stills of a film: the map of the film (with the order's borders), the processing station's
sheets, the review stills (two per page, with their time), the station's assets as the film shows them.
usage: python factory/line/review_pdf.py <out.pdf> <font.ttf> <title> [--map sheet.jpg] [--station dir_of_station_*.jpg]
                                         [--stills dir_of_t*.jpg] [--instation dir_of_s*.jpg + labels.json]"""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont

BG, GOLD, WHITE = (12, 24, 34), (226, 191, 106), (244, 239, 230)


def opt(a, k):
    return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None


def tsec(name, pre):
    return float(os.path.basename(name)[len(pre):-4].replace("_", "."))


def pairs(files, label, F, head):
    pages = []
    for k in range(0, len(files), 2):
        s = Image.new("RGB", (1920, 590), BG); d = ImageDraw.Draw(s)
        for j, f in enumerate(files[k:k + 2]):
            s.paste(Image.open(f).convert("RGB").resize((960, 540), Image.LANCZOS), (960 * j, 50))
            d.text((20 + 960 * j, 10), (head + label(f))[:64], font=F, fill=GOLD)
        pages.append(s)
    return pages


def main(a):
    if len(a) < 3: print(__doc__); sys.exit(1)
    out, font, title = a[0], a[1], a[2]
    F = ImageFont.truetype(font, 26); FT = ImageFont.truetype(font, 54)
    pages = []
    cover = Image.new("RGB", (1920, 590), BG); d = ImageDraw.Draw(cover)
    d.text((60, 200), title[:60], font=FT, fill=WHITE); d.text((60, 300), "review stills", font=F, fill=GOLD)
    pages.append(cover)
    m = opt(a, "--map")
    if m and os.path.exists(m):
        im = Image.open(m).convert("RGB"); im.thumbnail((1880, 1040))
        s = Image.new("RGB", (1920, im.height + 70), BG); s.paste(im, ((1920 - im.width) // 2, 60))
        ImageDraw.Draw(s).text((20, 14), "map of the film (red = the film's countries)", font=F, fill=GOLD); pages.append(s)
    st = opt(a, "--station")
    if st:
        for f in sorted(glob.glob(f"{st}/station_*.jpg"), key=lambda f: int(f.rsplit("_", 1)[1][:-4])):
            pages.append(Image.open(f).convert("RGB"))
    sd = opt(a, "--stills")
    if sd:
        fs = sorted(glob.glob(f"{sd}/t*.jpg"), key=lambda f: tsec(f, "t"))
        mmss = lambda f: f"{int(tsec(f, 't') // 60)}:{tsec(f, 't') % 60:04.1f}"
        pages += pairs(fs, mmss, F, "t = ")
    ins = opt(a, "--instation")
    if ins:
        lab = json.load(open(f"{ins}/labels.json")) if os.path.exists(f"{ins}/labels.json") else {}
        fs = sorted(glob.glob(f"{ins}/s*.jpg"), key=lambda f: tsec(f, "s"))
        pages += pairs(fs, lambda f: f"{tsec(f, 's')} s  ·  {lab.get(os.path.basename(f), '')}", F, "t = ")
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    print(f"review file: {len(pages)} pages -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
