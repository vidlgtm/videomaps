// Places the brain names -> world geometry of the engine basemap (same projection as the renderer).
import geoRaw from '../../engine/src/data/geo.json';
import {px, KM_PER_PX, WORLD_W, WORLD_H} from '../../engine/src/lib/proj';
import {fail, arr} from './util';

export {px, KM_PER_PX, WORLD_W, WORLD_H};
const G: any = geoRaw;
export type PathRec = {d?: string; label: [number, number]; bbox?: number[]; area_px?: number; name?: string};
export const PATHS: Record<string, PathRec> = {};
G.republics.forEach((r: any) => (PATHS['rep:' + r.id] = r));
Object.entries(G.shapes).forEach(([k, v]: any) => (PATHS['shape:' + k] = v));
(G.rus_republics ?? []).forEach((r: any) => (PATHS['rr:' + r.id] = r));
(G.breakaway ?? []).forEach((r: any) => (PATHS['brk:' + r.id] = r));
(G.rivers ?? []).forEach((r: any) => (PATHS['river:' + r.id] = r));
(G.context ?? []).forEach((r: any) => (PATHS['ctx:' + r.id] = r));
if (G.shapes.ussr_frontier) PATHS['frontier'] = G.shapes.ussr_frontier;
export const CITIES: Record<string, {lonlat: [number, number]; px: [number, number]}> = G.cities;
export const REPUBLIC_IDS: string[] = G.republics.map((r: any) => r.id);

/** inverse projection (Newton), world px -> [lon, lat] */
export function lonlat(wx: number, wy: number): [number, number] {
  let lon = G.lon0 ?? 60, lat = 50;
  for (let i = 0; i < 40; i++) {
    const [x, y] = px(lon, lat), e = 1e-4;
    const [x1, y1] = px(lon + e, lat), [x2, y2] = px(lon, lat + e);
    const a = (x1 - x) / e, b = (x2 - x) / e, c = (y1 - y) / e, d = (y2 - y) / e, det = a * d - b * c;
    const dx = wx - x, dy = wy - y;
    lon += (d * dx - b * dy) / det; lat += (-c * dx + a * dy) / det;
  }
  return [Math.round(lon * 1000) / 1000, Math.round(lat * 1000) / 1000];
}
export type Box = [number, number, number, number];
export type Place = {name: string; pt: [number, number]; box: Box | null; lonlat: [number, number]; ids: string[]; city?: string; shape: [number, number][]};
/** world-px points of an SVG path string (M/L absolute coordinates as written by geodata.py) */
const ptsOf = (d?: string): [number, number][] => {
  if (!d) return [];
  const n = d.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
  const out: [number, number][] = [];
  for (let i = 0; i + 1 < n.length; i += 2) out.push([n[i], n[i + 1]]);
  return out;
};
const boxOf = (p: PathRec): Box | null => {
  if (p.bbox && p.bbox.length === 4) return [p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]];
  const q = ptsOf(p.d); if (!q.length) return null;
  return [Math.min(...q.map((x) => x[0])), Math.min(...q.map((x) => x[1])), Math.max(...q.map((x) => x[0])), Math.max(...q.map((x) => x[1]))];
};
/** a representative point of a path: its label anchor, else the middle vertex of its line, else its box centre */
export const pointOf = (p: PathRec): [number, number] => {
  if (p.label) return p.label;
  const q = ptsOf(p.d); if (q.length) return q[Math.floor(q.length / 2)];
  const b = boxOf(p); return b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : [0, 0];
};
export const hasLabel = (id: string) => !!PATHS[id]?.label;
const RINGS: Record<string, [number, number][][]> = {};
/** polygon rings of a region path (M/L/Z absolute, as written by geodata.py) */
export function ringsOf(id: string): [number, number][][] {
  if (RINGS[id]) return RINGS[id];
  const d = PATHS[id]?.d ?? '', out: [number, number][][] = [];
  let cur: [number, number][] = [];
  for (const m of d.matchAll(/([MLZ])([^MLZ]*)/g)) {
    if (m[1] === 'M') { if (cur.length > 2) out.push(cur); cur = []; }
    if (m[1] === 'Z') { if (cur.length > 2) out.push(cur); cur = []; continue; }
    const n = m[2].match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
    for (let i = 0; i + 1 < n.length; i += 2) cur.push([n[i], n[i + 1]]);
  }
  if (cur.length > 2) out.push(cur);
  return (RINGS[id] = out);
}
/** up to ~160 outline points of a region (all its rings), or of a line, for framing */
export function shapeOf(id: string): [number, number][] {
  let pts: [number, number][] = ringsOf(id).flat();
  if (!pts.length) pts = ptsOf(PATHS[id]?.d);
  if (!pts.length) { const b = boxOf(PATHS[id] ?? ({} as any)); return b ? [[b[0], b[1]], [b[2], b[3]]] : [pointOf(PATHS[id])]; }
  const k = Math.max(1, Math.floor(pts.length / 160));
  return pts.filter((_, i) => i % k === 0);
}
/** even-odd point-in-region test in world px */
export function insideRegion(id: string, x: number, y: number) {
  let inside = false;
  for (const r of ringsOf(id)) for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside;
  }
  return inside;
}
export const unionBox = (bs: (Box | null)[], pts: [number, number][] = []): Box | null => {
  const xs: number[] = [], ys: number[] = [];
  bs.forEach((b) => { if (b) { xs.push(b[0], b[2]); ys.push(b[1], b[3]); } });
  pts.forEach((p) => { xs.push(p[0]); ys.push(p[1]); });
  return xs.length ? [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] : null;
};

export class Gazetteer {
  extra: Record<string, any>;                 // order.json "places": {"Name": [lon, lat] | "id" | ["id", "Name", ...]}
  extraCities: Record<string, [number, number]> = {};
  constructor(extra: Record<string, any> = {}) { this.extra = extra; }
  hasPath(id: string) { return !!PATHS[id]; }
  path(id: string): PathRec { const p = PATHS[id]; if (!p) fail(`unknown map region id "${id}" (not in geo.json)`); return p; }
  resolve(q: any, depth = 0): Place {
    if (depth > 6) fail(`place definition loops: ${JSON.stringify(q)}`);
    if (Array.isArray(q) && q.length === 2 && typeof q[0] === 'number') {
      const pt = px(q[0], q[1]) as [number, number];
      return {name: `[${q[0]}, ${q[1]}]`, pt, box: null, lonlat: [q[0], q[1]], ids: [], shape: [pt]};
    }
    if (Array.isArray(q)) {
      const ps = q.map((x) => this.resolve(x, depth + 1));
      const box = unionBox(ps.map((p) => p.box), ps.filter((p) => !p.box).map((p) => p.pt))!;
      const pt: [number, number] = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
      return {name: ps.map((p) => p.name).join(' + '), pt, box, lonlat: lonlat(pt[0], pt[1]), ids: ps.flatMap((p) => p.ids), shape: ps.flatMap((p) => p.shape)};
    }
    if (typeof q !== 'string') return fail(`bad place: ${JSON.stringify(q)}`);
    const s = q.trim();
    if (this.extra[s] !== undefined) {
      const p = this.resolve(this.extra[s], depth + 1);
      if (Array.isArray(this.extra[s]) && typeof this.extra[s][0] === 'number') { this.extraCities[s] = [this.extra[s][0], this.extra[s][1]]; return {...p, name: s, city: s}; }
      return {...p, name: s};
    }
    if (PATHS[s]) {
      const p = PATHS[s], pt = pointOf(p);
      return {name: s, pt, box: boxOf(p), lonlat: lonlat(pt[0], pt[1]), ids: [s], shape: shapeOf(s)};
    }
    const low = s.toLowerCase();
    const city = Object.keys(CITIES).find((c) => c.toLowerCase() === low);
    if (city) return {name: city, pt: CITIES[city].px, box: null, lonlat: CITIES[city].lonlat, ids: [], city, shape: [CITIES[city].px]};
    for (const pre of ['rep:', 'rr:', 'brk:', 'shape:', 'ctx:', 'river:']) {
      const id = Object.keys(PATHS).find((k) => k.startsWith(pre) && (k.slice(pre.length).toLowerCase() === low || (PATHS[k].name ?? '').toLowerCase() === low));
      if (id) return this.resolve(id, depth + 1);
    }
    return fail(`unknown place "${s}" - use a geo.json id (rep:EST, rr:Tatarstan, ctx:FIN, shape:crimea), a city of geo.json ` +
      `(${Object.keys(CITIES).slice(0, 8).join(', ')}, ...), or add it to order.json "places" as [lon, lat]`);
  }
  /** expand "film" / "film-except" helpers into republic ids */
  ids(q: any, film: string[]): string[] {
    const out: string[] = [];
    arr(q).forEach((x: any) => {
      if (x === 'film') out.push(...film.map((i) => 'rep:' + i));
      else if (typeof x === 'string' && /^[A-Z]{3}$/.test(x) && PATHS['rep:' + x]) out.push('rep:' + x);
      else if (typeof x === 'string' && (PATHS[x] || x === 'borders' || x === 'frontier')) out.push(x);
      else if (typeof x === 'string') { const p = this.resolve(x); if (!p.ids.length) fail(`"${x}" is a point, not a region (fill/border need a region)`); out.push(...p.ids); }
      else fail(`bad region: ${JSON.stringify(x)}`);
    });
    return out;
  }
}
export const kmToPx = (km: number) => km / KM_PER_PX;
