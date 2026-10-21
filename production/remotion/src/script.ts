// The film's visual score: every event is pinned to a word of the narration (forced alignment).
import {cue, cs, ce, TOTAL, WORDS} from './lib/cues';
import {h, OPENING, BANNERS, ICONS, DOCS, CUTOUTS, NUMERALS, TAGS, CHAIN} from './v2';

// ---------- helpers ----------
const C = cue;
/** start time of the k-th token inside a matched phrase */
const tok = (c: number, phrase: string, k: number) => {
  const t0 = C(c, phrase);
  const i = WORDS.findIndex((w) => w.c === c && Math.abs(w.t0 - t0) < 1e-6);
  return WORDS[i + k].t0;
};
export const END = TOTAL;

// ---------- palette ----------
export const COL: Record<string, string> = {
  RUS: '#A23E44', UKR: '#D2A93F', BLR: '#7A9B4E', KAZ: '#3F8F7F', UZB: '#5577B0', TKM: '#9BB25A', KGZ: '#C0663D',
  TJK: '#8D6CB0', GEO: '#86B39A', ARM: '#D9893A', AZE: '#9F78C9', MDA: '#B79257', EST: '#5C86C2', LVA: '#9B4F6E',
  LTU: '#C98B4E', UNION: '#8E3741', GOLD: '#E2BF6A', INK: '#0E1A24', TXT: '#F4EFE6', RED: '#D2434E', TEAL: '#4FA39E',
  KFSSR: '#6C8EBF', TATAR: '#E2BF6A', HIST: '#9E7A55',
};
export const ISO15 = ['RUS', 'UKR', 'BLR', 'KAZ', 'UZB', 'TKM', 'KGZ', 'TJK', 'GEO', 'ARM', 'AZE', 'MDA', 'EST', 'LVA', 'LTU'];
export const FLAG_CODE: Record<string, string> = {RUS: 'ru', UKR: 'ua', BLR: 'by', KAZ: 'kz', UZB: 'uz', TKM: 'tm', KGZ: 'kg', TJK: 'tj',
  GEO: 'ge', ARM: 'am', AZE: 'az', MDA: 'md', EST: 'ee', LVA: 'lv', LTU: 'lt'};
export const NAME: Record<string, string> = {RUS: 'Russia', UKR: 'Ukraine', BLR: 'Belarus', KAZ: 'Kazakhstan', UZB: 'Uzbekistan',
  TKM: 'Turkmenistan', KGZ: 'Kyrgyzstan', TJK: 'Tajikistan', GEO: 'Georgia', ARM: 'Armenia', AZE: 'Azerbaijan', MDA: 'Moldova',
  EST: 'Estonia', LVA: 'Latvia', LTU: 'Lithuania'};

// ---------- types ----------
export type CamKey = {t: number; lon?: number; lat?: number; x?: number; y?: number; w: number; tilt?: number; rotK?: number; dur?: number};
export type Fill = {id: string; color: string; op?: number; from: number; to?: number; fi?: number; fo?: number; pulse?: boolean; hatch?: boolean};
export type Stroke = {id: string; color: string; width: number; from: number; to?: number; draw?: number; dash?: boolean; glow?: boolean; op?: number};
export type Label = {text: string; at: string | [number, number]; size: number; from: number; to?: number; color?: string; italic?: boolean; spacing?: number; sub?: string};
export type Marker = {city: string; label?: string; sub?: string; from: number; to?: number; color?: string; pulse?: boolean; side?: 'r' | 'l' | 't' | 'b'};
export type Flag = {iso: string; t: number; to?: number; date?: string};
export type Line = {pts: [number, number][]; from: number; dur: number; to?: number; color: string; width: number; dash?: boolean};
export type Ring = {at: string; km: number[]; from: number; to?: number};
export type Card = {kind: 'date' | 'chapter' | 'quote' | 'big' | 'title' | 'strike' | 'end' | 'callout'; text: string; sub?: string; from: number; to: number; num?: string; at?: [number, number]};
export type Portrait = {img: string; name: string; sub?: string; caption?: string; captionFrom?: number; side: 'left' | 'right'; from: number; to: number};
export type Step = {at: number; s0: number; s1: number; rate?: number};
export type Clip = {src: string; from: number; to: number; steps: Step[]; kind: 'manim' | 'doll' | 'cauc'};
export type Sfx = {f: string; t: number; v?: number};

// ---------- camera views ----------
const V = {
  OV: {x: 4060, y: 2860, w: 9300, tilt: 0, rotK: 0},
  OVW: {lon: 50, lat: 50, w: 5400, tilt: 14},
  WEST: {lon: 36, lat: 52.5, w: 3500, tilt: 22},
  BALTIC: {lon: 25, lat: 57, w: 1050, tilt: 32},
  VOLGA: {lon: 50.5, lat: 55.3, w: 1500, tilt: 30},
  CAUC: {lon: 44.6, lat: 42.0, w: 1050, tilt: 34},
  CASIA: {lon: 64, lat: 43, w: 2900, tilt: 24},
  KAZ: {lon: 67, lat: 48, w: 3300, tilt: 22},
  CRIMEA: {lon: 34.3, lat: 45.4, w: 620, tilt: 36},
  UKR: {lon: 31.5, lat: 48.7, w: 1750, tilt: 28},
  MOSCOW: {lon: 37.6, lat: 55.6, w: 1400, tilt: 30},
  BELO: {lon: 30.5, lat: 53.6, w: 1700, tilt: 28},
  KARELIA: {lon: 31.5, lat: 61.5, w: 1800, tilt: 28},
  BREAK: {lon: 37.5, lat: 44.6, w: 2300, tilt: 26},
  WEST40: {lon: 29.5, lat: 56, w: 2500, tilt: 26},
  CHECH: {lon: 45.7, lat: 43.3, w: 520, tilt: 36},
};
const cam = (t: number, v: any, dur = 2.2): CamKey => ({t, dur, ...v});

// ======================= CHUNK 0 : HOOK =======================
const c0 = {
  flag: C(0, 'the red flag'), hours: C(0, 'Within hours'), fifteen: C(0, 'fifteen new nations'), strange: C(0, 'But here is'),
  notBuilt: C(0, 'was not built'), patch: C(0, 'a patchwork'), fiftyThree: C(0, 'fifty-three'), tatar: C(0, 'Tatarstan had'),
  yetEst: C(0, 'yet Estonia'), tatarNot: C(0, 'and Tatarstan did not'), chech: C(0, 'Chechnya would'), why: C(0, 'So why fifteen'),
  twenty: C(0, 'twenty'), fifty: C(0, 'or fifty'), answer: C(0, 'The answer'), title: C(0, 'This is why'), end: ce(0),
};
// ======================= CHUNK 1 : THE NESTING DOLL =======================
const c1 = {
  s: cs(1), bols: C(1, 'When the Bolsheviks'), broke: C(1, 'briefly broken free'), lenin: C(1, "Lenin's solution"),
  stalin: C(1, 'Ironically, Stalin'), join: C(1, 'join Russia'), overruled: C(1, 'Lenin overruled him'),
  dec30: C(1, 'On December 30th'), rus: tok(1, 'republics, Russia, Ukraine', 1), ukr: tok(1, 'republics, Russia, Ukraine', 2),
  blr: C(1, 'Belarus and Transcaucasia'), tsf: tok(1, 'Belarus and Transcaucasia', 2), treaty: C(1, 'signed a treaty'),
  paper: C(1, 'On paper, it was'), reality: C(1, 'In reality'), top: C(1, 'At the top stood'), inside: C(1, 'Inside them sat'),
  those: C(1, 'Inside those'), districts: C(1, 'smaller autonomous districts'), y1989: C(1, 'By 1989'),
  h15: C(1, 'fifteen union republics'), h20: C(1, 'twenty autonomous republics'), h8: C(1, 'eight autonomous regions'),
  h10: C(1, 'ten autonomous districts'), layer: C(1, 'Every layer'), capital: C(1, 'its own capital'),
  shell: C(1, 'But only the outer shell'), constit: C(1, 'The Soviet constitution guaranteed'), decades: C(1, 'For decades'),
  words: C(1, 'But the words were there'), e: ce(1),
};
// ======================= CHUNK 2 : STALIN'S RULES =======================
const c2 = {
  s: cs(2), uzb: C(2, 'Uzbekistan and Turkmenistan'), tjk: C(2, 'Tajikistan in 1929'), y1936: C(2, 'Then, in 1936'),
  kaz: C(2, 'Kazakhstan and Kyrgyzstan'), tsf: C(2, 'the Transcaucasian republic'), eleven: C(2, 'That made eleven'),
  asked: C(2, 'Other nations asked'), three: C(2, 'a nation needed three things'), first: C(2, 'First, it had'),
  afterAll: C(2, 'After all, Stalin argued'), second: C(2, 'Second, its namesake'), third: C(2, 'And third'),
  look: C(2, 'Now look at Tatarstan'), m36: C(2, 'three point six million'), m16: C(2, 'one point six million'),
  proud: C(2, 'A proud history'), deep: C(2, 'deep inside Russia'), rule1: C(2, "By Stalin's first rule"),
  same: C(2, 'The same was true'), chuv: C(2, 'Chuvashia'), volga: C(2, 'along the Volga'), practice: C(2, 'In practice'),
  kazProm: C(2, 'Kazakhstan was promoted'), kazakhs: C(2, 'Kazakhs no longer'), principle: C(2, 'But the principle was set'), e: ce(2),
};
// ======================= CHUNK 3 : SIXTEEN BECOMES FIFTEEN =======================
const c3 = {
  s: cs(3), moving: C(3, 'The map kept moving'), y1940: C(3, 'In 1940'), est: C(3, 'annexed Estonia'), lva: C(3, 'Latvia and Lithuania'),
  mda: C(3, 'the Moldavian republic'), kf: C(3, 'Karelo-Finnish'), sixteen: C(3, 'That brought the total'),
  finland: C(3, 'But Finland never fell'), y1956: C(3, 'So in 1956'), became: C(3, 'Sixteen became fifteen'),
  y1954: C(3, 'Two years earlier'), crimea: C(3, 'The Crimean peninsula'), transferred: C(3, 'was transferred'),
  detail: C(3, 'At the time'), nobody: C(3, 'Nobody imagined'), intl: C(3, 'international borders'), e: ce(3),
};
// ======================= CHUNK 4 : THE COLLAPSE =======================
const c4 = {
  s: cs(4), gorby: C(4, 'Mikhail Gorbachev'), sudden: C(4, 'Suddenly'), aug89: C(4, 'In August 1989'), hands: C(4, 'joined hands'),
  mar90: C(4, 'On March 11th, 1990'), lith: C(4, 'Lithuania declared'), law: C(4, 'Moscow responded'), refs: C(4, 'demanding referendums'),
  twoThirds: C(4, 'two-thirds majorities'), five: C(4, 'up to five years'), mar91: C(4, 'In March 1991'), six: C(4, 'Six republics refused'),
  aug91: C(4, 'Then, in August 1991'), coup: C(4, 'The coup collapsed'), weeks: C(4, 'Within weeks'), rar: C(4, 'republic after republic'),
  sept: C(4, 'In September'), dec1: C(4, 'On December 1st'), ninety: C(4, 'ninety percent'), week: C(4, 'A week later'),
  lodge: C(4, 'hunting lodge'), dec21: C(4, 'On December 21st'), four: C(4, 'Four days later'), resigned: C(4, 'Gorbachev resigned'),
  shells: C(4, 'The fifteen union republics'), states: C(4, 'fifteen independent states'), e: ce(4),
};
// ======================= CHUNK 5 : THE DOLLS INSIDE =======================
const c5 = {
  s: cs(5), dolls: C(5, 'But what about the dolls inside'), tatar: C(5, 'Tatarstan declared'), sixty: C(5, 'sixty-one percent'),
  noBorder: C(5, 'But with no foreign border'), treaty: C(5, 'special treaty'), chech: C(5, 'Chechnya went further'),
  nov91: C(5, 'In November 1991'), wars: C(5, 'two devastating wars'), again: C(5, 'and again from 1999'), firmly: C(5, 'firmly under'),
  abkh: C(5, 'Abkhazia, South Ossetia'), sos: tok(5, 'Abkhazia, South Ossetia', 1), nk: C(5, 'Nagorno-Karabakh'), tr: C(5, 'and Transnistria'),
  none: C(5, 'None of them'), why: C(5, 'Why?'), cis: C(5, 'formed their Commonwealth'), integrity: C(5, 'territorial integrity'),
  uti: C(5, 'uti possidetis juris'), means: C(5, 'which means'), inherit: C(5, 'inherit the borders'), legal: C(5, 'The fifteen union republics had'),
  units: C(5, 'The units inside them'), lines: C(5, 'So the lines drawn'), e: ce(5),
};
// ======================= CHUNK 6 : CONCLUSION =======================
const c6 = {
  s: cs(6), lang: C(6, 'language, religion or history'), seams: C(6, 'It broke along the seams'), system: C(6, 'Stalin built a system'),
  paper: C(6, 'only on paper'), edge: C(6, 'edge of the map'), never: C(6, 'He never imagined'), moment: C(6, 'When the moment came'),
  outer: C(6, 'outermost dolls'), why: C(6, 'And that is why'), exactly: C(6, 'exactly fifteen countries'), e: ce(6),
};
export const T = {c0, c1, c2, c3, c4, c5, c6};

// ======================= GLOBE (Three.js) =======================
export const GLOBE = {from: -10, to: -9, moscowAt: -9.5, pullBack: -9.2};   // v2: replaced by <Opening/>

// ======================= CAMERA =======================
export const CAMERA: CamKey[] = [
  cam(0, {lon: 39, lat: 55.2, w: 1900, tilt: 34}, 0.01),
  cam(h.hours - 0.1, V.OV, 2.6),                                              // Moscow -> the whole union
  cam(h.stood - 0.3, {x: 3900, y: 2900, w: 8700, tilt: 10, rotK: 0}, 3.2),   // drift over the fifteen flags
  cam(h.peoples - 0.2, {lon: 50, lat: 50, w: 5200, tilt: 18}, 2.4),          // the patchwork
  cam(h.organized - 0.3, {x: 4060, y: 2860, w: 9000, tilt: 6, rotK: 0}, 2.2), // fifty-three homelands
  cam(h.tatar - 0.5, {lon: 49.1, lat: 55.8, w: 1500, tilt: 34}, 1.6),        // Tatarstan
  cam(h.est1 - 0.55, {lon: 25.2, lat: 58.9, w: 1250, tilt: 34}, 1.3),        // Estonia
  cam(h.became - 0.6, {lon: 37.5, lat: 57.4, w: 2700, tilt: 28}, 1.4),       // both
  cam(h.chech - 0.45, {lon: 45.6, lat: 43.6, w: 1150, tilt: 36}, 1.5),       // Chechnya
  cam(h.endUp - 0.15, {lon: 41.5, lat: 50.5, w: 2700, tilt: 26}, 1.6),       // Moscow <- Grozny
  cam(h.why - 0.2, V.OV, 1.6),
  cam(h.answer - 0.1, {x: 4300, y: 2900, w: 8500, tilt: 12, rotK: 0}, 5.0),
  cam(h.title - 0.2, {x: 4060, y: 2860, w: 9800, tilt: 4, rotK: 0}, 5.0),
  // chunk 1
  cam(c1.bols - 0.2, {lon: 38.6, lat: 54.6, w: 2000, tilt: 30}, 2.2),          // Moscow: the Red Army
  cam(c1.broke - 0.6, {lon: 40, lat: 47, w: 3400, tilt: 20}, 2.4),              // nations break free
  cam(c1.lenin - 0.2, {lon: 44, lat: 50, w: 4200, tilt: 16}, 6.0),              // slow drift under Lenin & Stalin
  cam(c1.dec30 - 0.4, V.OVW, 2.4), cam(c1.paper, {lon: 52, lat: 52, w: 5600, tilt: 12}, 3.4),
  cam(c1.y1989 - 0.3, V.OV, 1.8),                                               // the 53 homelands, layer by layer
  cam(c1.layer - 0.3, {lon: 44.9, lat: 41.4, w: 1250, tilt: 32}, 2.6), cam(c1.shell, V.OV, 2.6),
  cam(c1.decades + 3.4, {lon: 40, lat: 60, w: 3800, tilt: 18}, 2.4),            // the Gulag (White Sea Canal)
  cam(c1.words, {lon: 50, lat: 54, w: 6200, tilt: 10}, 4.0),
  // chunk 2
  cam(c2.s + 0.5, V.OV, 1.0), cam(c2.uzb - 0.5, V.CASIA, 2.4),
  cam(c2.y1936 - 0.2, {lon: 56, lat: 49, w: 5000, tilt: 14}, 2.4), cam(c2.kaz - 0.3, {lon: 58, lat: 46, w: 4600, tilt: 16}, 2.2),
  cam(c2.eleven - 0.2, V.OV, 1.8),
  cam(c2.first - 0.1, {x: 4060, y: 2860, w: 9300, tilt: 10, rotK: 0}, 3.0),     // rule I: the outer frontier
  cam(c2.afterAll, {lon: 50, lat: 55, w: 2600, tilt: 26}, 2.4),                 // an enclosed republic
  cam(c2.second, {lon: 60, lat: 48, w: 5600, tilt: 14}, 2.4),
  cam(c2.look - 0.2, V.VOLGA, 2.0),
  cam(c2.m16 - 0.5, {lon: 37.5, lat: 57.4, w: 2700, tilt: 28}, 1.5),            // Tatarstan and Estonia together
  cam(c2.deep - 0.3, {lon: 49, lat: 55.5, w: 2300, tilt: 28}, 1.8), cam(c2.same, {lon: 50, lat: 55.2, w: 1900, tilt: 28}, 2.0),
  cam(c2.practice - 0.2, {lon: 44, lat: 53.5, w: 2600, tilt: 24}, 1.8),         // Moscow decides
  cam(c2.kazProm - 0.2, V.KAZ, 2.2), cam(c2.principle, V.OV, 2.4),
  // chunk 3
  cam(c3.y1940 - 0.3, V.WEST40, 2.6), cam(c3.kf - 0.3, V.KARELIA, 2.2),
  cam(c3.sixteen + 0.6, {lon: 40, lat: 54, w: 5200, tilt: 12}, 2.2), cam(c3.y1956 - 0.3, {lon: 33, lat: 60, w: 2600, tilt: 22}, 2.0),
  cam(c3.became - 0.2, V.OV, 1.8),
  cam(c3.y1954 - 0.2, V.CRIMEA, 2.8), cam(c3.detail, {lon: 35, lat: 47, w: 1600, tilt: 26}, 2.4), cam(c3.nobody, V.OV, 2.6),
  // chunk 4
  cam(c4.gorby - 0.2, {lon: 37.6, lat: 55.2, w: 2600, tilt: 24}, 3.0),
  cam(c4.aug89 - 0.4, V.BALTIC, 2.6), cam(c4.mar90 - 0.2, {lon: 25, lat: 55.2, w: 900, tilt: 34}, 1.6),
  cam(c4.law - 0.2, {lon: 30, lat: 55, w: 2200, tilt: 22}, 2.2),
  cam(c4.mar91 - 0.3, V.OVW, 2.4), cam(c4.aug91 - 0.2, V.MOSCOW, 2.4), cam(c4.weeks - 0.2, V.OV, 2.4),
  cam(c4.dec1 - 0.2, V.UKR, 2.4), cam(c4.week - 0.2, V.BELO, 2.2), cam(c4.dec21 - 0.2, {lon: 62, lat: 47, w: 5200, tilt: 14}, 2.4),
  cam(c4.shells, V.OV, 2.0),
  // chunk 5
  cam(c5.tatar - 0.4, V.VOLGA, 2.6), cam(c5.treaty - 0.2, {lon: 44, lat: 55.6, w: 1800, tilt: 28}, 2.0),
  cam(c5.chech + 2.0, V.CHECH, 0.01), cam(c5.wars + 0.5, {lon: 45.3, lat: 43.0, w: 900, tilt: 34}, 3.0),
  cam(c5.abkh - 0.4, V.BREAK, 2.6), cam(c5.cis - 0.3, V.OV, 2.6),
  cam(c5.legal - 0.2, {x: 4060, y: 2860, w: 9000, tilt: 8, rotK: 0}, 4.0), cam(c5.lines - 0.2, V.OVW, 3.0),
  // chunk 6
  cam(c6.s, V.OV, 1.0), cam(c6.never, {x: 4060, y: 2860, w: 8200, tilt: 8, rotK: 0}, 10),
];

// ======================= MAP LAYERS =======================
const RR = ['Tatarstan', 'Bashkortostan', 'Chuvashia', 'Mari El', 'Udmurtia', 'Mordovia', 'Chechnya', 'Ingushetia', 'Dagestan', 'North Ossetia',
  'Kabardino-Balkaria', 'Karachay-Cherkessia', 'Adygea', 'Kalmykia', 'Karelia', 'Komi', 'Sakha (Yakutia)', 'Buryatia', 'Tuva', 'Khakassia', 'Altai Republic'];
const QUILT = ['#B9785A','#7F9C6B','#C9A45C','#6E8FB0','#A0687E','#8FB0A0','#B58C55','#7C7AA8'];
const QUILT_IDS = [...ISO15.map((i) => 'rep:' + i), ...RR.map((r) => 'rr:' + r), 'brk:Abkhazia', 'brk:South Ossetia', 'brk:Transnistria', 'brk:Nagorno-Karabakh'];
const rep = (iso: string, from: number, to = END, op = 0.62, fi = 0.8, fo = 0.8): Fill => ({id: `rep:${iso}`, color: COL[iso], op, from, to, fi, fo});
const all15 = (from: number, to = END, op = 0.62, except: string[] = []) => ISO15.filter((i) => !except.includes(i)).map((i) => rep(i, from, to, op));

const UNION_1922_END = c2.uzb;          // until Central Asia appears
const STATE_1936_FROM = c2.kaz;
export const FILLS: Fill[] = [
  {id: 'rr:Tatarstan', color: '#8E8A84', op: 0.78, from: c2.rule1, to: c2.same + 1.0, fi: 0.3},
  // hook: the union, then fifteen nations
  {id: 'shape:ussr_1991', color: COL.UNION, op: 0.64, from: h.hours - 0.15, to: h.gone + 0.7, fi: 1.0, fo: 0.9},
  ...ISO15.map((i, k) => rep(i, h.fifteen + 0.05 + k * 0.12, h.patch + 0.3, 0.62, 0.45, 0.8)),
  ...QUILT_IDS.map((id, k) => ({id, color: QUILT[k % QUILT.length], op: 0.62, from: h.patch - 0.1 + (k % 9) * 0.07, to: h.tatar - 0.2, fi: 0.4, fo: 0.6} as Fill)),
  {id: 'rep:RUS', color: COL.UNION, op: 0.42, from: h.tatar - 0.5, to: h.why + 0.3},
  {id: 'rr:Tatarstan', color: COL.TATAR, op: 0.88, from: h.tatar, to: h.tatarNot + 0.15, pulse: true},
  {id: 'rr:Tatarstan', color: '#8E8A84', op: 0.75, from: h.tatarNot, to: h.chech - 0.3, fi: 0.3},
  rep('EST', h.est1, h.chech - 0.3, 0.82, 0.4),
  {id: 'rr:Chechnya', color: COL.RED, op: 0.9, from: h.chech, to: h.control + 0.15, pulse: true},
  {id: 'rr:Chechnya', color: COL.UNION, op: 0.9, from: h.control, to: h.why + 0.3, fi: 0.35},
  ...ISO15.map((i, k) => rep(i, h.f15 - 0.1 + k * 0.03, cs(1) + 2.0, 0.6, 0.5)),
  ...RR.map((r) => ({id: 'rr:' + r, color: COL.TATAR, op: 0.78, from: h.twenty - 0.05, to: h.answer + 0.4, fi: 0.35} as Fill)),
  // chunk 1 - 1922
  {id: 'shape:ussr_1938', color: COL.UNION, op: 0.55, from: cs(1) + 1.0, to: c1.reality + 1.5, fi: 1.5},
  {id: 'shape:ussr_1938', color: COL.UNION, op: 0.35, from: c1.y1989 - 0.5, to: c1.layer + 0.5},
  ...['GEO', 'ARM', 'AZE'].map((i) => rep(i, c1.layer, c1.shell + 1.0, 0.55)),
  {id: 'brk:Abkhazia', color: '#FFE08A', op: 0.9, from: c1.layer + 0.6, to: c1.shell + 1.0, hatch: true},
  {id: 'brk:South Ossetia', color: '#FFE08A', op: 0.9, from: c1.layer + 1.0, to: c1.shell + 1.0, hatch: true},
  {id: 'brk:Nagorno-Karabakh', color: '#FFE08A', op: 0.9, from: c1.layer + 1.4, to: c1.shell + 1.0, hatch: true},
  ...all15(c1.shell + 0.4, ce(1) + 1.0, 0.5),
  // chunk 2 - growth of the union
  {id: 'shape:rsfsr_1922', color: COL.RUS, op: 0.55, from: cs(2), to: c2.uzb + 0.5},
  {id: 'shape:rsfsr_1924', color: COL.RUS, op: 0.55, from: c2.uzb, to: c2.tjk + 0.5},
  {id: 'shape:rsfsr_1929', color: COL.RUS, op: 0.55, from: c2.tjk, to: c2.kaz + 0.5},
  {id: 'shape:ukr_1936', color: COL.UKR, op: 0.55, from: cs(2), to: c3.y1940 + 1.0},
  {id: 'shape:blr_1936', color: COL.BLR, op: 0.55, from: cs(2), to: c3.y1940 + 1.0},
  {id: 'shape:tsfsr', color: COL.GEO, op: 0.55, from: cs(2), to: c2.tsf + 1.4},
  {id: 'shape:uzb_1924', color: COL.UZB, op: 0.62, from: c2.uzb, to: c2.tjk + 0.6},
  rep('TKM', c2.uzb + 0.4, c3.e + 2.2, 0.62),
  {id: 'shape:uzb_1929', color: COL.UZB, op: 0.62, from: c2.tjk, to: c2.kaz + 0.8},
  rep('TJK', c2.tjk + 0.2, c3.e + 2.2, 0.62),
  {id: 'shape:rsfsr_1936', color: COL.RUS, op: 0.55, from: STATE_1936_FROM, to: c3.y1940 + 1.0},
  rep('KAZ', c2.kaz, c3.e + 2.2, 0.62), rep('KGZ', c2.kaz + 0.4, c3.e + 2.2, 0.62), rep('UZB', c2.kaz + 0.4, c3.e + 2.2, 0.62),
  rep('GEO', c2.tsf + 0.8, c3.e + 2.2, 0.62), rep('ARM', c2.tsf + 1.0, c3.e + 2.2, 0.62), rep('AZE', c2.tsf + 1.2, c3.e + 2.2, 0.62),
  {id: 'rr:Tatarstan', color: COL.TATAR, op: 0.9, from: c2.look, to: c2.practice + 0.5, pulse: true},
  {id: 'rr:Bashkortostan', color: '#D9A35A', op: 0.75, from: c2.same + 0.4, to: c2.practice + 0.5},
  {id: 'rr:Chuvashia', color: '#D9A35A', op: 0.75, from: c2.chuv, to: c2.practice + 0.5},
  ...['Mari El', 'Udmurtia', 'Mordovia'].map((n, i) => ({id: `rr:${n}`, color: '#D9A35A', op: 0.7, from: c2.volga + 0.2 * i, to: c2.practice + 0.5} as Fill)),
  {id: 'rep:KAZ', color: '#5FC1BA', op: 0.55, from: c2.kazProm, to: c2.principle + 1.0, pulse: true},
  // chunk 3 - 1940, Karelo-Finnish SSR, 1956, Crimea 1954
  {id: 'shape:rsfsr_1940', color: COL.RUS, op: 0.55, from: c3.y1940, to: c3.became + 0.6},
  {id: 'shape:rsfsr_1954', color: COL.RUS, op: 0.55, from: c3.became, to: c3.transferred + 1.6, fi: 2.2},
  {id: 'shape:ukr_1945', color: COL.UKR, op: 0.55, from: c3.y1940, to: c3.transferred + 1.6},
  rep('BLR', c3.y1940, c3.e + 2.2, 0.55),
  rep('EST', c3.est, c3.e + 2.2), rep('LVA', c3.lva, c3.e + 2.2), rep('LTU', c3.lva + 0.5, c3.e + 2.2), rep('MDA', c3.mda, c3.e + 2.2),
  {id: 'shape:kfssr', color: COL.KFSSR, op: 0.75, from: c3.kf, to: c3.became + 0.4, fo: 2.2},
  rep('RUS', c3.transferred + 0.8, c3.e + 2.2, 0.55, 1.2), rep('UKR', c3.transferred + 0.8, c3.e + 2.2, 0.55, 1.2),
  {id: 'shape:crimea', color: COL.RUS, op: 0.8, from: c3.crimea - 0.6, to: c3.transferred + 1.4, fo: 1.2},
  {id: 'shape:crimea', color: COL.UKR, op: 0.85, from: c3.transferred + 0.2, to: c3.detail + 1.5, fi: 1.2},
  // chunk 4 - the collapse
  ...all15(c4.s - 0.6, END, 0.58),
  ...['EST', 'LVA', 'LTU', 'GEO', 'ARM', 'MDA'].map((i) => ({id: `rep:${i}`, color: '#E8E8E8', op: 0.55, from: c4.six + 0.3, to: c4.aug91 + 0.5, hatch: true} as Fill)),
  {id: 'rep:UKR', color: '#F2CF62', op: 0.55, from: c4.dec1 + 0.3, to: c4.week + 0.5, pulse: true},
  // chunk 5
  {id: 'rr:Tatarstan', color: COL.TATAR, op: 0.9, from: c5.tatar, to: c5.chech + 1.0, pulse: true},
  {id: 'rr:Chechnya', color: COL.RED, op: 0.9, from: c5.chech + 9.0, to: c5.abkh, pulse: true},
  {id: 'brk:Abkhazia', color: '#F3F0E8', op: 0.6, from: c5.abkh, to: c5.cis + 1, hatch: true},
  {id: 'brk:South Ossetia', color: '#F3F0E8', op: 0.6, from: c5.sos, to: c5.cis + 1, hatch: true},
  {id: 'brk:Nagorno-Karabakh', color: '#F3F0E8', op: 0.6, from: c5.nk, to: c5.cis + 1, hatch: true},
  {id: 'brk:Transnistria', color: '#F3F0E8', op: 0.6, from: c5.tr, to: c5.cis + 1, hatch: true},
];

export const STROKES: Stroke[] = [
  {id: 'shape:ussr_frontier', color: '#FFD98A', width: 3.2, from: c2.first, to: c2.second - 0.2, draw: 2.0, glow: true},
  {id: 'borders', color: '#FF8A3D', width: 2.6, from: c5.lines, to: c5.lines + 3.4, draw: 1.4, glow: true},
  {id: 'borders', color: '#FFF6E0', width: 1.6, from: c5.lines + 3.0, to: ce(5) + 1.0},
  {id: 'borders', color: '#FFF6E0', width: 1.4, from: h.gone - 0.2, to: h.patch + 0.3, draw: 1.6},
  ...QUILT_IDS.map((id) => ({id, color: '#FFF6E0', width: 1.1, from: h.patch, to: h.tatar - 0.2, dash: true, op: 0.85} as Stroke)),
  {id: 'rep:EST', color: '#FFFFFF', width: 2.6, from: h.became - 0.1, to: h.chech - 0.3, draw: 0.6, glow: true},
  {id: 'rr:Tatarstan', color: '#FFE9A8', width: 2.2, from: h.tatar, to: h.tatarNot, glow: true},
  {id: 'rr:Tatarstan', color: '#D8D2C4', width: 1.8, from: h.tatarNot, to: h.chech - 0.3, dash: true},
  {id: 'rr:Chechnya', color: '#FFD0C8', width: 2.2, from: h.chech, to: h.why + 0.3, glow: true},
  {id: 'borders', color: '#FFF6E0', width: 1.3, from: h.f15 - 0.1, to: cs(1) + 2.0, draw: 1.2},
  {id: 'borders', color: '#FFF6E0', width: 1.1, from: c1.shell, to: ce(1) + 1, op: 0.9},
  {id: 'frontier', color: COL.GOLD, width: 3.2, from: c1.shell + 0.2, to: c1.decades + 3, draw: 3.0, glow: true},
  {id: 'frontier', color: COL.GOLD, width: 3.4, from: c2.first + 0.3, to: c2.second, draw: 3.2, glow: true},
  {id: 'river:Volga', color: '#9FE3FF', width: 3.0, from: c2.volga - 0.2, to: c2.practice + 0.5, draw: 2.0, glow: true},
  {id: 'river:Kama', color: '#9FE3FF', width: 2.2, from: c2.volga, to: c2.practice + 0.5, draw: 2.0, glow: true},
  {id: 'borders', color: '#FFF6E0', width: 1.1, from: c3.s, to: c3.nobody, op: 0.6},
  {id: 'borders', color: COL.GOLD, width: 1.8, from: c3.nobody + 0.6, to: c3.e + 1, draw: 3.0, glow: true},
  {id: 'borders', color: '#FFF6E0', width: 1.2, from: c4.s - 0.5, to: c5.lines, op: 0.85},
  {id: 'brk:Abkhazia', color: '#FFE7A0', width: 1.6, from: c1.layer + 0.6, to: c1.shell + 1, dash: true},
  {id: 'brk:South Ossetia', color: '#FFE7A0', width: 1.6, from: c1.layer + 1.0, to: c1.shell + 1, dash: true},
  {id: 'brk:Nagorno-Karabakh', color: '#FFE7A0', width: 1.6, from: c1.layer + 1.4, to: c1.shell + 1, dash: true},
  {id: 'rr:Tatarstan', color: '#FFE9A8', width: 2.2, from: c2.look, to: c2.practice + 0.5, glow: true},
  {id: 'rr:Tatarstan', color: '#FFE9A8', width: 2.2, from: c5.tatar, to: c5.chech + 1, glow: true},
  {id: 'borders', color: COL.GOLD, width: 2.0, from: c5.lines - 0.3, to: END, draw: 3.0, glow: true},
  {id: 'frontier', color: COL.GOLD, width: 3.2, from: c6.edge - 0.2, to: c6.never + 3, draw: 2.5, glow: true},
];

export const LINES: Line[] = [
  // Baltic Way: Tallinn - Riga - Vilnius (23 Aug 1989, ~675 km)
  {pts: [[24.75, 59.44], [24.6, 58.4], [24.11, 56.95], [24.6, 55.9], [25.28, 54.69]], from: c4.hands - 0.3, dur: 3.2, to: c4.law, color: '#FFF3C4', width: 4},
  // Belovezha: leaders of Russia, Ukraine, Belarus converge on Viskuli
  {pts: [[37.62, 55.75], [23.84, 52.63]], from: c4.week + 0.6, dur: 1.6, to: c4.dec21, color: COL.GOLD, width: 2.5, dash: true},
  {pts: [[30.52, 50.45], [23.84, 52.63]], from: c4.week + 0.8, dur: 1.6, to: c4.dec21, color: COL.GOLD, width: 2.5, dash: true},
  {pts: [[27.56, 53.90], [23.84, 52.63]], from: c4.week + 1.0, dur: 1.6, to: c4.dec21, color: COL.GOLD, width: 2.5, dash: true},
];
export const RINGS: Ring[] = [
  {at: 'rr:Tatarstan', km: [130, 260, 390], from: c2.deep, to: c2.rule1 + 0.5},
  {at: 'rr:Tatarstan', km: [130, 260, 390], from: c5.noBorder, to: c5.chech},
];

export const LABELS: Label[] = [
  {text: 'U.S.S.R.', at: 'shape:ussr_1991', size: 118, from: h.largest - 0.1, to: h.gone + 0.6, spacing: 0.32},
  {text: 'Arctic Ocean', at: [80, 77.5], size: 40, from: h.hours + 0.6, to: h.tatar - 0.4, italic: true},
  {text: 'Black Sea', at: [34.2, 43.1], size: 30, from: h.hours + 0.9, to: h.tatar - 0.4, italic: true},
  {text: 'Caspian Sea', at: [50.6, 41.6], size: 28, from: h.hours + 1.1, to: h.tatar - 0.4, italic: true},
  {text: 'Baltic Sea', at: [19.4, 57.4], size: 26, from: h.hours + 1.3, to: h.tatar - 0.4, italic: true},
  ...['RUS', 'KAZ', 'UKR', 'UZB', 'TKM', 'BLR'].map((i) => ({text: NAME[i].toUpperCase(), at: `rep:${i}`, size: i === 'RUS' ? 52 : 24, from: h.strange + 0.2, to: h.patch + 0.2} as Label)),
  {text: 'USSR', at: 'shape:ussr_1938', size: 64, from: c1.dec30, to: c1.reality, spacing: 0.4, sub: '30 December 1922'},
  {text: 'GEORGIA', at: 'rep:GEO', size: 26, from: c1.layer + 0.3, to: c1.shell + 0.8},
  {text: 'ARMENIA', at: 'rep:ARM', size: 22, from: c1.layer + 0.3, to: c1.shell + 0.8},
  {text: 'AZERBAIJAN', at: 'rep:AZE', size: 24, from: c1.layer + 0.3, to: c1.shell + 0.8},
  {text: 'Abkhaz ASSR', at: 'brk:Abkhazia', size: 20, from: c1.layer + 0.8, to: c1.shell + 0.8, italic: true},
  {text: 'South Ossetian AO', at: 'brk:South Ossetia', size: 20, from: c1.layer + 1.2, to: c1.shell + 0.8, italic: true},
  {text: 'Nagorno-Karabakh AO', at: 'brk:Nagorno-Karabakh', size: 20, from: c1.layer + 1.6, to: c1.shell + 0.8, italic: true},
  {text: 'UZBEK SSR', at: 'shape:uzb_1924', size: 26, from: c2.uzb + 0.3, to: c2.tjk, sub: '1924'},
  {text: 'TURKMEN SSR', at: 'rep:TKM', size: 26, from: c2.uzb + 0.7, to: c2.kaz, sub: '1924'},
  {text: 'TAJIK SSR', at: 'rep:TJK', size: 24, from: c2.tjk + 0.3, to: c2.kaz, sub: '1929'},
  {text: 'KAZAKH SSR', at: 'rep:KAZ', size: 34, from: c2.kaz + 0.3, to: c2.eleven + 1.5, sub: '1936'},
  {text: 'KIRGHIZ SSR', at: 'rep:KGZ', size: 24, from: c2.kaz + 0.7, to: c2.eleven + 1.5, sub: '1936'},
  {text: 'TATARSTAN', at: 'rr:Tatarstan', size: 30, from: c2.look + 0.3, to: c2.practice + 0.5},
  {text: 'BASHKORTOSTAN', at: 'rr:Bashkortostan', size: 22, from: c2.same + 0.6, to: c2.practice + 0.5},
  {text: 'CHUVASHIA', at: 'rr:Chuvashia', size: 20, from: c2.chuv + 0.2, to: c2.practice + 0.5},
  {text: 'Volga', at: [47.6, 54.2], size: 22, from: c2.volga + 0.6, to: c2.practice + 0.5, italic: true, color: '#BDEBFF'},
  {text: 'KAZAKH SSR', at: 'rep:KAZ', size: 34, from: c2.kazProm + 0.3, to: c2.principle + 0.8, sub: '1939 census: Kazakhs 38%'},
  {text: 'ESTONIA', at: 'rep:EST', size: 22, from: c3.est + 0.3, to: c3.kf, sub: '1940'},
  {text: 'LATVIA', at: 'rep:LVA', size: 22, from: c3.lva + 0.3, to: c3.kf, sub: '1940'},
  {text: 'LITHUANIA', at: 'rep:LTU', size: 22, from: c3.lva + 0.8, to: c3.kf, sub: '1940'},
  {text: 'MOLDAVIAN SSR', at: 'rep:MDA', size: 22, from: c3.mda + 0.3, to: c3.kf, sub: '1940'},
  {text: 'KARELO-FINNISH SSR', at: 'shape:kfssr', size: 28, from: c3.kf + 0.3, to: c3.became, sub: '1940–1956'},
  {text: 'FINLAND', at: [26.0, 63.0], size: 30, from: c3.kf + 0.8, to: c3.y1956, color: '#E8E2D4'},
  {text: 'KARELIAN ASSR', at: 'shape:kfssr', size: 26, from: c3.became + 0.4, to: c3.y1954, sub: 'inside Russia, 1956'},
  {text: 'CRIMEA', at: 'shape:crimea', size: 34, from: c3.crimea, to: c3.detail + 1.5},
  {text: 'LITHUANIA', at: 'rep:LTU', size: 26, from: c4.mar90 + 0.4, to: c4.law},
  {text: 'UKRAINE', at: 'rep:UKR', size: 40, from: c4.dec1 + 0.4, to: c4.week, sub: '90.3% for independence'},
  {text: 'TATARSTAN', at: 'rr:Tatarstan', size: 30, from: c5.tatar + 0.3, to: c5.chech},
  {text: 'CHECHNYA', at: 'rr:Chechnya', size: 30, from: c5.chech + 9.3, to: c5.abkh, sub: '1994–1996 · 1999–2009'},
  {text: 'ABKHAZIA', at: 'brk:Abkhazia', size: 22, from: c5.abkh + 0.2, to: c5.cis},
  {text: 'SOUTH OSSETIA', at: 'brk:South Ossetia', size: 20, from: c5.sos + 0.2, to: c5.cis},
  {text: 'NAGORNO-KARABAKH', at: 'brk:Nagorno-Karabakh', size: 20, from: c5.nk + 0.2, to: c5.cis, sub: 'until 2023'},
  {text: 'TRANSNISTRIA', at: 'brk:Transnistria', size: 20, from: c5.tr + 0.2, to: c5.cis},
];

export const MARKERS: Marker[] = [
  {city: 'Moscow', label: 'Moscow', from: h.endUp - 0.1, to: h.why + 0.2},
  {city: 'Kyiv', label: 'Ukraine', sub: '1917–1921', from: c1.broke - 0.6, to: c1.lenin + 0.5},
  {city: 'Tbilisi', label: 'Georgia', sub: '1918–1921', from: c1.broke - 0.3, to: c1.lenin + 0.5},
  {city: 'Yerevan', label: 'Armenia', sub: '1918–1920', from: c1.broke, to: c1.lenin + 0.5, side: 'l'},
  {city: 'Baku', label: 'Azerbaijan', sub: '1918–1920', from: c1.broke + 0.3, to: c1.lenin + 0.5},
  {city: 'Moscow', label: 'Russian SFSR', from: c1.rus, to: c1.reality},
  {city: 'Kharkiv', label: 'Ukrainian SSR', sub: 'capital Kharkiv', from: c1.ukr, to: c1.reality},
  {city: 'Minsk', label: 'Byelorussian SSR', from: c1.blr, to: c1.reality, side: 'l'},
  {city: 'Tbilisi', label: 'Transcaucasian SFSR', from: c1.tsf, to: c1.reality},
  {city: 'Sukhumi', from: c1.capital, to: c1.shell + 0.8}, {city: 'Tskhinvali', from: c1.capital + 0.2, to: c1.shell + 0.8},
  {city: 'Stepanakert', from: c1.capital + 0.4, to: c1.shell + 0.8},
  {city: 'Kazan', from: c2.look + 0.5, to: c2.practice + 0.5},
  {city: 'Moscow', label: 'Coup attempt', sub: '19–21 August 1991', from: c4.aug91 + 0.6, to: c4.weeks, pulse: true, color: COL.RED},
  {city: 'Viskuli', label: 'Viskuli hunting lodge', sub: 'Belovezha Forest', from: c4.lodge - 0.4, to: c4.dec21, pulse: true},
  {city: 'Almaty', label: 'Alma-Ata', sub: '21 December 1991', from: c4.dec21 + 0.4, to: c4.four, pulse: true},
  {city: 'Kazan', from: c5.tatar + 0.4, to: c5.chech},
  {city: 'Grozny', from: c5.chech + 9.2, to: c5.abkh},
];

// independence order (declarations): Lithuania 11 Mar 1990, Georgia 9 Apr 1991, then Aug-Dec 1991
const ORDER: [string, string][] = [['GEO', '9 Apr 1991'], ['EST', '20 Aug 1991'], ['LVA', '21 Aug 1991'], ['UKR', '24 Aug 1991'],
  ['BLR', '25 Aug 1991'], ['MDA', '27 Aug 1991'], ['AZE', '30 Aug 1991'], ['KGZ', '31 Aug 1991'], ['UZB', '31 Aug 1991'],
  ['TJK', '9 Sep 1991'], ['ARM', '23 Sep 1991'], ['TKM', '27 Oct 1991']];
export const FLAGS: Flag[] = [
  // hook: fifteen new nations
  ...ISO15.map((i, k) => ({iso: i, t: h.fifteen + k * 0.13, to: h.strange + 0.3} as Flag)),
  {iso: 'EST', t: h.became - 0.1, to: h.chech - 0.3},
  // 1990-1991
  {iso: 'LTU', t: c4.lith + 0.2, to: END, date: '11 Mar 1990'},
  ...ORDER.map(([i, d], k) => ({iso: i, t: c4.rar + 0.2 + k * 0.32, to: END, date: d} as Flag)),
  {iso: 'KAZ', t: c4.dec21 + 0.6, to: END, date: '16 Dec 1991'},
  {iso: 'RUS', t: c4.resigned + 0.5, to: END, date: 'successor state'},
];
export const FLAG_HIDE: [number, number][] = [[c5.s - 0.5, END + 1]];   // flags hidden while the film looks inside

// ======================= OVERLAY CARDS =======================
export const CARDS: Card[] = [
  {kind: 'chapter', num: 'I', text: 'THE NESTING DOLL', from: cs(1) + 0.1, to: cs(1) + 3.6},
  {kind: 'date', text: '30 DECEMBER 1922', sub: 'TREATY ON THE CREATION OF THE USSR', from: c1.dec30, to: c1.paper},
  {kind: 'chapter', num: 'II', text: "STALIN'S THREE RULES", from: cs(2) + 0.1, to: cs(2) + 3.6},
  {kind: 'date', text: '5 DECEMBER 1936', sub: 'THE "STALIN CONSTITUTION"', from: c2.y1936, to: c2.eleven},
  {kind: 'chapter', num: 'III', text: 'SIXTEEN BECOMES FIFTEEN', from: cs(3) + 0.1, to: cs(3) + 3.6},
  {kind: 'date', text: '1940', sub: 'ANNEXATIONS IN THE WEST', from: c3.y1940, to: c3.kf},
  {kind: 'date', text: '16 JULY 1956', sub: 'KARELO-FINNISH SSR DOWNGRADED', from: c3.y1956, to: c3.became + 1.0},
  {kind: 'date', text: '19 FEBRUARY 1954', sub: 'CRIMEA TRANSFERRED TO THE UKRAINIAN SSR', from: c3.y1954 + 0.3, to: c3.detail + 1.0},
  {kind: 'chapter', num: 'IV', text: 'THE COLLAPSE', from: cs(4) + 0.1, to: c4.gorby + 0.35},
  {kind: 'date', text: '23 AUGUST 1989', sub: 'THE BALTIC WAY · ~2 MILLION PEOPLE · 675 KM', from: c4.aug89, to: c4.mar90},
  {kind: 'date', text: '11 MARCH 1990', sub: 'LITHUANIA RESTORES INDEPENDENCE', from: c4.mar90, to: c4.law},
  {kind: 'date', text: '17 MARCH 1991', sub: 'ALL-UNION REFERENDUM · SIX REPUBLICS BOYCOTT', from: c4.mar91, to: c4.aug91},
  {kind: 'date', text: '19–21 AUGUST 1991', sub: 'THE AUGUST COUP', from: c4.aug91, to: c4.weeks},
  {kind: 'date', text: '6 SEPTEMBER 1991', sub: 'MOSCOW RECOGNIZES THE BALTIC STATES', from: c4.sept, to: c4.dec1},
  {kind: 'date', text: '1 DECEMBER 1991', sub: 'UKRAINIAN INDEPENDENCE REFERENDUM', from: c4.dec1, to: c4.week},
  {kind: 'date', text: '8 DECEMBER 1991', sub: 'BELOVEZHA ACCORDS', from: c4.week, to: c4.dec21},
  {kind: 'date', text: '21 DECEMBER 1991', sub: 'ALMA-ATA PROTOCOL · 11 REPUBLICS', from: c4.dec21, to: c4.four},
  {kind: 'date', text: '25 DECEMBER 1991', sub: 'GORBACHEV RESIGNS', from: c4.four, to: c4.shells + 1},
  {kind: 'chapter', num: 'V', text: 'THE DOLLS INSIDE', from: c4.e + 1.25, to: c5.dolls + 1.75},
  {kind: 'date', text: '30 AUGUST 1990', sub: 'TATARSTAN DECLARES SOVEREIGNTY', from: c5.tatar, to: c5.sixty},
  {kind: 'date', text: '21 MARCH 1992', sub: 'REFERENDUM · 61.4% FOR SOVEREIGN STATUS', from: c5.sixty, to: c5.treaty},
  {kind: 'date', text: '15 FEBRUARY 1994', sub: 'POWER-SHARING TREATY WITH MOSCOW', from: c5.treaty, to: c5.chech},
  {kind: 'date', text: '1 NOVEMBER 1991', sub: 'CHECHNYA DECLARES INDEPENDENCE', from: c5.nov91, to: c5.wars},
  {kind: 'callout', text: 'NO BROAD INTERNATIONAL RECOGNITION', from: c5.none + 0.2, to: c5.cis, at: [960, 930]},
  {kind: 'quote', text: '“…recognizing and respecting each other’s territorial integrity and the inviolability of existing borders.”', sub: 'Alma-Ata Declaration, 21 December 1991', from: c5.cis + 0.2, to: c5.uti - 0.2},
  {kind: 'strike', text: 'LANGUAGE|RELIGION|HISTORY', from: c6.lang - 0.2, to: c6.seams + 1.5},
  {kind: 'quote', text: '“Each Union Republic shall retain the right freely to secede from the USSR.”', sub: 'Only on paper — and only on the edge of the map', from: c6.paper - 0.4, to: c6.edge + 0.6},
  {kind: 'title', text: 'EXACTLY 15 COUNTRIES', from: c6.why, to: c6.e + 2.5},
  {kind: 'end', text: 'WHY THE SOVIET UNION BROKE INTO EXACTLY 15 COUNTRIES', sub: 'Sources: Constitution of the USSR (1936, 1977) · 1939 & 1989 Soviet censuses · Alma-Ata Declaration (1991) · Natural Earth · historical-basemaps', from: c6.e + 2.5, to: END},
];

export const PORTRAITS: Portrait[] = [];   // v2: archival cut-outs (v2.ts CUTOUTS)

// ======================= VIDEO CLIPS =======================
const MAN = (s: string) => `manim/${s}.webm`;
export const CLIPS: Clip[] = [
  // matryoshka (Hunyuan3D-2 mesh, Blender): idle, then three openings synced to the narration
  {kind: 'doll', src: 'matryoshka.webm', from: c1.reality - 0.2, to: c1.y1989 + 0.4, steps: [
    {at: c1.reality - 0.2, s0: 0, s1: 34 / 30}, {at: c1.inside, s0: 34 / 30, s1: 112 / 30},
    {at: c1.those, s0: 112 / 30, s1: 190 / 30}, {at: c1.districts, s0: 190 / 30, s1: 330 / 30}]},
  {kind: 'doll', src: 'matryoshka.webm', from: c5.dolls + 1.45, to: c5.tatar + 0.5, steps: [{at: c5.dolls + 1.45, s0: 320 / 30, s1: 330 / 30}]},
  {kind: 'cauc', src: 'caucasus.mp4', from: c5.chech - 0.3, to: c5.chech + 9.6, steps: [{at: c5.chech - 0.3, s0: 0, s1: 9.9}]},
  // v2: Manim documents (Article 72, uti possidetis) and the Blender flag-lowering callback at the resignation
  {kind: 'cauc', src: 'clips/article72.mp4', from: c4.sudden - 0.1, to: c4.aug89 - 0.3, steps: [{at: c4.sudden - 0.1, s0: 0, s1: 6.25, rate: 1.25}]},
  {kind: 'cauc', src: 'clips/uti.mp4', from: c5.uti - 0.3, to: c5.legal - 0.2, steps: [{at: c5.uti - 0.3, s0: 0, s1: 8.05}]},
  {kind: 'cauc', src: 'clips/opening.mp4', from: c4.resigned - 0.15, to: c4.shells - 0.1, steps: [{at: c4.resigned - 0.15, s0: 6.3, s1: 9.3}]},
  {kind: 'doll', src: 'matryoshka.webm', from: c6.moment - 0.2, to: c6.why + 0.2, steps: [{at: c6.moment - 0.2, s0: 320 / 30, s1: 330 / 30}]},
];
export const DOLL_LABELS = [
  {text: 'UNION REPUBLICS', k: 0, from: c1.top, to: c1.y1989 + 0.4}, {text: 'AUTONOMOUS REPUBLICS', k: 1, from: c1.inside + 1.8, to: c1.y1989 + 0.4},
  {text: 'AUTONOMOUS REGIONS', k: 2, from: c1.those + 1.8, to: c1.y1989 + 0.4}, {text: 'AUTONOMOUS DISTRICTS', k: 3, from: c1.districts + 1.8, to: c1.y1989 + 0.4},
  {text: 'COULD LEAVE', k: 0, from: c6.outer, to: c6.why + 0.2},
];
export const CHART = {from: -10, to: -9};   // v2: no charts (banners carry the numbers)
export const FLAGPOLE = {from: -10, lower: -9.8, lowered: -9.6, raise: -9.4, to: -9.2,
  from2: -10, lower2: -9.8, raise2: -9.6, to2: -9.4};   // v2: Blender callback clip instead

// ======================= MUSIC & SFX =======================
export const MUSIC = [
  {src: 'music/music_c1_hook.mp3', from: 0, to: cs(1) + 1.5, lufs: -9.5},
  {src: 'music/music_c2_origins.mp3', from: cs(1) - 0.3, to: ce(2) + 1.6, lufs: -11.3},
  {src: 'music/music_c3_annex.mp3', from: cs(3) - 0.4, to: ce(3) + 1.6, lufs: -15.3},
  {src: 'music/music_c4_collapse.mp3', from: cs(4) - 0.4, to: ce(4) + 1.6, lufs: -11.8},
  {src: 'music/music_c5_resolution.mp3', from: cs(5) - 0.4, to: END, lufs: -9.5},
];
// v2 hook Foley (sfx2.py: bell_toll, bell_small, wind_bed, cloth_flap, wood_thunk, war_rumble, forge_hiss, swell)
const HOOK_SFX: Sfx[] = [
  {f: 'bell_toll', t: 0.0, v: 0.6}, {f: 'wind_bed', t: 0.0, v: 0.5},
  {f: 'cloth_flap', t: 0.25, v: 0.32}, {f: 'cloth_flap', t: 1.7, v: 0.28}, {f: 'cloth_flap', t: 3.2, v: 0.3},
  {f: 'shimmer', t: h.y91 - 0.05, v: 0.25}, {f: 'whoosh_1', t: OPENING.kremlinIn - 0.1, v: 0.3},
  {f: 'bell_toll', t: OPENING.lower + 0.05, v: 0.45}, {f: 'cloth_flap', t: OPENING.lower + 0.4, v: 0.25},
  {f: 'bell_small', t: OPENING.lowered - 0.5, v: 0.3},
  {f: 'line_draw', t: h.gone - 0.2, v: 0.3}, {f: 'shimmer', t: h.patch, v: 0.3},
  {f: 'wood_thunk', t: h.tatar + 0.25, v: 0.5}, {f: 'cloth_flap', t: h.tatar + 0.35, v: 0.35},
  {f: 'wood_thunk', t: h.est1 + 0.15, v: 0.5}, {f: 'cloth_flap', t: h.est1 + 0.25, v: 0.35},
  {f: 'stamp', t: h.tatarNot, v: 0.4},
  {f: 'wood_thunk', t: h.chech + 0.2, v: 0.5}, {f: 'cloth_flap', t: h.chech + 0.3, v: 0.35},
  {f: 'war_rumble', t: h.two - 0.2, v: 0.5}, {f: 'line_draw', t: h.endUp + 0.1, v: 0.3},
  {f: 'tick', t: h.f15, v: 0.45}, {f: 'tick', t: h.twenty, v: 0.45}, {f: 'tick', t: h.fifty, v: 0.45},
  {f: 'paper', t: h.written - 0.1, v: 0.4}, {f: 'whoosh_2', t: h.joseph - 0.3, v: 0.3},
  {f: 'swell', t: h.title - 3.0, v: 0.5}, {f: 'boom', t: h.title, v: 0.6}, {f: 'drone_hit', t: h.ff, v: 0.35},
];
const V2_SFX: Sfx[] = [
  ...BANNERS.filter((b) => b.from > 40).flatMap((b) => [{f: 'wood_thunk', t: b.from + 0.2, v: 0.45}, {f: 'cloth_flap', t: b.from + 0.3, v: 0.3}]),
  ...ICONS.filter((i) => i.from > 42).map((i) => ({f: 'pop', t: i.from, v: 0.35})),
  ...DOCS.filter((d) => d.from > 50).map((d) => ({f: 'paper', t: d.from, v: 0.4})),
  ...CUTOUTS.filter((c) => c.from > 52).map((c) => ({f: 'whoosh_3', t: c.from - 0.15, v: 0.28})),
  ...NUMERALS.filter((n) => n.from > 46).map((n) => ({f: 'tick', t: n.from + 0.05, v: 0.45})),
  ...TAGS.map((g) => ({f: 'stamp', t: g.from + 0.15, v: 0.35})),
  {f: 'line_draw', t: CHAIN.from, v: 0.3}, {f: 'crowd_bed', t: CHAIN.from - 0.4, v: 0.3},
  {f: 'forge_hiss', t: c5.lines + 0.1, v: 0.45}, {f: 'war_rumble', t: c5.chech + 9.6, v: 0.4}, {f: 'bell_toll', t: c4.resigned - 0.1, v: 0.45},
];
const whooshes: Sfx[] = CAMERA.filter((k) => (k.dur ?? 2) > 1.5 && (k.dur ?? 2) <= 3.2 && k.t > 1).map((k, i) => ({f: `whoosh_${(i % 3) + 1}`, t: k.t - 0.15, v: 0.24}));
export const SFX: Sfx[] = [
  ...whooshes,
  ...FLAGS.map((f) => ({f: 'flag_drop', t: f.t + 0.42, v: 0.38})),
  ...CARDS.filter((c) => c.kind === 'chapter').map((c) => ({f: 'boom', t: c.from, v: 0.45})),
  ...CARDS.filter((c) => c.kind === 'date').map((c) => ({f: 'paper', t: c.from, v: 0.35})),
  ...CARDS.filter((c) => c.kind === 'big').map((c) => ({f: 'tick', t: c.from + 0.05, v: 0.5})),
  ...HOOK_SFX, ...V2_SFX, {f: 'pop', t: c1.rus, v: 0.3}, {f: 'pop', t: c1.ukr, v: 0.3}, {f: 'pop', t: c1.blr, v: 0.3},
  {f: 'pop', t: c1.tsf, v: 0.3}, {f: 'shimmer', t: c1.inside + 1.2, v: 0.25}, {f: 'shimmer', t: c1.those + 1.2, v: 0.25},
  {f: 'shimmer', t: c1.districts + 1.2, v: 0.25}, {f: 'line_draw', t: c1.shell + 0.2, v: 0.3}, {f: 'pop', t: c2.uzb, v: 0.3},
  {f: 'pop', t: c2.tjk, v: 0.3}, {f: 'pop', t: c2.kaz, v: 0.3}, {f: 'line_draw', t: c2.first + 0.3, v: 0.3},
  {f: 'shimmer', t: c2.look + 0.2, v: 0.3}, {f: 'stamp', t: c2.rule1 + 2.0, v: 0.3}, {f: 'line_draw', t: c2.volga, v: 0.25},
  {f: 'pop', t: c3.est, v: 0.3}, {f: 'pop', t: c3.lva, v: 0.3}, {f: 'pop', t: c3.mda, v: 0.3}, {f: 'pop', t: c3.kf, v: 0.3},
  {f: 'shimmer', t: c3.transferred + 0.2, v: 0.35}, {f: 'line_draw', t: c3.nobody + 0.6, v: 0.3},
  {f: 'crowd_bed', t: c4.hands - 0.5, v: 0.22}, {f: 'line_draw', t: c4.hands - 0.3, v: 0.3}, {f: 'drone_hit', t: c4.aug91, v: 0.35},
  {f: 'stamp', t: c4.six + 0.4, v: 0.3}, {f: 'shimmer', t: c4.ninety, v: 0.3}, {f: 'boom', t: c4.states, v: 0.4},
  {f: 'shimmer', t: c5.sixty, v: 0.25}, {f: 'drone_hit', t: c5.wars, v: 0.3}, {f: 'stamp', t: c5.none + 0.3, v: 0.35},
  {f: 'line_draw', t: c5.lines, v: 0.3}, {f: 'riser', t: c6.why - 2.4, v: 0.3}, {f: 'boom', t: c6.why + 0.1, v: 0.45},
];
