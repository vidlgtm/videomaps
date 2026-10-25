// FACTORY quality audit of the whole film (machine-readable for the director's second pass + human summary):
//  * overlaps that stay BOTH VISIBLE after the renderer's declutter (same rules as tools/overlaps.ts)
//  * OFF-SCREEN: a map text/billboard cut by the frame edge while visible and the camera is settled (new gate)
//  * SAFE: inside the frame but outside the 96 px title-safe area for more than 1 s (warning)
// usage: npx tsx tools/audit.ts out/audit.json   -> exit code 0 always; the workflow decides from the JSON
import * as fs from 'fs';
import {frameLayout, inter, Item} from '../src/lib/layout';
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
    if ([a.kind, b.kind].includes('doll') && [a.kind, b.kind].includes('dollL')) return false;
    return a.kind === 'doll' || b.kind === 'doll' || a.kind === 'end' || b.kind === 'end';
  }
  return false;
};
/** camera speed at t in screen px/s of the frame centre's map point */
const speed = (t: number) => {
  const a = cameraAt(t), b = cameraAt(t + 0.1);
  const q = project(b, a.x, a.y);
  return Math.hypot(q.x - 960, q.y - 540) / 0.1 + Math.abs(Math.log(b.zoom / a.zoom)) * 4000;
};
type Iv = {a: string; b?: string; ka: string; kb?: string; f0: number; f1: number; worst: number; box?: number[]};
const groups: Record<string, Map<string, Iv>> = {overlap: new Map(), off: new Map(), safe: new Map()};
const done: Record<string, Iv[]> = {overlap: [], off: [], safe: []};
const touch = (g: string, key: string, f: number, mk: () => Iv, worst: number) => {
  const cur = groups[g].get(key);
  if (cur && cur.f1 >= f - STEP * 2) { cur.f1 = f; cur.worst = Math.max(cur.worst, worst); return; }
  if (cur) done[g].push(cur);
  const n = mk(); n.f0 = f; n.f1 = f; n.worst = worst; groups[g].set(key, n);
};
for (let f = 0; f < N; f += STEP) {
  const {L, vis} = frameLayout(f);
  if (L.full) continue;
  const t = f / 30;
  const it = L.items.filter((x) => x.o > 0.3);
  for (let i = 0; i < it.length; i++) for (let j = i + 1; j < it.length; j++) {
    const a = it[i], b = it[j];
    if (ignore(a, b)) continue;
    const I = inter(a, b);
    if (I < 150) continue;
    const [p, q] = a.prio >= b.prio ? [a, b] : [b, a];
    if (!vis.get(q.id)) continue;                          // declutter hides the lower one: fine
    touch('overlap', p.id + ' x ' + q.id, f, () => ({a: p.id, b: q.id, ka: p.kind, kb: q.kind, f0: f, f1: f, worst: 0}), I);
  }
  const moving = speed(t) > 160;
  for (const x of it) {
    if (!MAPKINDS.has(x.kind) || x.o < 0.5 || !vis.get(x.id)) continue;
    const out = Math.max(0 - x.x0, x.x1 - 1920, 0 - x.y0, x.y1 - 1080);
    if (out > 6 && !moving) touch('off', x.id, f, () => ({a: x.id, ka: x.kind, f0: f, f1: f, worst: 0, box: [x.x0, x.y0, x.x1, x.y1].map(Math.round)}), out);
    else {
      const s = Math.max(SAFE - x.x0, x.x1 - (1920 - SAFE), SAFE * 0.6 - x.y0, x.y1 - (1080 - SAFE * 0.6));
      if (s > 8 && !moving) touch('safe', x.id, f, () => ({a: x.id, ka: x.kind, f0: f, f1: f, worst: 0, box: [x.x0, x.y0, x.x1, x.y1].map(Math.round)}), s);
    }
  }
}
Object.keys(groups).forEach((g) => groups[g].forEach((v) => done[g].push(v)));
const mmss = (f: number) => { const s = f / 30; return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`; };
const keep = (g: string, min: number) => done[g].filter((v) => (v.f1 - v.f0) / 30 >= min).sort((x, y) => x.f0 - y.f0)
  .map((v) => ({...v, t0: +(v.f0 / 30).toFixed(2), t1: +(v.f1 / 30).toFixed(2), worst: Math.round(v.worst)}));
const res = {overlaps: keep('overlap', 0.2), offscreen: keep('off', 0.4), unsafe: keep('safe', 1.0)};
fs.writeFileSync(OUT, JSON.stringify(res, null, 1));
for (const v of res.overlaps) console.log(`OVERLAP  ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] x ${v.b} [${v.kb}]  ${v.worst}px2`);
for (const v of res.offscreen) console.log(`OFFSCREEN ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] out by ${v.worst}px  box ${v.box}`);
for (const v of res.unsafe) console.log(`unsafe   ${mmss(v.f0)}-${mmss(v.f1)}  ${v.a} [${v.ka}] ${v.worst}px into the margin`);
console.log(`AUDIT overlaps ${res.overlaps.length} · offscreen ${res.offscreen.length} · outside title-safe ${res.unsafe.length}`);
