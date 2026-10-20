import {Easing, interpolate} from 'remotion';
export const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const ease = Easing.bezier(0.45, 0, 0.2, 1);
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
/** opacity envelope: fade in over fi after `from`, fade out over fo before `to` */
export function env(t: number, from: number, to = 1e9, fi = 0.6, fo = 0.6): number {
  if (t < from || t > to) return 0;
  const a = fi > 0 ? clamp((t - from) / fi) : 1;
  const b = fo > 0 ? clamp((to - t) / fo) : 1;
  return ease(Math.min(a, b));
}
export const prog = (t: number, from: number, dur: number) => clamp((t - from) / dur);
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export {interpolate};
