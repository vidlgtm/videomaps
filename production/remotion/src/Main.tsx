import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {MapStage} from './components/MapStage';
import {Overlays, DollLabelsLayer} from './components/Overlays';
import {Clips} from './components/Clips';
import {Globe} from './components/Globe';
import {AudioMix} from './components/AudioMix';
import {GLOBE} from './script';

export const Main: React.FC<{lite?: boolean}> = ({lite}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const globeFrames = Math.round(GLOBE.to * fps);
  return (
    <AbsoluteFill style={{background: '#0c1822'}}>
      {t > GLOBE.to - 1.4 ? <MapStage t={t} lite={!!lite} fps={fps} /> : null}
      <Clips t={t} kinds={['cauc']} />
      <Sequence from={0} durationInFrames={globeFrames} layout="none">
        <Globe t={t} />
      </Sequence>
      <Overlays t={t} />
      <Clips t={t} kinds={['doll', 'manim']} />
      <DollLabelsLayer t={t} />
      <AudioMix />
    </AbsoluteFill>
  );
};
