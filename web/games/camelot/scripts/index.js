import Board from './board.js';
import ChatLog from './chatlog.js';
import Painter from './painter.js';
import Socket, { generateCode } from './socket.js';
import stateManager from './state.js';

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

    stateManager.connect(socket);

    {
        const waitModal = $(document.getElementById('waitmodal'));
        const gameCode = document.getElementById('gamecode');
        gameCode.innerText = socket.code;
        waitModal.modal('show');
        await socket.on('game-ready');
        waitModal.modal('hide');
    }

    // set up chat logs
    {
        const chat = new ChatLog( document.getElementById('chatlog'));
    }

    // set up board and painter
    {
        const PIECE_MAP = new Map([
            [1, { player: 1, icon: 'man' }],
            [2, { player: 1, icon: 'knight' }],
            [3, { player: 2, icon: 'man' }],
            [4, { player: 2, icon: 'knight' }],
        ]);

        const board = new Board();
        const canvas = new Painter(board, PIECE_MAP);
        canvas.ready().then(() => {
            canvas.draw();
        });
    }
});

