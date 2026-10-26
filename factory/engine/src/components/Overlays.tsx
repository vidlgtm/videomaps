import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import * as echarts from 'echarts';
import {env, clamp, ease, easeOut, prog, lerp} from '../lib/anim';
import {CARDS, PORTRAITS, CHART, DOLL_LABELS, FLAGPOLE, CLIPS, ISO15, FLAG_CODE, COL} from '../script';
import {FONTS} from '../fonts';
import cauc from '../data/caucasus_labels.json';
import doll from '../data/matryoshka_timing.json';

const GOLD = COL.GOLD;
const panel: React.CSSProperties = {background: 'linear-gradient(160deg, rgba(14,26,36,0.93), rgba(9,17,24,0.93))',
  border: `1.5px solid rgba(226,191,106,0.75)`, borderRadius: 14, boxShadow: '0 18px 50px rgba(0,0,0,0.55)'};

const DateCard: React.FC<{text: string; sub?: string; o: number; k: number; pos?: 'tl' | 'tr'}> = ({text, sub, o, k, pos}) => (
  <div style={{position: 'absolute', ...(pos === 'tr' ? {right: 64 - 30 * (1 - k), flexDirection: 'row-reverse'} : {left: 64 - 30 * (1 - k)}), top: 58, opacity: o, display: 'flex', alignItems: 'stretch'} as React.CSSProperties}>
    <div style={{width: 4, background: GOLD, borderRadius: 2, [pos === 'tr' ? 'marginLeft' : 'marginRight']: 18, boxShadow: `0 0 12px ${GOLD}`} as React.CSSProperties} />
    <div style={{...panel, padding: '14px 26px 14px 22px', borderRadius: 8}}>
      <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 40, color: '#FFF8E6', letterSpacing: '0.08em'}}>{text}</div>
      {sub ? <div style={{fontFamily: FONTS.body, fontWeight: 600, fontSize: 16, color: GOLD, letterSpacing: '0.2em', marginTop: 4}}>{sub}</div> : null}
    </div>
  </div>
);

const Chapter: React.FC<{num?: string; text: string; o: number; k: number}> = ({num, text, o, k}) => (
  <AbsoluteFill style={{opacity: o, background: 'radial-gradient(ellipse at center, rgba(6,12,18,0.55) 0%, rgba(6,12,18,0.82) 70%)',
    alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
    <div style={{fontFamily: FONTS.head, fontSize: 34, color: GOLD, letterSpacing: '0.5em', marginBottom: 18}}>{num ? `CHAPTER ${num}` : ''}</div>
    <div style={{display: 'flex', alignItems: 'center', gap: 34}}>
      <div style={{width: 160 * k, height: 1.5, background: GOLD}} />
      <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: text.length > 18 ? 74 : 92, color: '#FFF8E6', letterSpacing: `${0.06 + 0.06 * k}em`,
        textShadow: '0 6px 30px rgba(0,0,0,0.6)', whiteSpace: 'nowrap'}}>{text}</div>
      <div style={{width: 160 * k, height: 1.5, background: GOLD}} />
    </div>
  </AbsoluteFill>
);

const Quote: React.FC<{text: string; sub?: string; o: number; k: number}> = ({text, sub, o, k}) => (
  <AbsoluteFill style={{opacity: o, alignItems: 'center', justifyContent: 'center', background: 'rgba(5,10,15,0.35)'}}>
    <div style={{...panel, width: 1180, padding: '56px 80px', transform: `translateY(${18 * (1 - k)}px)`, textAlign: 'center',
      background: 'linear-gradient(160deg, rgba(30,26,20,0.95), rgba(16,14,11,0.95))'}}>
      <div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 54, lineHeight: 1.25, color: '#F7EBD0'}}>{text}</div>
      <div style={{width: 120, height: 1.5, background: GOLD, margin: '30px auto 18px'}} />
      <div style={{fontFamily: FONTS.body, fontWeight: 600, fontSize: 19, color: GOLD, letterSpacing: '0.16em', textTransform: 'uppercase'}}>{sub}</div>
    </div>
  </AbsoluteFill>
);

const Big: React.FC<{text: string; sub?: string; o: number; k: number}> = ({text, sub, o, k}) => (
  <AbsoluteFill style={{opacity: o, alignItems: 'center', justifyContent: 'center', flexDirection: 'column',
    background: 'radial-gradient(ellipse at center, rgba(5,10,15,0.5) 0%, rgba(5,10,15,0) 60%)'}}>
    <div style={{fontFamily: FONTS.head, fontWeight: 800, fontSize: 240, lineHeight: 1, color: GOLD, transform: `scale(${0.85 + 0.15 * k})`,
      textShadow: '0 0 40px rgba(226,191,106,0.45), 0 10px 40px rgba(0,0,0,0.7)'}}>{text}</div>
    {sub ? <div style={{fontFamily: FONTS.body, fontWeight: 700, fontSize: 34, color: '#FFF8E6', letterSpacing: '0.22em', textTransform: 'uppercase',
      textShadow: '0 2px 10px rgba(0,0,0,0.9)', marginTop: 8}}>{sub}</div> : null}
  </AbsoluteFill>
);

const Title: React.FC<{text: string; o: number; k: number; t: number; from: number}> = ({text, o, k, t, from}) => (
  <AbsoluteFill style={{opacity: o, alignItems: 'center', justifyContent: 'center', flexDirection: 'column',
    background: 'radial-gradient(ellipse at center, rgba(6,12,18,0.62) 0%, rgba(6,12,18,0.88) 75%)'}}>
    <div style={{fontFamily: FONTS.head, fontWeight: 800, fontSize: text.length > 30 ? 74 : 110, lineHeight: 1.12, color: '#FFF8E6', textAlign: 'center',
      maxWidth: 1500, letterSpacing: `${0.03 + 0.03 * k}em`, textShadow: '0 8px 40px rgba(0,0,0,0.7)'}}>
      {text.split(' 15 ').length > 1 ? <>{text.split(' 15 ')[0]} <span style={{color: GOLD}}>15</span> {text.split(' 15 ')[1]}</> :
        text.startsWith('EXACTLY 15') ? <>EXACTLY <span style={{color: GOLD}}>15</span> COUNTRIES</> : text}
    </div>
    <div style={{width: 700 * k, height: 2, background: GOLD, margin: '34px 0 30px', boxShadow: `0 0 14px ${GOLD}`}} />
    <div style={{display: 'flex', gap: 14}}>
      {ISO15.map((iso, i) => {
        const p = easeOut(prog(t, from + 0.5 + i * 0.07, 0.5));
        return <div key={iso} style={{opacity: p, transform: `translateY(${(1 - p) * -40}px)`, boxShadow: '0 4px 10px rgba(0,0,0,0.5)'}}>
          <Img src={staticFile(`flags/4x3/${FLAG_CODE[iso]}.svg`)} style={{width: 72, height: 54, display: 'block'}} />
        </div>;
      })}
    </div>
  </AbsoluteFill>
);

const Strike: React.FC<{text: string; o: number; t: number; from: number}> = ({text, o, t, from}) => (
  <AbsoluteFill style={{opacity: o, alignItems: 'center', justifyContent: 'center', background: 'rgba(5,10,15,0.45)'}}>
    <div style={{display: 'flex', gap: 90}}>
      {text.split('|').map((w, i) => {
        const a = easeOut(prog(t, from + i * 0.55, 0.5));
        const s = ease(prog(t, from + 1.9 + i * 0.35, 0.45));
        return <div key={w} style={{position: 'relative', opacity: a, fontFamily: FONTS.head, fontWeight: 700, fontSize: 76, color: '#FFF8E6',
          letterSpacing: '0.1em', textShadow: '0 4px 20px rgba(0,0,0,0.8)'}}>
          {w}
          <div style={{position: 'absolute', left: -10, top: '52%', height: 6, width: `calc(${s * 100}% + ${20 * s}px)`, background: COL.RED,
            borderRadius: 3, boxShadow: '0 0 12px rgba(210,67,78,0.8)'}} />
        </div>;
      })}
    </div>
  </AbsoluteFill>
);

const End: React.FC<{text: string; sub?: string; o: number}> = ({text, sub, o}) => (
  <AbsoluteFill style={{opacity: o, background: '#070d12', alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
    <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 52, color: '#FFF8E6', letterSpacing: '0.06em', textAlign: 'center', maxWidth: 1400}}>{text}</div>
    <div style={{width: 220, height: 1.5, background: GOLD, margin: '30px 0'}} />
    <div style={{fontFamily: FONTS.body, fontSize: 19, color: '#B9C2C8', maxWidth: 1300, textAlign: 'center', lineHeight: 1.6}}>{sub}</div>
  </AbsoluteFill>
);

const Callout: React.FC<{text: string; o: number; at: [number, number]}> = ({text, o, at}) => (
  <div style={{position: 'absolute', left: at[0], top: at[1], transform: 'translate(-50%,-50%)', opacity: o, ...panel, borderColor: COL.RED,
    padding: '14px 34px', fontFamily: FONTS.head, fontWeight: 700, fontSize: 30, color: '#FFF8E6', letterSpacing: '0.12em'}}>{text}</div>
);

const Portrait: React.FC<{p: any; t: number}> = ({p, t}) => {
  const o = env(t, p.from, p.to, 0.6, 0.6);
  if (o <= 0) return null;
  const k = easeOut(prog(t, p.from, 0.9));
  const left = p.side === 'left';
  const co = p.caption ? env(t, p.captionFrom, p.to, 0.5, 0.5) : 0;
  return (
    <div style={{position: 'absolute', top: 150, [left ? 'left' : 'right']: 90 - 40 * (1 - k), opacity: o, width: 430}}>
      <div style={{...panel, padding: 14, borderRadius: 6}}>
        <div style={{width: 400, height: 520, overflow: 'hidden', borderRadius: 3}}>
          <Img src={staticFile(p.img)} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'grayscale(1) sepia(0.28) contrast(1.06) brightness(0.98)',
            transform: `scale(${1.04 + 0.04 * prog(t, p.from, p.to - p.from)})`}} />
        </div>
        <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 30, color: '#FFF8E6', letterSpacing: '0.1em', marginTop: 14, textAlign: 'center'}}>{p.name}</div>
        {p.sub ? <div style={{fontFamily: FONTS.body, fontSize: 15, color: GOLD, letterSpacing: '0.12em', textAlign: 'center', marginTop: 4, textTransform: 'uppercase'}}>{p.sub}</div> : null}
      </div>
      {p.caption ? <div style={{marginTop: 16, opacity: co, ...panel, padding: '14px 18px', fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600,
        fontSize: 30, color: '#F7EBD0', textAlign: 'center', transform: `translateY(${10 * (1 - co)}px)`}}>{p.caption}</div> : null}
    </div>
  );
};

const Chart: React.FC<{t: number}> = ({t}) => {
  const o = env(t, CHART.from, CHART.to, 0.5, 0.5);
  if (o <= 0) return null;
  const g = easeOut(prog(t, CHART.from + 0.3, 1.4));
  const chart = echarts.init(null as any, null as any, {renderer: 'svg', ssr: true, width: 640, height: 470});
  chart.setOption({
    animation: false, backgroundColor: 'transparent',
    title: {text: 'POPULATION · 1989 CENSUS', left: 'center', top: 10, textStyle: {color: '#E2BF6A', fontFamily: 'Inter', fontWeight: 700, fontSize: 18, letterSpacing: 3} as any},
    grid: {left: 70, right: 40, top: 70, bottom: 60},
    xAxis: {type: 'category', data: ['Tatarstan', 'Estonia'], axisLine: {lineStyle: {color: '#8A96A0'}},
      axisLabel: {color: '#FFF8E6', fontSize: 22, fontWeight: 700, fontFamily: 'Inter'}},
    yAxis: {type: 'value', max: 4, interval: 1, axisLabel: {color: '#9AA6AE', fontSize: 16, formatter: '{value}M'}, splitLine: {lineStyle: {color: 'rgba(255,255,255,0.12)'}}},
    series: [{type: 'bar', barWidth: 120, data: [
      {value: 3.64 * g, itemStyle: {color: '#E2BF6A', borderRadius: [6, 6, 0, 0]}},
      {value: 1.57 * g, itemStyle: {color: '#5B83B5', borderRadius: [6, 6, 0, 0]}}],
      label: {show: true, position: 'top', color: '#FFF8E6', fontSize: 26, fontWeight: 800, fontFamily: 'Inter', formatter: (p: any) => `${p.value.toFixed(2)}M`}}],
  });
  const svg = chart.renderToSVGString();
  chart.dispose();
  return (
    <div style={{position: 'absolute', left: 90, top: 200, opacity: o, ...panel, padding: 10, transform: `translateX(${-30 * (1 - g)}px)`}}>
      <div dangerouslySetInnerHTML={{__html: svg}} />
      <div style={{fontFamily: FONTS.body, fontSize: 15, color: '#9AA6AE', textAlign: 'center', marginTop: -6, marginBottom: 6}}>
        Tatar ASSR 3,641,742 · Estonian SSR 1,565,662
      </div>
    </div>
  );
};

/** label positions under the four dolls in the final line-up (Blender camera: 50 mm, distance ~9.3) */
const dollX = (k: number) => {
  const xs = (doll as any).xs as number[];
  const xc = (xs[0] + xs[xs.length - 1]) / 2;
  return 960 + (xs[k] - xc) * 292;
};
const DollLabels: React.FC<{t: number}> = ({t}) => (
  <div style={{position: 'absolute', right: 110, top: 300, display: 'flex', flexDirection: 'column', gap: 26}}>
    {DOLL_LABELS.map((d, i) => {
      const o = env(t, d.from, d.to, 0.5, 0.5);
      if (o <= 0) return null;
      const k = easeOut(prog(t, d.from, 0.7));
      return <div key={i} style={{opacity: o, transform: `translateX(${30 * (1 - k)}px)`, display: 'flex', alignItems: 'center', gap: 18}}>
        <div style={{width: 46, height: 46, borderRadius: '50%', border: `2px solid ${GOLD}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: FONTS.head, fontWeight: 700, fontSize: 22, color: GOLD, background: 'rgba(10,18,26,0.85)'}}>{d.k + 1}</div>
        <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 30 - d.k * 2, color: d.k === 0 ? GOLD : '#FFF8E6', letterSpacing: '0.1em',
          textShadow: '0 2px 10px rgba(0,0,0,0.9)', whiteSpace: 'nowrap'}}>{d.text}</div>
      </div>;
    })}
  </div>
);

const Flagpole: React.FC<{t: number}> = ({t}) => {
  const F = FLAGPOLE;
  const seg = (a: number, lo: number, ld: number, ra: number, to: number) => {
    const o = env(t, a, to, 0.6, 0.8);
    if (o <= 0) return null;
    const down = ease(prog(t, lo, ld - lo));
    const up = ease(prog(t, ra, 3.0));
    const top = 196, bottom = 760;
    const wave = Math.sin(t * 2.6) * 2;
    return (
      <div style={{position: 'absolute', left: 1530, top: 150, opacity: o}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: 6, height: 700, background: 'linear-gradient(90deg,#d9d4c8,#8d877a)', borderRadius: 3}} />
        <div style={{position: 'absolute', left: -6, top: -10, width: 18, height: 18, borderRadius: '50%', background: '#d9c48a'}} />
        <div style={{position: 'absolute', left: 6, top: lerp(top, bottom, down) - 150, width: 210, height: 105, opacity: 1 - prog(t, ld - 0.2, 0.6),
          transform: `skewY(${wave}deg)`, transformOrigin: 'left center', boxShadow: '0 6px 16px rgba(0,0,0,0.5)'}}>
          <Img src={staticFile('flags/su.svg')} style={{width: 210, height: 105, display: 'block'}} />
        </div>
        <div style={{position: 'absolute', left: 6, top: lerp(bottom, top, up) - 150, width: 210, height: 140, opacity: prog(t, ra, 0.4),
          transform: `skewY(${-wave}deg)`, transformOrigin: 'left center', boxShadow: '0 6px 16px rgba(0,0,0,0.5)'}}>
          <Img src={staticFile('flags/4x3/ru.svg')} style={{width: 210, height: 140, display: 'block'}} />
        </div>
      </div>
    );
  };
  return <>{seg(F.from, F.lower, F.lowered, F.raise, F.to)}{seg(F.from2, F.lower2, F.lower2 + 2.0, F.raise2, F.to2)}</>;
};

// v3: priority order (first = most important); a label never leaves the frame (soft fade at the edges) and
// never covers a more important one (it is lifted on a longer stem, continuously, so nothing jumps)
const CAUC_NAMES: [string, string][] = [['Grozny', 'CHECHNYA'], ['Sukhumi', 'ABKHAZIA'], ['Tskhinvali', 'SOUTH OSSETIA'],
  ['Tbilisi', 'GEORGIA'], ['Mount Elbrus', 'Mount Elbrus'], ['CASPIAN SEA', 'Caspian Sea'], ['BLACK SEA', 'Black Sea']];
const CaucLabels: React.FC<{t: number}> = ({t}) => {
  const clip = CLIPS.find((c) => c.kind === 'cauc' && !!c.labels && t >= c.from - 0.1 && t <= c.to + 0.1);
  if (!clip) return null;
  const o = env(t, clip.from + 0.6, clip.to, 0.6, 0.5);
  if (o <= 0) return null;
  const f = Math.floor((t - clip.from) * 30);
  const tr: any = (cauc as any).tracks;
  const placed: {x0: number; x1: number; y0: number; y1: number}[] = [];
  const out: React.ReactNode[] = [];
  (((cauc as any).names?.length ? (cauc as any).names : CAUC_NAMES) as [string, string, string?][]).forEach(([k, name, st]) => {
    const a = tr[k]?.[Math.min(Math.max(f, 0), (tr[k]?.length ?? 1) - 1)];
    if (!a || !a[2]) return;
    const sea = st === 'sea' || k.includes('SEA');
    const chech = st === 'hot' || k === 'Grozny';
    const fs = chech ? 34 : sea ? 30 : 24;
    const hw = (name.length * fs * (sea ? 0.56 : 0.74)) / 2 + 8;
    const stem0 = sea ? 0 : 28;
    const h = fs * 1.25;
    const edge = clamp((a[0] - hw - 24) / 70) * clamp((1896 - hw - a[0]) / 70) * clamp((a[1] - h - stem0 - 20) / 60);
    if (edge <= 0) return;
    let lift = 0;
    for (let it = 0; it < 3; it++) {
      for (const b of placed) {
        const y1 = a[1] - stem0 - lift, y0 = y1 - h;
        const hov = Math.min(a[0] + hw, b.x1) - Math.max(a[0] - hw, b.x0);
        const vov = Math.min(y1, b.y1) - Math.max(y0, b.y0);
        if (hov > 0 && vov > 0) lift += (vov + 6) * clamp(hov / 24);
      }
    }
    const y1 = a[1] - stem0 - lift;
    placed.push({x0: a[0] - hw, x1: a[0] + hw, y0: y1 - h, y1});
    out.push(<div key={k} style={{position: 'absolute', left: a[0], top: a[1], transform: 'translate(-50%,-100%)', opacity: o * edge, textAlign: 'center',
      fontFamily: sea ? FONTS.serif : FONTS.head, fontStyle: sea ? 'italic' : 'normal', fontWeight: 700, fontSize: fs,
      color: chech ? '#FF8A80' : sea ? '#CFE9F5' : '#FFF8E6', letterSpacing: sea ? '0.04em' : '0.12em', whiteSpace: 'nowrap',
      textShadow: '0 2px 10px rgba(0,0,0,0.95)'}}>
      {name}{!sea ? <div style={{width: 1.5, height: 22 + lift, background: 'rgba(255,255,255,0.75)', margin: '6px auto 0'}} /> : null}
    </div>);
  });
  return <>{out}</>;
};

export const Overlays: React.FC<{t: number}> = ({t}) => {
  const dollOn = CLIPS.filter((c) => c.kind === 'doll' || c.kind === 'manim').reduce((m, c) => Math.max(m, env(t, c.from, c.to, 0.6, 0.6)), 0);
  return (
    <AbsoluteFill>
      {/* vignette */}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.42) 100%)'}} />
      {/* dim the map behind 3D/Manim overlays */}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(6,11,16,0.55), rgba(6,11,16,0.85))', opacity: dollOn}} />
      <Flagpole t={t} />
      {PORTRAITS.map((p, i) => <Portrait key={i} p={p} t={t} />)}
      <Chart t={t} />
      <CaucLabels t={t} />
      {CARDS.map((c, i) => {
        const o = env(t, c.from, c.to, c.kind === 'end' ? 1.2 : 0.55, c.kind === 'title' ? 1.0 : 0.55);
        if (o <= 0) return null;
        const k = easeOut(prog(t, c.from, 1.2));
        switch (c.kind) {
          case 'date': return <DateCard key={i} text={c.text} sub={c.sub} o={o} k={k} pos={c.pos} />;
          case 'chapter': return <Chapter key={i} num={c.num} text={c.text} o={o} k={k} />;
          case 'quote': return <Quote key={i} text={c.text} sub={c.sub} o={o} k={k} />;
          case 'big': return <Big key={i} text={c.text} sub={c.sub} o={o} k={k} />;
          case 'title': return <Title key={i} text={c.text} o={o} k={k} t={t} from={c.from} />;
          case 'strike': return <Strike key={i} text={c.text} o={o} t={t} from={c.from} />;
          case 'end': return <End key={i} text={c.text} sub={c.sub} o={o} />;
          case 'callout': return <Callout key={i} text={c.text} o={o} at={c.at ?? [960, 900]} />;
          default: return null;
        }
      })}
    </AbsoluteFill>
  );
};
export const DollLabelsLayer = DollLabels;
