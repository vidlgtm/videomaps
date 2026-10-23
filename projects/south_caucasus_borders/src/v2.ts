import {cue as C, cs, ce} from './lib/cues';
import {OFF} from './types';
import type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain, OpeningSpec} from './types';
export type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain} from './types';

const p0 = {s:cs(0), three:C(0,'Three countries'), puzzle:C(0,'The region looks like a puzzle'), key:C(0,'The key is that'), e:ce(0)};
const p1 = {s:cs(1), south:C(1,'South of its crest'), border:C(1,'A border drawn'), e:ce(1)};
const p2 = {s:cs(2), early:C(2,'In the early nineteenth century'), gul:C(2,'The Treaty of Gulistan'), 1813:C(2,'eighteen thirteen'), turk:C(2,'Treaty of Turkmenchay'), aras:C(2,'The Aras River'), e:ce(2)};
const p3 = {s:cs(3), collapsed:C(3,'The Russian Empire collapsed'), republics:C(3,'independent republics emerged'), soviet:C(3,'Then Soviet rule spread'), e:ce(3)};
const p4 = {s:cs(4), kars:C(4,'the Treaty of Kars'), nakh:C(4,'Nakhchivan'), karabakh:C(4,'Nagorno-Karabakh'), dissolved:C(4,'When that union dissolved'), e:ce(4)};
const p5 = {s:cs(5), patch:C(5,'look like a patchwork'), aras:C(5,'The Aras still marks'), e:ce(5)};
const p6 = {s:cs(6), question:C(6,'Who controlled this land'), answer:C(6,'The answer changes'), e:ce(6)};
export const P={p0,p1,p2,p3,p4,p5,p6};
export const OPENING: OpeningSpec={clip:null,mapIn:p0.three+0.15,end:p0.three+1.4,textOut:p0.key,rule:p0.puzzle,bloom:0.34,lines:[
 {text:'THREE COUNTRIES',from:p0.three,kind:'kicker'},
 {text:'ONE MOUNTAIN CROSSROADS',from:p0.puzzle,kind:'year'},
 {text:'SOUTH CAUCASUS',from:p0.key,kind:'place'}]};
export const BANNERS: Banner[]=[];
export const ICONS: Icon[]=[{name:'treaty_scroll',az:35,at:[46.3,40.3],from:p2.gul,to:p2.e,size:0.8}];
export const DOTS: Dot[]=[]; export const DOT_COL=['#FFD36B','#FFFFFF','#8FD3FF','#B9F28C']; export const DOT_SHOWS:DotShow[]=[];
export const DOCS:Doc[]=[]; export const CUTOUTS:Cutout[]=[]; export const NUMERALS:Numeral[]=[]; export const ARROWS:Arrow[]=[]; export const TAGS:Tag[]=[];
export const CHAIN:Chain={pts:[],from:OFF,dur:0,to:OFF};
export const TITLE:{from:number;to:number;lines:TitleLine[]}={from:p6.answer,to:p6.e+3,lines:[
 {text:'THE SOUTH CAUCASUS',from:p6.answer},{text:'BORDERS, LAYER BY LAYER',from:p6.answer+0.7},{text:'WHO DREW THIS LINE?',from:p6.answer+1.4,hi:'LINE'}]};
export const CREDITS={from:p6.e+0.5,lines:[
 'Historical sources: Encyclopaedia Britannica · Treaty texts · Wikimedia Commons',
 'Imagery and boundaries: Natural Earth · NASA · EOX Sentinel-2 (CC BY 4.0) · Narration: synthetic voice · Music: original score']};
export const STAR={from:OFF}; export const STAR_TARGETS:[string,number,number][]=[]; export const DEPTH_IDS:string[]=[];
export const LIGHTS={from:OFF,off0:OFF,off1:OFF,lift0:OFF,lift1:OFF}; export const CITY_LIGHTS:[number,number,number][]=[];
