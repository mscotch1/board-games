import { installSprite } from './camelot/sprite.js';
import { mountFooters } from './shared/footer.js';
import { mountThemePickers } from './shared/theme.js';

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));
mountFooters();
