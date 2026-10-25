// Fitting: every map element inside the frame (auto re-framing), placement choices that avoid overlaps
// (banner/icon spots, marker sides, date-card corner, numeral height, document/portrait sides), and the rhythm
// filler (slow camera drifts so no view is held over 10 s and something new happens every 2-4 s).
import type {Director} from './plan';
import {px, PATHS, lonlat} from './geo';
import {keyState, unproject, inSafe, scr, CamKey, keyDistance} from './cam';
import * as BX from './boxes';
import {clamp, r2, r3} from './util';

const W = (ll: [number, number]) => px(ll[0], ll[1]) as [number, number];
const flagAnchor = (d: Director, f: any, t: number): [number, number] => {
  const home = PATHS['rep:' + f.iso]?.label ?? (f.at ? W(f.at) : [0, 0]);
  if (!f.at) return home as [number, number];
  const cx = W(f.at);
  if (f.atUntil === undefined || t < f.atUntil) return cx;
  const k = clamp((t - f.atUntil) / 1.2);
  return [cx[0] + (home[0] - cx[0]) * k, cx[1] + (home[1] - cx[1]) * k];
};
const anchorOf = (at: any): [number, number] => (Array.isArray(at) ? W(at as [number, number]) : (PATHS[at]?.label as [number, number]) ?? [0, 0]);
const settle = (d: Director, from: number, to: number) => {
  let tc = from + 0.6;
  const i = d.path.keyAt(tc), k = d.keys[i];
  if (i > 0 && tc < k.t + (k.dur ?? 2.2)) tc = Math.min(k.t + (k.dur ?? 2.2) + 0.15, (from + to) / 2);
  return Math.min(tc, to - 0.1);
};
/** world points of the top/side extent of a screen box drawn above anchor a (so the camera includes the billboard) */
const extentPts = (c: any, b: BX.SBox): [number, number][] => [unproject(c, b.x0, b.y0), unproject(c, b.x1, b.y0), unproject(c, b.x0, b.y1), unproject(c, b.x1, b.y1)];

export function visibility(d: Director) {
  for (let pass = 0; pass < 3; pass++) {
    let changed = false;
    const need = (from: number, to: number, why: string, pts: (c: any) => [number, number][]) => {
      for (const tc of [settle(d, from, to), Math.max(settle(d, from, to), to - 0.6)]) {
        if (tc <= from) continue;
        const c = d.path.at(tc);
        if (d.ensureVisible(tc, pts(c), why)) { changed = true; break; }
      }
    };
    d.F.banners.forEach((b) => need(b.from, b.to, `banner ${b.title}`, (c) => extentPts(c, BX.bannerBox(c, W(b.at), b.size ?? 1))));
    d.F.icons.forEach((i) => need(i.from, i.to, `icon ${i.name}`, (c) => extentPts(c, BX.iconBox(c, W(i.at), i.size ?? 1, d.a.icons?.[i.name]?.bb))));
    d.F.markers.forEach((m) => {
      if (m.dot) return;
      const ll = d.gaz.resolve(m.city).lonlat;
      need(m.from, m.to, `marker ${m.city}`, (c) => extentPts(c, BX.markerBox(c, W(ll), m.label, m.sub, m.side, m.city)));
    });
    d.F.labels.forEach((l) => { if (!l.italic) need(l.from, l.to, `label ${l.text}`, (c) => extentPts(c, BX.labelBox(c, anchorOf(l.at), l.text, l.size, l.italic, l.sub))); });
    d.F.flags.forEach((f) => {
      if (d.F.flag_hide.some(([a, b]: number[]) => f.t > a && f.t < b)) return;
      const to = Math.min(f.to, f.t + 6);
      need(f.t, to, `flag ${f.iso}`, (c) => extentPts(c, BX.flagBox(c, flagAnchor(d, f, settle(d, f.t, to)), f.date)));
    });
    d.F.arrows.forEach((a) => need(a.t, a.to, 'arrow', () => [W(a.a), W(a.b)]));
    d.F.lines.forEach((l) => need(l.from, l.to, 'route', () => l.pts.map((p: [number, number]) => W(p))));
    if (!changed) break;
    d.buildKeys();
  }
}

// ---------------------------------------------------------------- placement
type It = BX.SBox & {k: string};
export function itemsAt(d: Director, t: number, skip: string): It[] {
  const c = d.path.at(t), out: It[] = [];
  const on = (e: any, a = 'from', b = 'to') => t >= e[a] && t <= e[b] && e._k !== skip;
  const add = (k: string, b: BX.SBox) => out.push({...b, k});
  d.F.banners.forEach((b) => on(b) && add(b._k, BX.bannerBox(c, W(b.at), b.size ?? 1)));
  d.F.icons.forEach((i) => on(i) && add(i._k, BX.iconBox(c, W(i.at), i.size ?? 1, d.a.icons?.[i.name]?.bb)));
  d.F.markers.forEach((m) => { if (on(m) && !m.dot) add(m._k, BX.markerBox(c, W(d.gaz.resolve(m.city).lonlat), m.label, m.sub, m.side, m.city)); });
  d.F.labels.forEach((l) => on(l) && add(l._k, BX.labelBox(c, anchorOf(l.at), l.text, l.size, l.italic, l.sub)));
  const hidden = d.F.flag_hide.some(([a, b]: number[]) => t > a && t < b);
  if (!hidden) d.F.flags.forEach((f) => t >= f.t && t <= f.to && f._k !== skip && add(f._k, BX.flagBox(c, flagAnchor(d, f, t), f.date)));
  d.F.cards.forEach((cd) => {
    if (!on(cd)) return;
    if (cd.kind === 'date') add(cd._k, BX.dateBox(cd.text, cd.sub, cd.pos ?? 'tl'));
    else if (cd.kind === 'chapter') add(cd._k, BX.chapterBox(cd.text));
    else if (BX.CARD_BOX[cd.kind]) add(cd._k, BX.CARD_BOX[cd.kind]);
  });
  d.F.docs.forEach((o) => on(o) && o.side && add(o._k, BX.docBox(o.side, d.aspect(o.img), o.cap, !!o.sigs)));
  d.F.cutouts.forEach((o) => on(o) && o.side && add(o._k, BX.cutBox(o.side, d.aspect(o.img))));
  d.F.numerals.forEach((n) => on(n) && add(n._k, BX.numeralBox(n.text, n.sub, n.y ?? 250, n.size ?? 250)));
  d.F.tags.forEach((g) => on(g) && add(g._k, BX.tagBox(g.num !== undefined, g.slot)));
  return out;
}
const samples = (from: number, to: number) => { const a = from + 0.5, b = to - 0.3; return b <= a ? [Math.max(from, (from + to) / 2)] : [a, (a + b) / 2, b]; };
const cost = (d: Director, el: any, ts: number[], box: (t: number) => BX.SBox, outW = 40) =>
  ts.reduce((s, t) => { const b = box(t); return s + itemsAt(d, t, el._k).reduce((q, it) => q + BX.inter(b, it), 0) + outW * 100 * BX.outBy(b, 70); }, 0);

export function placement(d: Director) {
  const overlapT = (a: any, b: any) => Math.min(a.to, b.to) - Math.max(a.from, b.from) > 0.3;
  // portraits: a pair on screen -> left + right; else away from a document; default right
  d.F.cutouts.sort((a, b) => a.from - b.from).forEach((c) => {
    if (c.side) return;
    const other = d.F.cutouts.find((o) => o !== c && o.side && overlapT(o, c));
    const doc = d.F.docs.find((o) => o.side && overlapT(o, c));
    c.side = other ? (other.side === 'r' ? 'l' : 'r') : doc ? (doc.side === 'r' ? 'l' : 'r') : 'r';
  });
  d.F.cutouts.forEach((c) => {                                   // a portrait that starts while another is on its side moves over
    const clash = d.F.cutouts.find((o) => o !== c && o.side === c.side && overlapT(o, c));
    if (clash && clash.from < c.from) c.side = c.side === 'r' ? 'l' : 'r';
  });
  d.F.docs.forEach((o) => { if (!o.side) { const cut = d.F.cutouts.find((c) => overlapT(c, o)); o.side = cut ? (cut.side === 'r' ? 'l' : 'r') : 'r'; } });
  // banners and icons: the spot near their place that covers nothing and stays in frame
  const spots = (el: any, cands: number[][], box: (c: any, w: [number, number]) => BX.SBox) => {
    const ts = samples(el.from, el.to), tc = settle(d, el.from, el.to), c0 = d.path.at(tc), q = scr(c0, W(el.at));
    let best = el.at, bestC = Infinity;
    for (const [dx, dy] of cands) {
      const wpt = unproject(c0, q.x + dx, q.y + dy), ll = lonlat(wpt[0], wpt[1]);
      const cc = cost(d, el, ts, (t) => box(d.path.at(t), W(ll))) + 3 * Math.hypot(dx, dy);
      if (cc < bestC) { bestC = cc; best = ll; }
    }
    el.at = best;
  };
  const BC = [[0, 0], [170, 0], [-170, 0], [0, 110], [170, 110], [-170, 110], [260, -40], [-260, -40], [0, 200]];
  d.F.banners.forEach((b) => spots(b, BC, (c, w) => BX.bannerBox(c, w, b.size ?? 1)));
  d.F.icons.forEach((i) => spots(i, [[0, 0], [120, 0], [-120, 0], [0, 90], [120, 90], [-120, 90], [0, -80]], (c, w) => BX.iconBox(c, w, i.size ?? 1, d.a.icons?.[i.name]?.bb)));
  // marker label side
  d.F.markers.forEach((m) => {
    if (m.dot || !(m.label || m.sub) || m._fixedSide) return;
    const ll = d.gaz.resolve(m.city).lonlat, ts = samples(m.from, m.to);
    let best = m.side, bc = Infinity;
    for (const s of [m.side, 'r', 'l', 'b', 't']) {
      const cc = cost(d, m, ts, (t) => BX.markerBox(d.path.at(t), W(ll), m.label, m.sub, s, m.city)) + (s === m.side ? 0 : 400);
      if (cc < bc) { bc = cc; best = s; }
    }
    m.side = best;
  });
  // date cards: top-left unless something lives there
  d.F.cards.filter((c) => c.kind === 'date').forEach((cd) => {
    const ts = samples(cd.from, cd.to);
    const tl = cost(d, cd, ts, () => BX.dateBox(cd.text, cd.sub, 'tl')), tr = cost(d, cd, ts, () => BX.dateBox(cd.text, cd.sub, 'tr'));
    cd.pos = tr < tl * 0.8 ? 'tr' : 'tl';
  });
  // numerals: low (700) or high (250), whichever covers less of the map story
  d.F.numerals.forEach((n) => {
    const ts = samples(n.from, n.to);
    const lo = cost(d, n, ts, () => BX.numeralBox(n.text, n.sub, 700, n.size)), hi = cost(d, n, ts, () => BX.numeralBox(n.text, n.sub, 250, n.size));
    n.y = hi < lo * 0.8 ? 250 : 700;
  });
}

// ---------------------------------------------------------------- rhythm
export function rhythm(d: Director) {
  const blocked = (t: number) =>
    d.F.clips.some((c) => c.kind === 'cauc' && t > c.from - 0.5 && t < c.to + 0.5) ||
    d.F.cards.some((c) => ['chapter', 'title', 'quote', 'end', 'strike'].includes(c.kind) && t > c.from - 0.3 && t < c.to + 0.3) ||
    (d.opening && t < d.opening.end + 0.5) || (d.title && t > d.title.from - 0.3 && t < d.title.to);
  const events: number[] = [];
  const push = (t: number) => events.push(t);
  ['fills', 'labels', 'markers', 'banners', 'icons', 'cards', 'docs', 'cutouts', 'numerals', 'tags', 'lines', 'arrows', 'rings', 'dot_shows', 'clips']
    .forEach((n) => d.F[n].forEach((e: any) => push(e.from ?? e.t)));
  d.F.flags.forEach((f) => push(f.t));
  d.F.strokes.filter((s) => s.draw).forEach((s) => push(s.from));
  d.keys.forEach((k) => push(k.t));
  events.sort((a, b) => a - b);
  const add: CamKey[] = [];
  let n = 0;
  const drift = (t: number) => {
    if (blocked(t) || d.keys.some((k) => Math.abs(k.t - t) < 1.8) || add.some((k) => Math.abs(k.t - t) < 3)) return;
    const i = d.path.keyAt(t), base = d.keys[i];
    if (base.kind === 'hold') return;
    const sh = d.shots.find((s) => s.key === base.src);
    if (sh?.hold) return;
    const c = d.path.at(t);
    const vis = itemsAt(d, t + 1.5, '').filter((it) => it.y1 < 1080 && it.y0 > 0);
    const push = n % 2 === 0;
    const k: CamKey = {...base, t: r3(t), dur: 3.6, kind: 'drift', src: (base.src ?? '') + '/drift',
      w: Math.round(base.w * (push ? 0.91 : 1.07)), tilt: r2(clamp((base.tilt ?? 0) + (push ? 2.5 : -2), 0, 40))};
    if (vis.length && base.lon !== undefined) {                            // lean towards the story on screen (<= 3 % of the view)
      const mx = vis.reduce((s, b) => s + (b.x0 + b.x1) / 2, 0) / vis.length, my = vis.reduce((s, b) => s + (b.y0 + b.y1) / 2, 0) / vis.length;
      const dx = clamp(mx - 960, -58, 58), dy = clamp(my - 540, -32, 32);
      const [wx, wy] = unproject(c, 960 + dx, 540 + dy), ll = lonlat(wx, wy);
      k.lon = r3(base.lon + (ll[0] - lonlat(c.x, c.y)[0])); k.lat = r3(base.lat! + (ll[1] - lonlat(c.x, c.y)[1]));
    }
    // keep what is on screen on screen
    const s2 = keyState(k);
    const bad = vis.some((b) => { const q = [unproject(c, b.x0, b.y0), unproject(c, b.x1, b.y1)]; return q.some((p) => !inSafe(s2, p, -40)); });
    if (bad) { k.w = Math.round(base.w * 1.06); k.tilt = base.tilt; if (base.lon !== undefined) { k.lon = base.lon; k.lat = base.lat; } }
    add.push(k); n++;
  };
  // holds over ~9 s get a slow drift every ~6 s
  d.keys.forEach((k, i) => {
    const s = k.t + (k.dur ?? 2.2), e = i + 1 < d.keys.length ? d.keys[i + 1].t : d.END;
    for (let t = s + 5.5; t < e - 3.5; t += 6.5) drift(t);
  });
  // gaps without anything new for more than ~4.2 s
  for (let j = 0; j + 1 < events.length; j++) if (events[j + 1] - events[j] > 4.6) drift(events[j] + 2.0);
  if (add.length) { d.keys = [...d.keys, ...add].sort((a, b) => a.t - b.t); d.path = new (d.path.constructor as any)(d.keys); }
  return add.length;
}
