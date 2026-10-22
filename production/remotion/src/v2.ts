// v2 visual score additions: banners on poles, 3D icons, homeland dots, documents, cut-outs, numerals, arrows, opening.
import {cue as C, cs} from './lib/cues';

export type Banner = {at: [number, number]; img: string; title: string; sub?: string; from: number; to: number; size?: number; lean?: number};
export type Icon = {name: string; az: number; at: [number, number]; from: number; to: number; size?: number};
export type Dot = {n: string; lon: number; lat: number; layer: 0 | 1 | 2 | 3};
export type DotShow = {from: number; to: number; layers: number[]; stagger?: number};
export type Doc = {img: string; from: number; to: number; side: 'l' | 'r'; cap?: string; w?: number};
export type Cutout = {img: string; name: string; sub?: string; from: number; to: number; side: 'l' | 'r'};
export type Numeral = {text: string; from: number; to: number; y?: number; size?: number; sub?: string};
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
  last: C(0, 'last time'), hours: C(0, 'Within a day'), largest: C(0, 'largest country'), gone: C(0, 'was gone'),
  stood: C(0, 'stood fifteen'), fifteen: C(0, 'fifteen new nations'), strange: C(0, 'But here is'), notB: C(0, 'not built'),
  peoples: C(0, 'fifteen peoples'), patch: C(0, 'patchwork'), hundred: C(0, 'hundred nationalities'), organized: C(0, 'organized'),
  f53: C(0, 'fifty-three'), homelands: C(0, 'official homelands'), tatar: C(0, 'Tatarstan had'), twice: C(0, 'twice'),
  est1: C(0, 'Estonia', 'start', 0), yet: C(0, 'yet Estonia'), became: C(0, 'became a country'), tatarNot: C(0, 'and Tatarstan did not'),
  not2: C(0, 'did not'), chech: C(0, 'Chechnya would'), two: C(0, 'two brutal'), wars: C(0, 'wars over'), indep: C(0, 'independence'),
  endUp: C(0, 'and end up'), moscow: C(0, "Moscow's control"), control: C(0, 'control'), why: C(0, 'So why fifteen'),
  f15: C(0, 'fifteen', 'start', 2), twenty: C(0, 'twenty'), fifty: C(0, 'fifty'), answer: C(0, 'The answer'), written: C(0, 'written'),
  joseph: C(0, 'by Lenin and Stalin'), stalin: C(0, 'Stalin themselves'), title: C(0, 'This is why'), exactly: C(0, 'exactly fifteen'),
  ff: C(0, 'fifteen countries'), c1: cs(1),
};

// ---------------- opening: night globe -> Kremlin flag lowering ----------------
export const OPENING = {kremlinIn: h.flag - 0.55, lower: h.down - 0.05, lowered: h.last + 0.55, mapIn: h.hours - 0.25, end: h.hours + 1.3};

// ---------------- banners on poles (archival photos) ----------------
export const BANNERS: Banner[] = [
  {at: [49.12, 55.79], img: 'archive/kazan.jpg', title: 'TATARSTAN', sub: '3.6 million people', from: h.tatar + 0.15, to: h.chech - 0.35},
  {at: [24.75, 59.44], img: 'archive/tallinn.jpg', title: 'ESTONIA', sub: '1.6 million people', from: h.est1 + 0.05, to: h.became - 0.1},
  {at: [45.69, 43.32], img: 'archive/grozny.jpg', title: 'CHECHNYA', sub: 'wars 1994–96 · 1999–2009', from: h.chech + 0.1, to: h.why - 0.2},
];

// ---------------- 3D icons (TripoSR meshes rendered in Blender) ----------------
export const ICONS: Icon[] = [
  {name: 'swords', az: 270, at: [48.3, 42.35], from: h.wars - 0.1, to: h.why - 0.2, size: 1.35},
  {name: 'kremlin', az: 180, at: [37.62, 55.75], from: h.endUp - 0.1, to: h.why + 0.2, size: 0.95},
];

export const DOT_SHOWS: DotShow[] = [
  {from: h.organized + 0.1, to: h.tatar - 0.3, layers: [0, 1, 2, 3], stagger: 0.32},
  {from: h.fifty - 0.05, to: h.answer + 0.6, layers: [0, 1, 2, 3], stagger: 0.06},
];

export const DOCS: Doc[] = [
  {img: 'archive/const1936.jpg', from: h.written - 0.1, to: h.joseph + 0.15, side: 'l', cap: 'THE 1936 CONSTITUTION'},
];
export const CUTOUTS: Cutout[] = [
  {img: 'archive/lenin_cut.png', name: 'VLADIMIR LENIN', sub: 'Soviet leader · 1917–1924', from: h.joseph - 0.1, to: h.title - 0.25, side: 'l'},
  {img: 'archive/stalin_cut.png', name: 'JOSEPH STALIN', sub: 'General Secretary · 1922–1952', from: h.stalin - 0.2, to: h.title - 0.25, side: 'r'},
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

// =====================================================================================================
// FULL FILM (chapters I-VI): same visual vocabulary as the hook, every element pinned to a narration word
// =====================================================================================================
export type Tag = {num?: string; text: string; from: number; to: number; slot?: number};
export type Chain = {pts: [number, number][]; from: number; dur: number; to: number};
const k1 = {
  bols: C(1, 'When the Bolsheviks'), broke: C(1, 'briefly broken free'), lenin: C(1, "Lenin's solution"), stalin: C(1, 'Ironically, Stalin'),
  overruled: C(1, 'Lenin overruled him'), dec30: C(1, 'On December 30th'), treaty: C(1, 'approved a treaty'), paper: C(1, 'On paper, it was'),
  y1989: C(1, 'By 1989'), h15: C(1, 'fifteen union republics'), h20: C(1, 'twenty autonomous republics'), h8: C(1, 'eight autonomous regions'),
  h10: C(1, 'ten autonomous districts'), layer: C(1, 'Every layer'), shell: C(1, 'But only the outer shell'),
  constit: C(1, 'The Soviet constitution guaranteed'), decades: C(1, 'For decades'), any: C(1, 'Any real attempt'), words: C(1, 'But the words were there'),
};
const k2 = {
  s: cs(2), y1936: C(2, 'Then, in 1936'), kaz: C(2, 'Kazakhstan and Kyrgyzstan'), eleven: C(2, 'That made eleven'), asked: C(2, 'When the draft constitution'),
  three: C(2, 'a nation needed three things'), first: C(2, 'First, it had'), afterAll: C(2, 'After all, Stalin argued'), second: C(2, 'Second, its namesake'),
  third: C(2, 'And third'), look: C(2, 'Now look at Tatarstan'), m16: C(2, 'one point six million'), deep: C(2, 'deep inside Russia'),
  rule1: C(2, "By Stalin's first rule"), same: C(2, 'Stalin himself used'), practice: C(2, 'In practice'), kazProm: C(2, 'Kazakhstan was promoted'),
};
const k3 = {
  y1940: C(3, 'In 1940'), est: C(3, 'annexed Estonia'), lva: C(3, 'Latvia and Lithuania'), mda: C(3, 'the Moldavian republic'), kf: C(3, 'Karelo-Finnish'),
  sixteen: C(3, 'That brought the total'), finland: C(3, 'But Finland never fell'), became: C(3, 'Sixteen became fifteen'), y1954: C(3, 'Two years earlier'),
  detail: C(3, 'At the time'),
};
const k4 = {
  s: cs(4), gorby: C(4, 'Mikhail Gorbachev'), sudden: C(4, 'Suddenly'), aug89: C(4, 'In August 1989'), mar90: C(4, 'On March 11th, 1990'),
  law: C(4, 'Moscow responded'), refs: C(4, 'demanding referendums'), twoThirds: C(4, 'two-thirds majorities'), five: C(4, 'up to five years'),
  mar91: C(4, 'In March 1991'), aug91: C(4, 'Then, in August 1991'), weeks: C(4, 'Within weeks'), dec1: C(4, 'On December 1st'),
  week: C(4, 'A week later'), lodge: C(4, 'hunting lodge'), dec21: C(4, 'On December 21st'), four: C(4, 'Four days later'),
  resigned: C(4, 'Gorbachev resigned'), shells: C(4, 'The fifteen union republics'), states: C(4, 'fifteen independent states'),
};
const k5 = {
  tatar: C(5, 'Tatarstan declared'), treaty: C(5, 'special treaty'), chech: C(5, 'Chechnya went further'), wars: C(5, 'two devastating wars'),
  abkh: C(5, 'Abkhazia, South Ossetia'), tr: C(5, 'and Transnistria'), nk: C(5, 'Nagorno-Karabakh'), none: C(5, 'None of them'), cis: C(5, 'formed their Commonwealth'),
  uti: C(5, 'uti possidetis juris'), legal: C(5, 'The fifteen union republics had'), lines: C(5, 'So the lines drawn'),
};
export const K = {k1, k2, k3, k4, k5};
const MOSCOW: [number, number] = [37.62, 55.75];

BANNERS.push(
  {at: MOSCOW, img: 'archive/redarmy.jpg', title: 'THE RED ARMY', sub: 'Moscow', from: cs(1) + 3.75, to: k1.broke - 0.4},
  {at: [34.8, 63.6], img: 'archive/gulag.jpg', title: 'THE GULAG', sub: 'White Sea Canal · 1930s', from: k1.any + 0.1, to: k1.words + 2.4},
  {at: [49.12, 55.79], img: 'archive/kazan.jpg', title: 'TATARSTAN', sub: '3.6 million people (1989)', from: k2.look + 0.25, to: k2.same - 0.3},
  {at: [24.75, 59.44], img: 'archive/tallinn.jpg', title: 'ESTONIA', sub: '1.6 million people (1989)', from: k2.m16 - 0.2, to: k2.deep - 0.3},
  {at: [34.35, 61.79], img: 'archive/winterwar.jpg', title: 'THE WINTER WAR', sub: 'Soviet-Finnish war · 1939–40', from: k3.kf + 0.3, to: k3.sixteen - 0.2},
  {at: [25.4, 57.45], img: 'archive/balticway.jpg', title: 'THE BALTIC WAY', sub: '23 August 1989', from: k4.aug89 + 0.4, to: k4.mar90 - 0.25},
  {at: [25.28, 54.69], img: 'archive/lithuania90.jpg', title: 'LITHUANIA', sub: 'Vilnius · 11 March 1990', from: k4.mar90 + 0.2, to: k4.law - 0.25},
  {at: MOSCOW, img: 'archive/tanks91.jpg', title: 'THE AUGUST COUP', sub: 'Moscow · 19–21 August 1991', from: k4.aug91 + 0.3, to: k4.weeks - 0.2},
  {at: [23.85, 52.62], img: 'archive/viskuli.jpg', title: 'VISKULI', sub: 'Belovezha Forest · 8 Dec 1991', from: k4.week + 0.3, to: k4.dec21 - 0.25},
  {at: [76.95, 43.25], img: 'archive/almaata.jpg', title: 'ALMA-ATA', sub: '21 December 1991', from: k4.dec21 + 0.3, to: k4.four - 0.1},
  {at: [49.12, 55.79], img: 'archive/kazan.jpg', title: 'TATARSTAN', sub: 'sovereignty declared 1990', from: k5.tatar + 0.3, to: k5.chech - 0.4},
  {at: [45.69, 43.32], img: 'archive/grozny.jpg', title: 'CHECHNYA', sub: 'Grozny · wars 1994–96 · 1999–2009', from: k5.chech + 9.5, to: k5.abkh - 0.35},
  {at: [41.02, 43.0], img: 'archive/sukhumi.jpg', title: 'ABKHAZIA', sub: 'Sukhumi · parliament burned 1993', from: k5.abkh + 0.3, to: k5.nk - 0.25},
  {at: [29.48, 46.83], img: 'archive/bender.jpg', title: 'TRANSNISTRIA', sub: 'Bender · 1992', from: k5.tr + 0.2, to: k5.nk - 0.25},
);
ICONS.push(
  {name: 'scroll', az: 270, at: [39.6, 55.2], from: k1.treaty, to: k1.paper + 3.0, size: 1.1},
  {name: 'kremlin', az: 180, at: MOSCOW, from: k2.practice + 0.1, to: k2.kazProm - 0.2, size: 1.1},
  {name: 'ballot', az: 270, at: MOSCOW, from: k4.mar91 + 0.4, to: k4.aug91 - 0.2, size: 1.1},
  {name: 'tank', az: 270, at: [39.5, 54.05], from: k4.aug91 + 0.7, to: k4.weeks - 0.2, size: 1.2},
  {name: 'ballot', az: 270, at: [30.52, 50.45], from: k4.dec1 + 0.3, to: k4.week - 0.2, size: 1.1},
  {name: 'scroll', az: 270, at: [52.3, 54.9], from: k5.treaty, to: k5.chech - 0.4, size: 1.1},
  {name: 'swords', az: 270, at: [47.65, 42.1], from: k5.chech + 9.7, to: k5.abkh - 0.35, size: 1.35},
  {name: 'swords', az: 270, at: [46.75, 39.82], from: k5.abkh + 0.8, to: k5.cis - 0.3, size: 1.1},
  {name: 'scroll', az: 270, at: [76.95, 43.25], from: k5.cis + 0.2, to: k5.uti - 0.3, size: 1.1},
);
DOT_SHOWS.push(
  {from: k1.h15 - 0.05, to: k1.layer - 0.3, layers: [0], stagger: 0}, {from: k1.h20 - 0.05, to: k1.layer - 0.3, layers: [1], stagger: 0},
  {from: k1.h8 - 0.05, to: k1.layer - 0.3, layers: [2], stagger: 0}, {from: k1.h10 - 0.05, to: k1.layer - 0.3, layers: [3], stagger: 0},
);
DOCS.push(
  {img: 'archive/treaty1922.jpg', from: k1.treaty - 0.2, to: k1.paper + 3.2, side: 'r', cap: 'TREATY ON THE CREATION OF THE USSR · 1922'},
  {img: 'archive/const1936_a17.jpg', from: k1.constit, to: k1.any - 0.3, side: 'r', cap: 'ARTICLE 17 · “THE RIGHT FREELY TO SECEDE”'},
  {img: 'archive/const1936.jpg', from: k2.y1936 + 0.2, to: k2.kaz + 4.5, side: 'r', cap: 'THE 1936 CONSTITUTION'},
  {img: 'archive/const1936_a13.jpg', from: k2.eleven + 0.1, to: k2.three - 0.3, side: 'r', cap: 'ARTICLE 13 · ELEVEN UNION REPUBLICS'},
  {img: 'archive/crimea1954.jpg', from: k3.y1954 + 0.6, to: k3.detail + 2.6, side: 'r', cap: '1954 · CRIMEA TRANSFERRED TO THE UKRAINIAN SSR'},
  {img: 'archive/belovezha.jpg', from: k4.lodge + 1.6, to: k4.dec21 - 0.25, side: 'r', cap: 'THE BELOVEZHA ACCORDS · 8 DECEMBER 1991'},
);
CUTOUTS.push(
  {img: 'archive/lenin_cut.png', name: 'VLADIMIR LENIN', sub: 'a union of “equal” republics', from: k1.lenin - 0.1, to: k1.dec30 - 0.3, side: 'r'},
  {img: 'archive/stalin_cut.png', name: 'JOSEPH STALIN', sub: 'Commissar for Nationalities · 1917–23', from: k1.stalin, to: k1.overruled + 1.6, side: 'l'},
  {img: 'archive/stalin_cut.png', name: 'JOSEPH STALIN', sub: 'speech of 25 November 1936', from: k2.asked, to: k2.three + 0.9, side: 'l'},
  {img: 'archive/gorbachev_cut.png', name: 'MIKHAIL GORBACHEV', sub: 'General Secretary · 1985–91', from: k4.gorby - 0.1, to: k4.sudden - 0.2, side: 'r'},
);
NUMERALS.push(
  {text: '15', sub: 'union republics', from: k1.h15 - 0.05, to: k1.h20 - 0.05, y: 760, size: 190},
  {text: '20', sub: 'autonomous republics', from: k1.h20 - 0.05, to: k1.h8 - 0.05, y: 760, size: 190},
  {text: '8', sub: 'autonomous regions', from: k1.h8 - 0.05, to: k1.h10 - 0.05, y: 760, size: 190},
  {text: '10', sub: 'autonomous districts', from: k1.h10 - 0.05, to: k1.layer - 0.3, y: 760, size: 190},
  {text: '11', sub: 'union republics', from: k2.eleven - 0.05, to: k2.asked - 0.1, y: 700, size: 220},
  {text: '16', sub: 'union republics', from: k3.sixteen + 0.9, to: k3.finland - 0.1, y: 700, size: 220},
  {text: '15', sub: 'and the number never changed again', from: k3.became - 0.05, to: k3.y1954 - 0.2, y: 700, size: 220},
  {text: '90%+', sub: 'of Ukrainian voters chose independence', from: C(4, 'ninety percent') - 0.1, to: k4.week - 0.2, y: 700, size: 200},
  {text: '15', sub: 'independent states', from: k4.states - 0.2, to: k4.states + 4.2, y: 700, size: 220},
);
ARROWS.push(
  {a: MOSCOW, b: [24.75, 59.44], t: k3.est, dur: 0.9, to: k3.kf - 0.2, color: '#C8504F', bend: 0.18},
  {a: MOSCOW, b: [24.11, 56.95], t: k3.lva, dur: 0.9, to: k3.kf - 0.2, color: '#C8504F', bend: 0.16},
  {a: MOSCOW, b: [25.28, 54.69], t: k3.lva + 0.35, dur: 0.9, to: k3.kf - 0.2, color: '#C8504F', bend: 0.14},
  {a: MOSCOW, b: [28.86, 47.0], t: k3.mda, dur: 1.0, to: k3.kf - 0.2, color: '#C8504F', bend: -0.16},
  {a: [49.12, 55.79], b: MOSCOW, t: k5.treaty + 0.1, dur: 1.0, to: k5.chech - 0.4, color: '#E8C36A', bend: 0.2},
);
export const TAGS: Tag[] = [
  {num: 'I', text: 'ON THE OUTER BORDER', from: k2.first, to: k2.second - 0.2},
  {num: 'II', text: 'A COMPACT MAJORITY', from: k2.second, to: k2.third - 0.2},
  {num: 'III', text: 'MORE THAN 1 MILLION PEOPLE', from: k2.third, to: k2.look - 0.3},
  {text: 'REFERENDUM', from: k4.refs, to: k4.mar91 - 0.3, slot: 0},
  {text: 'TWO-THIRDS MAJORITY', from: k4.twoThirds, to: k4.mar91 - 0.3, slot: 1},
  {text: 'UP TO FIVE YEARS', from: k4.five, to: k4.mar91 - 0.3, slot: 2},
];
export const CHAIN: Chain = {pts: [[24.75, 59.44], [24.42, 58.9], [24.5, 58.38], [24.36, 57.86], [24.11, 56.95], [24.19, 56.41],
  [24.36, 55.73], [24.76, 55.25], [25.28, 54.69]], from: k4.aug89 + 1.0, dur: 6.5, to: k4.mar90 - 0.2};

// archival credits (CC licences require attribution) — shown under the end card
export const CREDITS = {from: cs(6) + 36.4, lines: [
  'Archival images via Wikimedia Commons — Public domain: Lenin (1920) · Stalin · Red Army in Moscow · Treaty on the Creation of the USSR (1922) · White Sea Canal · USSR Constitution (1936) · Winter War · Transfer of Crimea (1954) · Gorbachev (1987)',
  'CC BY-SA 4.0: Kazan Kremlin — Fendes · Baltic Way — Laimonis Stīpnieks · Alma-Ata, 21 Dec 1991 — EgemenMedia   |   CC BY 4.0: Lithuania, 11 Mar 1990 — Paulius Lileikis (Lithuanian Central State Archive) · Bender 1992 — unknown author',
  'CC BY-SA 3.0: Belovezha & Viskuli, 8 Dec 1991 — Yuriy Ivanov / RIA Novosti · Grozny 1995 — Mikhail Evstafiev · Tallinn — Ivar Leidus (CC BY-SA 3.0 EE)   |   CC BY-SA 2.0: Moscow, 20 Aug 1991 — Tove Knutsen · Sukhumi — Clay Gilliland',
  'Relief: AWS Terrain Tiles (SRTM, ETOPO) · Imagery: NASA Blue Marble & Black Marble · Boundaries: Natural Earth · Narration: synthetic voice · Music: original score',
]};

// ---- v3 additions ----
// conclusion: "Lenin and Stalin built a system ..." - both founders on screen
CUTOUTS.push(
  {img: 'archive/lenin_cut.png', name: 'VLADIMIR LENIN', sub: 'Soviet leader · 1917–1924', from: C(6, 'Lenin and Stalin built') - 0.15, to: C(6, 'and in practice') - 0.1, side: 'l'},
  {img: 'archive/stalin_cut.png', name: 'JOSEPH STALIN', sub: 'General Secretary · 1922–1952', from: C(6, 'Stalin built a system') - 0.1, to: C(6, 'and in practice') - 0.1, side: 'r'},
);
/** climax: the Soviet star shatters into 15 shards, each lands on its republic's capital */
export const STAR = {from: C(4, 'The fifteen union republics') - 0.15};
export const STAR_TARGETS: [string, number, number][] = [
  ['EST', 24.75, 59.44], ['LVA', 24.11, 56.95], ['RUS', 37.62, 55.75], ['LTU', 25.28, 54.69], ['BLR', 27.56, 53.9],
  ['UKR', 30.52, 50.45], ['MDA', 28.86, 47.01], ['GEO', 44.79, 41.72], ['ARM', 44.51, 40.18], ['AZE', 49.87, 40.41],
  ['TKM', 58.38, 37.95], ['UZB', 69.24, 41.3], ['TJK', 68.79, 38.56], ['KGZ', 74.59, 42.87], ['KAZ', 76.95, 43.24],
];
