// Lambert Conformal Conic exactly as in geodata.py (sphere R=6371 km, lat1 45, lat2 62, lat0 55, lon0 90)
import geo from '../data/geo.json';
const G: any = geo;
const R = 6371000, D = Math.PI / 180;
const lat0 = 55 * D, lat1 = 45 * D;
export const LON0: number = G.lon0;
export const N: number = G.cone_n;
const F = (Math.cos(lat1) * Math.pow(Math.tan(Math.PI / 4 + lat1 / 2), N)) / N;
const rho = (latDeg: number) => (R * F) / Math.pow(Math.tan(Math.PI / 4 + (latDeg * D) / 2), N);
const rho0 = (R * F) / Math.pow(Math.tan(Math.PI / 4 + lat0 / 2), N);
export const WORLD_W: number = G.width, WORLD_H: number = G.height;
export const KM_PER_PX: number = G.res_m / 1000;
export function px(lon: number, lat: number): [number, number] {
  let dl = lon - LON0;
  while (dl > 180) dl -= 360;
  while (dl < -180) dl += 360;
  const th = N * dl * D, r = rho(lat);
  return [(r * Math.sin(th) - G.minx) / G.res_m, (G.maxy - (rho0 - r * Math.cos(th))) / G.res_m];
}
export const meridian = (lon: number) => N * (lon - LON0); // degrees; rotate map by this to make local north point up

export type CamState = {x: number; y: number; zoom: number; tilt: number; rot: number};
export const PERSP = 1700;
/** world px -> screen px (same math as the CSS transform used by MapStage) */
export function project(c: CamState, wx: number, wy: number): {x: number; y: number; s: number} {
  const X0 = (wx - c.x) * c.zoom, Y0 = (wy - c.y) * c.zoom;
  const r = c.rot * D, t = c.tilt * D;
  const X1 = X0 * Math.cos(r) - Y0 * Math.sin(r);
  const Y1 = X0 * Math.sin(r) + Y0 * Math.cos(r);
  const Y2 = Y1 * Math.cos(t), Z2 = Y1 * Math.sin(t);
  const k = PERSP / (PERSP - Z2);
  return {x: 960 + X1 * k, y: 540 + Y2 * k, s: k};
}
export const cssTransform = (c: CamState) =>
  `translate(960px,540px) rotateX(${c.tilt}deg) rotateZ(${c.rot}deg) scale(${c.zoom}) translate(${-c.x}px,${-c.y}px)`;
