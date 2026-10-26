// Word-accurate times from the voice timeline. The order gives EXACT words of the narration; the factory finds them.
import {fail} from './util';

export type Word = {w: string; n: string; c: number; k: number; t0: number; t1: number};
export type Timeline = {total: number; fps: number; chunks: {i: number; start: number; end: number}[]; words: Word[]};
const norm = (s: string) => s.toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]/g, '');

export class Cues {
  tl: Timeline; ids: string[];
  constructor(tl: Timeline, paragraphIds: string[]) {
    this.tl = tl; this.ids = paragraphIds;
    if (tl.chunks.length !== paragraphIds.length) fail(`timeline has ${tl.chunks.length} paragraphs but narration.json has ${paragraphIds.length}`);
  }
  idx(pid: string) { const i = this.ids.indexOf(pid); if (i < 0) fail(`unknown paragraph id "${pid}"`); return i; }
  start(c: number) { return this.tl.chunks[c].start; }
  end(c: number) { return this.tl.chunks[c].end; }
  get total() { return this.tl.total; }
  /** "words", "words#2" (2nd occurrence), "02:words" (other paragraph), "start", "end", "words@end" (end of the words) */
  resolve(c0: number, spec: string): {t: number; c: number; t1: number} {
    let s = spec.trim(), c = c0;
    const m = s.match(/^(\d{2}):(.*)$/);
    if (m) { c = this.idx(m[1]); s = m[2].trim(); }
    if (s === 'start') return {t: this.start(c), c, t1: this.start(c)};
    if (s === 'end') return {t: this.end(c), c, t1: this.end(c)};
    let edge: 'start' | 'end' = 'start';
    if (s.endsWith('@end')) { edge = 'end'; s = s.slice(0, -4).trim(); }
    let nth = 1;
    const h = s.match(/^(.*)#(\d+)$/);
    if (h) { s = h[1].trim(); nth = parseInt(h[2], 10); }
    const toks = s.split(/\s+/).map(norm).filter(Boolean);
    if (!toks.length) fail(`empty cue in paragraph ${this.ids[c]}`);
    const ws = this.tl.words.filter((w) => w.c === c);
    let count = 0;
    for (let i = 0; i + toks.length <= ws.length; i++) {
      if (toks.every((t, j) => ws[i + j].n === t)) {
        count++;
        if (count === nth) { const a = ws[i], b = ws[i + toks.length - 1]; return {t: edge === 'start' ? a.t0 : b.t1, c, t1: b.t1}; }
      }
    }
    const near = ws.filter((w) => w.n === toks[0]).map((w) => ws.slice(w.k, w.k + toks.length + 2).map((x) => x.w).join(' '));
    return fail(`cue not found in paragraph ${this.ids[c]}: "${spec}"` + (near.length ? ` - the narration has: ${near.map((x) => `"${x}"`).join(', ')}` : ' - the first word does not occur in this paragraph'));
  }
  /** speech activity windows (for music ducking etc.) */
  wordsIn(a: number, b: number) { return this.tl.words.filter((w) => w.t0 >= a && w.t1 <= b); }
}
