import { PIECE_DEFS } from './pieces.js';

const SHIELD = 'M10 8 H90 V60 C90 92 66 108 50 114 C34 108 10 92 10 60 Z';
const SHIELD_LEFT_HALF = 'M10 8 H50 V114 C34 108 10 92 10 60 Z';

/** Every symbol the pages draw with <use>: pieces, castles, shields and the crest. */
export const SPRITE = `
  ${PIECE_DEFS}

  <symbol id="shield-white" viewBox="0 0 100 120">
    <path class="shield-fill white" d="${SHIELD}" />
    <path class="shield-trim" d="${SHIELD}" />
  </symbol>
  <symbol id="shield-black" viewBox="0 0 100 120">
    <path class="shield-fill black" d="${SHIELD}" />
    <path class="shield-trim" d="${SHIELD}" />
  </symbol>
  <symbol id="shield-random" viewBox="0 0 100 120">
    <path class="shield-fill black" d="${SHIELD}" />
    <path class="shield-fill white" d="${SHIELD_LEFT_HALF}" />
    <path class="shield-trim" d="${SHIELD}" />
  </symbol>

  <symbol id="crest" viewBox="0 0 100 120">
    <path class="crest-fill" d="${SHIELD}" />
    <path class="crest-chief" d="M10 8 H90 V24 H10 Z" />
    <use class="piece white" href="#piece-knight" x="12" y="14" width="76" height="76" />
    <path class="shield-trim" d="${SHIELD}" />
  </symbol>
`;

/** Puts the symbols into the page, so any element can reference them. */
export function installSprite() {
  document.body.insertAdjacentHTML(
    'afterbegin',
    `<svg class="sprite-sheet" width="0" height="0" aria-hidden="true" focusable="false"><defs>${SPRITE}</defs></svg>`,
  );
}
