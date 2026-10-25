// Second pass: the engine audit (tools/audit.ts: overlaps that stay visible, text cut by the frame) -> patches that
// the director applies on the next run (move a billboard/label inward, switch a side/corner, re-frame the shot,
// or as a last resort shorten the lower-priority element). Patches accumulate in <order>/out/patches.json.
import type {Director} from './plan';
import {px, lonlat, PATHS} from './geo';
import {unproject, scr} from './cam';
import {r3} from './util';

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
  const camShift = (t: number, dx: number, dy: number, wmul = 1) => {
    const i = d.path.keyAt(t), src = d.keys[i]?.src;
    if (!src || src.includes('/drift')) return;
    const q = P[src] ?? {}; P[src] = {...q, shift: [(q.shift?.[0] ?? 0) + dx, (q.shift?.[1] ?? 0) + dy], wmul: (q.wmul ?? 1) * wmul};
  };
  const moveAt = (e: {arr: string; key: string; el: any}, t: number, dx: number, dy: number) => {
    const c = d.path.at(t), at = e.el.at;
    const w = Array.isArray(at) ? px(at[0], at[1]) : PATHS[at]?.label;
    if (!w) return false;
    const q = scr(c, w as [number, number]), n = unproject(c, q.x + dx, q.y + dy);
    set(e, {at: lonlat(n[0], n[1])}); return true;
  };
  for (const v of audit.offscreen ?? []) {
    const e = elOf(v.a, v.t0); if (!e) continue;
    const [x0, y0, x1, y1] = v.box, m = 40;
    const dx = x0 < 0 ? -x0 + m : x1 > 1920 ? 1920 - x1 - m : 0, dy = y0 < 0 ? -y0 + m : y1 > 1080 ? 1080 - y1 - m : 0;
    if (e.arr === 'markers') set(e, {side: dx > 0 ? 'r' : dx < 0 ? 'l' : dy > 0 ? 'b' : 't', _fixedSide: true});
    else if (e.arr === 'banners' || e.arr === 'icons' || (e.arr === 'labels' && Array.isArray(e.el.at))) moveAt(e, v.t0 + 0.2, dx, dy);
    else camShift(v.t0, -dx, -dy, 1.04);
  }
  for (const v of audit.overlaps ?? []) {
    const lo = elOf(v.b, v.t0), hi = elOf(v.a, v.t0);
    if (!lo) continue;
    const el = lo.el;
    if (lo.arr === 'cards' && el.kind === 'date') { set(lo, {pos: el.pos === 'tr' ? 'tl' : 'tr'}); continue; }
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
        if (moveAt(lo, v.t0 + 0.1, Math.cos(ang) * dist, Math.sin(ang) * dist)) continue;
      }
    }
    // last resort: the lower element gives way in time
    const from = el.from ?? el.t, to = el.to;
    if (v.t0 - from >= 1.5) set(lo, {to: r3(v.t0 - 0.1)});
    else if (to - v.t1 >= 1.5) set(lo, el.t !== undefined ? {t: r3(v.t1 + 0.2)} : {from: r3(v.t1 + 0.2)});
    else set(lo, {to: r3(from + 0.02)});
  }
  return P;
}
