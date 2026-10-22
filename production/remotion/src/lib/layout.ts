// v4 screen-space layout of every overlay element at time t (pure TS).
//  * renderer: declutter() -> lower-priority elements fade (smoothly, over +-0.3 s) wherever a higher-priority one
//    covers them: screen cards > banners > icons > city markers > flags > map labels > country names
//  * tools/overlaps.ts: static audit of the whole film (raw overlaps before declutter)
import {project, px, CamState} from './proj';
import {clamp, env, ease} from './anim';
import {cameraAt, unproject} from './camera';
import {PATHS, CITIES, anchor} from './paths';
import {FLAGS, FLAG_HIDE, MARKERS, LABELS, CARDS, CLIPS, DOLL_LABELS, FILLS, T} from '../script';
import {BANNERS, ICONS, DOCS, CUTOUTS, NUMERALS, TAGS, TITLE, CREDITS, STAR} from '../v2';
import {SOV, MODERN, SHAPE_NAME, CTX_NAME} from '../names';

export type Box = {x0: number; y0: number; x1: number; y1: number};
export type Item = Box & {id: string; kind: string; prio: number; o: number; rank?: number};
const B = (x0: number, y0: number, x1: number, y1: number): Box => ({x0, y0, x1, y1});
const area = (b: Box) => Math.max(0, b.x1 - b.x0) * Math.max(0, b.y1 - b.y0);
export const inter = (a: Box, b: Box) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
const onScreen = (q: {x: number; y: number}, m = 260) => q.x > -m && q.x < 1920 + m && q.y > -m && q.y < 1080 + m * 1.6;

// ---------------- shared geometry (also used by the components) ----------------
export const OFF: Record<string, [number, number]> = {EST: [-26, -40], LVA: [-52, -6], LTU: [-40, 30], BLR: [-6, 14], MDA: [-30, 26],
  UKR: [0, 0], GEO: [-34, -10], ARM: [-26, 34], AZE: [30, 26], KGZ: [16, -8], TJK: [-6, 22], TKM: [0, 6], UZB: [6, -6], KAZ: [0, 0], RUS: [0, 0]};
export const flagSizeK = (zoom: number) => clamp(Math.sqrt(zoom / 0.24), 0.85, 1.6);
export const bannerSizeK = (zoom: number) => 1.55 * clamp(Math.sqrt(zoom / 1.6), 0.85, 1.12);

export type FlagL = {iso: string; f: any; x: number; y: number; ax: number; ay: number; size: number; o: number; dateO: number};
export function flagLayout(t: number, cam: CamState): FlagL[] {
  const sizeK = flagSizeK(cam.zoom);
  const hidden = FLAG_HIDE.some(([a, b]) => t > a && t < b);
  const hideO = FLAG_HIDE.reduce((m, [a, b]) => Math.min(m, 1 - env(t, a, b, 0.6, 0.8)), 1);
  const active: Record<string, any> = {};
  FLAGS.forEach((f) => { if (t >= f.t - 0.05 && t <= (f.to ?? 1e9)) active[f.iso] = f; });
  const out: FlagL[] = [];
  Object.values(active).forEach((f: any) => {
    const [sx, sy] = anchor('rep:' + f.iso);
    const gk = f.at ? (f.atUntil !== undefined ? ease(clamp((t - f.atUntil) / 1.2)) : 0) : 1;   // custom spot, then glide home
    const [cx, cy] = f.at ? px(f.at[0], f.at[1]) : [sx, sy];
    const [wx, wy] = [cx + (sx - cx) * gk, cy + (sy - cy) * gk];
    const q = project(cam, wx, wy);
    if (q.x < -200 || q.x > 2120 || q.y < -100 || q.y > 1300) return;
    const ov = cam.zoom < 0.42 ? OFF[f.iso] ?? [0, 0] : [0, 0];
    const k = clamp((0.42 - cam.zoom) / 0.1) * gk;
    out.push({iso: f.iso, f, x: q.x + ov[0] * k * sizeK, y: q.y + ov[1] * k * sizeK, ax: q.x, ay: q.y, size: sizeK * q.s,
      o: env(t, f.t - 0.05, f.to ?? 1e9, 0.15, 0.6) * (hidden ? hideO : 1), dateO: f.date ? env(t, f.t + 0.3, f.t + 3.2, 0.3, 0.6) : 0});
  });
  // v4: flags never sit on each other - symmetric relaxation (newer flags move more), leader lines drawn by <Flag/>
  out.sort((a, b) => a.f.t - b.f.t);
  const box = (g: FlagL) => { const d = clamp(g.dateO * 4); return B(g.x - 5 - 50 * d, g.y - 72 * g.size - 5, Math.max(g.x + 62.4 * g.size + 5, g.x + 54 * d), g.y + 7 + 22 * d); };
  for (let it = 0; it < 48; it++) {
    let moved = false;
    for (let i = 0; i < out.length; i++) for (let j = 0; j < i; j++) {
      const a = box(out[i]), b = box(out[j]);
      const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
      if (ox <= 0 || oy <= 0) continue;
      const w = clamp(Math.min(out[i].o, out[j].o) * 2) * 0.5;
      const horiz = ox < oy * 1.25;
      const d = horiz ? (a.x0 + a.x1 < b.x0 + b.x1 ? -ox : ox) : (a.y0 + a.y1 < b.y0 + b.y1 ? -oy : oy);
      if (horiz) { out[i].x += d * w * 1.3; out[j].x -= d * w * 0.7; } else { out[i].y += d * w * 1.3; out[j].y -= d * w * 0.7; }
      moved = true;
    }
    if (!moved) break;
  }
  return out;
}

/** alpha bounding boxes of the Blender icon renders (fractions of the 768 px square) */
export const ICON_BOX: Record<string, [number, number, number, number]> = {
  ballot_a180: [0.225, 0.164, 0.734, 0.777], ballot_a270: [0.246, 0.202, 0.736, 0.737], kremlin_a180: [0.341, 0.22, 0.638, 0.74],
  kremlin_a270: [0.35, 0.163, 0.645, 0.702], scroll_a180: [0.354, 0.34, 0.674, 0.69], scroll_a270: [0.225, 0.397, 0.766, 0.599],
  swords_a180: [0.352, 0.142, 0.63, 0.79], swords_a270: [0.223, 0.221, 0.781, 0.688], tank_a180: [0.251, 0.339, 0.764, 0.668],
  tank_a270: [0.219, 0.366, 0.76, 0.633], swords_a90: [0.201, 0.197, 0.802, 0.729], lodge_a180: [0.255, 0.21, 0.757, 0.773], lodge_a270: [0.23, 0.243, 0.77, 0.664],
};
/** v4: icons are sized by their visible content (the old 190 px box left the tank ~110 px wide) */
export const ICON_TARGET = 236;
export function iconLayout(name: string, az: number, x: number, y: number, s: number) {
  const bb = ICON_BOX[`${name}_a${az}`] ?? [0.25, 0.2, 0.75, 0.75];
  const cw = bb[2] - bb[0], ch = bb[3] - bb[1];
  const size = (ICON_TARGET * s) / Math.max(cw, ch * 1.08);      // full PNG square in px
  const left = x - ((bb[0] + bb[2]) / 2) * size, top = y - bb[3] * size + 0.012 * size;
  return {size, left, top, cx: x, cw: cw * size, content: B(left + bb[0] * size, top + bb[1] * size, left + bb[2] * size, top + bb[3] * size)};
}

const ASPECT: Record<string, number> = {'archive/const1936.jpg': 1280 / 2106, 'archive/const1936_a13.jpg': 1280 / 2106,
  'archive/const1936_a17.jpg': 1280 / 2106, 'archive/treaty1922.jpg': 2400 / 1533, 'archive/crimea1954.jpg': 2400 / 2278,
  'archive/belovezha.jpg': 2400 / 1578, 'archive/lenin_cut.png': 1270 / 1600, 'archive/stalin_cut.png': 1044 / 1231,
  'archive/gorbachev_cut.png': 1094 / 1541, 'archive/stalin1918_cut.png': 1188 / 1600};

// ---------------- names ----------------
export type NameL = {id: string; text: string; sub?: string; ctx: boolean; wx: number; wy: number; fs: number; o: number; q: {x: number; y: number; s: number}};
const sovietEra = (t: number) => t >= T.c1.s && t < T.c4.s;
const modernEra = (t: number) => t < T.c1.s || t >= T.c4.states;
function nameFor(id: string, t: number): string | null {
  if (id === 'shape:ussr_1991') return t < T.c1.s ? 'SOVIET UNION' : null;
  if (id.startsWith('rep:')) { const iso = id.slice(4); return modernEra(t) ? MODERN[iso] : sovietEra(t) ? SOV[iso] : null; }
  if (SHAPE_NAME[id]) return sovietEra(t) ? SHAPE_NAME[id] : null;
  return null;
}
/** screen dy that moves a text centred at q to just below a flag standing near it (0 if none) */
function underFlag(q: {x: number; y: number}, fs: number, flags: FlagL[]): number {
  let dy = 0;
  for (const g of flags) {
    if (g.o < 0.05 || Math.abs(g.x - q.x) > 90 || Math.abs(g.y - q.y) > 55) continue;
    const target = g.y + fs * 0.62 + 10 + 22 * g.dateO;
    if (target > q.y) dy = Math.max(dy, (target - q.y) * Math.min(1, g.o * 1.5));
  }
  return dy;
}
function namesAt(t: number, cam: CamState, flags: FlagL[]): NameL[] {
  const acc: Record<string, {text: string; o: number; w: number; x: number; y: number; pid: string; po: number}> = {};
  const put = (key: string, text: string, pid: string, o: number) => {
    const p = PATHS[pid];
    if (!p || !p.label) return;
    const a = (acc[key] ??= {text, o: 0, w: 0, x: 0, y: 0, pid, po: -1});
    a.o = Math.max(a.o, o); a.w += o; a.x += o * p.label[0]; a.y += o * p.label[1];
    if (o > a.po) { a.po = o; a.pid = pid; }
  };
  const lab = LABELS.filter((l) => t > l.from - 0.8 && t < (l.to ?? 1e9) + 0.8);
  const dup = (text: string, pid: string) => lab.some((l) => l.at === pid || text.includes(l.text.toUpperCase()) || l.text.toUpperCase().includes(text));
  FILLS.forEach((f) => {
    if (t < f.from + 0.3 || t > (f.to ?? 1e9) + 0.6) return;
    const text = nameFor(f.id, t);
    if (text && !dup(text, f.id)) put(text, text, f.id, env(t, f.from + 0.45, f.to ?? 1e9, 0.6, 0.5));
  });
  if (modernEra(t) && t > 3) Object.entries(CTX_NAME).forEach(([iso, text]) => { if (!dup(text, 'ctx:' + iso)) put(text + '|ctx', text, 'ctx:' + iso, 1); });
  const out: NameL[] = [];
  Object.entries(acc).forEach(([key, v]) => {
    if (v.w <= 0.001) return;
    const p = PATHS[v.pid];
    const ctx = v.pid.startsWith('ctx:');
    const wx = v.x / v.w, wy = v.y / v.w;
    const q = project(cam, wx, wy);
    if (q.x < 40 || q.x > 1880 || q.y < 60 || q.y > 1040) return;
    const bb = p.bbox ?? [wx - 60, wy - 40, wx + 60, wy + 40];
    const sw = (bb[2] - bb[0]) * cam.zoom * q.s, sh = (bb[3] - bb[1]) * cam.zoom * q.s;
    const L = Math.sqrt(Math.max(1, p.area_px ?? (bb[2] - bb[0]) * (bb[3] - bb[1]) * 0.5)) * cam.zoom * q.s;
    const maxFs = ctx ? 22 : v.text.length > 14 ? 30 : 38;
    let fs = clamp(L * (ctx ? 0.06 : 0.085), ctx ? 15 : 16, maxFs);
    const em = ctx ? 0.62 : 1.06;   // Cormorant italic caps + 0.18em / Cinzel caps + 0.28em
    let text = v.text, sub: string | undefined;
    if (!ctx && text.length * fs * em > sw * 1.15 && /\sS?F?SR$/.test(text)) {   // two lines: "UKRAINIAN" / "SSR"
      const i = text.lastIndexOf(' '); sub = text.slice(i + 1); text = text.slice(0, i);
    }
    while (text.length * fs * em > sw * 1.15 && fs > (ctx ? 15 : 16)) fs -= 1;
    if (text.length * fs * em > sw * 1.2 || sh < fs * 1.3) return;
    const dy = underFlag(q, fs, flags);
    const [nx, ny] = dy ? unproject(cam, q.x, q.y + dy) : [wx, wy];
    out.push({id: 'name:' + key, text, sub, ctx, wx: nx, wy: ny, fs, o: v.o * (ctx ? 0.62 : 1), q: {x: q.x, y: q.y + dy, s: q.s}});
  });
  return out;
}

// ---------------- all items at time t ----------------
export type Layout = {cam: CamState; items: Item[]; names: NameL[]; flags: FlagL[]; full: boolean; labelDy: Record<number, number>};
const tw = (s: string, fs: number, em: number) => s.length * fs * em;

export function layoutAt(t: number): Layout {
  const cam = cameraAt(t);
  const items: Item[] = [];
  const add = (id: string, kind: string, prio: number, o: number, b: Box) => { if (o > 0.02) items.push({id, kind, prio, o, ...b}); };
  const full = CLIPS.some((c) => c.kind === 'cauc' && t >= c.from + 0.3 && t <= c.to - 0.3);
  // screen-fixed overlays
  CARDS.forEach((c, i) => {
    if (t < c.from - 0.05 || t > c.to + 0.6) return;
    const o = env(t, c.from, c.to, 0.35, 0.5), id = 'card:' + i;
    if (c.kind === 'date') {
      const W = Math.max(tw(c.text, 40, 0.58), tw(c.sub ?? '', 16, 0.72)) + 74, x0 = c.pos === 'tr' ? 1920 - 64 - W : 64;
      add(id, 'date', 100, o, B(x0, 58, x0 + W, 58 + (c.sub ? 101 : 78)));
    } else if (c.kind === 'chapter') {
      const W = tw(c.text, c.text.length > 18 ? 74 : 92, 0.8) + 400;
      add(id, 'chapter', 100, o, B(960 - W / 2, 400, 960 + W / 2, 610));
    } else if (c.kind === 'quote') add(id, 'quote', 100, o, B(370, 300, 1550, 780));
    else if (c.kind === 'big') add(id, 'big', 100, o, B(540, 370, 1380, 730));
    else if (c.kind === 'title') add(id, 'title', 100, o, B(240, 330, 1680, 760));
    else if (c.kind === 'strike') add(id, 'strike', 100, o, B(380, 380, 1540, 700));
    else if (c.kind === 'end') add(id, 'end', 100, o, B(0, 0, 1920, 1080));
    else if (c.kind === 'callout' && c.at) { const W = tw(c.text, 22, 0.7) + 70; add(id, 'callout', 100, o, B(c.at[0] - W / 2, c.at[1] - 34, c.at[0] + W / 2, c.at[1] + 34)); }
  });
  DOCS.forEach((d, i) => {
    if (t < d.from || t > d.to) return;
    const w = d.w ?? 420, left = d.side === 'l' ? 130 : 1920 - 130 - w;
    const imgH = (w - 28) / (ASPECT[d.img] ?? 0.75), sigH = d.sigs ? 72 : 0;
    const capH = d.cap ? 14 + Math.ceil(tw(d.cap, 22, 0.96) / w) * 30 : 0;
    add('doc:' + i, 'doc', 100, clamp((d.to - t) / 0.4) * clamp((t - d.from) / 0.25), B(left - 14, 108, left + w + 14, 120 + 28 + imgH + sigH + capH + 8));
  });
  CUTOUTS.forEach((c, i) => {
    if (t < c.from || t > c.to) return;
    const o = clamp((c.to - t) / 0.45) * clamp((t - c.from) / 0.3), W = 900 * (ASPECT[c.img] ?? 0.8), r = c.side === 'r';
    const x1 = r ? 1880 : 40 + W, x0 = x1 - W;
    add('cut:' + i, 'cutout', 100, o, B(x0 + 0.1 * W, 250, x1 - 0.06 * W, 1080));
    const pw = Math.max(tw(c.name, 30, 0.94), tw(c.sub ?? '', 20, 0.5)) + 44;
    add('cutn:' + i, 'cutout', 100, o, r ? B(1830 - pw, 1080 - 70 - 84, 1830, 1010) : B(90, 1080 - 70 - 84, 90 + pw, 1010));
  });
  NUMERALS.forEach((n, i) => {
    if (t < n.from - 0.05 || t > n.to + 0.2) return;
    const fs = n.size ?? 250, top = n.y ?? 250, W = Math.max(tw(n.text, fs, 0.74), tw(n.sub ?? '', 40, 0.5));
    add('num:' + i, 'numeral', 100, env(t, n.from, n.to, 0.12, 0.18), B(960 - W / 2, top + 0.12 * fs, 960 + W / 2, top + 1.12 * fs + (n.sub ? 40 : 0)));
  });
  TAGS.forEach((g, i) => {
    if (t < g.from || t > g.to + 0.4) return;
    const W = g.num ? 700 : 500, cx = g.slot === undefined ? 960 : 960 + (g.slot - 1) * 560;
    add('tag:' + i, 'tag', 100, clamp((g.to + 0.4 - t) / 0.4), B(cx - W / 2, 846, cx + W / 2, 952));
  });
  if (t >= TITLE.from && t <= TITLE.to) add('title', 'title', 100, env(t, TITLE.from, TITLE.to, 0.6, 0.7), B(200, 320, 1720, 700));
  if (t >= CREDITS.from) add('credits', 'credits', 100, clamp((t - CREDITS.from) / 0.8), B(160, 800, 1760, 1034));
  if (t >= STAR.from - 0.1 && t <= STAR.from + 1.3) add('star', 'star', 100, 1, B(790, 285, 1130, 625));
  // v5: the four dolls of the final line-up (measured on the 1080p frame) and the rows of the level list actually shown
  const DOLLS: [number, number, number, number][] = [[404, 205, 698, 775], [762, 322, 990, 775], [1051, 414, 1234, 770], [1295, 487, 1442, 769]];
  CLIPS.forEach((c, i) => {
    if (c.kind === 'doll' && t >= c.from && t <= c.to)
      DOLLS.forEach((d, k) => add(`doll:${i}.${k}`, 'doll', 100, env(t, c.from, c.to, 0.5, 0.5), B(d[0] + (c.dx ?? 0), d[1], d[2] + (c.dx ?? 0), d[3])));
  });
  const rows = DOLL_LABELS.filter((d) => t >= d.from && t <= d.to);
  if (rows.length) {
    const W = rows.map((d) => 64 + tw(d.text, 30 - 2 * d.k, 0.8)), Wm = Math.max(...W);
    rows.forEach((d, r) => add(`dollL:${r}`, 'dollL', 100, env(t, d.from, d.to, 0.5, 0.5), B(1810 - Wm, 300 + 72 * r, 1810 - Wm + W[r], 346 + 72 * r)));
  }
  // map billboards
  const bk = bannerSizeK(cam.zoom);
  BANNERS.forEach((b, i) => {
    if (t < b.from || t > b.to) return;
    const q = project(cam, ...px(b.at[0], b.at[1]));
    if (!onScreen(q)) return;
    const S = bk * q.s * (b.size ?? 1);
    add('banner:' + i, 'banner', 80, clamp((t - b.from) / 0.1) * clamp((b.to - t) / 0.45), B(q.x - 116 * S, q.y - 252 * S, q.x + 116 * S, q.y + 6 * S));
  });
  ICONS.forEach((ic, i) => {
    if (t < ic.from || t > ic.to) return;
    const q = project(cam, ...px(ic.at[0], ic.at[1]));
    if (!onScreen(q)) return;
    const L = iconLayout(ic.name, ic.az, q.x, q.y, (bk / 1.55) * q.s * (ic.size ?? 1));
    add('icon:' + i, 'icon', 70, clamp((t - ic.from) / 0.08) * clamp((ic.to - t) / 0.4), L.content);
  });
  MARKERS.forEach((m, i) => {
    const o = env(t, m.from, m.to, 0.4, 0.5);
    if (o <= 0 || !CITIES[m.city]) return;
    const q = project(cam, CITIES[m.city].px[0], CITIES[m.city].px[1]);
    const side = m.side ?? 'r';
    if (m.dot) return;
    if (m.label || m.sub) {
      const w = Math.max(tw(m.label ?? '', 25, 0.66), tw(m.sub ?? '', 15, 0.56)), h = (m.label ? 32 : 0) + (m.sub ? 20 : 0);
      const x0 = side === 'r' ? q.x + 14 : side === 'l' ? q.x - 14 - w : q.x - w / 2, y0 = side === 't' ? q.y - 54 : side === 'b' ? q.y + 12 : q.y - 14;
      add('mlab:' + i, 'marker', 60, o, B(x0, y0, x0 + w, y0 + h));
    } else add('mlab:' + i, 'marker', 60, o, B(q.x + 12, q.y - 11, q.x + 12 + tw(m.city, 16, 0.56), q.y + 9));
  });
  const flags = flagLayout(t, cam);
  flags.forEach((g) => {
    const w = 60 * g.size, pole = 72 * g.size;
    add('flag:' + g.iso, 'flag', 50, g.o, B(g.x - 3, g.y - pole - 2, g.x + 2.4 * g.size + w + 3, g.y + 4));
    if (g.dateO > 0.05) add('fdate:' + g.iso, 'flag', 50, g.o * g.dateO, B(g.x - 52, g.y + 6, g.x + 52, g.y + 25));
  });
  const labelDy: Record<number, number> = {};
  LABELS.forEach((l, i) => {
    const o = env(t, l.from, l.to, 0.6, 0.6);
    if (o <= 0) return;
    const [wx, wy] = anchor(l.at);
    const q0 = project(cam, wx, wy);
    const dy = underFlag(q0, l.size * q0.s, flags);
    if (dy) labelDy[i] = dy;
    const q = {...q0, y: q0.y + dy};
    const fs = l.size * q.s, W = Math.max(tw(l.text, fs, l.italic ? 0.5 + (l.spacing ?? 0.22) : 0.8 + (l.spacing ?? 0.2)), tw(l.sub ?? '', fs * 0.5, 0.62));
    add('label:' + i, 'label', l.italic ? 35 : 40, o, B(q.x - W / 2, q.y - 0.45 * fs, q.x + W / 2, q.y + (l.sub ? 1.3 : 0.6) * fs));
  });
  const names = full ? [] : namesAt(t, cam, flags);
  names.forEach((n, k) => {
    const em = n.ctx ? 0.62 : 1.06, W = Math.max(tw(n.text, n.fs, em), tw(n.sub ?? '', n.fs * 0.55, 1.06));
    items.push({id: n.id, kind: 'name', prio: 30, rank: k, o: n.o, x0: n.q.x - W / 2 - 6, y0: n.q.y - 0.55 * n.fs, x1: n.q.x + W / 2 + 6,
      y1: n.q.y + (n.sub ? 1.15 : 0.5) * n.fs});
  });
  return {cam, items, names, flags, full, labelDy};
}

// ---------------- declutter ----------------
const covered = (a: Item, b: Item) => { const i = inter(a, b); return i > 0 && (i > 0.08 * area(a) || i > 700); };
function visibleAt(L: Layout): Map<string, number> {
  const vis = new Map<string, number>();
  const nameArea = (it: Item) => area(it) * (it.id.includes('|ctx') ? 0.3 : 1);
  const order = [...L.items].sort((a, b) => b.prio - a.prio || (a.kind === 'name' && b.kind === 'name' ? nameArea(b) - nameArea(a) : 0));
  const placed: Item[] = [];
  for (const it of order) {
    let hidden = false;
    for (const p of placed) {
      if (p.prio > it.prio || (it.kind === 'name' && p.kind === 'name')) { if (covered(it, p)) { hidden = true; break; } }
    }
    vis.set(it.id, hidden ? 0 : 1);
    if (!hidden && it.o > 0.25) placed.push(it);
  }
  return vis;
}
const CACHE = new Map<number, {L: Layout; vis: Map<string, number>}>();
export function frameLayout(f: number) {
  let c = CACHE.get(f);
  if (!c) {
    if (CACHE.size > 600) CACHE.clear();
    const L = layoutAt(f / 30);
    c = {L, vis: visibleAt(L)};
    CACHE.set(f, c);
  }
  return c;
}
/** smoothed visibility factor (0..1) of every element id at time t (7 samples over +-0.3 s) */
export function declutter(t: number): (id: string) => number {
  const f0 = Math.round(t * 30);
  const S = [-9, -6, -3, 0, 3, 6, 9].map((d) => frameLayout(f0 + d).vis);
  return (id: string) => S.reduce((s, m) => s + (m.get(id) ?? 1), 0) / S.length;
}
