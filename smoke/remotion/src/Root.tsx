import React from 'react';
import {Composition} from 'remotion';
import {Smoke} from './Smoke';

export const Root: React.FC = () => (
  <Composition id="Smoke" component={Smoke} durationInFrames={150} fps={30} width={1920} height={1080} />
);
