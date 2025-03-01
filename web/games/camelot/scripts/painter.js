import stateManager from './state.js';

export default class Painter {
    SQUARE_EDGE_PX = 58;
    #images = [];
    #sprites = new Map();

    constructor(board, PIECE_MAP, SPRITE_NAMES) {
        this.ROWS = board.ROWS;
        this.COLS = board.COLS;
        this.BOARD_MASK = board.BOARD_MASK;
        this.PIECE_MAP = PIECE_MAP;
        this.SPRITE_NAMES = SPRITE_NAMES;

        this.board = board;

        this.canvas = document.getElementById('board-canvas');
        this.ctx = this.canvas.getContext('2d');

        this.canvas.width = this.COLS * this.SQUARE_EDGE_PX;
        this.canvas.height = this.ROWS * this.SQUARE_EDGE_PX;

        this.readyPromise = new Promise(async (resolve) => {
            await this.loadSprites();

            this.subscribeEvents(board);

            // all board changes re-draw the board
            stateManager.subscribe('board', () => {
                this.draw();
            });

            resolve();
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
                if (this.BOARD_MASK[i]) {
                    if (this.board.assignment == 1) {
                        callback(row, col, i);
                    } else {
                        callback(this.ROWS - 1 - row, this.COLS - 1 - col, i);
                    }
                }
            }
        }
    }

    drawSingleSquare(row, col, i) {
        let color = (row + col) % 2 === 0 ? Painter.getColor('square-1') : Painter.getColor('square-2'); // Alternating colors

        const hoverState = stateManager.getState('board/interact/hovercell')
        const moveCell = stateManager.getState('board/turn/move')?.at(-1);

        // override default color if hovering
        if (i === hoverState?.own && this.board.isOwnPiece(i)) {
            if (this.board.isCurrentPlayerPiece(i)) {
                color = Painter.getColor('square-hover-own');
            } else {
                color = Painter.getColor('square-hover-opponent');
            }
        } else if (i === hoverState?.own && this.board.isOpponentPiece(i)) {
            color = Painter.getColor('square-hover-opponent');
        } else if (i === hoverState?.own) {
            color = Painter.getColor('square-hover');
        } else if (i === hoverState?.other) {
            color = Painter.getColor('square-hover-ghost');
        }

        // override default and hover if selected
        if (i === moveCell) {
            color = Painter.getColor('square-select');
        }

        this.ctx.fillStyle = color;
        const args = [col * this.SQUARE_EDGE_PX, row * this.SQUARE_EDGE_PX, this.SQUARE_EDGE_PX, this.SQUARE_EDGE_PX];
        this.ctx.fillRect(...args);

        this.ctx.strokeStyle = Painter.getColor('border');
        this.ctx.lineWidth = 3;
        if (this.BOARD_MASK[i]) {
            this.ctx.strokeRect(...args);
        }
    }

    drawDecorations(row, col, i, squareIndex) {
        if (row === 0 || row === this.ROWS - 1) {
            // castle circles
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
                '5': 'A',
                '6': 'B',
                '185': 'Y',
                '186': 'Z',
            }[`${i}`], col * this.SQUARE_EDGE_PX + 2, (row + 1) * this.SQUARE_EDGE_PX - 2);
        } else {
            // numbers
            this.ctx.font = 'bold 11px MedievalSharp';
            this.ctx.fillStyle = Painter.getColor('border');
            this.ctx.fillText(squareIndex, col * this.SQUARE_EDGE_PX + 2, (row + 1) * this.SQUARE_EDGE_PX - 2);
        }
    }

    #drawSquares() {
        let squareIndex = 1;
        this.#iterateSquares((row, col, i) => {
            this.drawSingleSquare(row, col, i);
            this.drawDecorations(row, col, i, squareIndex);
            if (row > 0 && row < this.ROWS - 1) {
                ++squareIndex;
            }
        });
    }

    #drawPieces() {
        // Draw the pieces
        const move = stateManager.getState('board/turn/move');
        const boardState = this.board.makeMoves(
            stateManager.getState('board/pieces'),
            move,
        );

        const validMoves = this.board.validMoves(move);
        
        this.#iterateSquares((row, col, i) => {
            if (boardState[i]) {
                const { player, icon } = this.PIECE_MAP.get(boardState[i]);
                this.ctx.drawImage(this.#sprites.get(`${icon}${player}`), col * this.SQUARE_EDGE_PX + 8, row * this.SQUARE_EDGE_PX + 4);
                this.ctx.filter = 'none';
            }

            if (validMoves.includes(i)) {
              // draw indicator
              this.ctx.strokeStyle = Painter.getColor('candidate');
              this.ctx.fillStyle = Painter.getColor('candidate');
              const center = [(col + 0.5) * this.SQUARE_EDGE_PX, (row + 0.5) * this.SQUARE_EDGE_PX];
              this.ctx.beginPath();
              this.ctx.arc(...center, 6, 0, 2 * Math.PI);
              this.ctx.fill();
              this.ctx.stroke();
            }
        });
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.#drawSquares();
        this.#drawPieces();
    }

    // helper methods for use in event listeners
    calculateRowCol(offsetX, offsetY) {
        const row = Math.floor((offsetY + 1) / this.canvas.offsetHeight * this.ROWS);
        const col = Math.floor((offsetX + 1) / this.canvas.offsetWidth * this.COLS);

        return { row, col };
    }

    calculateIndex(offsetX, offsetY) {
        const { row, col } = this.calculateRowCol(offsetX, offsetY);
        const index = row * this.COLS + col;
        if (this.board.assignment == 1) {
            return index;
        }

        return this.BOARD_MASK.length - 1 - index;
    }

    subscribeEvents(board) {
        this.canvas.addEventListener('mousemove', (e) => {
            const index = this.calculateIndex(e.offsetX, e.offsetY);
            board.onHover(index);
        });
        this.canvas.addEventListener('mouseout', (_e) => {
            board.onCursorLeave();
        });
        this.canvas.addEventListener('click', (e) => {
            const index = this.calculateIndex(e.offsetX, e.offsetY);
            board.onClick(index);
        });
    }

    loadSprites() {
        return Promise.all(this.SPRITE_NAMES.map((path) => {
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
        }))
    }
}
