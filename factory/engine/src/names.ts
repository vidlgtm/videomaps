// FACTORY ENGINE - era-correct names on the map, from the order's name sets and eras (data/film.json "names").
// nameFor(id, t): the name shown on a FILLED region at time t (null = none). ctxNamesOn(t): neighbour names now?
import film from './data/film.json';

type Era = {from: number; set: string | null; extra?: Record<string, string>; neighbours?: boolean};
const N: any = (film as any).names ?? {eras: [], sets: {}, ctx: {}};
const ERAS: Era[] = [...(N.eras as Era[])].sort((a, b) => a.from - b.from);
const SETS: Record<string, Record<string, string>> = N.sets ?? {};
/** neighbour names (key = ISO of a ctx: path) */
export const CTX_NAME: Record<string, string> = N.ctx ?? {};
const eraAt = (t: number): Era | null => { let e: Era | null = null; for (const x of ERAS) if (x.from <= t) e = x; return e; };
export function nameFor(id: string, t: number): string | null {
  const e = eraAt(t);
  if (!e) return null;
  if (e.extra && e.extra[id] !== undefined) return e.extra[id] || null;
  if (!e.set) return null;
  return SETS[e.set]?.[id] ?? null;
}
export const ctxNamesOn = (t: number) => t > 3 && !!eraAt(t)?.neighbours;
