"""Manim documents for v2 (no charts): hand-written reveals on parchment, shown on banners in the film.
render: manim render -qh --fps 30 -r 1920,1080 scenes2.py Article72 UtiPossidetis"""
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


def paper():
    im = ImageMobject(parchment()); im.stretch_to_fit_width(config.frame_width); im.stretch_to_fit_height(config.frame_height)
    return im


def seal(label="1991"):
    edge = Star(n=28, outer_radius=1.05, inner_radius=0.94, color=RED, fill_color=RED, fill_opacity=1, stroke_width=0)
    disc = Circle(radius=0.86, color="#6E1212", stroke_width=5, fill_color="#9A2020", fill_opacity=1)
    ring = Circle(radius=0.70, color="#C9665E", stroke_width=2)
    t = Text(label, font="Cormorant Garamond", weight=BOLD, color="#F6DDB8").scale(0.62)
    return VGroup(edge, disc, ring, t)


class Article72(Scene):
    """narration: 'The Soviet constitution guaranteed each of them the right to freely leave the Union.'"""
    def construct(self):
        self.add(paper())
        head = Text("CONSTITUTION OF THE USSR  \u00b7  1977", font="Cormorant Garamond", weight=BOLD, color=BROWN).scale(0.62)
        head.to_edge(UP, buff=1.05)
        rule = Line(LEFT * 3.2, RIGHT * 3.2, color=BROWN, stroke_width=2).next_to(head, DOWN, buff=0.28)
        art = Text("Article 72", font="Cormorant Garamond", slant=ITALIC, weight=BOLD, color=RED).scale(1.0).next_to(rule, DOWN, buff=0.55)
        body = Paragraph("Each Union Republic shall retain", "the right freely to secede", "from the USSR.",
                         font="Cormorant Garamond", alignment="center", line_spacing=0.85, color=INK).scale(1.05)
        body.next_to(art, DOWN, buff=0.6)
        self.play(FadeIn(head, shift=DOWN * 0.15), Create(rule), run_time=0.8)
        self.play(Write(art), run_time=0.7)
        self.play(Write(body), run_time=2.1, rate_func=linear)
        und = Underline(body[1], color=RED, stroke_width=7, buff=0.08)
        self.play(Create(und), run_time=0.5)
        self.wait(2.2)


class UtiPossidetis(Scene):
    """narration: '... a legal principle called uti possidetis juris, which means that new states inherit
    the borders they held as administrative units.'  (clip starts 0.2 s before 'uti')"""
    def construct(self):
        self.add(paper())
        title = Text("Uti possidetis juris", font="Great Vibes", color=INK).scale(2.1).shift(UP * 1.25)
        g1 = Text("new states inherit the borders", font="Cormorant Garamond", slant=ITALIC, color=BROWN).scale(0.85)
        g2 = Text("they held as administrative units", font="Cormorant Garamond", slant=ITALIC, color=BROWN).scale(0.85)
        gl = VGroup(g1, g2).arrange(DOWN, buff=0.28).next_to(title, DOWN, buff=0.75)
        sl = seal().scale(0.95).to_corner(DR, buff=1.0)
        self.wait(0.2)
        self.play(Write(title), run_time=1.9, rate_func=linear)
        self.wait(1.2)
        self.play(FadeIn(g1, shift=UP * 0.12), run_time=0.6)
        self.wait(1.0)
        self.play(FadeIn(g2, shift=UP * 0.12), run_time=0.6)
        self.wait(0.3)
        self.play(FadeIn(sl, scale=1.6), run_time=0.35, rate_func=rush_into)
        self.play(sl.animate.scale(1.04), run_time=0.12, rate_func=there_and_back)
        self.wait(1.8)
