import Board from './board.js';
import ChatLog from './chatlog.js';
import Painter from './painter.js';
import Socket, { generateCode } from './socket.js';

const ROWS = 16;
const COLS = 12;
const BOARD_MASK = new Uint8Array([
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
const initialState = new Uint8Array([
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

$(document).ready(async () => {
    // connect to server
    const socket = await new Promise((resolve) => {
        // either get code from user or generate one
        const codeModal = $(document.getElementById('codemodal'));
        codeModal.modal('show');

        const newGame = codeModal.find('#newgame');
        const joinGame = codeModal.find('#joingame');
        const clean = () => {
            newGame.off('click');
            joinGame.off('submit');
        };

        newGame.on('click', () => {
            resolve(new Socket(generateCode()));
            codeModal.modal('hide');
            clean();
        });

        joinGame.on('submit', function (e) {
            const formData = new FormData(this);
            e.preventDefault();
            resolve(new Socket(formData.get('gamecode')));
            codeModal.modal('hide');
            clean();
        });
    });

    {
        const waitModal = $(document.getElementById('waitmodal'));
        const gameCode = document.getElementById('gamecode');
        gameCode.innerText = socket.code;
        waitModal.modal('show');
        await socket.on('game-ready');
        waitModal.modal('hide');
    }

    // set up board
    {
        const pieceMap = new Map([
            [1, { player: 1, icon: 'man' }],
            [2, { player: 1, icon: 'knight' }],
            [3, { player: 2, icon: 'man' }],
            [4, { player: 2, icon: 'knight' }],
        ]);
        const canvas = new Painter(ROWS, COLS, BOARD_MASK, pieceMap);
        const board = new Board(ROWS, COLS, BOARD_MASK, initialState, canvas);
        board.ready().then(() => {
            board.draw();
        });
    }

    // set up chat logs
    const chat = new ChatLog(
        document.getElementById('chatlog'),
        (message) => { socket.publish('chat', message); },
    );
    socket.subscribe('chat', (message) => {
        chat.addMessage(message);
    });
});

