import { installSprite } from '../camelot/sprite.js';
import { mountFooters } from '../shared/footer.js';
import { mountThemePickers } from '../shared/theme.js';
import { renderDiagrams } from './diagram.js';
import './rules.css';

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));
renderDiagrams();
mountFooters();
