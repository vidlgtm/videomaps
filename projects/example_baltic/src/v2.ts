// EXAMPLE PROJECT "The Baltic Way" - billboards (banners on poles, 3D icons), documents, cut-outs, titles, opening,
// creative layers. Cue times P are defined here once and imported by script.ts.
import {cue as C, cs, ce} from './lib/cues';
import {OFF} from './types';
import type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain, OpeningSpec} from './types';
export type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain} from './types';

// ---------- cue times per paragraph (exact words of narration.json) ----------
const p0 = {s: cs(0), evening: C(0, 'On the evening'), august: C(0, 'August twenty-third'), y89: C(0, 'nineteen eighty-nine'),
  million: C(0, 'two million'), hands: C(0, 'joined hands'), drew: C(0, 'drew a living line'), three: C(0, 'three nations'),
  swallowed: C(0, 'swallowed'), e: ce(0)};
const p1 = {s: cs(1), fifty: C(1, 'Fifty years earlier'), nazi: C(1, 'Nazi Germany'), pact: C(1, 'signed a pact'),
  secret: C(1, 'secret protocol'), split: C(1, 'split Eastern Europe'), aug40: C(1, 'In August'), est: C(1, 'Estonia'),
  lva: C(1, 'Latvia'), ltu: C(1, 'Lithuania'), annexed: C(1, 'were annexed'), e: ce(1)};
const p2 = {s: cs(2), anniv: C(2, "fiftieth anniversary"), chain: C(2, 'human chain'), km: C(2, 'six hundred seventy-five'),
  tallinn: C(2, 'from Tallinn'), riga: C(2, 'through Riga'), vilnius: C(2, 'to Vilnius'), fifteen: C(2, 'For fifteen minutes'),
  held: C(2, 'held the line'), e: ce(2)};
const p3 = {s: cs(3), seven: C(3, 'Less than seven months'), ltu: C(3, 'Lithuania became'), first: C(3, 'the first Soviet republic'),
  declare: C(3, 'declare independence'), estlva: C(3, 'Estonia and Latvia'), lva: C(3, 'and Latvia'), aug91: C(3, 'in August'),
  coup: C(3, 'failed coup'), moscow: C(3, 'shook Moscow'), e: ce(3)};
const p4 = {s: cs(4), sept: C(4, 'On September sixth'), recognized: C(4, 'Moscow recognized'), all3: C(4, 'all three'),
  flags: C(4, 'Three flags were back'), europe: C(4, 'map of Europe'), e: ce(4)};
export const P = {p0, p1, p2, p3, p4};

// ---------------- opening text over the Three.js globe (script.ts GLOBE); clip = null (no hero video) ----------------
export const OPENING: OpeningSpec = {
  clip: null, mapIn: p0.hands + 0.1, end: p0.hands + 1.3, textOut: p0.hands + 0.2, rule: p0.y89 + 0.35, bloom: 0.38,
  lines: [
    {text: '23 AUGUST', from: p0.august, kind: 'kicker'},
    {text: '1989', from: p0.y89, kind: 'year'},
    {text: 'Tallinn · Riga · Vilnius · 7:00 pm', from: p0.million, kind: 'place'},
  ],
};

// ---------------- banner on a pole (archival photo, 2.5D depth parallax via DEPTH_IDS) ----------------
export const BANNERS: Banner[] = [
  {at: [27.35, 57.75], img: 'archive/balticway.jpg', title: 'THE BALTIC WAY', sub: 'about 2 million people · 675 km', from: p2.km - 0.2, to: p2.fifteen + 1.6},
];
// ---------------- 3D icon (TripoSR mesh of icons_ref/scroll.png rendered in Blender at 4 azimuths) ----------------
export const ICONS: Icon[] = [
  {name: 'scroll', az: 270, at: [26.6, 55.25], from: p3.ltu + 0.1, to: p3.estlva - 0.2, size: 0.8},
];
export const DOTS: Dot[] = [];
export const DOT_COL = ['#FFD36B', '#FFFFFF', '#8FD3FF', '#B9F28C'];
export const DOT_SHOWS: DotShow[] = [];
export const DOCS: Doc[] = [];
export const CUTOUTS: Cutout[] = [];
export const NUMERALS: Numeral[] = [];
export const ARROWS: Arrow[] = [];
export const TAGS: Tag[] = [];

// ---------------- the Baltic Way itself: a human chain drawn with Apache ECharts (SSR) along the real route ----------------
export const CHAIN: Chain = {pts: [[24.75, 59.44], [24.42, 58.9], [24.5, 58.38], [24.36, 57.86], [24.11, 56.95], [24.19, 56.41],
  [24.36, 55.93], [24.33, 55.73], [24.9, 55.25], [25.28, 54.69]], from: p2.chain - 0.1, dur: p2.vilnius + 0.8 - (p2.chain - 0.1), to: p2.e + 0.5};

// ---------------- closing title (3 lines, the last one large; hi = highlighted word) ----------------
export const TITLE: {from: number; to: number; lines: TitleLine[]} = {
  from: p4.flags - 0.2, to: ce(4) + 2.6,
  lines: [{text: 'THE BALTIC WAY', from: p4.flags - 0.1}, {text: 'TALLINN · RIGA · VILNIUS', from: p4.flags + 0.7},
    {text: '23 AUGUST 1989', from: p4.europe, hi: '1989', hiAt: p4.europe + 0.4}],
};
export const CREDITS = {from: ce(4) + 0.5, lines: [
  'Photo: The Baltic Way, 23 Aug 1989 — Laimonis Stīpnieks (CC BY-SA 4.0, Wikimedia Commons)   |   Narration: synthetic voice · Music: original score',
  'Relief: AWS Terrain Tiles (SRTM, ETOPO) · Imagery: NASA Blue Marble & Black Marble · Sentinel-2 cloudless 2016 by EOX (CC BY 4.0) · Boundaries: Natural Earth',
]};

// ---------------- features of the reference film that this project does not use: switched OFF ----------------
export const STAR = {from: OFF};
export const STAR_TARGETS: [string, number, number][] = [];
/** archive images that get a depth-cut near layer (archive/<id>_fg.png, built at prep from <id>_depth.png) */
export const DEPTH_IDS = ['balticway'];
export const LIGHTS = {from: OFF, off0: OFF, off1: OFF, lift0: OFF, lift1: OFF};
export const CITY_LIGHTS: [number, number, number][] = [];
