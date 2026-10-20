// Fallback renderer: frames A..B as individual stills, each in a fresh page: node scripts/stills_range.mjs <serve> A B DIR
import {openBrowser, renderStill, selectComposition} from '@remotion/renderer';
import {bundle} from '@remotion/bundler';
import path from 'path';
const [serve, A, B, dir] = process.argv.slice(2);
const serveUrl = /^https?:/.test(serve) ? serve : /\.tsx?$/.test(serve) ? await bundle({entryPoint: path.resolve(serve)}) : path.resolve(serve);
const chromiumOptions = {gl: 'swangle'};
const browser = await openBrowser('chrome', {chromiumOptions});
const comp = await selectComposition({serveUrl, id: 'Main', inputProps: {}, puppeteerInstance: browser, chromiumOptions});
for (let f = +A; f <= +B; f++) {
  await renderStill({composition: comp, serveUrl, frame: f, output: path.join(dir, `f_${String(f).padStart(6, '0')}.jpg`), imageFormat: 'jpeg',
    jpegQuality: 95, inputProps: {}, puppeteerInstance: browser, chromiumOptions, timeoutInMilliseconds: 600000});
  if (f % 60 === 0) console.log('still', f);
}
try { await browser.close({silent: true}); } catch (e) {}
