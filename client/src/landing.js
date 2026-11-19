import { mountThemePickers } from './shared/theme.js';
import { installSprite } from './camelot/sprite.js';

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));
