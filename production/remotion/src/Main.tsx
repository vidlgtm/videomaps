import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {MapStage} from './components/MapStage';
import {Overlays, DollLabelsLayer} from './components/Overlays';
import {Clips} from './components/Clips';
import {Opening} from './components/Opening';
import {Globe} from './components/Globe';
import {V2Overlays} from './components/V2';
import {AudioMix} from './components/AudioMix';
import {ExtrasMap, ExtrasTop} from './extras';
import {OPENING} from './v2';
import {GLOBE} from './script';

// Layer order (bottom -> top): map stage, full-frame 3D clips, Three.js globe, project creative layer (map level),
// opening text, screen overlays (cards, flags row, docs, cut-outs, titles), stepped Manim/Blender clips, project creative
// layer (top). AudioMix is the only sound source (all videos are muted).
export const Main: React.FC<{lite?: boolean; audioOnly?: boolean}> = ({lite, audioOnly}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const openFrames = Math.ceil(OPENING.end * fps) + 1;
  if (audioOnly) return <AudioMix />;
  return (
    <AbsoluteFill style={{background: '#0c1822'}}>
      {t > OPENING.mapIn - 0.4 ? <MapStage t={t} lite={!!lite} fps={fps} /> : null}
      <Clips t={t} kinds={['cauc']} />
      {GLOBE.to > 0 && t >= GLOBE.from && t <= GLOBE.to ? <Globe t={t} /> : null}
      <ExtrasMap t={t} />
      {OPENING.end > 0 ? (
        <Sequence from={0} durationInFrames={openFrames} layout="none">
          <Opening t={t} />
        </Sequence>
      ) : null}
      <Overlays t={t} />
      <V2Overlays t={t} />
      <Clips t={t} kinds={['doll', 'manim']} />
      <DollLabelsLayer t={t} />
      <ExtrasTop t={t} />
      <AudioMix />
    </AbsoluteFill>
  );
};
