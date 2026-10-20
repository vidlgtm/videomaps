import {loadFont as cinzel} from '@remotion/google-fonts/Cinzel';
import {loadFont as inter} from '@remotion/google-fonts/Inter';
import {loadFont as cormorant} from '@remotion/google-fonts/CormorantGaramond';
const a = cinzel('normal', {weights: ['400', '600', '700', '800'], subsets: ['latin']});
const b = inter('normal', {weights: ['400', '500', '600', '700', '800'], subsets: ['latin']});
const c = cormorant('italic', {weights: ['500', '600'], subsets: ['latin']});
const c2 = cormorant('normal', {weights: ['500', '700'], subsets: ['latin']});
export const FONTS = {head: a.fontFamily, body: b.fontFamily, serif: c.fontFamily || c2.fontFamily};
