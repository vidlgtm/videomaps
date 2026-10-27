// World-space geometry lookup shared by the renderer and the layout/overlap tools (pure TS, no React).
import geo from '../data/geo.json';
import {px} from './proj';

const G: any = geo;
export type P = {d: string; label: [number, number]; bbox?: number[]; area_px?: number; name?: string};
export const PATHS: Record<string, P> = {};
G.republics.forEach((r: any) => (PATHS['rep:' + r.id] = r));
Object.entries(G.shapes).forEach(([k, v]: any) => (PATHS['shape:' + k] = v));
(G.rus_republics ?? []).forEach((r: any) => (PATHS['rr:' + r.id] = r));
(G.breakaway ?? []).forEach((r: any) => (PATHS['brk:' + r.id] = r));
(G.rivers ?? []).forEach((r: any) => (PATHS['river:' + r.id] = r));
(G.context ?? []).forEach((r: any) => (PATHS['ctx:' + r.id] = r));
if (G.shapes.frontier ?? G.shapes.ussr_frontier) PATHS['frontier'] = G.shapes.frontier ?? G.shapes.ussr_frontier;
export const CITIES: Record<string, {px: [number, number]}> = G.cities;
export const anchor = (id: string | [number, number]): [number, number] =>
  Array.isArray(id) ? px(id[0], id[1]) : (PATHS[id]?.label as [number, number]) ?? [0, 0];
