// v2 visual score additions: banners on poles, 3D icons, homeland dots, documents, cut-outs, numerals, arrows, opening.
import {cue as C, cs} from './lib/cues';

export type Banner = {at: [number, number]; img: string; title: string; sub?: string; from: number; to: number; size?: number; lean?: number};
export type Icon = {name: string; az: number; at: [number, number]; from: number; to: number; size?: number};
export type Dot = {n: string; lon: number; lat: number; layer: 0 | 1 | 2 | 3};
export type DotShow = {from: number; to: number; layers: number[]; stagger?: number};
export type Doc = {img: string; from: number; to: number; side: 'l' | 'r'; cap?: string; w?: number};
export type Cutout = {img: string; name: string; sub?: string; from: number; to: number; side: 'l' | 'r'};
export type Numeral = {text: string; from: number; to: number; y?: number; size?: number};
export type Arrow = {a: [number, number]; b: [number, number]; t: number; dur: number; to: number; color: string; bend?: number};
export type TitleLine = {text: string; from: number; hi?: string; hiAt?: number};

// ---------------- the 53 official national homelands of 1989 (capitals) ----------------
// layer 0: union republics (15) · 1: autonomous republics (20) · 2: autonomous regions (8) · 3: autonomous districts (10)
export const DOTS: Dot[] = [
  ...([['Moscow', 37.62, 55.76], ['Kyiv', 30.52, 50.45], ['Minsk', 27.56, 53.9], ['Tashkent', 69.28, 41.31], ['Alma-Ata', 76.89, 43.24],
    ['Tbilisi', 44.79, 41.72], ['Baku', 49.87, 40.41], ['Vilnius', 25.28, 54.69], ['Kishinev', 28.86, 47.01], ['Riga', 24.11, 56.95],
    ['Frunze', 74.59, 42.87], ['Dushanbe', 68.79, 38.56], ['Yerevan', 44.51, 40.18], ['Ashkhabad', 58.33, 37.96], ['Tallinn', 24.75, 59.44]] as const)
    .map(([n, lon, lat]) => ({n, lon, lat, layer: 0} as Dot)),
  ...([['Ufa', 55.97, 54.74], ['Ulan-Ude', 107.58, 51.83], ['Grozny', 45.69, 43.32], ['Cheboksary', 47.25, 56.13], ['Makhachkala', 47.5, 42.98],
    ['Nalchik', 43.62, 43.49], ['Elista', 44.26, 46.31], ['Petrozavodsk', 34.35, 61.79], ['Syktyvkar', 50.84, 61.67], ['Yoshkar-Ola', 47.89, 56.63],
    ['Saransk', 45.18, 54.19], ['Ordzhonikidze', 44.68, 43.02], ['Kazan', 49.12, 55.79], ['Kyzyl', 94.45, 51.72], ['Izhevsk', 53.21, 56.85],
    ['Yakutsk', 129.73, 62.03], ['Sukhumi', 41.02, 43.0], ['Batumi', 41.64, 41.64], ['Nakhichevan', 45.41, 39.21], ['Nukus', 59.6, 42.46]] as const)
    .map(([n, lon, lat]) => ({n, lon, lat, layer: 1} as Dot)),
  ...([['Maykop', 40.1, 44.61], ['Gorno-Altaysk', 85.96, 51.96], ['Birobidzhan', 132.92, 48.79], ['Cherkessk', 42.06, 44.23], ['Abakan', 91.44, 53.72],
    ['Tskhinvali', 43.97, 42.23], ['Stepanakert', 46.75, 39.82], ['Khorog', 71.55, 37.49]] as const)
    .map(([n, lon, lat]) => ({n, lon, lat, layer: 2} as Dot)),
  ...([['Aginskoye', 114.53, 51.1], ['Anadyr', 177.51, 64.73], ['Tura', 100.22, 64.27], ['Khanty-Mansiysk', 69.02, 61.0], ['Kudymkar', 54.66, 59.01],
    ['Palana', 159.95, 59.08], ['Naryan-Mar', 53.01, 67.64], ['Dudinka', 86.18, 69.4], ['Ust-Ordynsky', 104.76, 52.81], ['Salekhard', 66.6, 66.53]] as const)
    .map(([n, lon, lat]) => ({n, lon, lat, layer: 3} as Dot)),
];
export const DOT_COL = ['#FFD36B', '#FFFFFF', '#8FD3FF', '#B9F28C'];

// ---------------- cue times: chunk 0 (hook) ----------------
export const h = {
  dec: C(0, 'December'), y91: C(0, '1991'), flag: C(0, 'the red flag'), kremlin: C(0, 'Kremlin'), down: C(0, 'came down'),
  last: C(0, 'last time'), hours: C(0, 'Within hours'), largest: C(0, 'largest country'), gone: C(0, 'was gone'),
  stood: C(0, 'stood fifteen'), fifteen: C(0, 'fifteen new nations'), strange: C(0, 'But here is'), notB: C(0, 'not built'),
  peoples: C(0, 'fifteen peoples'), patch: C(0, 'patchwork'), hundred: C(0, 'hundred nationalities'), organized: C(0, 'organized'),
  f53: C(0, 'fifty-three'), homelands: C(0, 'official homelands'), tatar: C(0, 'Tatarstan had'), twice: C(0, 'twice'),
  est1: C(0, 'Estonia', 'start', 0), yet: C(0, 'yet Estonia'), became: C(0, 'became a country'), tatarNot: C(0, 'and Tatarstan did not'),
  not2: C(0, 'did not'), chech: C(0, 'Chechnya would'), two: C(0, 'two brutal'), wars: C(0, 'wars over'), indep: C(0, 'independence'),
  endUp: C(0, 'and end up'), moscow: C(0, "Moscow's control"), control: C(0, 'control'), why: C(0, 'So why fifteen'),
  f15: C(0, 'fifteen', 'start', 2), twenty: C(0, 'twenty'), fifty: C(0, 'fifty'), answer: C(0, 'The answer'), written: C(0, 'written'),
  joseph: C(0, 'Joseph'), stalin: C(0, 'Stalin himself'), title: C(0, 'This is why'), exactly: C(0, 'exactly fifteen'),
  ff: C(0, 'fifteen countries'), c1: cs(1),
};

// ---------------- opening: night globe -> Kremlin flag lowering ----------------
export const OPENING = {kremlinIn: h.flag - 0.55, lower: h.down - 0.05, lowered: h.last + 0.55, mapIn: h.hours - 0.25, end: h.hours + 1.3};

// ---------------- banners on poles (archival photos) ----------------
export const BANNERS: Banner[] = [
  {at: [49.12, 55.79], img: 'archive/kazan.jpg', title: 'TATARSTAN', sub: '3.6 million people', from: h.tatar + 0.15, to: h.chech - 0.35},
  {at: [24.75, 59.44], img: 'archive/tallinn.jpg', title: 'ESTONIA', sub: '1.6 million people', from: h.est1 + 0.05, to: h.chech - 0.35},
  {at: [45.69, 43.32], img: 'archive/grozny.jpg', title: 'CHECHNYA', sub: 'wars 1994–96 · 1999–2009', from: h.chech + 0.1, to: h.why - 0.2},
];

// ---------------- 3D icons (TripoSR meshes rendered in Blender) ----------------
export const ICONS: Icon[] = [
  {name: 'swords', az: 270, at: [46.6, 43.75], from: h.wars - 0.1, to: h.why - 0.2, size: 1.0},
  {name: 'kremlin', az: 180, at: [37.62, 55.75], from: h.endUp - 0.1, to: h.why + 0.2, size: 0.95},
];

export const DOT_SHOWS: DotShow[] = [
  {from: h.organized + 0.1, to: h.tatar - 0.3, layers: [0, 1, 2, 3], stagger: 0.32},
  {from: h.fifty - 0.05, to: h.answer + 0.6, layers: [0, 1, 2, 3], stagger: 0.06},
];

export const DOCS: Doc[] = [
  {img: 'archive/const1936.jpg', from: h.written - 0.1, to: h.title - 0.25, side: 'l', cap: 'THE 1936 CONSTITUTION'},
];
export const CUTOUTS: Cutout[] = [
  {img: 'archive/stalin_cut.png', name: 'JOSEPH STALIN', sub: 'General Secretary · 1922–1952', from: h.joseph - 0.25, to: h.title - 0.25, side: 'r'},
];
export const NUMERALS: Numeral[] = [
  {text: '53', from: h.f53 - 0.05, to: h.tatar - 0.35, y: 770, size: 200},
  {text: '15?', from: h.f15 - 0.05, to: h.twenty - 0.02}, {text: '20?', from: h.twenty - 0.02, to: h.fifty - 0.02},
  {text: '50?', from: h.fifty, to: h.answer + 0.2},
];
export const ARROWS: Arrow[] = [
  {a: [37.62, 55.76], b: [45.69, 43.32], t: h.endUp + 0.25, dur: 1.1, to: h.why + 0.2, color: '#E8C36A', bend: 0.22},
];
export const TITLE: {from: number; to: number; lines: TitleLine[]} = {
  from: h.title - 0.15, to: h.c1 - 0.25,
  lines: [{text: 'WHY THE SOVIET UNION', from: h.title - 0.1}, {text: 'BROKE INTO', from: C(0, 'broke into')},
    {text: 'EXACTLY 15 COUNTRIES', from: h.exactly, hi: '15', hiAt: h.ff}],
};
