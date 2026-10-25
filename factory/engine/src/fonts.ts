// Kit fonts are bundled (repo fonts/ -> public/fonts/ at prep) and loaded locally, so a render never depends on
// Google Fonts being reachable. Families and weights are exactly those of our films: Cinzel (titles, country names),
// Inter (UI, dates, captions), Cormorant Garamond (italic serif: neighbour names, quotes, places).
import {continueRender, delayRender, staticFile} from 'remotion';

const FACES: [string, string, string, string][] = [
  ['Cinzel', 'fonts/Cinzel.ttf', 'normal', '400 900'],
  ['Inter', 'fonts/Inter.ttf', 'normal', '100 900'],
  ['Cormorant Garamond', 'fonts/CormorantGaramond.ttf', 'normal', '300 700'],
  ['Cormorant Garamond', 'fonts/CormorantGaramond-Italic.ttf', 'italic', '300 700'],
];
if (typeof document !== 'undefined' && typeof FontFace !== 'undefined') {
  const handle = delayRender('kit fonts');
  Promise.all(FACES.map(([family, file, style, weight]) =>
    new FontFace(family, `url(${staticFile(file)})`, {style, weight}).load().then((f) => (document as any).fonts.add(f))))
    .then(() => continueRender(handle))
    .catch((e) => { console.error('font load failed', e); continueRender(handle); });
}
export const FONTS = {head: 'Cinzel', body: 'Inter', serif: 'Cormorant Garamond'};
