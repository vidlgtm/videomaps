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
export type Place = {name: string; pt: [number, number]; box: Box | null; lonlat: [number, number]; ids: string[]; city?: string};
const boxOf = (p: PathRec): Box | null => (p.bbox && p.bbox.length === 4 ? [p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]] : null);
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
      return {name: `[${q[0]}, ${q[1]}]`, pt, box: null, lonlat: [q[0], q[1]], ids: []};
    }
    if (Array.isArray(q)) {
      const ps = q.map((x) => this.resolve(x, depth + 1));
      const box = unionBox(ps.map((p) => p.box), ps.filter((p) => !p.box).map((p) => p.pt))!;
      const pt: [number, number] = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
      return {name: ps.map((p) => p.name).join(' + '), pt, box, lonlat: lonlat(pt[0], pt[1]), ids: ps.flatMap((p) => p.ids)};
    }
    if (typeof q !== 'string') return fail(`bad place: ${JSON.stringify(q)}`);
    const s = q.trim();
    if (this.extra[s] !== undefined) {
      const p = this.resolve(this.extra[s], depth + 1);
      if (Array.isArray(this.extra[s]) && typeof this.extra[s][0] === 'number') { this.extraCities[s] = [this.extra[s][0], this.extra[s][1]]; return {...p, name: s, city: s}; }
      return {...p, name: s};
    }
    if (PATHS[s]) {
      const p = PATHS[s];
      return {name: s, pt: p.label, box: boxOf(p), lonlat: lonlat(p.label[0], p.label[1]), ids: [s]};
    }
    const low = s.toLowerCase();
    const city = Object.keys(CITIES).find((c) => c.toLowerCase() === low);
    if (city) return {name: city, pt: CITIES[city].px, box: null, lonlat: CITIES[city].lonlat, ids: [], city};
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
