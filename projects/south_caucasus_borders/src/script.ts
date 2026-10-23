import {TOTAL} from './lib/cues';
import {OFF} from './types';
import type {CamKey,Fill,Stroke,Label,Marker,Flag,Line,Ring,Card,Portrait,Clip,Sfx,Music,GlobeSpec} from './types';
import {P,ICONS,BANNERS} from './v2';
export type {CamKey,Fill,Stroke,Label,Marker,Flag,Line,Ring,Card,Portrait,Step,Clip,Sfx,Music} from './types';
export const END=TOTAL;
export const COL:Record<string,string>={GEO:'#9B4F6E',ARM:'#C98B4E',AZE:'#5C86C2',RUS:'#8E3741',IRN:'#7E9275',TUR:'#B79B63',GOLD:'#E2BF6A',INK:'#0E1A24',TXT:'#F4EFE6',TEAL:'#4FA39E'};
export const ISO15=['GEO','ARM','AZE'];
export const FLAG_CODE:Record<string,string>={GEO:'ge',ARM:'am',AZE:'az',RUS:'ru',IRN:'ir',TUR:'tr'};
export const FLAG_ASPECT:Record<string,number>={};
export const NAME:Record<string,string>={GEO:'Georgia',ARM:'Armenia',AZE:'Azerbaijan'};
export const T=P;
export const GLOBE:GlobeSpec={from:0,to:P.p0.three+1.5,tex:'globe_night_4k.jpg',overlay:null,spin:1.2,keys:[{t:0,lon:42,lat:30,dist:4.8},{t:P.p0.three,lon:45,lat:39,dist:2.2},{t:P.p0.key,lon:46,lat:40,dist:1.6}]};
const V={REGION:{lon:46.2,lat:40.7,w:1950,tilt:24},GEORGIA:{lon:44.6,lat:42,w:1050,tilt:29},EAST:{lon:47.5,lat:40,w:950,tilt:27},RIVER:{lon:46.2,lat:39.6,w:1250,tilt:29},OUT:{lon:46,lat:40.5,w:2300,tilt:22}};
const cam=(t:number,v:any,dur=2.3):CamKey=>({t,dur,...v});
export const CAMERA:CamKey[]=[cam(0,V.REGION,0.01),cam(P.p1.s,V.GEORGIA),cam(P.p2.s,V.RIVER),cam(P.p2.aras,V.EAST),cam(P.p3.s,V.REGION),cam(P.p4.s,V.EAST),cam(P.p5.s,V.RIVER),cam(P.p6.s,V.OUT,3.2)];
const countries=['rep:GEO','rep:ARM','rep:AZE'];
export const FILLS:Fill[]=countries.map((id,i)=>({id,color:[COL.GEO,COL.ARM,COL.AZE][i],op:0.42,from:P.p0.s,to:END+1,fi:1.1}));
export const STROKES:Stroke[]=[{id:'borders',color:'#FFE7A8',width:2.6,from:P.p0.s,to:END+1,draw:2.6,glow:true},{id:'frontier',color:'#F4D58A',width:2,from:P.p2.s,to:END+1,draw:1.6,glow:true}];
export const LINES:Line[]=[]; export const RINGS:Ring[]=[];
export const LABELS:Label[]=[{text:'BLACK SEA',at:[41.8,41.6],size:24,from:P.p0.s,to:END+1,italic:true},{text:'CASPIAN SEA',at:[50.2,40.7],size:24,from:P.p0.s,to:END+1,italic:true},{text:'ARAS RIVER',at:[45.5,39.5],size:20,from:P.p2.aras,to:END+1,italic:true}];
export const MARKERS:Marker[]=[{city:'Tbilisi',label:'Tbilisi',from:P.p1.s,to:END+1,side:'r'},{city:'Yerevan',label:'Yerevan',from:P.p1.s,to:END+1,side:'l'},{city:'Baku',label:'Baku',from:P.p1.s,to:END+1,side:'r'}];
export const FLAGS:Flag[]=[
 {iso:'GEO',t:P.p0.three+0.2,to:END+1,at:[44.8,41.7]},{iso:'ARM',t:P.p0.three+0.8,to:END+1,at:[44.5,40.18]},{iso:'AZE',t:P.p0.three+1.4,to:END+1,at:[49.9,40.4]},
 {iso:'RUS',t:P.p2.s+0.3,to:END+1,at:[44,44]},{iso:'IRN',t:P.p2.s+1,to:END+1,at:[47.5,37.5]},{iso:'TUR',t:P.p4.s+0.2,to:END+1,at:[40.8,40.7]}];
export const FLAG_HIDE:[number,number][]=[];
export const CARDS:Card[]=[
 {kind:'chapter',text:'A MOUNTAIN CROSSROADS',sub:'BLACK SEA · CASPIAN SEA',from:P.p1.s,to:P.p1.e,pos:'tl'},
 {kind:'date',text:'1813',sub:'TREATY OF GULISTAN',from:P.p2.gul,to:P.p2.turk,pos:'tr'},
 {kind:'date',text:'1828',sub:'TREATY OF TURKMENCHAY',from:P.p2.turk,to:P.p2.e,pos:'tr'},
 {kind:'chapter',text:'1917–1921',sub:'EMPIRE COLLAPSES · NEW REPUBLICS',from:P.p3.collapsed,to:P.p3.e,pos:'tl'},
 {kind:'date',text:'1921',sub:'TREATY OF KARS',from:P.p4.kars,to:P.p4.karabakh,pos:'tr'},
 {kind:'date',text:'1923',sub:'NAGORNO-KARABAKH AUTONOMOUS REGION',from:P.p4.karabakh,to:P.p4.dissolved,pos:'tr'},
 {kind:'chapter',text:'BORDERS CHANGE MEANING',sub:'INTERNAL LINES BECOME INTERNATIONAL',from:P.p4.dissolved,to:P.p5.s,pos:'tl'}];
export const PORTRAITS:Portrait[]=[]; export const CLIPS:Clip[]=[]; export const DOLL_LABELS:{text:string;k:number;from:number;to:number}[]=[];
export const CHART={from:OFF,to:OFF+1}; export const FLAGPOLE={from:OFF,lower:OFF+0.2,lowered:OFF+0.4,raise:OFF+0.6,to:OFF+0.8,from2:OFF,lower2:OFF+0.2,raise2:OFF+0.4,to2:OFF+0.6};
export const MUSIC:Music[]=[{src:'music/music_c1_hook.mp3',from:0,to:P.p3.s,lufs:-9.5,xin:1.2,xout:4},{src:'music/music_c5_resolution.mp3',from:P.p3.s-1.5,to:END,lufs:-9.5,xin:4,xout:3}];
export const SFX:Sfx[]=[{f:'shimmer',t:0,v:0.2},{f:'riser',t:P.p0.three-1,v:0.25},{f:'stamp',t:P.p2.gul,v:0.32},{f:'stamp',t:P.p2.turk,v:0.32},{f:'paper',t:P.p4.kars,v:0.3},{f:'flag_drop',t:P.p0.three+0.4,v:0.4},{f:'flag_drop',t:P.p0.three+1,v:0.4},{f:'flag_drop',t:P.p0.three+1.6,v:0.4},{f:'flag_drop',t:P.p2.s+0.7,v:0.4},{f:'flag_drop',t:P.p2.s+1.4,v:0.4},{f:'flag_drop',t:P.p4.s+0.6,v:0.4},...CAMERA.slice(1).map((k,i)=>({f:`whoosh_${i%3+1}`,t:k.t-0.12,v:0.2})),...ICONS.map(ic=>({f:'wood_thunk',t:ic.from+0.25,v:0.3})),...BANNERS.map(b=>({f:'cloth_flap',t:b.from+0.2,v:0.3}))];
