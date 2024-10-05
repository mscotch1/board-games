export default class ChatLog {
    constructor(el, onSend) {
        this.el = el;
        this.chatLog = document.getElementById('chatlog');
        this.chatForm = document.getElementById('chat');
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const form = new FormData(this.chatForm)
            this.chatForm.reset();
            const message = form.get('message');
            this.addMessage(message, true);
            onSend(message);
        });
    }

    addMessage(text, self = false) {
        const timestamp = new Date().toLocaleString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const chatBubble = document.createElement('div');

        const chatBubbleClasses = ['badge', 'rounded-pill', 'text-start', 'text-wrap', 'fs-6', 'm-2'];
        if (self) {
            chatBubbleClasses.push('text-bg-primary', 'align-self-end');
        } else {
            chatBubbleClasses.push('text-bg-secondary', 'align-self-start');
        }

        chatBubble.classList.add(...chatBubbleClasses);
        chatBubble.innerText = `${text}`;
        chatBubble.title = timestamp;

        this.chatLog.appendChild(chatBubble);

    }
}
