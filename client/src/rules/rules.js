import { installSprite } from '../camelot/sprite.js';
import { mountThemePickers } from '../shared/theme.js';
import { renderDiagrams } from './diagram.js';
import './rules.css';

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));
renderDiagrams();
