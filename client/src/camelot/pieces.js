// The pieces and other symbols the board draws, as SVG <symbol> markup. Each
// piece is drawn on a 100 x 100 canvas and coloured by CSS variables set on the
// <use> element (--fill, --edge, --shine and --rim), so one drawing serves both
// sides. Knights face right.

const PLINTH = `
  <ellipse class="piece-shade" cx="50" cy="88" rx="30" ry="6" />
  <path class="piece-body" d="M23 87 C23 81 29 79 35 79 H65 C71 79 77 81 77 87 Z" />
  <path class="piece-rim" d="M31 83 H69" />
`;

export const PIECE_DEFS = `
  <symbol id="piece-man" viewBox="0 0 100 100">
    ${PLINTH}
    <path class="piece-body" d="M30 79 C30 66 37 59 42 52 H58 C63 59 70 66 70 79 Z" />
    <rect class="piece-body" x="35" y="45" width="30" height="9" rx="4.5" />
    <circle class="piece-body" cx="50" cy="31" r="14" />
    <path class="piece-rim" d="M38 31 A12 12 0 0 1 62 31" />
    <path class="piece-body" d="M50 17 C46 11 52 6 58 9 C55 11 54 14 54 18 Z" />
    <circle class="piece-shine" cx="45" cy="27" r="3.5" />
  </symbol>

  <symbol id="piece-knight" viewBox="0 0 100 100">
    ${PLINTH}
    <path class="piece-body" d="
      M31 79
      C28 68 30 58 37 50
      C31 44 29 36 33 27
      C34 22 36 18 37 13
      L38 5 L44 16
      L50 6 L53 18
      C62 17 72 23 79 33
      C84 39 88 47 88 53
      C88 58 84 61 79 60
      C75 59 72 57 68 57
      C64 56 60 54 58 56
      C57 63 64 70 74 79 Z" />
    <path class="piece-mane" d="
      M37 13
      C29 16 25 24 27 30
      C21 32 21 40 27 43
      C21 47 22 55 28 57
      C24 62 25 70 30 74
      L36 70
      C34 62 35 52 41 46
      C36 40 36 28 37 13 Z" />
    <path class="piece-mane" d="M44 16 C47 12 52 12 54 18 C50 19 47 20 44 16 Z" />
    <path class="piece-rim" d="M60 37 C58 44 60 50 64 54" />
    <path class="piece-rim" d="M82 58 C79 58 76 58 74 58" />
    <circle class="piece-eye" cx="65" cy="31" r="3.4" />
    <circle class="piece-shine" cx="66" cy="29.8" r="1.2" />
    <ellipse class="piece-eye" cx="83" cy="49" rx="1.8" ry="1.3" transform="rotate(-25 83 49)" />
  </symbol>

  <symbol id="castle" viewBox="0 0 100 100">
    <path class="castle-tower" d="M20 88 V42 H28 V32 H37 V42 H43 V32 H57 V42 H63 V32 H72 V42 H80 V88 Z M44 88 V70 A6 6 0 0 1 56 70 V88 Z" fill-rule="evenodd" />
    <path class="castle-pole" d="M50 32 V9" />
    <path class="castle-flag" d="M50 9 L74 16 L50 23 Z" />
  </symbol>
`;
