import React from 'react';
import {Audio, Sequence, staticFile} from 'remotion';
import {MUSIC, SFX, END} from '../script';
import {speechAt} from '../lib/cues';
import {clamp} from '../lib/anim';

const FPS = 30;
const duck = (t: number) => {
  let s = 0;
  for (let k = -4; k <= 4; k++) s += speechAt(t + k * 0.12);
  return s / 9;
};
export const AudioMix: React.FC = () => (
  <>
    <Audio src={staticFile('voice.wav')} volume={1} />
    {MUSIC.map((m, i) => {
      const from = Math.round(m.from * FPS), dur = Math.round((Math.min(m.to, END) - m.from) * FPS);
      const g = Math.pow(10, (-27.5 - m.lufs) / 20);
      return (
        <Sequence key={'m' + i} from={from} durationInFrames={dur} layout="none">
          <Audio src={staticFile(m.src)} volume={(f) => {
            const t = m.from + f / FPS;
            const fade = Math.min(clamp(f / (1.5 * FPS)), clamp((dur - f) / (1.8 * FPS)));
            return g * (1 + 1.6 * (1 - duck(t))) * fade;
          }} />
        </Sequence>
      );
    })}
    {SFX.filter((s) => s.t >= 0 && s.t < END - 0.5).map((s, i) => (
      <Sequence key={'s' + i} from={Math.round(s.t * FPS)} durationInFrames={Math.round(6.5 * FPS)} layout="none">
        <Audio src={staticFile(`sfx/${s.f}.wav`)} volume={s.v ?? 0.35} />
      </Sequence>
    ))}
  </>
);
