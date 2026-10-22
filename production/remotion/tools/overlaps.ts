// Static overlap audit of the whole film: every pair of overlay elements whose boxes intersect (raw, before declutter),
// grouped into time intervals, plus what the renderer's declutter will do about it.
import {layoutAt, inter, frameLayout, Item} from '../src/lib/layout';
import {TOTAL} from '../src/lib/cues';

const N = Math.ceil(TOTAL * 30);
const STEP = 2;
type Iv = {a: string; b: string; ka: string; kb: string; f0: number; f1: number; maxI: number; hid: Set<string>};
const open = new Map<string, Iv>(), done: Iv[] = [];
const ignore = (a: Item, b: Item) => {
  if (a.kind === 'name' || b.kind === 'name') return true;                 // names are auto-placed, decluttered at render time
  if (a.id.replace(/^\w+:/, '') === b.id.replace(/^\w+:/, '') && a.kind === b.kind) return true;   // flag + its date, cut-out + its plate
  if (a.prio === 100 && b.prio === 100) {
    if ([a.kind, b.kind].includes('doll') && [a.kind, b.kind].includes('dollL')) return false;   // v5: the doll list vs the dolls
    return a.kind === 'doll' || b.kind === 'doll' || a.kind === 'end' || b.kind === 'end';
  }
  return false;
};
for (let f = 0; f < N; f += STEP) {
  const {L, vis} = frameLayout(f);
  if (L.full) continue;
  const it = L.items.filter((x) => x.o > 0.3);
  const seen = new Set<string>();
  for (let i = 0; i < it.length; i++) for (let j = i + 1; j < it.length; j++) {
    const a = it[i], b = it[j];
    if (ignore(a, b)) continue;
    const I = inter(a, b);
    if (I < 150) continue;
    const [p, q] = a.prio >= b.prio ? [a, b] : [b, a];
    const key = p.id + ' x ' + q.id;
    seen.add(key);
    const cur = open.get(key);
    if (cur && cur.f1 >= f - STEP * 2) { cur.f1 = f; cur.maxI = Math.max(cur.maxI, I); if (!vis.get(q.id)) cur.hid.add(q.id); }
    else { if (cur) done.push(cur); open.set(key, {a: p.id, b: q.id, ka: p.kind, kb: q.kind, f0: f, f1: f, maxI: I, hid: new Set(vis.get(q.id) ? [] : [q.id])}); }
  }
}
open.forEach((v) => done.push(v));
const mmss = (f: number) => { const s = f / 30; return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`; };
const rows = done.filter((v) => (v.f1 - v.f0) / 30 >= 0.2).sort((x, y) => x.f0 - y.f0);
for (const v of rows) {
  const fade = v.hid.size ? `-> ${[...v.hid].join(',')} fades` : '-> BOTH VISIBLE';
  console.log(`${mmss(v.f0)}-${mmss(v.f1)} (${((v.f1 - v.f0) / 30).toFixed(1)}s)  ${v.a} [${v.ka}]  x  ${v.b} [${v.kb}]  ${Math.round(v.maxI)}px2  ${fade}`);
}
console.log('intervals:', rows.length);
