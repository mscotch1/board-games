export default class Painter {
    squareEdgePx = 68;
    #images = [];
    #sprites = new Map();

    constructor(rows, cols, boardMask, pieceMap) {
        this.readyPromise = new Promise((resolve) => {
            this.rows = rows;
            this.cols = cols;
            this.boardMask = boardMask;
            this.pieceMap = pieceMap;

            this.canvas = document.getElementsByClassName('board')[0];
            this.ctx = this.canvas.getContext('2d');

            this.canvas.width = cols * this.squareEdgePx;
            this.canvas.height = rows * this.squareEdgePx;

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
            })).then(() => { resolve(); });
        });
    }

    static getColor(varName) {
        return getComputedStyle(document.body).getPropertyValue(`--${varName}`);
    }

    ready() {
        return this.readyPromise;
    }

    #iterateSquares(callback) {
        for (let row = 0; row < this.rows; ++row) {
            for (let col = 0; col < this.cols; ++col) {
                const i = row * this.cols + col;
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
            if (this.boardMask[i]) {
                let squareColor = (row + col) % 2 === 0 ? Painter.getColor('square-1') : Painter.getColor('square-2'); // Alternating colors
                if (row === ownRow && col === ownCol) {
                    squareColor = Painter.getColor('square-hover');
                } else if (row === otherRow && col === otherCol) {
                    squareColor = Painter.getColor('square-hover-opponent');
                }
                this.ctx.fillStyle = squareColor;
                const args = [col * this.squareEdgePx, row * this.squareEdgePx, this.squareEdgePx, this.squareEdgePx];
                this.ctx.fillRect(...args);

                this.ctx.strokeStyle = Painter.getColor('border');
                this.ctx.lineWidth = 3;
                if (this.boardMask[i]) {
                    this.ctx.strokeRect(...args);
                }

                // draw castle circles and letter text
                if (row === 0 || row === this.rows - 1) {
                    this.ctx.strokeStyle = Painter.getColor('border');
                    this.ctx.fillStyle = Painter.getColor('castle');
                    const center = [(col + 0.5) * this.squareEdgePx, (row + 0.5) * this.squareEdgePx];
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
                    }[`${row}_${col}`], col * this.squareEdgePx + 2, (row + 1) * this.squareEdgePx - 2);
                } else if (this.boardMask[i]) {
                    this.ctx.font = 'bold 11px MedievalSharp';
                    this.ctx.fillStyle = Painter.getColor('border');
                    this.ctx.fillText(squareIndex++, col * this.squareEdgePx + 2, (row + 1) * this.squareEdgePx - 2);
                }
            }
        });
    }

    #drawPieces(boardState) {
        // Draw the pieces
        this.#iterateSquares((row, col, i) => {
            if (boardState[i]) {
                const { player, icon } = this.pieceMap.get(boardState[i]);
                this.ctx.drawImage(this.#sprites.get(`${icon}${player}`), col * this.squareEdgePx + 12, row * this.squareEdgePx + 8);
                this.ctx.filter = 'none';
            }
        });
    }

    draw(boardState, currentLocations) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.#drawSquares(currentLocations);
        this.#drawPieces(boardState);
    }

    addEventListener(event, callback) {
        return this.canvas.addEventListener(event, callback);
    }
}
