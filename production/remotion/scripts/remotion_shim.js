// Stand-in for 'remotion' so AudioMix's element tree can be evaluated in Node (CI audio job; exact event list + volume curves)
export {Easing} from '../node_modules/remotion/dist/cjs/easing.js';
export {interpolate} from '../node_modules/remotion/dist/cjs/interpolate.js';
export const Audio = () => null; Audio.__kind = 'Audio';
export const Sequence = () => null; Sequence.__kind = 'Sequence';
export const staticFile = (p) => p;
