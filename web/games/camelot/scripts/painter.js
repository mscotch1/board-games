import stateManager from './state.js';

export default class Painter {
    SQUARE_EDGE_PX = 68;
    #images = [];
    #sprites = new Map();

    constructor(board, PIECE_MAP) {
        this.readyPromise = new Promise((resolve) => {
            this.ROWS = board.ROWS;
            this.COLS = board.COLS;
            this.BOARD_MASK = board.BOARD_MASK;

            this.pieceMap = PIECE_MAP;

            this.canvas = document.getElementsByClassName('board')[0];
            this.ctx = this.canvas.getContext('2d');

            this.canvas.width = this.COLS * this.SQUARE_EDGE_PX;
            this.canvas.height = this.ROWS * this.SQUARE_EDGE_PX;

            Promise.all(['man1', 'man2', 'knight1', 'knight2'].map((path) => {
                return new Promise((resolve) => {
                    const image = new Image();
                    this.#images.push(image);
                    image.onload = () => {
                        createImageBitmap(image, 0, 0, 42, 42).then((sprite) => {
                            this.#sprites.set(path, sprite);
                            resolve();
                        });
                    };
                    image.src = `./sprites/${path}.png`;
                });
            })).then(() => {
                this.canvas.addEventListener('mousemove', (e) => { this.onMouseMove(e); });
                this.canvas.addEventListener('mouseout', (e) => { this.onMouseOut(e); });

                // all board changes re-draw the board
                stateManager.subscribe('board', () => {
                    this.draw();
                });
                resolve();
            });
        });
    }

    static getColor(varName) {
        return getComputedStyle(document.body).getPropertyValue(`--${varName}`);
    }

    ready() {
        return this.readyPromise;
    }

    #iterateSquares(callback) {
        for (let row = 0; row < this.ROWS; ++row) {
            for (let col = 0; col < this.COLS; ++col) {
                const i = row * this.COLS + col;
                callback(row, col, i);
            }
        }
    }

    #drawSquares(currentLocations) {
        const ownRow = currentLocations.own?.row;
        const ownCol = currentLocations.own?.col;
        const otherRow = currentLocations.other?.row;
        const otherCol = currentLocations.other?.col;
        // Draw the squares
        let squareIndex = 1;
        this.#iterateSquares((row, col, i) => {
            if (this.BOARD_MASK[i]) {
                let squareColor = (row + col) % 2 === 0 ? Painter.getColor('square-1') : Painter.getColor('square-2'); // Alternating colors
                if (row === ownRow && col === ownCol) {
                    squareColor = Painter.getColor('square-hover');
                } else if (row === otherRow && col === otherCol) {
                    squareColor = Painter.getColor('square-hover-opponent');
                }
                this.ctx.fillStyle = squareColor;
                const args = [col * this.SQUARE_EDGE_PX, row * this.SQUARE_EDGE_PX, this.SQUARE_EDGE_PX, this.SQUARE_EDGE_PX];
                this.ctx.fillRect(...args);

                this.ctx.strokeStyle = Painter.getColor('border');
                this.ctx.lineWidth = 3;
                if (this.BOARD_MASK[i]) {
                    this.ctx.strokeRect(...args);
                }

                // draw castle circles and letter text
                if (row === 0 || row === this.ROWS - 1) {
                    this.ctx.strokeStyle = Painter.getColor('border');
                    this.ctx.fillStyle = Painter.getColor('castle');
                    const center = [(col + 0.5) * this.SQUARE_EDGE_PX, (row + 0.5) * this.SQUARE_EDGE_PX];
                    this.ctx.beginPath();
                    this.ctx.arc(...center, 10, 0, 2 * Math.PI);
                    this.ctx.fill();
                    this.ctx.stroke();

                    this.ctx.font = 'bold 11px MedievalSharp';
                    this.ctx.fillStyle = Painter.getColor('border');
                    this.ctx.fillText({
                        '0_5': 'A',
                        '0_6': 'B',
                        '15_5': 'X',
                        '15_6': 'Y',
                    }[`${row}_${col}`], col * this.SQUARE_EDGE_PX + 2, (row + 1) * this.SQUARE_EDGE_PX - 2);
                } else if (this.BOARD_MASK[i]) {
                    this.ctx.font = 'bold 11px MedievalSharp';
                    this.ctx.fillStyle = Painter.getColor('border');
                    this.ctx.fillText(squareIndex++, col * this.SQUARE_EDGE_PX + 2, (row + 1) * this.SQUARE_EDGE_PX - 2);
                }
            }
        });
    }

    #drawPieces(boardState) {
        // Draw the pieces
        this.#iterateSquares((row, col, i) => {
            if (boardState[i]) {
                const { player, icon } = this.pieceMap.get(boardState[i]);
                this.ctx.drawImage(this.#sprites.get(`${icon}${player}`), col * this.SQUARE_EDGE_PX + 12, row * this.SQUARE_EDGE_PX + 8);
                this.ctx.filter = 'none';
            }
        });
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.#drawSquares(stateManager.getState('board/currentcell'));
        this.#drawPieces(stateManager.getState('board/pieces'));
    }

    // helper methods for use in event listeners
    calculateRowCol(offsetX, offsetY) {
        const row = Math.floor((offsetY + 1) / this.canvas.offsetHeight * this.ROWS);
        const col = Math.floor((offsetX + 1) / this.canvas.offsetWidth * this.COLS);

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
