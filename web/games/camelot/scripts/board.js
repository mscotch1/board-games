import stateManager from './state.js';

export default class Board {
    constructor(ROWS, COLS, BOARD_MASK, initBoardState, canvas) {
        if (ROWS * COLS !== BOARD_MASK.length) {
            throw new Error(`Board mask does not fit rows (${ROWS}) × cols (${COLS})`);
        }

        if (initBoardState.length !== BOARD_MASK.length) {
            throw new Error(`Board mask (length ${BOARD_MASK.length}) must be same length as board state (length ${initBoardState.length})`);
        }

        this.ROWS = ROWS;
        this.COLS = COLS;
        this.BOARD_MASK = BOARD_MASK;

        // register all state for board and reducers
        stateManager.registerReducer('board/pieces', (state, action) => {
            switch (action?.type) {
                // TODO add more mutators
                default:
                    return state;
            }
        }, initBoardState);

        stateManager.registerReducer('board/currentcell', (state, action, signature) => {
            switch (action?.type) {
                case 'SET':
                    if (stateManager.signature === signature) {
                        return { ...state, own: action.payload };
                    } else {
                        return { ...state, other: action.payload };
                    }
                default:
                    return state;
            }
        }, { own: null, other: null });

        // all board changes re-draw the board
        stateManager.subscribe('board', () => {
            this.draw();
        });

        this.canvas = canvas;
        this.canvas.ready().then(() => {
            // register event receivers
            this.canvas.addEventListener('mousemove', (e) => { this.onMouseMove(e); });
            this.canvas.addEventListener('mouseout', (e) => { this.onMouseOut(e); });
        });
    }

    ready() {
        return this.canvas.ready();
    }

    draw() {
        this.canvas.draw(
            stateManager.getState('board/pieces'),
            stateManager.getState('board/currentcell'),
        );
    }

    // helper methods for use in event listeners
    calculateRowCol(offsetX, offsetY) {
        const row = Math.floor((offsetY + 1) / this.canvas.canvas.offsetHeight * this.ROWS);
        const col = Math.floor((offsetX + 1) / this.canvas.canvas.offsetWidth * this.COLS);

        return { row, col };
    }

    // define event listeners
    onMouseMove(e) {
        const { row, col } = this.calculateRowCol(e.offsetX, e.offsetY);

        const own = stateManager.getState('board/currentcell')?.own;
        if (row === own?.row && col === own?.col) {
            return;
        }

        if (this.BOARD_MASK[row * this.COLS + col]) {
            stateManager.dispatch({ channel: 'board/currentcell', type: 'SET', payload: { row, col } });
        } else {
            stateManager.dispatch({ channel: 'board/currentcell', type: 'SET', payload: null });
        }
    }

    onMouseOut(_e) {
        stateManager.dispatch({ channel: 'board/currentcell', type: 'SET', payload: null });
    }
}
