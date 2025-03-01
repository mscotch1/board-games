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

        joinGame.on('submit', function onSubmit(e) {
            const formData = new FormData(this);
            e.preventDefault();
            resolve(new Socket(formData.get('gamecode')));
            codeModal.modal('hide');
            clean();
        });
    });

    let assignment;
    {
        const waitModal = $(document.getElementById('waitmodal'));
        const gameCode = document.getElementById('gamecode');
        gameCode.innerText = socket.code;

        waitModal.modal('show');
        assignment = (await socket.on('game-ready'))?.assignment;
        waitModal.modal('hide');

        stateManager.connect(socket);
    }

    // set up chat logs
    {
        new ChatLog(document.getElementById('chatlog'));
    }

    // set up board, painter, other UI elements
    {
        const PIECE_MAP = new Map([
            [1, { icon: 'man', player: 1 }],
            [2, { icon: 'knight', player: 1 }],
            [3, { icon: 'man', player: 2 }],
            [4, { icon: 'knight', player: 2 }],
        ]);
        const SPRITE_NAMES = ['man1', 'man2', 'knight1', 'knight2'];

        const board = new Board(assignment);
        const canvas = new Painter(board, PIECE_MAP, SPRITE_NAMES);
        canvas.ready().then(() => {
            canvas.draw();
        });

        // turn indicator
        stateManager.subscribe('game/turn', (state) => {
            const turnIndicator = document.getElementById('turn-indicator');
            turnIndicator.innerText = state === board.assignment ? 'Your turn' : 'Waiting for opponent ⏳';
            const [oldClass, newClass] = state === board.assignment
                ? ['bg-danger', 'bg-success']
                : ['bg-success', 'bg-danger'];
            turnIndicator.classList.remove(oldClass);
            turnIndicator.classList.add(newClass);
        });
    }
});

