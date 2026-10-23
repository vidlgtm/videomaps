// Project-specific creative layer: the treaty's parchment edge unfolds into a gold map seam.
import React from 'react';
import {P} from './v2';

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);

export const ExtrasMap: React.FC<{t: number}> = () => null;
export const ExtrasTop: React.FC<{t: number}> = ({t}) => {
  const start = P.p1.treaty - 0.05;
  const unfold = P.p1.union + 0.55;
  const finish = P.p1.noExit + 0.1;
  const inA = easeOut((t - start) / 0.32);
  const outA = 1 - easeOut((t - finish) / 0.28);
  const opacity = inA * outA;
  if (opacity < 0.01) return null;
  const fold = easeOut((t - start) / Math.max(0.2, unfold - start));
  const thread = easeOut((t - unfold) / 0.45);
  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', opacity, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 92, bottom: 86, width: 332, height: 124,
        transformOrigin: 'left center', transform: `perspective(900px) rotateY(${(1 - fold) * 52}deg)`,
        border: '1px solid rgba(226,191,106,0.9)', boxShadow: '0 12px 28px rgba(0,0,0,0.38)',
        background: 'linear-gradient(180deg, #f4e8c8 0%, #e6d3a6 55%, #d2bb86 100%)', color: '#0E1A24',
        padding: '18px 22px', boxSizing: 'border-box'}}>
        <div style={{fontFamily: 'Cinzel, serif', fontSize: 15, letterSpacing: '0.16em', fontWeight: 700}}>THE UNION TREATY</div>
        <div style={{height: 1, background: '#9c6c2e', margin: '9px 0 7px'}} />
        <div style={{fontFamily: 'Cormorant Garamond, serif', fontSize: 21, fontStyle: 'italic'}}>A republic may leave the Union</div>
        <div style={{fontFamily: 'Inter, sans-serif', fontSize: 10, letterSpacing: '0.13em', marginTop: 4}}>ARTICLE 26 · 30 DECEMBER 1922</div>
      </div>
      <div style={{position: 'absolute', left: 420, bottom: 145, width: `${thread * 365}px`, height: 2,
        background: 'linear-gradient(90deg, rgba(226,191,106,0.08), #FFE3A0)',
        boxShadow: '0 0 9px rgba(255,227,160,0.62)', transform: 'rotate(-8deg)', transformOrigin: 'left center'}} />
    </div>
  );
};
