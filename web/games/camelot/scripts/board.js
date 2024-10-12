import stateManager from './state.js';

export default class Board {
    ROWS = 16;

    COLS = 12;

    BOARD_MASK = new Uint8Array([
        0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0,
        0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,
        0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0,
        0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,
        0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0,
    ]);

    state = new Uint8Array([
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 2, 1, 1, 1, 1, 1, 1, 2, 0, 0,
        0, 0, 0, 2, 1, 1, 1, 1, 2, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 4, 3, 3, 3, 3, 4, 0, 0, 0,
        0, 0, 4, 3, 3, 3, 3, 3, 3, 4, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    ]);

    constructor(assignment) {
        // register all state for board and reducers
        this.assignment = assignment;

        stateManager.registerReducer('board/pieces', (state, action) => {
            switch (action?.type) {
                case 'MOVE': {
                    const { from, to } = action.payload;
                    this.handleMove(from, to);
                    break;
                }
                default:
                    return state;
            }
        }, this.state);

        stateManager.registerReducer('board/interact/hovercell', (state, action, signature) => {
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

        stateManager.registerReducer('board/interact/selectcell', (state, action) => {
            switch (action?.type) {
                case 'SELECT':
                default:
                    return state === action.payload ? null : action.payload;
            }
        });

        stateManager.registerReducer('game/turn', (state, action) => {
            switch (action?.type) {
                case 'SWITCH':
                default:
                    return state === '1' ? '2' : '1';
            }
        }, '1');
    }

    handleMove(from, to) {
        console.log(from, to);
        // check if legal move

        // if so, perform move
        
        // if piece has no further legal moves, switch whose turn it is
    }

    isOwnPiece(index) {
        const playerIndex = this.assignment === '1' ? 1 : 0;

        return Math.floor((this.state[index] - 1) / 2) === playerIndex;
    }

    onClick(index) {
        const currentPlayer = stateManager.getState('game/turn');
        if (currentPlayer !== this.assignment) {
            return;
        }

        if (this.isOwnPiece(index)) {
            stateManager.dispatch({ channel: 'board/interact/selectcell', type: 'SELECT', payload: index });
        } else {
            stateManager.dispatch({ channel: 'board/interact/selectcell', type: 'SELECT', payload: null });
        }
    }

    onHover(index) {
        const own = stateManager.getState('board/interact/hovercell')?.own;
        if (index === own) {
            return;
        }

        if (this.BOARD_MASK[index]) {
            stateManager.dispatch({ channel: 'board/interact/hovercell', type: 'SET', payload: index });
        } else {
            stateManager.dispatch({ channel: 'board/interact/hovercell', type: 'SET', payload: null });
        }
    }

    onCursorLeave() {
        stateManager.dispatch({ channel: 'board/interact/hovercell', type: 'SET', payload: null });
    }
}
