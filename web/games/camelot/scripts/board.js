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
                case 'INIT':
                    return action.payload;
                default:
                    return state;
            }
        });
        stateManager.dispatch({ channel: 'board/pieces', type: 'INIT', payload: initBoardState });

        stateManager.registerReducer('board/currentcell', (state, action) => {
            switch (action?.type) {
                case 'SET':
                    return action.payload;
                default:
                    return state;
            }
        });
        stateManager.dispatch({ channel: 'board/currentcell', type: 'SET', payload: null });

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

        if (row === this.currentCell?.row && col === this.currentCell?.col) {
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
