// Opening (hook) text layer of our films: optional full-frame clip (e.g. a Blender/Kaggle hero shot in public/clips/),
// the date/kicker typeset letter by letter on the dark left third, a gold rule, an italic place line, then a light-bloom
// dissolve into the map. Everything is data: OPENING in src/v2.ts (project). clip = null -> text over the globe/map.
import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {OPENING} from '../v2';
import {clamp, easeOut, env, lerp, prog} from '../lib/anim';
import {FONTS} from '../fonts';

const Letters: React.FC<{text: string; t: number; from: number; step: number; style: React.CSSProperties}> = ({text, t, from, step, style}) => (
  <div style={style}>
    {text.split('').map((ch, i) => {
      const k = easeOut(prog(t, from + i * step, 0.55));
      return (
        <span key={i} style={{display: 'inline-block', opacity: k, transform: `translateY(${(1 - k) * 18}px)`, filter: `blur(${(1 - k) * 6}px)`,
          whiteSpace: 'pre'}}>{ch}</span>
      );
    })}
  </div>
);

const STYLE: Record<string, React.CSSProperties> = {
  kicker: {fontFamily: FONTS.head, fontWeight: 700, fontSize: 50, letterSpacing: '0.3em', color: '#F1DFAE', textShadow: '0 3px 14px rgba(0,0,0,0.9)'},
  year: {fontFamily: FONTS.head, fontWeight: 800, fontSize: 132, letterSpacing: '0.16em', color: '#E9C46A', marginTop: -6,
    textShadow: '0 5px 26px rgba(0,0,0,0.85)'},
  place: {fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 31, color: '#E4E9F0', letterSpacing: '0.08em', marginTop: 14,
    textShadow: '0 2px 10px rgba(0,0,0,0.9)'},
};
const STEP: Record<string, number> = {kicker: 0.045, year: 0.07, place: 0.022};

export const Opening: React.FC<{t: number}> = ({t}) => {
  if (t > OPENING.end || (!OPENING.clip && !OPENING.lines.length)) return null;
  const x = clamp((t - OPENING.mapIn) / Math.max(0.1, OPENING.end - OPENING.mapIn));
  const textO = env(t, 0, OPENING.textOut, 0.01, 0.6);
  const rule = OPENING.rule !== undefined ? easeOut(prog(t, OPENING.rule, 0.8)) : 0;
  const lines = OPENING.lines;
  const ruleAfter = lines.findIndex((l) => l.kind === 'year');
  return (
    <AbsoluteFill style={{opacity: OPENING.clip ? 1 - x * x : 1}}>
      {OPENING.clip ? (
        <OffthreadVideo src={staticFile(OPENING.clip)} muted
          style={{width: 1920, height: 1080, filter: `blur(${x * 9}px) brightness(${1 + x * 0.6})`, transform: `scale(${1 + x * 0.05})`}} />
      ) : null}
      <AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 30%, rgba(0,0,0,0) 45%)', opacity: textO}} />
      <div style={{position: 'absolute', left: 120, top: 360, opacity: textO}}>
        {lines.map((l, i) => (
          <React.Fragment key={i}>
            <Letters text={l.text} t={t} from={l.from - 0.08} step={l.step ?? STEP[l.kind]} style={STYLE[l.kind]} />
            {i === ruleAfter && OPENING.rule !== undefined ? (
              <div style={{width: lerp(0, 420, rule), height: 2, marginTop: 6, background: 'linear-gradient(90deg,#E9C46A,rgba(233,196,106,0))'}} />
            ) : null}
          </React.Fragment>
        ))}
      </div>
      {OPENING.clip ? <AbsoluteFill style={{boxShadow: 'inset 0 0 240px rgba(0,0,0,0.7)'}} /> : null}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(255,244,220,0.9), rgba(255,244,220,0) 70%)',
        opacity: Math.sin(Math.PI * x) * (OPENING.bloom ?? 0.45)}} />
    </AbsoluteFill>
  );
};
