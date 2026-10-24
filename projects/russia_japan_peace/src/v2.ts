import {cue as C, cs, ce} from './lib/cues';
import {OFF} from './types';
import type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain, OpeningSpec} from './types';
export type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain} from './types';

const p0 = {s: cs(0), war: C(0, 'World War Two ended'), surrender: C(0, 'Japan surrendered'), occupied: C(0, 'Soviet forces occupied'), treaty: C(0, 'no formal peace treaty'), islands: C(0, 'four islands'), nineteenth: C(0, 'nineteenth century'), e: ce(0)};
const p1 = {s: cs(1), chain: C(1, 'Kuril chain'), hokkaido: C(1, 'Hokkaido'), northern: C(1, 'Northern Territories'), southern: C(1, 'Southern Kurils'), etorofu: C(1, 'Etorofu'), kunashiri: C(1, 'Kunashiri'), shikotan: C(1, 'Shikotan'), habomai: C(1, 'Habomai group'), administers: C(1, 'Russia administers'), e: ce(1)};
const p2 = {s: cs(2), first: C(2, 'first important line'), y1855: C(2, 'eighteen fifty-five'), shimoda: C(2, 'Treaty of Shimoda'), boundary: C(2, 'boundary between Etorofu and Urup'), japanese: C(2, 'Etorofu was Japanese'), urup: C(2, 'Urup'), documents: C(2, 'different documents'), e: ce(2)};
const p3 = {s: cs(3), years: C(3, 'Twenty years later'), y1875: C(3, 'eighteen seventy-five'), kuril: C(3, 'Kuril chain'), sakhalin: C(3, 'Sakhalin'), y1904: C(3, 'nineteen oh four'), y1905: C(3, 'nineteen oh five'), southern: C(3, 'southern half'), e: ce(3)};
const p4 = {s: cs(4), war: C(4, 'World War Two'), yalta: C(4, 'Yalta'), august: C(4, 'August nineteen forty-five'), order: C(4, 'General Order Number One'), september: C(4, 'September second'), control: C(4, 'Soviet control'), contested: C(4, 'contested question'), e: ce(4)};
const p5 = {s: cs(5), four: C(5, 'four southern islands'), etorofu: C(5, 'Etorofu, Kunashiri, Shikotan, and Habomai'), iturup: C(5, 'Iturup and Kunashir'), japan: C(5, 'Japan says'), russia: C(5, 'Russia says'), decide: C(5, 'does not decide'), difficult: C(5, 'peace treaty is difficult'), e: ce(5)};
const p6 = {s: cs(6), obstacle: C(6, 'next obstacle'), y1951: C(6, 'nineteen fifty-one'), sanfran: C(6, 'San Francisco Peace Treaty'), renounced: C(6, 'Japan renounced'), soviet: C(6, 'Soviet Union did not sign'), unresolved: C(6, 'unresolved'), e: ce(6)};
const p7 = {s: cs(7), dots: C(7, 'not merely dots'), okhotsk: C(7, 'Sea of Okhotsk'), fishing: C(7, 'fishing waters'), strategic: C(7, 'strategic meaning'), geography: C(7, 'geography became'), e: ce(7)};
const p8 = {s: cs(8), y1956: C(8, 'nineteen fifty-six'), declaration: C(8, 'Joint Declaration'), ended: C(8, 'ended the state of war'), article: C(8, 'Article Nine'), habomai: C(8, 'Habomai and Shikotan'), etorofu: C(8, 'Etorofu and Kunashiri'), bridge: C(8, 'final bridge'), e: ce(8)};
const p9 = {s: cs(9), conditional: C(9, 'conditional language'), four: C(9, 'all four islands'), coldwar: C(9, 'Cold War'), whichIslands: C(9, 'Which islands'), whichTreaty: C(9, 'Which treaty'), concession: C(9, 'would a concession'), e: ce(9)};
const p10 = {s: cs(10), dissolved: C(10, 'Soviet Union dissolved'), y1991: C(10, 'nineteen ninety-one'), y1993: C(10, 'nineteen ninety-three'), tokyo: C(10, 'Tokyo Declaration'), names: C(10, 'four names'), dilemma: C(10, 'same dilemma'), e: ce(10)};
const p11 = {s: cs(11), declaration: C(11, 'nineteen fifty-six declaration'), invasion: C(11, 'full-scale invasion of Ukraine'), march: C(11, 'March twenty twenty-two'), february: C(11, 'February twenty twenty-six'), august: C(11, 'August twenty twenty-six'), putin: C(11, 'Vladimir Putin'), iturup: C(11, 'Iturup'), unacceptable: C(11, 'unacceptable'), crisis: C(11, 'new crisis'), e: ce(11)};
const p12 = {s: cs(12), noTreaty: C(12, 'no peace treaty'), declaration: C(12, 'nineteen fifty-six declaration'), diplomatic: C(12, 'diplomatic relations'), embassies: C(12, 'embassies'), foundation: C(12, 'final legal foundation'), settlement: C(12, 'settlement did not'), e: ce(12)};
const p13 = {s: cs(13), century: C(13, 'century and a half'), border: C(13, 'first Russia-Japan border'), exchange: C(13, 'exchange of Sakhalin'), wars: C(13, 'two wars'), generations: C(13, 'for generations'), e: ce(13)};
const p14 = {s: cs(14), question: C(14, 'why did Russia and Japan'), occupation: C(14, 'Soviet occupation'), y1945: C(14, 'nineteen forty-five'), y1951: C(14, 'nineteen fifty-one treaty'), y1956: C(14, 'nineteen fifty-six'), controls: C(14, 'Russia controls'), claim: C(14, 'Japan maintains'), hokkaido: C(14, 'Hokkaido and Kamchatka'), e: ce(14)};
export const P = {p0, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14};

// Start on the sharp geographic map; the abstract 3D island forms were intentionally removed after review.
export const OPENING: OpeningSpec = {clip: null, mapIn: 0, end: p0.nineteenth + 0.8, textOut: p0.nineteenth + 0.1, rule: p0.treaty + 0.15, bloom: 0.20, lines: [
  {text: 'THE LAST WAR', from: p0.war + 0.1, kind: 'kicker'},
  {text: 'WITHOUT A TREATY', from: p0.treaty, kind: 'year'},
  {text: 'HOKKAIDO · KURIL ISLANDS · KAMCHATKA', from: p0.islands, kind: 'place'},
]};

export const BANNERS: Banner[] = [
  {at: [146.1, 44.4], img: 'archive/shimoda1855.jpg', title: 'TREATY OF SHIMODA', sub: '7 FEBRUARY 1855', from: p2.shimoda + 0.1, to: p2.documents - 0.25, size: 0.86},
  {at: [143.2, 48.0], img: 'archive/saint_petersburg1875.jpg', title: 'SAKHALIN FOR THE KURILS', sub: '1875', from: p3.y1875 + 0.2, to: p3.y1904 - 0.25, size: 0.8},
  {at: [34.2, 44.5], img: 'archive/yalta1945.jpg', title: 'YALTA', sub: 'FEBRUARY 1945', from: p4.yalta + 0.15, to: p4.august - 0.3, size: 0.85},
  {at: [140.7, 36.9], img: 'archive/japanese_surrender1945.jpg', title: 'JAPANESE SURRENDER', sub: '2 SEPTEMBER 1945', from: p4.september + 0.1, to: p4.e - 0.25, size: 0.78},
  {at: [141.5, 45.0], img: 'archive/yeltsin_hosokawa1993.jpg', title: 'TOKYO DECLARATION', sub: '1993', from: p10.tokyo + 0.1, to: p10.dilemma - 0.25, size: 0.85},
];
export const ICONS: Icon[] = [
  {name: 'brass_compass', az: 90, at: [145.5, 44.0], from: p2.boundary + 0.1, to: p2.documents - 0.15, size: 0.88},
  {name: 'seal_press', az: 270, at: [146.3, 44.7], from: p6.sanfran + 0.1, to: p6.unresolved - 0.2, size: 0.82},
  {name: 'telegraph_key', az: 0, at: [144.0, 43.6], from: p8.declaration + 0.1, to: p8.bridge - 0.2, size: 0.9},
];
export const DOTS: Dot[] = []; export const DOT_COL = ['#FFD36B', '#FFFFFF', '#8FD3FF', '#B9F28C']; export const DOT_SHOWS: DotShow[] = [];
export const DOCS: Doc[] = []; export const CUTOUTS: Cutout[] = []; export const NUMERALS: Numeral[] = []; export const ARROWS: Arrow[] = []; export const TAGS: Tag[] = [];
export const CHAIN: Chain = {pts: [], from: OFF, dur: 0, to: OFF};
export const TITLE: {from: number; to: number; lines: TitleLine[]} = {from: p14.controls - 0.2, to: p14.e + 3.0, lines: [
  {text: 'RUSSIA AND JAPAN', from: p14.controls - 0.1},
  {text: 'ONE UNFINISHED LINE', from: p14.claim + 0.45},
  {text: 'THE PEACE TREATY THAT NEVER CAME', from: p14.hokkaido + 0.8, hi: 'NEVER', hiAt: p14.hokkaido + 1.0},
]};
export const CREDITS = {from: p14.e + 0.5, lines: [
  'Archival photographs: World Imaging (CC BY-SA 3.0) · U.S. National Archives (Public Domain) · Ministry of Foreign Affairs of Japan (CC BY 4.0)',
  'Map imagery: NASA Blue Marble (Public Domain) · Sentinel-2 cloudless by EOX (CC BY 4.0) · Natural Earth (Public Domain) · Original music and sound design',
]};
export const STAR = {from: OFF}; export const STAR_TARGETS: [string, number, number][] = []; export const DEPTH_IDS: string[] = [];
export const LIGHTS = {from: OFF, off0: OFF, off1: OFF, lift0: OFF, lift1: OFF}; export const CITY_LIGHTS: [number, number, number][] = [];
