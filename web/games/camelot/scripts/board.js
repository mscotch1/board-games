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
        0, 0, 4, 3, 3, 3, 3, 3, 3, 4, 0, 0,
        0, 0, 0, 4, 3, 3, 3, 3, 4, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 2, 1, 1, 1, 1, 2, 0, 0, 0,
        0, 0, 2, 1, 1, 1, 1, 1, 1, 2, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    ]);

    constructor(assignment) {
        // register all state for board and reducers
        this.assignment = assignment;

        this.setupMenuBar();
        this.registerReducers();
        this.subscribe();
    }

    registerReducers() {
        stateManager.registerReducer('board/pieces', (state, action) => {
            switch (action?.type) {
                case 'MOVE': {
                    return this.makeMoves(state, action.payload);
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

        stateManager.registerReducer('board/turn/move', (state, action) => {
            switch (action?.type) {
                case 'PUSH':
                    if (state?.at(-1) === action?.payload && state.length === 1) {
                        return []
                    } else if (this.isValidMove([...state, action.payload])) {
                        return [...state, action.payload];
                    } else if (this.isSameTeam(state?.[0], action?.payload) && state?.length === 0) {
                        return [action.payload];
                    } else {
                        return state;
                    }
                case 'RESET':
                    return [];
                case 'POP':
                    return state.slice(0, state.length - 1);
                default:
                    return state;
            }
        }, []);

        stateManager.registerReducer('game/turn', (state, action) => {
            switch (action?.type) {
                case 'SWITCH':
                default:
                    return state === '1' ? '2' : '1';
            }
        }, '1');

        stateManager.registerReducer('menu/endturn', (_state, action) => {
            switch (action?.type) {
                case 'ENABLE':
                    return false;
                case 'DISABLE':
                    return true;
                default:
                    throw new Error('unknown action type');
            }
        }, true);

        stateManager.registerReducer('menu/undo', (_state, action) => {
            switch (action?.type) {
                case 'ENABLE':
                    return false;
                case 'DISABLE':
                    return true;
                default:
                    throw new Error('unknown action type');
            }
        }, true);
    }

    subscribe() {
        stateManager.subscribe('board/pieces', (state) => {
            this.state = state;
        });
        stateManager.subscribe('board/turn/move', (state) => {
            const isCurrentTurn = stateManager.getState('game/turn') === this.assignment;
            const canEndTurn = this.isValidMove(state) && state.length >= 2 && isCurrentTurn;
            stateManager.dispatch({
                channel: 'menu/endturn',
                type: canEndTurn ? 'ENABLE' : 'DISABLE',
            }, false);
            stateManager.dispatch({
                channel: 'menu/undo',
                type: (state.length < 1 || !isCurrentTurn) ? 'DISABLE' : 'ENABLE',
            }, false);
        }, true);
        stateManager.subscribe('menu/undo', (state) => {
            this.undoButton.disabled = state;
        });
        stateManager.subscribe('menu/endturn', (state) => {
            this.endTurnButton.disabled = state;
        });
        stateManager.subscribe('game/turn', (state) => {
            this.turnIndicator.innerText = state === this.assignment ? '✅' : '❌';
            const [oldClass, newClass] = state === this.assignment
                ? ['bg-danger', 'bg-success']
                : ['bg-success', 'bg-danger'];
            this.turnIndicator.classList.remove(oldClass);
            this.turnIndicator.classList.add(newClass);
        });
    }

    setupMenuBar() {
        this.endTurnButton = document.getElementById('end-turn');
        this.endTurnButton.onclick = () => {
            this.endTurn();
        };
        this.undoButton = document.getElementById('undo');
        this.undoButton.onclick = () => {
            stateManager.dispatch({
              channel: 'board/turn/move', 
              type: 'POP',
            });
        };
        this.turnIndicator = document.getElementById('turn-indicator');
    }

    endTurn() {
        stateManager.dispatch({
            channel: 'board/pieces',
            type: 'MOVE',
            payload: stateManager.getState('board/turn/move'),
        });
        stateManager.dispatch({ channel: 'game/turn', type: 'SWITCH' });
        stateManager.dispatch({ channel: 'board/turn/move', type: 'RESET' });
    }

    isValidMove(moves) {
        if (moves.length < 1) {
            return false;
        }

        if (moves.length == 1) {
            return this.isCurrentPlayerPiece(moves[0]);
        }

        // simple move
        const neighbors = this.getAdjacentSquareIndices(moves[0]);
        if (moves.length == 2 && neighbors.includes(moves[1])) {
            return this.isEmpty(moves[1]);
        }

        // not simple move, so has to be jump, canter, or knight's charge
        const isMan = this.isMan(moves[0]);

        let isJumping = false;
        let isCantering = false;

        let tempBoard = this.makeMoves(this.state, []);
        for (let i = 1; i < moves.length; ++i) {
            const from = moves[i - 1];
            const to = moves[i];
            const jumped = (from + to) / 2;
            const nextIsJump = !this.isEmpty(jumped, tempBoard) && !this.isSameTeam(jumped, moves[0]);
            const nextIsCanter = this.isSameTeam(jumped, moves[0]);

            if (!nextIsJump && !nextIsCanter) {
                return false;
            }

            if (moves.length >= 3 && moves[i - 2] === to) {
                return false;
            }

            if (!this.getJumpableIndices(from).includes(to) || !this.isEmpty(to, tempBoard)) {
                return false;
            }

            if (isCantering && nextIsJump && isMan) {
                return false; // only knights can do knight's charge
            }

            if (isJumping && !nextIsJump) {
                return false;
            }

            isJumping = nextIsJump;
            isCantering = nextIsCanter;

            tempBoard = this.makeMoves(this.state, moves.slice(0, i + 1));
        }

        return true;
    }

    validMoves(move) {
      if (!move || move.length < 1) {
        return [];
      }

      return this
        .getAdjacentSquareIndices(move.at(-1))
        .concat(this.getJumpableIndices(move.at(-1)))
        .map((index) => move.concat(index))
        .filter((candidateMove) => this.isValidMove(candidateMove))
        .map((validCandidate) => validCandidate.at(-1));
    }

    makeMoves(boardState, moves) {
        const arr = new ArrayBuffer(boardState.byteLength);
        const newBoardState = new Uint8Array(arr);
        boardState.forEach((v, i) => {
            newBoardState[i] = v;
        });

        for (let i = 1; i < moves.length; ++i) {
            const from = moves[i - 1];
            const to = moves[i];
            const jumped = (from + to) / 2;
            const isOpponentPiece = !this.isEmpty(jumped, newBoardState) && !this.isSameTeam(jumped, from, newBoardState)

            newBoardState[to] = newBoardState[from];
            newBoardState[from] = 0;
            if (
                this.getJumpableIndices(from).includes(to)
                && isOpponentPiece) {
                newBoardState[jumped] = 0;
            }
        }

        return newBoardState;
    }

    isSameTeam(index1, index2, board = this.state) {
        return board[index1] > 0 && board[index2] > 0 
            && Math.floor((board[index1] - 1) / 2) === Math.floor((board[index2] - 1) / 2);
    }

    isOwnPiece(index, board = this.state) {
        const playerIndex = this.assignment === '1' ? 0 : 1;
        return !this.isEmpty(index, board) && Math.floor((board[index] - 1) / 2) === playerIndex;
    }

    isOpponentPiece(index, board = this.state) {
        return !this.isEmpty(index, board) && !this.isOwnPiece(index, board);
    }

    isCurrentPlayerPiece(index, board = this.state) {
        const playerIndex = stateManager.getState('game/turn') === '1' ? 0 : 1;
        return !this.isEmpty(index, board) && Math.floor((board[index] - 1) / 2) === playerIndex;
    }

    isEmpty(index, board = this.state) {
        return board[index] === 0;
    }

    isMan(index, board = this.state) {
        return !this.isEmpty(index, board) && (board[index] % 2 === 1);
    }

    isKnight(index, board = this.state) {
        return !this.isEmpty(index, board) && !this.isMan(index, board);
    }

    rowFromIndex(index) {
        return Math.floor(index / this.COLS)
    }

    // filters for when neighbors are out of bounds
    getAdjacentSquareIndices(index) {
        const offsets = [
            -this.COLS - 1, -this.COLS, -this.COLS + 1,
                        -1,                          1,
             this.COLS - 1,  this.COLS,  this.COLS + 1,
        ];

        const currRow = this.rowFromIndex(index);
        return offsets.map((v) => v + index).filter((candidateIndex) => {
            // check if in adjacent or same row
            const candidateRow = this.rowFromIndex(candidateIndex);
            if (Math.abs(candidateRow - currRow) > 1) {
                return false;
            }

            // check if valid according to board mask
            return this.BOARD_MASK[candidateIndex];
        });
    }

    getJumpableIndices(index) {
        const offsets = [
            -this.COLS - 1, -this.COLS, -this.COLS + 1,
                        -1,                          1,
             this.COLS - 1,  this.COLS,  this.COLS + 1,
        ].map((v) => v * 2);

        const currRow = this.rowFromIndex(index);
        return offsets.map((v) => v + index).filter((candidateIndex) => {
            // check if in 2 * adjacent or same row
            const candidateRow = this.rowFromIndex(candidateIndex);
            const rowDiff = Math.abs(candidateRow - currRow);
            if (rowDiff !== 0 && rowDiff !== 2) {
                return false;
            }

            // check if valid according to board mask
            return this.BOARD_MASK[candidateIndex];
        });
    }

    onClick(index) {
        const currentPlayer = stateManager.getState('game/turn');
        if (currentPlayer !== this.assignment) {
            return;
        }

        stateManager.dispatch({ channel: 'board/turn/move', type: 'PUSH', payload: index });
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
