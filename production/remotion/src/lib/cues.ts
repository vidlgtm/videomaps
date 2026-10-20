// Word-accurate cue times (seconds) from the forced alignment of the narration.
import tl from '../data/timeline.json';
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
type W = {w: string; n: string; c: number; k: number; t0: number; t1: number};
export const WORDS: W[] = (tl as any).words;
export const TOTAL: number = (tl as any).total;
export const CH = (tl as any).chunks as {i: number; start: number; end: number}[];
export const cs = (c: number) => CH[c].start;
export const ce = (c: number) => CH[c].end;
export function cue(c: number, phrase: string, edge: 'start' | 'end' = 'start', nth = 0): number {
  const toks = phrase.split(/\s+/).map(norm).filter(Boolean);
  const ws = WORDS.filter((w) => w.c === c);
  let count = 0;
  for (let i = 0; i + toks.length <= ws.length; i++) {
    if (toks.every((t, j) => ws[i + j].n === t)) {
      if (count === nth) return edge === 'start' ? ws[i].t0 : ws[i + toks.length - 1].t1;
      count++;
    }
  }
  throw new Error(`cue not found: [${c}] "${phrase}"`);
}
/** speech activity 0..1 at time t (for music ducking) */
export function speechAt(t: number): number {
  let lo = 0, hi = WORDS.length - 1;
  while (lo < hi) { const m = (lo + hi) >> 1; if (WORDS[m].t1 < t) lo = m + 1; else hi = m; }
  const w = WORDS[lo];
  if (!w) return 0;
  const prev = WORDS[lo - 1];
  const inside = t >= w.t0 - 0.25 && t <= w.t1 + 0.25;
  const gapSmall = prev && t > prev.t1 && t < w.t0 && w.t0 - prev.t1 < 0.9;
  return inside || gapSmall ? 1 : 0;
}
