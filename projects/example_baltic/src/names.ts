// Country names on the map, era-correct (Cinzel caps for the film's countries, Cormorant italic caps for neighbours).
// nameFor(id, t): the name shown on a FILLED region at time t (null = none). ctxNamesOn(t): show neighbour names now?
import {T} from './script';

export const SOV: Record<string, string> = {EST: 'ESTONIAN SSR', LVA: 'LATVIAN SSR', LTU: 'LITHUANIAN SSR'};
export const MODERN: Record<string, string> = {EST: 'ESTONIA', LVA: 'LATVIA', LTU: 'LITHUANIA'};
export const SHAPE_NAME: Record<string, string> = {};
/** neighbours whose names are valid in every year this film shows (1939-1991) */
export const CTX_NAME: Record<string, string> = {FIN: 'FINLAND', SWE: 'SWEDEN', POL: 'POLAND'};

/** independence moments (seconds): before them the republic is Soviet (from the annexation on) */
const indep = (iso: string, t: number) =>
  iso === 'LTU' ? t >= T.p3.ltu : iso === 'EST' ? t >= T.p3.estlva : iso === 'LVA' ? t >= T.p3.lva : false;
export function nameFor(id: string, t: number): string | null {
  if (!id.startsWith('rep:')) return SHAPE_NAME[id] ?? null;
  const iso = id.slice(4);
  if (t < T.p1.annexed) return MODERN[iso] ?? null;          // 1939: still independent states
  if (t < T.p2.s) return SOV[iso] ?? null;                    // 1940: Soviet republics
  if (t < T.p3.s) return null;                                // 1989 chain: keep the map clean for the chain
  return indep(iso, t) ? MODERN[iso] ?? null : SOV[iso] ?? null;
}
export const ctxNamesOn = (t: number) => t > T.p0.hands + 0.8 && t < T.p4.flags - 0.3;
