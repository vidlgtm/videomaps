// Second pass: the engine audit (tools/audit.ts: overlaps that stay visible, text cut by the frame, elements the
// declutter keeps hidden) -> patches that the director applies on the next run (move a billboard/label, switch a
// side/corner, re-frame the shot, or as a last resort shorten the lower-priority element).
// Patches accumulate in <order>/out/patches.json.
import type {Director} from './plan';
import {px, lonlat, PATHS} from './geo';
import {unproject, scr} from './cam';
import {r3, clamp} from './util';
import {innerPoint} from './fit';
import * as BX from './boxes';

const ARR: Record<string, string> = {banner: 'banners', icon: 'icons', mlab: 'markers', label: 'labels', card: 'cards', doc: 'docs', cut: 'cutouts',
  cutn: 'cutouts', num: 'numerals', tag: 'tags'};
export function feedbackToPatches(audit: any, d: Director, film: any, patches: Record<string, any>) {
  if (!film) return patches;
  const P = {...patches};
  const elOf = (id: string, t: number): {arr: string; key: string; el: any} | null => {
    const [pre, rest] = [id.split(':')[0], id.slice(id.indexOf(':') + 1)];
    if (pre === 'flag' || pre === 'fdate') {
      const i = film.flags.findIndex((f: any) => f.iso === rest && f.t <= t + 0.1 && f.to >= t - 0.1);
      return i >= 0 ? {arr: 'flags', key: film.keys.flags[i], el: film.flags[i]} : null;
    }
    const a = ARR[pre]; if (!a) return null;
    const i = parseInt(rest, 10);
    return film[a]?.[i] ? {arr: a, key: film.keys[a][i], el: film[a][i]} : null;
  };
  const set = (e: {arr: string; key: string}, s: any) => { const k = `${e.arr}:${e.key}`; P[k] = {set: {...(P[k]?.set ?? {}), ...s}}; };
  const shifted = new Set<string>();
  const camShift = (t: number, dx: number, dy: number) => {                // last resort, small and once per shot per pass
    const i = d.path.keyAt(t), src = d.keys[i]?.src;
    if (!src || src.includes('/drift') || shifted.has(src) || d.keys[i].x !== undefined) return;   // overviews slide in the director instead
    shifted.add(src);
    const q = P[src] ?? {};
    P[src] = {...q, shift: [clamp((q.shift?.[0] ?? 0) + clamp(dx, -90, 90), -220, 220), clamp((q.shift?.[1] ?? 0) + clamp(dy, -90, 90), -220, 220)]};
  };
  const moveAt = (e: {arr: string; key: string; el: any}, t: number, dx: number, dy: number) => {
    const c = d.path.at(t), at = e.el.at;
    const w = Array.isArray(at) ? px(at[0], at[1]) : PATHS[at]?.label;
    if (!w) return false;
    const q = scr(c, w as [number, number]), n = unproject(c, q.x + dx, q.y + dy);
    set(e, {at: lonlat(n[0], n[1])}); return true;
  };
  const fixOff = (v: any) => {
    const e = elOf(v.a, v.t0); if (!e) return;
    const [x0, y0, x1, y1] = v.box, m = 40;
    const dx = x0 < 0 ? -x0 + m : x1 > 1920 ? 1920 - x1 - m : 0, dy = y0 < 0 ? -y0 + m : y1 > 1080 ? 1080 - y1 - m : 0;
    const c = d.path.at(v.t0 + 0.2);
    if (e.arr === 'markers') set(e, {side: dx > 0 ? 'r' : dx < 0 ? 'l' : dy > 0 ? 'b' : 't', _fixedSide: true});
    else if (e.arr === 'banners' || e.arr === 'icons' || (e.arr === 'labels' && Array.isArray(e.el.at))) moveAt(e, v.t0 + 0.2, dx, dy);
    else if (e.arr === 'labels' && typeof e.el.at === 'string') {
      const p = innerPoint(e.el.at, c, (x1 - x0) / 2 + 12, 30, 40);
      if (p) set(e, {at: lonlat(p[0], p[1])}); else camShift(v.t0, -dx, -dy);
    } else if (e.arr === 'flags' && !e.el.at) {
      const p = innerPoint('rep:' + e.el.iso, c, 70, 110, e.el.date ? 60 : 30);
      if (p) set(e, {at: lonlat(p[0], p[1])}); else camShift(v.t0, -dx, -dy);
    } else camShift(v.t0, -dx, -dy);
  };
  for (const v of audit.offscreen ?? []) fixOff(v);
  // UNSEEN: a story element the viewer does not really see. Under a clip -> it starts when the clip ends (and keeps
  // 2 s); a flag cut by an overview -> that overview frames a little wider; partly cut by the frame -> moved inward as
  // above. Entirely outside the shot: no blind repair - the camera has to go there (the line stops on it).
  const widened = new Set<string>();
  const camWiden = (t: number) => {
    const i = d.path.keyAt(t), k = d.keys[i], src = k?.src;
    if (!src || src.includes('/drift') || k.x === undefined || widened.has(src)) return;
    widened.add(src);
    const q = P[src] ?? {};
    P[src] = {...q, wmul: r3(clamp((q.wmul ?? 1) * 1.06, 0.8, 1.25))};
  };
  for (const v of audit.unseen ?? []) {
    const e = elOf(v.a, v.tm); if (!e) continue;
    if (v.why === 'clip') {
      const ends = (film.clips ?? []).filter((c: any) => c.from < v.t1 && c.to > v.t0 + 0.3).map((c: any) => c.to);
      if (!ends.length) continue;
      const nf = r3(Math.max(...ends) + 0.15), k = e.arr === 'flags' ? 't' : 'from';
      if (nf >= (e.el.to ?? Infinity) + 1.5) continue;
      set(e, {[k]: nf, ...(e.el.to !== undefined && e.el.to < nf + 2.0 ? {to: r3(nf + 2.0)} : {})});
    } else if (v.why === 'off') {
      if (e.arr === 'flags') camWiden(v.tm);
      else if (v.box && v.box[2] > 0 && v.box[0] < 1920 && v.box[3] > 0 && v.box[1] < 1080) fixOff({...v, t0: v.tm});
    }
  }
  // HIDDEN (audit "smothered"): an element kept under a higher one for most of its life. Per hiding element:
  // 1. a date card takes the other top corner; 2. a billboard / free label steps aside just enough to clear
  // everything it hides (and stays there); 3. otherwise each hidden element moves (free position, other marker
  // side, other inner point of its region / country) or, last resort, gives way in time.
  type BB = BX.SBox;
  const bb = (a: number[]): BB => BX.B(a[0], a[1], a[2], a[3]);
  const fixed = (e: {arr: string; key: string}, f: string) => !!P[`${e.arr}:${e.key}`]?.set?.[f];
  const movable = (e: {arr: string; el: any}) => e.arr === 'banners' || e.arr === 'icons' || (e.arr === 'labels' && Array.isArray(e.el.at));
  const SF = {x0: 96, y0: 58, x1: 1824, y1: 1022};
  const clearShift = (mv: BB, keep: BB, lim: number, m = 36): [number, number] | null => {
    const c: [number, number][] = [[keep.x1 + m - mv.x0, 0], [keep.x0 - m - mv.x1, 0], [0, keep.y1 + m - mv.y0], [0, keep.y0 - m - mv.y1]];
    const ok = c.filter(([dx, dy]) => Math.hypot(dx, dy) <= lim && mv.x0 + dx >= SF.x0 && mv.x1 + dx <= SF.x1 && mv.y0 + dy >= SF.y0 && mv.y1 + dy <= SF.y1);
    ok.sort((p, q) => Math.hypot(p[0], p[1]) - Math.hypot(q[0], q[1]));
    return ok[0] ?? null;
  };
  const dotOf = (e: {el: any}, b: BB) => {                                   // a marker's dot is part of what must stay clear
    const sd = e.el.side ?? 'r';
    return {x: sd === 'l' ? b.x1 + 14 : sd === 'r' ? b.x0 - (e.el.label || e.el.sub ? 14 : 12) : (b.x0 + b.x1) / 2,
      y: sd === 't' ? b.y0 + 54 : sd === 'b' ? b.y0 - 12 : b.y0 + (e.el.label || e.el.sub ? 14 : 11)};
  };
  const keepBox = (e: {arr: string; el: any}, b: BB): BB => {
    if (e.arr !== 'markers') return b;
    const p = dotOf(e, b);
    return BX.B(Math.min(b.x0, p.x - 12), Math.min(b.y0, p.y - 12), Math.max(b.x1, p.x + 12), Math.max(b.y1, p.y + 12));
  };
  const giveWay = (lo: {arr: string; key: string; el: any}, t0: number, t1: number) => {
    const el = lo.el, from = el.from ?? el.t, to = el.to;
    if (t0 - from >= 1.5) set(lo, {to: r3(t0 - 0.1)});
    else if (to - t1 >= 1.5) set(lo, el.t !== undefined ? {t: r3(t1 + 0.2)} : {from: r3(t1 + 0.2)});
    else set(lo, {to: r3(from + 0.02)});
  };
  const groups = new Map<string, any[]>();
  for (const v of audit.smothered ?? []) (groups.get(v.a) ?? groups.set(v.a, []).get(v.a)!).push(v);
  for (const [hid, vs] of groups) {
    const v0 = vs[0], hi = elOf(hid, v0.tm), A = bb(v0.boxA);
    const los = vs.map((v) => ({v, e: elOf(v.b, v.tm)})).filter((x) => x.e) as {v: any; e: {arr: string; key: string; el: any}}[];
    if (!los.length) continue;
    if (hi && hi.arr === 'cards' && hi.el.kind === 'date' && !fixed(hi, '_posFixed')) { set(hi, {pos: hi.el.pos === 'tr' ? 'tl' : 'tr', _posFixed: true}); continue; }
    if (hi && movable(hi) && !fixed(hi, '_keep')) {
      // one shift, the same direction for every element it hides (each judged at its own moment), inside the frame
      let best: [number, number] | null = null, bm = Infinity;
      for (const [ux, uy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as [number, number][]) {
        let need = 0;
        for (const x of los) {
          const Ai = bb(x.v.boxA), K = keepBox(x.e, bb(x.v.boxB)), m = 36;
          need = Math.max(need, ux > 0 ? K.x1 + m - Ai.x0 : ux < 0 ? Ai.x1 - (K.x0 - m) : uy > 0 ? K.y1 + m - Ai.y0 : Ai.y1 - (K.y0 - m));
        }
        if (need <= 0 || need > 300) continue;
        const inside = los.every((x) => { const Ai = bb(x.v.boxA);
          return Ai.x0 + ux * need >= SF.x0 && Ai.x1 + ux * need <= SF.x1 && Ai.y0 + uy * need >= SF.y0 && Ai.y1 + uy * need <= SF.y1; });
        if (inside && need < bm) { bm = need; best = [ux * need, uy * need]; }
      }
      if (best && moveAt(hi, v0.tm, best[0], best[1])) { set(hi, {_keep: true}); continue; }
    }
    for (const {v, e} of los) {
      const Bv = bb(v.boxB);
      if (movable(e) && !fixed(e, '_keep')) {
        const sh = clearShift(Bv, A, 300);
        if (sh && moveAt(e, v.tm, sh[0], sh[1])) { set(e, {_keep: true}); continue; }
      }
      if (e.arr === 'markers' && (e.el.label || e.el.sub) && !fixed(e, '_fixedSide')) {
        const p = dotOf(e, Bv);
        if (!(p.x > A.x0 - 8 && p.x < A.x1 + 8 && p.y > A.y0 - 8 && p.y < A.y1 + 8)) {
          const side = (A.x0 + A.x1) / 2 > p.x ? 'l' : 'r';
          if (side !== (e.el.side ?? 'r')) { set(e, {side, _fixedSide: true}); continue; }
        }
      }
      const c = d.path.at(v.tm);
      if (e.arr === 'labels' && typeof e.el.at === 'string' && !fixed(e, '_keep')) {
        const W = Bv.x1 - Bv.x0, H = Bv.y1 - Bv.y0, fs = H / (e.el.sub ? 1.75 : 1.05);
        const pt = innerPoint(e.el.at, c, W / 2 + 12, 30, 40, {box: A, rel: [-W / 2, -0.45 * fs, W / 2, H - 0.45 * fs]});
        if (pt) { set(e, {at: lonlat(pt[0], pt[1]), _keep: true}); continue; }
      }
      if (e.arr === 'flags' && !e.el.at) {
        const W = Bv.x1 - Bv.x0, H = Bv.y1 - Bv.y0;
        const pt = innerPoint('rep:' + e.el.iso, c, 70, 110, e.el.date ? 60 : 30, {box: A, rel: [-3, -(H - 4), W - 3, 4]});
        if (pt) { set(e, {at: lonlat(pt[0], pt[1])}); continue; }
      }
      giveWay(e, v.t0, v.t1);
    }
  }
  for (const v of audit.overlaps ?? []) {
    const lo = elOf(v.b, v.t0), hi = elOf(v.a, v.t0);
    if (!lo) continue;
    const el = lo.el;
    if (lo.arr === 'cards' && el.kind === 'date') { set(lo, {pos: el.pos === 'tr' ? 'tl' : 'tr', _posFixed: true}); continue; }
    if (lo.arr === 'numerals') { set(lo, {y: (el.y ?? 700) === 700 ? 250 : 700}); continue; }
    if ((lo.arr === 'docs' || lo.arr === 'cutouts') && !(P[`${lo.arr}:${lo.key}`]?.set?.side)) { set(lo, {side: el.side === 'r' ? 'l' : 'r'}); continue; }
    if (lo.arr === 'markers' && !(P[`${lo.arr}:${lo.key}`]?.set?._fixedSide)) { set(lo, {side: el.side === 'r' ? 'l' : 'r', _fixedSide: true}); continue; }
    if ((lo.arr === 'banners' || lo.arr === 'icons' || (lo.arr === 'labels' && Array.isArray(el.at))) && hi && hi.el.at) {
      const c = d.path.at(v.t0 + 0.1);
      const wa = Array.isArray(hi.el.at) ? px(hi.el.at[0], hi.el.at[1]) : PATHS[hi.el.at]?.label;
      const wb = Array.isArray(el.at) ? px(el.at[0], el.at[1]) : PATHS[el.at]?.label;
      if (wa && wb) {
        const qa = scr(c, wa as [number, number]), qb = scr(c, wb as [number, number]);
        const ang = Math.atan2(qb.y - qa.y, qb.x - qa.x), dist = Math.sqrt(v.worst) + 40;
        const dx = Math.cos(ang) * dist, dy = Math.sin(ang) * dist, B0 = v.boxB ? bb(v.boxB) : null;
        // the step away must keep the element inside the title-safe frame, or the fitting pulls it back on the next pass
        const fits = !B0 || (B0.x0 + dx >= SF.x0 && B0.x1 + dx <= SF.x1 && B0.y0 + dy >= SF.y0 && B0.y1 + dy <= SF.y1);
        if (fits && moveAt(lo, v.t0 + 0.1, dx, dy)) continue;
      }
    }
    // a date card above a map element takes the other top corner; a free element steps aside (boxes from the audit)
    if (hi && hi.arr === 'cards' && hi.el.kind === 'date' && !fixed(hi, '_posFixed')) { set(hi, {pos: hi.el.pos === 'tr' ? 'tl' : 'tr', _posFixed: true}); continue; }
    if (movable(lo) && !fixed(lo, '_keep') && v.boxA && v.boxB) {
      const sh = clearShift(bb(v.boxB), bb(v.boxA), 300);
      if (sh && moveAt(lo, v.tm ?? v.t0, sh[0], sh[1])) { set(lo, {_keep: true}); continue; }
    }
    // last resort: the lower element gives way in time
    const from = el.from ?? el.t, to = el.to;
    if (v.t0 - from >= 1.5) set(lo, {to: r3(v.t0 - 0.1)});
    else if (to - v.t1 >= 1.5) set(lo, el.t !== undefined ? {t: r3(v.t1 + 0.2)} : {from: r3(v.t1 + 0.2)});
    else set(lo, {to: r3(from + 0.02)});
  }
  return P;
}
