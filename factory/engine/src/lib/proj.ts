// The map's conformal projection exactly as in factory/maps/mapdef.py (sphere R = 6371 km), read from geo.json:
// kind "lcc" (Lambert conformal conic: lat0, lat1, lat2, lon0; the v5 map: 55, 45, 62, 90) or "merc" (Mercator, cone_n = 0).
import geo from '../data/geo.json';
const G: any = geo;
const R = 6371000, D = Math.PI / 180;
export const KIND: string = G.kind ?? 'lcc';
export const LON0: number = G.lon0;
export const N: number = KIND === 'merc' ? 0 : G.cone_n;
const lat0 = (G.lat0 ?? 55) * D, lat1 = (G.lat1 ?? 45) * D;
const F = KIND === 'merc' ? 0 : (Math.cos(lat1) * Math.pow(Math.tan(Math.PI / 4 + lat1 / 2), N)) / N;
const rho = (latDeg: number) => (R * F) / Math.pow(Math.tan(Math.PI / 4 + (Math.max(-89.9, Math.min(89.9, latDeg)) * D) / 2), N);
const rho0 = KIND === 'merc' ? 0 : (R * F) / Math.pow(Math.tan(Math.PI / 4 + lat0 / 2), N);
export const WORLD_W: number = G.width, WORLD_H: number = G.height;
export const KM_PER_PX: number = G.res_m / 1000;
export function px(lon: number, lat: number): [number, number] {
  let dl = lon - LON0;
  while (dl > 180) dl -= 360;
  while (dl < -180) dl += 360;
  if (KIND === 'merc') {
    const la = Math.max(-85, Math.min(85, lat)) * D;
    return [(R * dl * D - G.minx) / G.res_m, (G.maxy - R * Math.log(Math.tan(Math.PI / 4 + la / 2))) / G.res_m];
  }
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
