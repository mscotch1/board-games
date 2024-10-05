export function uuidv4() {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
    (+c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> +c / 4).toString(16)
  );
}

export function generateCode() {
    return Math.random().toString(16).slice(2, 10)
}

export default class Socket {
    constructor(code = generateCode()) {
        this.code = code;

        this.socket = io({
            extraHeaders: {
                'Game-Code': code,
            },
        });
        this.subs = new Map();

        this.socket.on('connect', () => {
            console.info('socket connected!');
        });

        this.socket.on('disconnect', () => {
            console.warn('socket disconnected!');
        });

        this.socket.on('message', ({ topic, message }) => {
            this.subs.get(topic)?.forEach((callback) => callback(message));
        });
    }

    publish(topic, message) {
        this.socket.emit('message', { topic, message, signature: this.signature });
    }

    subscribe(topic, callback) {
        const guid = uuidv4();
        if (!this.subs.has(topic)) {
            this.subs.set(topic, new Map());
        }
        this.subs.get(topic).set(guid, callback);

        return () => {
            this.subs.get(topic).delete(guid);
        };
    }

    on(topic) {
        return new Promise((resolve) => {
            let unsubscribe = this.subscribe(topic, (message) => {
                resolve(message);
                unsubscribe();
            });
        });
    }
}
