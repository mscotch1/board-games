import stateManager from './state.js';

export default class ChatLog {
    constructor(el) {
        this.el = el;
        this.chatLog = document.getElementById('chatlog');
        this.chatForm = document.getElementById('chat');
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const form = new FormData(this.chatForm)
            this.chatForm.reset();
            const payload = form.get('message');
            stateManager.dispatch({ channel: 'chat', type: 'NEW_MESSAGE', payload });
        });

        stateManager.registerReducer('chat', (state, action, signature) => {
            switch (action?.type) {
                case 'NEW_MESSAGE':
                    return state.concat([{ message: action.payload, signature }]);
                default:
                    return state;
            }
        }, []);
        stateManager.subscribe('chat', (allMessages) => { this._renderMessages(allMessages); });
    }

    _renderMessages(allMessages) {
        this.chatLog.innerHTML = '';

        allMessages.forEach(({ message, signature }) => {
            const timestamp = new Date().toLocaleString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const chatBubble = document.createElement('div');

            const chatBubbleClasses = ['badge', 'rounded-pill', 'text-start', 'text-wrap', 'fs-6', 'm-2'];
            if (signature === stateManager.signature) {
                chatBubbleClasses.push('text-bg-primary', 'align-self-end');
            } else {
                chatBubbleClasses.push('text-bg-secondary', 'align-self-start');
            }

            chatBubble.classList.add(...chatBubbleClasses);
            chatBubble.innerText = message;
            chatBubble.title = timestamp;

            this.chatLog.appendChild(chatBubble);
        });
    }
}
