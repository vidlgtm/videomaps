// FACTORY quality audit of the whole film (machine-readable for the director's second pass + human summary):
//  * overlaps that stay BOTH VISIBLE after the renderer's declutter (same rules as tools/overlaps.ts)
//  * OFF-SCREEN: a map text/billboard CUT by the frame edge (partly seen) while visible and the camera is settled (new gate)
//  * SAFE: inside the frame but outside the 96 px title-safe area for more than 1 s (warning)
//  * HIDDEN: a map element the declutter keeps under a higher-priority one for most of its life (the viewer never
//    reads it and it flickers in/out at its edges) -> problem, the director moves one of the two
//  * CLIP LABELS: a 3D label track must be bound to exactly the clip it was made for (never to a document clip)
//  * UNSEEN: a story element (banner, icon, flag drop, city marker, place label) that the viewer does not really see
//    for enough of its time: outside the frame or cut by it, kept hidden by the declutter, or under a clip
//    (full-frame clip, or a 3D overlay that dims the map). "Entirely outside the frame" is NOT fine for these.
// usage: npx tsx tools/audit.ts out/audit.json   -> exit code 0 always; the workflow decides from the JSON
import * as fs from 'fs';
import {frameLayout, inter, covered, Item} from '../src/lib/layout';
import {CLIPS, FLAGS, FLAG_HIDE, MARKERS, LABELS} from '../src/script';
import {BANNERS, ICONS} from '../src/v2';
import {env} from '../src/lib/anim';
import caucL from '../src/data/caucasus_labels.json';
import clipLabels from '../src/data/clip_labels.json';
import {cameraAt} from '../src/lib/camera';
import {project} from '../src/lib/proj';
import {TOTAL} from '../src/lib/cues';

const OUT = process.argv[2] ?? 'out/audit.json';
const N = Math.ceil(TOTAL * 30), STEP = 2, SAFE = 96;
const MAPKINDS = new Set(['label', 'marker', 'flag', 'banner', 'icon']);
const ignore = (a: Item, b: Item) => {
  if (a.kind === 'name' || b.kind === 'name') return true;
  if (a.id.replace(/^\w+:/, '') === b.id.replace(/^\w+:/, '') && a.kind === b.kind) return true;
  if (a.prio === 100 && b.prio === 100) {
    const k = [a.kind, b.kind];                     // a 3D doll over a card or a list is a real overlap (end card / credits excepted)
    if (k.includes('doll')) return k.includes('end') || k.includes('credits') || (a.kind === 'doll' && b.kind === 'doll');
    return a.kind === 'end' || b.kind === 'end';
  }
  return false;
};
/** camera speed at t in screen px/s of the frame centre's map point */
const speed = (t: number) => {
  const a = cameraAt(t), b = cameraAt(t + 0.1);
  const q = project(b, a.x, a.y);
  return Math.hypot(q.x - 960, q.y - 540) / 0.1 + Math.abs(Math.log(b.zoom / a.zoom)) * 4000;
};
type Iv = {a: string; b?: string; ka: string; kb?: string; f0: number; f1: number; worst: number; box?: number[]; boxA?: number[]; boxB?: number[]; fw?: number};
const groups: Record<string, Map<string, Iv>> = {overlap: new Map(), off: new Map(), safe: new Map()};
const done: Record<string, Iv[]> = {overlap: [], off: [], safe: []};
const touch = (g: string, key: string, f: number, mk: () => Iv, worst: number, bx?: {a: number[]; b: number[]}) => {
  const cur = groups[g].get(key);
  if (cur && cur.f1 >= f - STEP * 2) {
    cur.f1 = f;
    if (bx && worst > cur.worst) { cur.boxA = bx.a; cur.boxB = bx.b; cur.fw = f; }
    cur.worst = Math.max(cur.worst, worst); return;
  }
  if (cur) done[g].push(cur);
  const n = mk(); n.f0 = f; n.f1 = f; n.worst = worst;
  if (bx) { n.boxA = bx.a; n.boxB = bx.b; n.fw = f; }
  groups[g].set(key, n);
};
type Snap = {f: number; hi: string; kh: string; a: number[]; b: number[]};
type Life = {id: string; kind: string; last: number; alive: number; hid: number; by: Map<string, number>; snaps: Snap[]};
const life = new Map<string, Life>();
const smothered: any[] = [];
const endLife = (r: Life) => {
  // >= 1 s hidden and at least half of its life; a billboard (banner / icon: a picture tied to the narration) already
  // when a quarter of its life is lost
  const part = r.kind === 'banner' || r.kind === 'icon' ? 0.25 : 0.5;
  if (r.alive < 30 || r.hid < 30 || r.hid < part * r.alive) return;
  const top = [...r.by.entries()].sort((x, y) => y[1] - x[1])[0];
  if (!top) return;
  const sn = r.snaps.filter((x) => x.hi === top[0]), m = sn[Math.floor(sn.length / 2)];
  smothered.push({a: top[0], b: r.id, ka: m.kh, kb: r.kind, f0: sn[0].f, f1: sn[sn.length - 1].f, tm: +(m.f / 30).toFixed(2),
    t0: +(sn[0].f / 30).toFixed(2), t1: +(sn[sn.length - 1].f / 30).toFixed(2),
    hidden: +(r.hid / 30).toFixed(1), alive: +(r.alive / 30).toFixed(1), boxA: m.a.map(Math.round), boxB: m.b.map(Math.round)});
};
for (let f = 0; f < N; f += STEP) {
  const {L, vis} = frameLayout(f);
  if (L.full) continue;
  const t = f / 30;
  for (const x of L.items) {
    if (!MAPKINDS.has(x.kind) || x.o < 0.5) continue;
    let r = life.get(x.id);
    if (r && f - r.last > 30) { endLife(r); r = undefined; }
    if (!r) { r = {id: x.id, kind: x.kind, last: f, alive: 0, hid: 0, by: new Map(), snaps: []}; life.set(x.id, r); }
    r.last = f; r.alive += STEP;
    if (vis.get(x.id)) continue;
    r.hid += STEP;
    let best: Item | null = null, bi = 0;
    for (const p of L.items) {
      if (p.prio <= x.prio || p.o <= 0.25 || !vis.get(p.id)) continue;
      const I = inter(x, p);
      if (I > bi && covered(x, p)) { bi = I; best = p; }
    }
    if (best) {
      r.by.set(best.id, (r.by.get(best.id) ?? 0) + STEP);
      r.snaps.push({f, hi: best.id, kh: best.kind, a: [best.x0, best.y0, best.x1, best.y1], b: [x.x0, x.y0, x.x1, x.y1]});
    }
  }
  const it = L.items.filter((x) => x.o > 0.3);
  for (let i = 0; i < it.length; i++) for (let j = i + 1; j < it.length; j++) {
    const a = it[i], b = it[j];
    if (ignore(a, b)) continue;
    const I = inter(a, b);
    if (I < 150) continue;
    const [p, q] = a.prio >= b.prio ? [a, b] : [b, a];
    if (!vis.get(q.id)) continue;                          // declutter hides the lower one: fine
    touch('overlap', p.id + ' x ' + q.id, f, () => ({a: p.id, b: q.id, ka: p.kind, kb: q.kind, f0: f, f1: f, worst: 0}), I,
      {a: [p.x0, p.y0, p.x1, p.y1].map(Math.round), b: [q.x0, q.y0, q.x1, q.y1].map(Math.round)});
  }
  const moving = speed(t) > 160;
  for (const x of it) {
    if (!MAPKINDS.has(x.kind) || x.o < 0.5 || !vis.get(x.id)) continue;
    const out = Math.max(0 - x.x0, x.x1 - 1920, 0 - x.y0, x.y1 - 1080);
    const visW = Math.min(x.x1, 1920) - Math.max(x.x0, 0), visH = Math.min(x.y1, 1080) - Math.max(x.y0, 0);
    if (visW < 10 || visH < 10) continue;                    // entirely outside the frame = not seen = fine
    if (out > 6 && !moving) touch('off', x.id, f, () => ({a: x.id, ka: x.kind, f0: f, f1: f, worst: 0, box: [x.x0, x.y0, x.x1, x.y1].map(Math.round)}), out);
    else {
      const s = Math.max(SAFE - x.x0, x.x1 - (1920 - SAFE), SAFE * 0.6 - x.y0, x.y1 - (1080 - SAFE * 0.6));
      if (s > 8 && !moving) touch('safe', x.id, f, () => ({a: x.id, ka: x.kind, f0: f, f1: f, worst: 0, box: [x.x0, x.y0, x.x1, x.y1].map(Math.round)}), s);
    }
  }
}
Object.keys(groups).forEach((g) => groups[g].forEach((v) => done[g].push(v)));
// ---- UNSEEN: frame by frame, how long each story element is really seen during its window
//  seen = drawn (opacity >= 0.5), kept by the declutter, >= 90 % of its box inside the frame, not under a clip
type Un = {id: string; kind: string; what: string; t0: number; t1: number; a0: number; a1: number; need: (A: number) => number;
  alive: number; seen: number; off: number; hid: number; clip: number; bad: number[]; by: Map<string, number>; box?: number[]};
const bill = (A: number) => Math.max(0.6 * A, Math.min(1.5, 0.8 * A));
const UN: Un[] = [];
const un = (id: string, kind: string, what: string, t0: number, t1: number, a0: number, a1: number, need: (A: number) => number) => {
  if (a1 - a0 >= 0.2) UN.push({id, kind, what, t0, t1, a0, a1, need, alive: 0, seen: 0, off: 0, hid: 0, clip: 0, bad: [], by: new Map()});
};
BANNERS.forEach((b: any, i: number) => un('banner:' + i, 'banner', `banner ${b.title}`, b.from, b.to, b.from + 0.5, b.to - 0.4, bill));
ICONS.forEach((b: any, i: number) => un('icon:' + i, 'icon', `icon ${b.name}`, b.from, b.to, b.from + 0.5, b.to - 0.4, bill));
MARKERS.forEach((m: any, i: number) => { if (!m.dot) un('mlab:' + i, 'marker', `marker ${m.label ?? m.city}`, m.from, m.to, m.from + 0.5, m.to - 0.4, (A) => Math.min(1.0, 0.6 * A)); });
LABELS.forEach((l: any, i: number) => { if (!l.italic) un('label:' + i, 'label', `label ${l.text}`, l.from, l.to, l.from + 0.5, l.to - 0.4, (A) => Math.min(1.2, 0.6 * A)); });
FLAGS.forEach((g: any) => {                                     // a flag is about its drop: the first 3 s count
  if (FLAG_HIDE.some(([a, b]) => g.t > a && g.t < b)) return;
  const end = Math.min(g.to ?? TOTAL, g.t + 3.0);
  un('flag:' + g.iso, 'flag', `flag ${g.iso}`, g.t, g.to ?? TOTAL, g.t + 0.3, end - (end < (g.to ?? TOTAL) ? 0 : 0.4), (A) => 0.6 * A);
});
const dimAt = (t: number) => CLIPS.filter((c: any) => c.kind === 'doll' || c.kind === 'manim').reduce((m: number, c: any) => Math.max(m, env(t, c.from, c.to, 0.6, 0.6)), 0);
for (let f = 0; f < N; f += STEP) {
  const t = f / 30, act = UN.filter((u) => t >= u.a0 && t <= u.a1);
  if (!act.length) continue;
  const {L, vis} = frameLayout(f);
  const cover = L.full || dimAt(t) >= 0.5;
  const byId = new Map(L.items.map((x) => [x.id, x]));
  for (const u of act) {
    u.alive += STEP;
    const x = byId.get(u.id);
    let bad = '';
    if (cover) bad = 'clip';
    else if (!x || x.o < 0.5) bad = 'off';
    else if (!vis.get(x.id)) {
      bad = 'hid';
      for (const p of L.items) if (p.prio > x.prio && vis.get(p.id) && p.o > 0.25 && covered(x, p)) { u.by.set(p.id, (u.by.get(p.id) ?? 0) + STEP); break; }
    } else {
      const w = Math.max(1, x.x1 - x.x0), h = Math.max(1, x.y1 - x.y0);
      const iw = Math.max(0, Math.min(x.x1, 1920) - Math.max(x.x0, 0)), ih = Math.max(0, Math.min(x.y1, 1080) - Math.max(x.y0, 0));
      if ((iw * ih) / (w * h) < 0.9) bad = 'off';
    }
    if (!bad) { u.seen += STEP; continue; }
    (u as any)[bad] += STEP; u.bad.push(t);
    if (x && !u.box) u.box = [x.x0, x.y0, x.x1, x.y1].map(Math.round);
  }
}
const mmss = (f: number) => { const s = f / 30; return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`; };
const keep = (g: string, min: number) => done[g].filter((v) => (v.f1 - v.f0) / 30 >= min).sort((x, y) => x.f0 - y.f0)
  .map((v) => ({...v, t0: +(v.f0 / 30).toFixed(2), t1: +(v.f1 / 30).toFixed(2), worst: Math.round(v.worst), ...(v.fw !== undefined ? {tm: +(v.fw / 30).toFixed(2)} : {})}));
life.forEach(endLife);
smothered.sort((x, y) => x.f0 - y.f0);
// every labelled clip has its own label track (data/clip_labels.json by labels file; the v5 track as fallback), the track
// covers every frame the clip shows, and one track belongs to one clip only
const cliplabels: {problem: string}[] = [];
const lc = CLIPS.filter((c: any) => c.labels), lsrc = [...new Set(lc.map((c) => c.src))];
const trackOf = (c: any) => (clipLabels as any)[c.labels] ?? (c.labels === 'caucasus_labels.json' ? caucL : null);
lc.forEach((c: any) => {
  const L: any = trackOf(c);
  if (!L || !Object.keys(L.tracks ?? {}).length) { cliplabels.push({problem: `label track ${c.labels} of ${c.src} is missing or empty`}); return; }
  const need = Math.max(...c.steps.map((s: any) => s.s1)) * (L.fps ?? 30);
  if ((L.frames ?? 0) < need - 1) cliplabels.push({problem: `label track ${c.labels} has ${L.frames} frames, ${c.src} shows ${Math.ceil(need)}`});
});
const bound = new Map<string, Set<string>>();
lc.forEach((c: any) => { if (!bound.has(c.labels)) bound.set(c.labels, new Set()); bound.get(c.labels)!.add(c.src); });
bound.forEach((srcs, lab) => { if (srcs.size > 1) cliplabels.push({problem: `label track ${lab} bound to ${srcs.size} different clips: ${[...srcs].join(', ')}`}); });
const smo = new Set(smothered.map((v) => v.b));                // hidden for long: the HIDDEN repair handles it
const unseen = UN.filter((u) => !smo.has(u.id) && u.seen / 30 < u.need(u.alive / 30) - 1e-6).map((u) => {
  const why = u.clip >= u.off && u.clip >= u.hid ? 'clip' : u.off >= u.hid ? 'off' : 'hidden';
  const tm = u.bad.length ? u.bad[Math.floor(u.bad.length / 2)] : (u.a0 + u.a1) / 2;
  const by = [...u.by.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  return {a: u.id, ka: u.kind, what: u.what, t0: +u.t0.toFixed(2), t1: +u.t1.toFixed(2), tm: +tm.toFixed(2), why, ...(by ? {by} : {}),
    seen: +(u.seen / 30).toFixed(1), alive: +(u.alive / 30).toFixed(1), need: +u.need(u.alive / 30).toFixed(1), ...(u.box ? {box: u.box} : {})};
});
const res = {overlaps: keep('overlap', 0.2), offscreen: keep('off', 0.4), unsafe: keep('safe', 1.0), smothered, cliplabels, unseen};
fs.writeFileSync(OUT, JSON.stringify(res, null, 1));
for (const v of res.overlaps) console.log(`OVERLAP  ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] x ${v.b} [${v.kb}]  ${v.worst}px2`);
for (const v of res.offscreen) console.log(`OFFSCREEN ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] out by ${v.worst}px  box ${v.box}`);
for (const v of res.smothered) console.log(`HIDDEN   ${mmss(v.f0)}-${mmss(v.f1)}  ${v.b} [${v.kb}] under ${v.a} [${v.ka}]  hidden ${v.hidden}s of ${v.alive}s`);
for (const v of res.cliplabels) console.log(`CLIPLABELS ${v.problem}`);
const why: Record<string, string> = {off: 'outside / cut by the frame', hidden: 'kept hidden', clip: 'under a clip'};
for (const v of res.unseen) console.log(`UNSEEN   ${mmss(v.t0 * 30)}-${mmss(v.t1 * 30)}  ${v.what} [${v.ka}] seen ${v.seen}s of ${v.alive}s (needs ${v.need}s): ${why[v.why]}${v.by ? ' under ' + v.by : ''}`);
console.log(`3D label track on: ${lsrc.join(', ') || 'no clip'}`);
for (const v of res.unsafe) console.log(`unsafe   ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] ${v.worst}px into the margin`);
console.log(`AUDIT overlaps ${res.overlaps.length} · offscreen ${res.offscreen.length} · hidden ${res.smothered.length} · clip labels ${res.cliplabels.length} · unseen ${res.unseen.length} · outside title-safe ${res.unsafe.length}`);
