// Opening: Blender Cycles shot (clips/opening.mp4: the red flag over the Kremlin dome, snow, lowering) with the
// date typeset letter by letter on the dark left third, then a light-bloom dissolve into the map.
import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {OPENING, h} from '../v2';
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

export const Opening: React.FC<{t: number}> = ({t}) => {
  if (t > OPENING.end) return null;
  const x = clamp((t - OPENING.mapIn) / (OPENING.end - OPENING.mapIn));
  const textO = env(t, 0, OPENING.kremlinIn + 0.5, 0.01, 0.6);
  const rule = easeOut(prog(t, h.y91 + 0.25, 0.8));
  return (
    <AbsoluteFill style={{opacity: 1 - x * x}}>
      <OffthreadVideo src={staticFile('clips/opening.mp4')} muted
        style={{width: 1920, height: 1080, filter: `blur(${x * 9}px) brightness(${1 + x * 0.6})`, transform: `scale(${1 + x * 0.05})`}} />
      <AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 30%, rgba(0,0,0,0) 45%)', opacity: textO}} />
      <div style={{position: 'absolute', left: 120, top: 360, opacity: textO}}>
        <Letters text="25 DECEMBER" t={t} from={h.dec - 0.08} step={0.045}
          style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 50, letterSpacing: '0.3em', color: '#F1DFAE', textShadow: '0 3px 14px rgba(0,0,0,0.9)'}} />
        <Letters text="1991" t={t} from={h.y91 - 0.08} step={0.07}
          style={{fontFamily: FONTS.head, fontWeight: 800, fontSize: 132, letterSpacing: '0.16em', color: '#E9C46A', marginTop: -6,
            textShadow: '0 5px 26px rgba(0,0,0,0.85)'}} />
        <div style={{width: lerp(0, 420, rule), height: 2, marginTop: 6, background: 'linear-gradient(90deg,#E9C46A,rgba(233,196,106,0))'}} />
        <Letters text="Moscow · the Kremlin · 7:32 pm" t={t} from={h.y91 + 0.55} step={0.022}
          style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 31, color: '#E4E9F0', letterSpacing: '0.08em', marginTop: 14,
            textShadow: '0 2px 10px rgba(0,0,0,0.9)'}} />
      </div>
      <AbsoluteFill style={{boxShadow: 'inset 0 0 240px rgba(0,0,0,0.7)'}} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(255,244,220,0.9), rgba(255,244,220,0) 70%)',
        opacity: Math.sin(Math.PI * x) * 0.45}} />
    </AbsoluteFill>
  );
};
