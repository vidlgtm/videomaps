import {T} from './script';
export const SOV:Record<string,string>={GEO:'GEORGIAN SSR',ARM:'ARMENIAN SSR',AZE:'AZERBAIJAN SSR'};
export const MODERN:Record<string,string>={GEO:'GEORGIA',ARM:'ARMENIA',AZE:'AZERBAIJAN'};
export const SHAPE_NAME:Record<string,string>={};
export const CTX_NAME:Record<string,string>={RUS:'RUSSIA',IRN:'IRAN',TUR:'TURKEY'};
const indep=(iso:string,t:number)=>t>=T.p6.s;
export function nameFor(id:string,t:number):string|null {if(!id.startsWith('rep:'))return SHAPE_NAME[id]??null;const iso=id.slice(4);return indep(iso,t)?MODERN[iso]??null:SOV[iso]??null;}
export const ctxNamesOn=(t:number)=>t>T.p0.s;
