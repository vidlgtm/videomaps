import React from 'react';
import {Composition} from 'remotion';
import {Main} from './Main';
import tl from './data/timeline.json';
export const FPS = 30;
export const RemotionRoot: React.FC = () => (
  <Composition id="Main" component={Main as any} durationInFrames={Math.ceil((tl as any).total * FPS)} fps={FPS}
    width={1920} height={1080} defaultProps={{lite: false}} />
);
