"""FACTORY - Manim document from the order's text (processing station). Aged paper, hand-written reveal, full frame;
the film plays it as a full-frame clip (the director stretches it 0.8-1.3x to the narration).
One JSON per document (written by station.py from sources.json "documents"):
  layout "article": {"head": "CONSTITUTION OF THE USSR · 1977", "title": "Article 72", "title_font": "serif" | "script",
                     "body": ["line", "line", "line"], "underline": 1 | null, "seal": "1991" | null, "hold": 2.2}
  layout "maxim"  : {"title": "Uti possidetis juris", "gloss": ["line", "line"], "seal": "1991" | null, "hold": 1.8}
render: DOC_JSON=path manim render -qh --fps 30 -r 1920,1080 doc_scene.py Doc -o <id>   (repo fonts installed)"""
import json, os
import numpy as np
from manim import *
from scipy.ndimage import gaussian_filter, zoom

INK, RED, BROWN = "#2A1D12", "#8E1B1B", "#5A4026"


def parchment(w=1920, h=1080, seed=3):
    rng = np.random.default_rng(seed)
    base = np.array([234, 222, 192], np.float32)
    n = gaussian_filter(rng.standard_normal((h // 4, w // 4)).astype(np.float32), 7) * 16 + \
        gaussian_filter(rng.standard_normal((h // 4, w // 4)).astype(np.float32), 1.0) * 4
    n = zoom(n, 4, order=1)[:h, :w]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vign = np.clip(1 - 0.55 * np.clip(r - 0.5, 0, 1) ** 1.4, 0.55, 1)
    img = (base[None, None, :] + n[..., None]) * vign[..., None]
    img[..., 2] *= 0.96
    return np.clip(img, 0, 255).astype(np.uint8)


def seal(label):
    edge = Star(n=28, outer_radius=1.05, inner_radius=0.94, color=RED, fill_color=RED, fill_opacity=1, stroke_width=0)
    disc = Circle(radius=0.86, color="#6E1212", stroke_width=5, fill_color="#9A2020", fill_opacity=1)
    ring = Circle(radius=0.70, color="#C9665E", stroke_width=2)
    t = Text(label, font="Cormorant Garamond", weight=BOLD, color="#F6DDB8").scale(0.62)
    return VGroup(edge, disc, ring, t)


class Doc(Scene):
    def construct(self):
        d = json.load(open(os.environ["DOC_JSON"]))
        im = ImageMobject(parchment()); im.stretch_to_fit_width(config.frame_width); im.stretch_to_fit_height(config.frame_height)
        self.add(im)
        script = d.get("title_font", "script" if d.get("layout") == "maxim" else "serif") == "script"
        sl = seal(d["seal"]).scale(0.95).to_corner(DR, buff=1.0) if d.get("seal") else None
        if d.get("layout") == "maxim":
            title = Text(d["title"], font="Great Vibes", color=INK).scale(2.1)
            if title.width > config.frame_width - 2.4: title.scale((config.frame_width - 2.4) / title.width)
            title.shift(UP * 1.25)
            gl = [Text(g, font="Cormorant Garamond", slant=ITALIC, color=BROWN).scale(0.85) for g in d.get("gloss", [])]
            grp = VGroup(*gl).arrange(DOWN, buff=0.28).next_to(title, DOWN, buff=0.75) if gl else None
            self.wait(0.2)
            self.play(Write(title), run_time=1.9, rate_func=linear)
            self.wait(1.2)
            for k, g in enumerate(gl):
                self.play(FadeIn(g, shift=UP * 0.12), run_time=0.6)
                self.wait(1.0 if k < len(gl) - 1 else 0.3)
        else:
            head = Text(d["head"], font="Cormorant Garamond", weight=BOLD, color=BROWN).scale(0.62).to_edge(UP, buff=1.05) if d.get("head") else None
            rule = Line(LEFT * 3.2, RIGHT * 3.2, color=BROWN, stroke_width=2)
            rule.next_to(head, DOWN, buff=0.28) if head else rule.to_edge(UP, buff=1.45)
            title = (Text(d["title"], font="Great Vibes", color=INK).scale(1.7) if script else
                     Text(d["title"], font="Cormorant Garamond", slant=ITALIC, weight=BOLD, color=RED).scale(1.0)).next_to(rule, DOWN, buff=0.55)
            body = Paragraph(*d["body"], font="Cormorant Garamond", alignment="center", line_spacing=0.85, color=INK).scale(1.05)
            if body.width > config.frame_width - 3.0: body.scale((config.frame_width - 3.0) / body.width)
            body.next_to(title, DOWN, buff=0.6)
            if sl and body.get_bottom()[1] < sl.get_top()[1] + 0.2 and body.get_right()[0] > sl.get_left()[0] - 0.2:
                body.scale(0.85).next_to(title, DOWN, buff=0.5)            # keep the seal on clear paper
            self.play(*([FadeIn(head, shift=DOWN * 0.15)] if head else []), Create(rule), run_time=0.8)
            self.play(Write(title), run_time=1.4 if script else 0.7)
            self.play(Write(body), run_time=max(1.2, 0.7 * len(d["body"])), rate_func=linear)
            u = d.get("underline")
            if u is not None and 0 <= int(u) < len(d["body"]):
                self.play(Create(Underline(body[int(u)], color=RED, stroke_width=7, buff=0.08)), run_time=0.5)
        if sl:
            self.play(FadeIn(sl, scale=1.6), run_time=0.35, rate_func=rush_into)
            self.play(sl.animate.scale(1.04), run_time=0.12, rate_func=there_and_back)
        self.wait(float(d.get("hold", 1.8 if d.get("layout") == "maxim" else 2.2)))
