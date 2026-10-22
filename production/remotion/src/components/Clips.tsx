import React from 'react';
import {AbsoluteFill, OffthreadVideo, Sequence, Freeze, staticFile, useCurrentFrame} from 'remotion';
import {CLIPS, Clip, Step} from '../script';
import {env} from '../lib/anim';

const FPS = 30;
const StepClip: React.FC<{src: string; s: Step; transparent: boolean}> = ({src, s, transparent}) => {
  const f = useCurrentFrame();
  const rate = s.rate ?? 1;
  const play = Math.max(1, Math.round(((s.s1 - s.s0) * FPS) / rate));
  const v = <OffthreadVideo src={staticFile(src)} startFrom={Math.round(s.s0 * FPS)} playbackRate={rate} muted transparent={transparent}
    style={{width: 1920, height: 1080}} />;
  return f < play ? v : <Freeze frame={play - 1}>{v}</Freeze>;
};

const ClipView: React.FC<{c: Clip; t: number}> = ({c, t}) => {
  const o = env(t, c.from, c.to, c.kind === 'cauc' ? 0.7 : 0.45, 0.6);
  const transparent = c.kind !== 'cauc';
  return (
    <AbsoluteFill style={{opacity: o, transform: c.dx ? `translateX(${c.dx}px)` : undefined}}>
      {c.steps.map((s, i) => {
        const next = i + 1 < c.steps.length ? c.steps[i + 1].at : c.to;
        const from = Math.round(s.at * FPS), dur = Math.max(1, Math.round(next * FPS) - from);
        return (
          <Sequence key={i} from={from} durationInFrames={dur} layout="none">
            <AbsoluteFill><StepClip src={c.src} s={s} transparent={transparent} /></AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const Clips: React.FC<{t: number; kinds: string[]}> = ({t, kinds}) => (
  <>
    {CLIPS.filter((c) => kinds.includes(c.kind) && t >= c.from - 0.1 && t <= c.to + 0.1).map((c, i) => <ClipView key={i} c={c} t={t} />)}
  </>
);
