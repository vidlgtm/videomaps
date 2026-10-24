import {T} from './script';

export const SOV: Record<string, string> = {RUS: 'SOVIET UNION'};
export const MODERN: Record<string, string> = {RUS: 'RUSSIA'};
export const SHAPE_NAME: Record<string, string> = {};
export const CTX_NAME: Record<string, string> = {JPN: 'JAPAN', KOR: 'KOREA', CHN: 'CHINA'};

export function nameFor(id: string, t: number): string | null {
  if (!id.startsWith('rep:')) return SHAPE_NAME[id] ?? null;
  const iso = id.slice(4);
  if (iso !== 'RUS') return MODERN[iso] ?? null;
  if (t < T.p4.august) return 'RUSSIAN EMPIRE';
  if (t < T.p10.dissolved) return SOV.RUS;
  return MODERN.RUS;
}
export const ctxNamesOn = (t: number) => t > T.p0.islands + 0.5 && t < T.p14.controls - 0.3;
