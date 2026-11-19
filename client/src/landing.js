import { initThemeToggle } from './shared/theme.js';
import { installSprite } from './camelot/sprite.js';

installSprite();
initThemeToggle(document.querySelector('.theme-toggle'));
