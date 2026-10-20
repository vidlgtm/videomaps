import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {MapStage} from './components/MapStage';
import {Overlays, DollLabelsLayer} from './components/Overlays';
import {Clips} from './components/Clips';
import {Opening} from './components/Opening';
import {V2Overlays} from './components/V2';
import {AudioMix} from './components/AudioMix';
import {OPENING} from './v2';

export const Main: React.FC<{lite?: boolean; audioOnly?: boolean}> = ({lite, audioOnly}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const openFrames = Math.ceil(OPENING.end * fps) + 1;
  // audio-only pass: AudioMix is the sole sound source (all clips are muted), so this yields the identical mix fast
  if (audioOnly) return <AudioMix />;
  return (
    <AbsoluteFill style={{background: '#0c1822'}}>
      {t > OPENING.mapIn - 0.4 ? <MapStage t={t} lite={!!lite} fps={fps} /> : null}
      <Clips t={t} kinds={['cauc']} />
      <Sequence from={0} durationInFrames={openFrames} layout="none">
        <Opening t={t} />
      </Sequence>
      <Overlays t={t} />
      <V2Overlays t={t} />
      <Clips t={t} kinds={['doll', 'manim']} />
      <DollLabelsLayer t={t} />
      <AudioMix />
    </AbsoluteFill>
  );
};
