// Era-correct map names for the five beats in USSR60.
import {T} from './script';

const MODERN: Record<string, string> = {
  RUS: 'RUSSIA', UKR: 'UKRAINE', BLR: 'BELARUS', KAZ: 'KAZAKHSTAN', UZB: 'UZBEKISTAN', TKM: 'TURKMENISTAN',
  KGZ: 'KYRGYZSTAN', TJK: 'TAJIKISTAN', GEO: 'GEORGIA', ARM: 'ARMENIA', AZE: 'AZERBAIJAN', MDA: 'MOLDOVA',
  EST: 'ESTONIA', LVA: 'LATVIA', LTU: 'LITHUANIA',
};
const SOV1922: Record<string, string> = {
  RUS: 'RUSSIAN SFSR', UKR: 'UKRAINIAN SSR', BLR: 'BYELORUSSIAN SSR',
};
const SOV1936: Record<string, string> = {
  ...SOV1922, KAZ: 'KAZAKH SSR', UZB: 'UZBEK SSR', TKM: 'TURKMEN SSR', KGZ: 'KIRGHIZ SSR', TJK: 'TAJIK SSR',
  GEO: 'GEORGIAN SSR', ARM: 'ARMENIAN SSR', AZE: 'AZERBAIJANI SSR',
};
const SOV1940: Record<string, string> = {
  ...SOV1936, EST: 'ESTONIAN SSR', LVA: 'LATVIAN SSR', LTU: 'LITHUANIAN SSR', MDA: 'MOLDAVIAN SSR',
};
export const SHAPE_NAME: Record<string, string> = {
  'shape:tsfsr': 'TRANSCAUCASIAN SFSR',
  'shape:kfssr': 'KARELO-FINNISH SSR',
  'rr:Tatarstan': 'TATARSTAN',
};
export const CTX_NAME: Record<string, string> = {
  FIN: 'FINLAND', SWE: 'SWEDEN', NOR: 'NORWAY', POL: 'POLAND', TUR: 'TURKEY', IRN: 'IRAN', AFG: 'AFGHANISTAN',
  CHN: 'CHINA', MNG: 'MONGOLIA', JPN: 'JAPAN', KOR: 'KOREA',
};

export function nameFor(id: string, t: number): string | null {
  if (id in SHAPE_NAME) return SHAPE_NAME[id];
  if (!id.startsWith('rep:')) return null;
  const iso = id.slice(4);
  if (t < T.p1.s) return MODERN[iso] ?? null;
  if (t < T.p2.s) return SOV1922[iso] ?? null;
  if (t < T.p3.s) return SOV1936[iso] ?? null;
  if (t < T.p4.s) return SOV1940[iso] ?? null;
  return MODERN[iso] ?? null;
}
export const ctxNamesOn = (t: number) => t > T.p0.nextDay + 0.7 && t < T.p4.fifteen - 0.5;
