// Camera: an exact copy of the renderer's camera path (engine src/lib/camera.ts) + the planner that turns the brain's
// "go" beats into keyframes (framing that fits the places, tilt by distance, eased moves, wide chapter openings,
// no view held over 10 s, no repeated framing within 60 s).
import {px, project, meridian, PERSP, KM_PER_PX, WORLD_W, WORLD_H, CamState} from '../../engine/src/lib/proj';
import {clamp, lerp, ease, r2, r3} from './util';
import {Box, lonlat} from './geo';

export type CamKey = {t: number; lon?: number; lat?: number; x?: number; y?: number; w: number; tilt?: number; rotK?: number; dur?: number;
  src?: string; kind?: string};
export type {CamState};
export function keyState(k: CamKey): CamState {
  const [x, y] = k.x !== undefined ? [k.x, k.y as number] : px(k.lon as number, k.lat as number);
  const zoom = 1920 / (k.w / KM_PER_PX);
  const rot = k.lon !== undefined ? (k.rotK ?? 0.72) * meridian(k.lon) : 0;
  return {x, y, zoom, tilt: k.tilt ?? 0, rot};
}
export function unproject(c: CamState, sx: number, sy: number): [number, number] {
  const D = Math.PI / 180, r = c.rot * D, tl = c.tilt * D, a = sy - 540;
  const Y1 = (a * PERSP) / (PERSP * Math.cos(tl) + a * Math.sin(tl));
  const k = PERSP / (PERSP - Y1 * Math.sin(tl));
  const X1 = (sx - 960) / k;
  const X0 = X1 * Math.cos(r) + Y1 * Math.sin(r), Y0 = -X1 * Math.sin(r) + Y1 * Math.cos(r);
  return [X0 / c.zoom + c.x, Y0 / c.zoom + c.y];
}
function clampCam(c: CamState): CamState {
  let s = {...c};
  const M = 6;
  for (let it = 0; it < 6; it++) {
    const pts = [[-M, -M], [1920 + M, -M], [-M, 1080 + M], [1920 + M, 1080 + M], [960, -M], [960, 1080 + M], [-M, 540], [1920 + M, 540]]
      .map(([x, y]) => unproject(s, x, y));
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const spanX = maxX - minX, spanY = maxY - minY;
    if (spanX > WORLD_W || spanY > WORLD_H) { s = {...s, zoom: s.zoom * Math.max(spanX / WORLD_W, spanY / WORLD_H) * 1.01}; continue; }
    let dx = 0, dy = 0;
    if (minX < 0) dx = -minX; else if (maxX > WORLD_W) dx = WORLD_W - maxX;
    if (minY < 0) dy = -minY; else if (maxY > WORLD_H) dy = WORLD_H - maxY;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) break;
    s = {...s, x: s.x + dx, y: s.y + dy};
  }
  return s;
}
/** camera path of a key list - same maths as the renderer */
export class CamPath {
  keys: CamKey[]; st: CamState[]; from: (CamState | null)[];
  constructor(keys: CamKey[]) {
    this.keys = [...keys].sort((a, b) => a.t - b.t);
    this.st = this.keys.map(keyState);
    this.from = this.keys.map(() => null);
    for (let i = 1; i < this.keys.length; i++) this.from[i] = this.raw(this.keys[i].t, i - 1);
  }
  private raw(t: number, upto: number): CamState {
    let i = upto;
    while (i > 0 && this.keys[i].t > t) i--;
    const k = this.keys[i], to = this.st[i], dur = k.dur ?? 2.2;
    const drift = (s: CamState, since: number) => ({...s, zoom: s.zoom * (1 + Math.min(0.07, 0.0045 * Math.max(0, since)))});
    if (i === 0) return drift(to, t - k.t);
    const from = this.from[i] ?? this.raw(k.t, i - 1);
    const p = clamp((t - k.t) / dur);
    if (p >= 1) return drift(to, t - k.t - dur);
    const e = ease(p);
    let zoom = Math.exp(lerp(Math.log(from.zoom), Math.log(to.zoom), e));
    const dist = Math.hypot(to.x - from.x, to.y - from.y) * Math.min(from.zoom, to.zoom);
    if (dist > 1500) zoom *= 1 - 0.32 * Math.sin(Math.PI * e) * clamp((dist - 1500) / 3000);
    return {x: lerp(from.x, to.x, e), y: lerp(from.y, to.y, e), zoom, tilt: lerp(from.tilt, to.tilt, e), rot: lerp(from.rot, to.rot, e)};
  }
  at(t: number): CamState { return clampCam(this.raw(t, this.keys.length - 1)); }
  /** index of the key whose move/hold covers t */
  keyAt(t: number) { let i = this.keys.length - 1; while (i > 0 && this.keys[i].t > t) i--; return i; }
  moving(t: number) { const i = this.keyAt(t), k = this.keys[i]; return i > 0 && t < k.t + (k.dur ?? 2.2); }
}
export const scr = (c: CamState, p: [number, number]) => project(c, p[0], p[1]);

// ---------------- framing ----------------
const TILT: [number, number][] = [[620, 36], [1250, 32], [2000, 29], [2700, 26], [3500, 22], [5000, 15], [6200, 10], [9300, 4]];
export function tiltFor(w: number) {
  const L = Math.log2(w);
  if (w <= TILT[0][0]) return TILT[0][1];
  for (let i = 1; i < TILT.length; i++) if (w <= TILT[i][0]) {
    const [w0, a] = TILT[i - 1], [w1, b] = TILT[i];
    return lerp(a, b, (L - Math.log2(w0)) / (Math.log2(w1) - Math.log2(w0)));
  }
  return TILT[TILT.length - 1][1];
}
export const W_MIN = 480, W_MAX = 9800;
const FRAC: Record<string, number> = {close: 0.85, region: 0.75, context: 0.45, auto: 0.72};
const W_FLOOR: Record<string, number> = {close: 480, region: 800, context: 1300, auto: 900};
const POINT_W: Record<string, number> = {close: 900, region: 1400, context: 2500, auto: 1250};
export const SAFE = {x0: 96, y0: 96, x1: 1824, y1: 984};
/** projected bounds of a world box at a camera state */
export function projBounds(c: CamState, b: Box | [number, number][]) {
  const pts: [number, number][] = [];
  if (Array.isArray(b[0])) pts.push(...(b as [number, number][]));
  else { const x = b as Box; for (let i = 0; i <= 4; i++) for (let j = 0; j <= 4; j++) if (i === 0 || i === 4 || j === 0 || j === 4) pts.push([lerp(x[0], x[2], i / 4), lerp(x[1], x[3], j / 4)]); }
  const q = pts.map((p) => project(c, p[0], p[1]));
  return {x0: Math.min(...q.map((p) => p.x)), x1: Math.max(...q.map((p) => p.x)), y0: Math.min(...q.map((p) => p.y)), y1: Math.max(...q.map((p) => p.y))};
}
/** key that shows world box b at fraction f of the title-safe frame (lon/lat key with local-north rotation) */
/** key that shows the places (outline points, or a box) at fraction f of the title-safe frame (lon/lat key, local north) */
export function frameBox(b: Box | [number, number][], kind = 'auto', opts: {tiltAdd?: number; wMul?: number} = {}): CamKey {
  const f = FRAC[kind] ?? 0.7;
  const P = Array.isArray(b[0]) ? (b as [number, number][]) : null;
  const bb: Box = P ? [Math.min(...P.map((p) => p[0])), Math.min(...P.map((p) => p[1])), Math.max(...P.map((p) => p[0])), Math.max(...P.map((p) => p[1]))] : (b as Box);
  let cx = (bb[0] + bb[2]) / 2, cy = (bb[1] + bb[3]) / 2, w = 2000;
  const fw = (SAFE.x1 - SAFE.x0) * f, fh = (SAFE.y1 - SAFE.y0) * f;
  for (let it = 0; it < 4; it++) {
    const ll = lonlat(cx, cy), tilt = clamp(tiltFor(w) + (opts.tiltAdd ?? 0), 0, 40);
    let lo = Math.log(W_MIN), hi = Math.log(W_MAX);
    for (let s = 0; s < 26; s++) {
      const mid = (lo + hi) / 2;
      const c = keyState({t: 0, lon: ll[0], lat: ll[1], w: Math.exp(mid), tilt});
      const pb = projBounds(c, b);
      if (pb.x1 - pb.x0 <= fw && pb.y1 - pb.y0 <= fh) hi = mid; else lo = mid;
    }
    w = Math.exp(hi);
    const c = keyState({t: 0, lon: ll[0], lat: ll[1], w, tilt});
    const pb = projBounds(c, b);
    const mx = (pb.x0 + pb.x1) / 2, my = (pb.y0 + pb.y1) / 2 - 20;          // the places sit a touch below centre: billboards rise above them
    const [nx, ny] = unproject(c, 960 + (mx - 960), 540 + (my - 540));
    cx += (nx - c.x) * 0.9; cy += (ny - c.y) * 0.9;
  }
  w = clamp(Math.max(w, W_FLOOR[kind] ?? W_MIN) * (opts.wMul ?? 1), W_MIN, W_MAX);
  // near the edge of the basemap the renderer would push the view sideways (clampCam) and the places would sit off-centre:
  // come closer instead, as long as the places still fit (<= 95 % of the title-safe frame)
  const ll = lonlat(cx, cy);
  for (let it = 0; it < 10; it++) {
    const k: CamKey = {t: 0, lon: ll[0], lat: ll[1], w, tilt: clamp(tiltFor(w) + (opts.tiltAdd ?? 0), 0, 40)};
    const c = keyState(k), v = viewBox(c, 0);
    const over = Math.max(-v[0], v[2] - WORLD_W, -v[1], v[3] - WORLD_H, 0);
    if (over < 8) break;
    const w2 = w * 0.92, c2 = keyState({...k, w: w2, tilt: clamp(tiltFor(w2) + (opts.tiltAdd ?? 0), 0, 40)}), pb = projBounds(c2, b);
    if (pb.x1 - pb.x0 > (SAFE.x1 - SAFE.x0) * 0.95 || pb.y1 - pb.y0 > (SAFE.y1 - SAFE.y0) * 0.95 || w2 < W_MIN) break;
    w = w2;
  }
  return {t: 0, lon: r3(ll[0]), lat: r3(ll[1]), w: Math.round(w), tilt: r2(clamp(tiltFor(w) + (opts.tiltAdd ?? 0), 0, 40))};
}
export function framePoint(p: [number, number], kind = 'auto'): CamKey {
  const w = POINT_W[kind] ?? 1250, ll = lonlat(p[0], p[1]);
  // centre slightly south of the point so a banner/flag standing on it has room above
  const c = keyState({t: 0, lon: ll[0], lat: ll[1], w, tilt: tiltFor(w)});
  const [nx, ny] = unproject(c, 960, 540 - 90);
  const l2 = lonlat(nx, ny);
  return {t: 0, lon: r3(l2[0]), lat: r3(l2[1]), w, tilt: r2(tiltFor(w))};
}
/** whole film area, canvas-aligned (north up, no rotation) like our overview shots */
export function overviewKey(area: Box, variant = 0): CamKey {
  const V = [{tilt: 0, w: 1.0, dx: 0, dy: 0}, {tilt: 4, w: 0.97, dx: -120, dy: 30}, {tilt: 7, w: 0.95, dx: 160, dy: -10}, {tilt: 2, w: 1.0, dx: 60, dy: 40},
    {tilt: 5, w: 0.98, dx: -60, dy: 10}][variant % 5];
  const cx = (area[0] + area[2]) / 2, cy = (area[1] + area[3]) / 2;
  const wpx = Math.max(area[2] - area[0], (area[3] - area[1]) * 16 / 9) * 1.1;
  const w = clamp(wpx * KM_PER_PX * V.w, 2000, W_MAX);
  return {t: 0, x: Math.round(cx + V.dx), y: Math.round(cy - 110 + V.dy), w: Math.round(w), tilt: V.tilt, rotK: 0};
}
/** similarity of two keys (0 = same framing) */
export function keyDistance(a: CamKey, b: CamKey) {
  const sa = keyState(a), sb = keyState(b);
  const d = Math.hypot(sa.x - sb.x, sa.y - sb.y) * Math.min(sa.zoom, sb.zoom) / 1920;
  return d + Math.abs(Math.log(a.w / b.w)) + Math.abs((a.tilt ?? 0) - (b.tilt ?? 0)) / 40;
}
/** world points visible inside the title-safe frame at camera state c */
export const inSafe = (c: CamState, p: [number, number], m = 0) => { const q = project(c, p[0], p[1]); return q.x > SAFE.x0 + m && q.x < SAFE.x1 - m && q.y > SAFE.y0 + m && q.y < SAFE.y1 - m; };
/** the world box currently framed by c (approx, for "zoom out to include") */
export function viewBox(c: CamState, m = -1): Box {
  const a = m < 0 ? SAFE : {x0: m, y0: m, x1: 1920 - m, y1: 1080 - m};
  const pts = [[a.x0, a.y0], [a.x1, a.y0], [a.x0, a.y1], [a.x1, a.y1], [960, a.y0], [960, a.y1], [a.x0, 540], [a.x1, 540]].map(([x, y]) => unproject(c, x, y));
  return [Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1]))];
}
