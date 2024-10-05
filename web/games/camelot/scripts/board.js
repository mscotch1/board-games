export default class Board {
    constructor(rows, cols, boardMask, boardState, canvas) {
        this.rows = rows;
        this.cols = cols;

        this.boardMask = boardMask;
        this.boardState = boardState;

        this.current = null;

        this.canvas = canvas;
        this.canvas.ready().then(() => {
            this.canvas.addEventListener('mousemove', (e) => {

                const row = Math.floor((e.offsetY + 1) / this.canvas.canvas.offsetHeight * this.rows);
                const col = Math.floor((e.offsetX + 1) / this.canvas.canvas.offsetWidth * this.cols);

                if (row === this.current?.row && col === this.current?.col) {
                    return;
                }

                if (this.boardMask[row * this.cols + col]) {
                    this.current = { row, col };
                } else {
                    this.current = null;
                }

                this.draw();
            });
            this.canvas.addEventListener('mouseout', (e) => {
                this.current = null;
                this.draw();
            });
        });

        if (this.rows * this.cols !== boardMask.length) {
            throw new Error(`Board mask does not fit rows (${rows}) × cols (${cols})`);
        }

        if (this.boardState.length !== this.boardMask.length) {
            throw new Error(`Board mask (length ${boardMask.length}) must be same length as board state (length ${boardState.length})`);
        }
    }

    ready() {
        return this.canvas.ready();
    }

    draw() {
        this.canvas.draw(this.boardState, this.current);
    }
}
