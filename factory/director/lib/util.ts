// small shared helpers of the automatic director
import * as fs from 'fs';
export const readJSON = (p: string) => JSON.parse(fs.readFileSync(p, 'utf8'));
export const exists = (p: string) => fs.existsSync(p);
export const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const r2 = (x: number) => Math.round(x * 100) / 100;
export const r3 = (x: number) => Math.round(x * 1000) / 1000;
export const arr = <T>(x: T | T[] | undefined | null): T[] => (x === undefined || x === null ? [] : Array.isArray(x) ? x : [x]);
/** cubic-bezier easing identical to remotion Easing.bezier (same solver: Newton + bisection) */
export function bezier(x1: number, y1: number, x2: number, y2: number) {
  const A = (a1: number, a2: number) => 1 - 3 * a2 + 3 * a1, B = (a1: number, a2: number) => 3 * a2 - 6 * a1, C = (a1: number) => 3 * a1;
  const calc = (t: number, a1: number, a2: number) => ((A(a1, a2) * t + B(a1, a2)) * t + C(a1)) * t;
  const slope = (t: number, a1: number, a2: number) => 3 * A(a1, a2) * t * t + 2 * B(a1, a2) * t + C(a1);
  const tFor = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) { const s = slope(t, x1, x2); if (Math.abs(s) < 1e-6) break; t -= (calc(t, x1, x2) - x) / s; }
    if (t < 0 || t > 1 || Math.abs(calc(t, x1, x2) - x) > 1e-5) {
      let lo = 0, hi = 1; t = x;
      for (let i = 0; i < 40; i++) { const v = calc(t, x1, x2); if (Math.abs(v - x) < 1e-7) break; if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; }
    }
    return t;
  };
  return (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : calc(tFor(x), y1, y2));
}
export const ease = bezier(0.45, 0, 0.2, 1);
export class DirectorError extends Error {}
export const fail = (msg: string): never => { throw new DirectorError(msg); };
/** deterministic small hash (stable variations without randomness) */
export const hash = (s: string) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
