// Camera path (pure TS): keyframes from script.ts -> eased camera state at time t, clamped to the basemap.
import {px, KM_PER_PX, WORLD_W, WORLD_H, PERSP, meridian, CamState} from './proj';
import {clamp, ease, lerp} from './anim';
import {CAMERA, CamKey} from '../script';

function keyState(k: CamKey): CamState {
  const [x, y] = k.x !== undefined ? [k.x, k.y as number] : px(k.lon as number, k.lat as number);
  const zoom = 1920 / (k.w / KM_PER_PX);
  const rot = k.lon !== undefined ? (k.rotK ?? 0.72) * meridian(k.lon) : 0;
  return {x, y, zoom, tilt: k.tilt ?? 0, rot};
}
const STATES = CAMERA.map(keyState);
function stateAt(t: number, upto = CAMERA.length - 1): CamState {
  let i = upto;
  while (i > 0 && CAMERA[i].t > t) i--;
  const k = CAMERA[i], to = STATES[i], dur = k.dur ?? 2.2;
  const drift = (s: CamState, since: number) => ({...s, zoom: s.zoom * (1 + Math.min(0.07, 0.0045 * Math.max(0, since)))});
  if (i === 0) return drift(to, t - k.t);
  const from = stateAt(k.t, i - 1);
  const p = clamp((t - k.t) / dur);
  if (p >= 1) return drift(to, t - k.t - dur);
  const e = ease(p);
  let zoom = Math.exp(lerp(Math.log(from.zoom), Math.log(to.zoom), e));
  const dist = Math.hypot(to.x - from.x, to.y - from.y) * Math.min(from.zoom, to.zoom);
  if (dist > 1500) zoom *= 1 - 0.32 * Math.sin(Math.PI * e) * clamp((dist - 1500) / 3000);
  return {x: lerp(from.x, to.x, e), y: lerp(from.y, to.y, e), zoom, tilt: lerp(from.tilt, to.tilt, e), rot: lerp(from.rot, to.rot, e)};
}
/** inverse of project(): screen px -> world px on the map plane */
export function unproject(c: CamState, sx: number, sy: number): [number, number] {
  const D = Math.PI / 180, r = c.rot * D, tl = c.tilt * D, a = sy - 540;
  const Y1 = (a * PERSP) / (PERSP * Math.cos(tl) + a * Math.sin(tl));
  const k = PERSP / (PERSP - Y1 * Math.sin(tl));
  const X1 = (sx - 960) / k;
  const X0 = X1 * Math.cos(r) + Y1 * Math.sin(r), Y0 = -X1 * Math.sin(r) + Y1 * Math.cos(r);
  return [X0 / c.zoom + c.x, Y0 / c.zoom + c.y];
}
/** keep the camera inside the basemap canvas: shift, and zoom in if the view is larger than the canvas */
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
export const cameraAt = (t: number) => clampCam(stateAt(t));
