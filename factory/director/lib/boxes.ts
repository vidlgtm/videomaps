// Screen boxes of every element (replicas of the renderer's layout.ts formulas) for placement decisions.
// The engine audit (factory/engine/tools/audit.ts) is the final judge; these only steer the choices.
import {project, CamState} from '../../engine/src/lib/proj';
import {clamp} from './util';

export type SBox = {x0: number; y0: number; x1: number; y1: number};
export const B = (x0: number, y0: number, x1: number, y1: number): SBox => ({x0, y0, x1, y1});
export const inter = (a: SBox, b: SBox) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
export const area = (a: SBox) => Math.max(0, a.x1 - a.x0) * Math.max(0, a.y1 - a.y0);
const tw = (s: string, fs: number, em: number) => s.length * fs * em;
export const flagSizeK = (zoom: number) => clamp(Math.sqrt(zoom / 0.24), 0.85, 1.6);
export const bannerSizeK = (zoom: number) => 1.55 * clamp(Math.sqrt(zoom / 1.6), 0.85, 1.12);
/** how far a box sticks out of the frame (0 = inside), with an inner margin m */
export const outBy = (b: SBox, m = 0) => Math.max(m - b.x0, b.x1 - (1920 - m), m - b.y0, b.y1 - (1080 - m), 0);

export function bannerBox(c: CamState, w: [number, number], size = 1): SBox {
  const q = project(c, w[0], w[1]), S = bannerSizeK(c.zoom) * q.s * size;
  return B(q.x - 116 * S, q.y - 252 * S, q.x + 116 * S, q.y + 6 * S);
}
export function iconBox(c: CamState, w: [number, number], size = 1, bb: number[] = [0.25, 0.2, 0.75, 0.75]): SBox {
  const q = project(c, w[0], w[1]), s = (bannerSizeK(c.zoom) / 1.55) * q.s * size;
  const cw = bb[2] - bb[0], ch = bb[3] - bb[1], full = (236 * s) / Math.max(cw, ch * 1.08);
  const left = q.x - ((bb[0] + bb[2]) / 2) * full, top = q.y - bb[3] * full + 0.012 * full;
  return B(left + bb[0] * full, top + bb[1] * full, left + bb[2] * full, top + bb[3] * full);
}
export function markerBox(c: CamState, w: [number, number], label: string | undefined, sub: string | undefined, side: string, city: string): SBox {
  const q = project(c, w[0], w[1]);
  if (label || sub) {
    const ww = Math.max(tw(label ?? '', 25, 0.66), tw(sub ?? '', 15, 0.56)), h = (label ? 32 : 0) + (sub ? 20 : 0);
    const x0 = side === 'r' ? q.x + 14 : side === 'l' ? q.x - 14 - ww : q.x - ww / 2, y0 = side === 't' ? q.y - 54 : side === 'b' ? q.y + 12 : q.y - 14;
    return B(x0, y0, x0 + ww, y0 + h);
  }
  return B(q.x + 12, q.y - 11, q.x + 12 + tw(city, 16, 0.56), q.y + 9);
}
export function flagBox(c: CamState, w: [number, number], date?: string): SBox {
  const q = project(c, w[0], w[1]), size = flagSizeK(c.zoom) * q.s, fw = 60 * size, pole = 72 * size;
  return B(q.x - (date ? 52 : 3), q.y - pole - 2, Math.max(q.x + 2.4 * size + fw + 3, q.x + (date ? 54 : 0)), q.y + (date ? 25 : 4));
}
export function labelBox(c: CamState, w: [number, number], text: string, size: number, italic?: boolean, sub?: string, spacing?: number): SBox {
  const q = project(c, w[0], w[1]), fs = size * q.s;
  const W = Math.max(tw(text, fs, italic ? 0.5 + (spacing ?? 0.22) : 0.8 + (spacing ?? 0.2)), tw(sub ?? '', fs * 0.5, 0.62));
  return B(q.x - W / 2, q.y - 0.45 * fs, q.x + W / 2, q.y + (sub ? 1.3 : 0.6) * fs);
}
// screen-fixed elements
export const dateBox = (text: string, sub: string | undefined, pos: string) => {
  const W = Math.max(tw(text, 40, 0.58), tw(sub ?? '', 16, 0.72)) + 74, x0 = pos === 'tr' ? 1920 - 64 - W : 64;
  return B(x0, 58, x0 + W, 58 + (sub ? 101 : 78));
};
export const docBox = (side: string, aspect: number, cap?: string, sigs?: boolean, w = 420) => {
  const left = side === 'l' ? 130 : 1920 - 130 - w, imgH = (w - 28) / aspect, sigH = sigs ? 72 : 0;
  const capH = cap ? 14 + Math.ceil(tw(cap, 22, 0.96) / w) * 30 : 0;
  return B(left - 14, 108, left + w + 14, 120 + 28 + imgH + sigH + capH + 8);
};
export const cutBox = (side: string, aspect: number) => {
  const W = 900 * aspect, r = side === 'r', x1 = r ? 1880 : 40 + W, x0 = x1 - W;
  return B(x0 + 0.1 * W, 250, x1 - 0.06 * W, 1080);
};
export const numeralBox = (text: string, sub: string | undefined, y: number, size: number) => {
  const W = Math.max(tw(text, size, 0.74), tw(sub ?? '', 40, 0.5));
  return B(960 - W / 2, y + 0.12 * size, 960 + W / 2, y + 1.12 * size + (sub ? 40 : 0));
};
export const tagBox = (num: boolean, slot?: number) => { const W = num ? 700 : 500, cx = slot === undefined ? 960 : 960 + (slot - 1) * 560; return B(cx - W / 2, 846, cx + W / 2, 952); };
export const chapterBox = (text: string) => { const W = tw(text, text.length > 18 ? 74 : 92, 0.8) + 400; return B(960 - W / 2, 400, 960 + W / 2, 610); };
export const CARD_BOX: Record<string, SBox> = {quote: B(370, 300, 1550, 780), big: B(540, 370, 1380, 730), title: B(240, 330, 1680, 760),
  strike: B(380, 380, 1540, 700), end: B(0, 0, 1920, 1080)};
