// v4: country names on the map. Era-correct forms: modern names in the 1991 hook and after the 15 states are
// independent; official Soviet forms (1922-1956 scenes) in chapters I-III; none in the busy collapse chapter.
export const SOV: Record<string, string> = {
  RUS: 'RUSSIAN SFSR', UKR: 'UKRAINIAN SSR', BLR: 'BYELORUSSIAN SSR', KAZ: 'KAZAKH SSR', UZB: 'UZBEK SSR', TKM: 'TURKMEN SSR',
  KGZ: 'KIRGHIZ SSR', TJK: 'TAJIK SSR', GEO: 'GEORGIAN SSR', ARM: 'ARMENIAN SSR', AZE: 'AZERBAIJAN SSR', MDA: 'MOLDAVIAN SSR',
  EST: 'ESTONIAN SSR', LVA: 'LATVIAN SSR', LTU: 'LITHUANIAN SSR',
};
export const MODERN: Record<string, string> = {
  RUS: 'RUSSIA', UKR: 'UKRAINE', BLR: 'BELARUS', KAZ: 'KAZAKHSTAN', UZB: 'UZBEKISTAN', TKM: 'TURKMENISTAN', KGZ: 'KYRGYZSTAN',
  TJK: 'TAJIKISTAN', GEO: 'GEORGIA', ARM: 'ARMENIA', AZE: 'AZERBAIJAN', MDA: 'MOLDOVA', EST: 'ESTONIA', LVA: 'LATVIA', LTU: 'LITHUANIA',
};
/** historical shapes used by the fills (all Soviet era) */
export const SHAPE_NAME: Record<string, string> = {
  'shape:rsfsr_1922': 'RUSSIAN SFSR', 'shape:rsfsr_1924': 'RUSSIAN SFSR', 'shape:rsfsr_1929': 'RUSSIAN SFSR', 'shape:rsfsr_1936': 'RUSSIAN SFSR',
  'shape:rsfsr_1940': 'RUSSIAN SFSR', 'shape:rsfsr_1954': 'RUSSIAN SFSR', 'shape:ukr_1936': 'UKRAINIAN SSR', 'shape:ukr_1945': 'UKRAINIAN SSR',
  'shape:blr_1936': 'BYELORUSSIAN SSR', 'shape:tsfsr': 'TRANSCAUCASIAN SFSR', 'shape:uzb_1924': 'UZBEK SSR', 'shape:uzb_1929': 'UZBEK SSR',
  'shape:kfssr': 'KARELO-FINNISH SSR',
};
/** neighbours (names valid both in 1991 and today) */
export const CTX_NAME: Record<string, string> = {
  CHN: 'CHINA', MNG: 'MONGOLIA', IRN: 'IRAN', AFG: 'AFGHANISTAN', TUR: 'TURKEY', FIN: 'FINLAND', POL: 'POLAND', ROU: 'ROMANIA',
  NOR: 'NORWAY', SWE: 'SWEDEN', IRQ: 'IRAQ', SYR: 'SYRIA', PAK: 'PAKISTAN', IND: 'INDIA', JPN: 'JAPAN', HUN: 'HUNGARY', GRC: 'GREECE',
  BGR: 'BULGARIA',
};
