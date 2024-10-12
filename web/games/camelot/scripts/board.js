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
                // TODO add more mutators
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
