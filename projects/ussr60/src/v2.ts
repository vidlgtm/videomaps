// PROJECT USSR60 — the 60-second test. All cues are pinned to the exact narration words.
import {cue as C, cs, ce} from './lib/cues';
import {OFF} from './types';
import type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain, OpeningSpec} from './types';
export type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain} from './types';

// ---------- cue times per paragraph (the sole word-to-time table) ----------
const p0 = {
  s: cs(0), date: C(0, 'December twenty-fifth'), redFlag: C(0, 'the red flag'),
  fell: C(0, 'fell over the Kremlin'), nextDay: C(0, 'By the next day'), gone: C(0, 'was gone'),
  fifteen: C(0, 'fifteen states'), why: C(0, 'Why exactly fifteen'), answer: C(0, 'The answer'),
  map: C(0, 'in its map'), e: ce(0),
};
const p1 = {
  s: cs(1), year: C(1, 'In nineteen twenty-two'), four: C(1, 'four republics'), union: C(1, 'formed the Union'),
  russia: C(1, 'Russia'), ukraine: C(1, 'Ukraine'), belarus: C(1, 'Belarus'), transcaucasia: C(1, 'Transcaucasia'),
  treaty: C(1, 'The treaty'), leave: C(1, 'let each leave'), smaller: C(1, 'smaller autonomous republics'),
  noExit: C(1, 'had no exit'), e: ce(1),
};
const p2 = {
  s: cs(2), year: C(2, 'In nineteen thirty-six'), stalin: C(2, 'Stalin'), tests: C(2, 'set three tests'),
  border: C(2, 'an external border'), majority: C(2, 'a compact titular majority'), million: C(2, 'over one million people'),
  tatar: C(2, 'Tatarstan'), more: C(2, 'had more people than Estonia'), estonia: C(2, 'Estonia'),
  noFrontier: C(2, 'no foreign border'), e: ce(2),
};
const p3 = {
  s: cs(3), baltic: C(3, 'The Baltic republics'), annexed: C(3, 'were annexed'), y1940: C(3, 'in nineteen forty'),
  karelo: C(3, 'Karelo-Finnish'), sixteen: C(3, 'made sixteen'), demotion: C(3, 'its nineteen fifty-six demotion'),
  restored: C(3, 'restored fifteen'), right: C(3, 'the constitutional right'), secede: C(3, 'to secede'), e: ce(3),
};
const p4 = {
  s: cs(4), year: C(4, 'In nineteen ninety-one'), fifteen: C(4, 'fifteen union republics'),
  independent: C(4, 'became independent states'), borders: C(4, 'on Soviet borders'), smaller: C(4, 'Smaller units'),
  exit: C(4, 'no matching exit'), founders: C(4, 'The founders'), seams: C(4, 'drew the seams'),
  split: C(4, 'that split the Union'), e: ce(4),
};
export const P = {p0, p1, p2, p3, p4};

// ---------- opening text over the night globe ----------
export const OPENING: OpeningSpec = {
  clip: null, mapIn: p0.nextDay - 0.2, end: p0.fifteen + 1.0, textOut: p0.fifteen + 0.6,
  rule: p0.date + 0.4, bloom: 0.38,
  lines: [
    {text: '25 DECEMBER', from: p0.date, kind: 'kicker'},
    {text: '1991', from: p0.date + 0.28, kind: 'year'},
    {text: 'THE KREMLIN · FIFTEEN NEW NATIONS', from: p0.fifteen, kind: 'place'},
  ],
};

// ---------- archival banner and Kaggle-rendered 3D icons ----------
export const BANNERS: Banner[] = [
  {at: [37.62, 55.75], img: 'archive/treaty1922.jpg', title: 'THE UNION TREATY', sub: '30 DECEMBER 1922', from: p1.treaty - 0.15, to: p1.noExit + 0.4},
];
export const ICONS: Icon[] = [
  {name: 'kremlin', az: 270, at: [37.62, 55.75], from: p0.fell - 0.2, to: p0.why + 0.25, size: 0.9},
  {name: 'matryoshka', az: 90, at: [49.12, 55.79], from: p4.founders - 0.2, to: p4.e + 1.0, size: 0.82},
];
export const DOTS: Dot[] = [];
export const DOT_COL = ['#FFD36B', '#FFFFFF', '#8FD3FF', '#B9F28C'];
export const DOT_SHOWS: DotShow[] = [];
export const DOCS: Doc[] = [];
export const CUTOUTS: Cutout[] = [];
export const NUMERALS: Numeral[] = [];
export const ARROWS: Arrow[] = [];
export const TAGS: Tag[] = [];

// ---------- original creative touch: a gold-red seam linking the treaty's four founders ----------
export const CHAIN: Chain = {
  pts: [[37.62, 55.75], [27.56, 53.9], [30.52, 50.45], [44.79, 41.72], [49.87, 40.41]],
  from: p1.union - 0.1, dur: 2.6, to: p1.e + 0.4,
};

// ---------- closing title ----------
export const TITLE: {from: number; to: number; lines: TitleLine[]} = {
  from: p4.founders - 0.35, to: ce(4) + 2.5,
  lines: [
    {text: 'WHY THE SOVIET UNION BROKE', from: p4.founders},
    {text: 'INTO EXACTLY', from: p4.seams + 0.35},
    {text: '15 COUNTRIES', from: p4.split, hi: '15', hiAt: p4.split + 0.25},
  ],
};
export const CREDITS = {from: ce(4) + 0.6, lines: [
  'Narration: platform voice · Music: original score · Archival document: 1922 Declaration and Treaty, public domain',
  'Boundaries: Natural Earth · Relief and imagery: NASA Blue Marble, AWS Terrain, EOX Sentinel-2 cloudless',
]};

// ---------- unused features switched OFF ----------
export const STAR = {from: OFF};
export const STAR_TARGETS: [string, number, number][] = [];
export const DEPTH_IDS: string[] = [];
export const LIGHTS = {from: OFF, off0: OFF, off1: OFF, lift0: OFF, lift1: OFF};
export const CITY_LIGHTS: [number, number, number][] = [];
