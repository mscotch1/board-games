import { io } from 'socket.io-client';

/**
 * A connection to the game server. Everything travels as `{ topic, message }`
 * on a single socket event, and each topic has at most one handler.
 *
 * `getAuth` is called on every connection attempt, including each reconnect, so
 * it can hand over the latest details (the player's token above all). The
 * connection comes back on its own after a drop or a server restart; the server
 * recognises the token and sends the game again.
 */
export function connect(getAuth) {
  const socket = io({
    auth: (callback) => callback(getAuth()),
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  });
  const handlers = new Map();

  socket.on('message', ({ topic, message }) => handlers.get(topic)?.(message ?? {}));

  return {
    on(topic, handler) {
      handlers.set(topic, handler);
    },

    send(topic, message = {}) {
      socket.emit('message', { topic, message });
    },

    /**
     * The server turned the connection down, with a reason and a machine-readable
     * code (e.g. the game is full or has expired). It won't be retried.
     */
    onRefused(handler) {
      socket.on('connect_error', (error) => {
        if (error.data) {
          handler(error.message, error.data.code);
        }
      });
    },

    /** Called with false when the connection is down (and being retried) and true when it is up. */
    onStatus(handler) {
      socket.on('connect', () => handler(true));
      socket.on('disconnect', (reason) => {
        if (reason !== 'io client disconnect') {
          handler(false);
        }
      });
      // couldn't reach the server (a refusal carries data and is handled above)
      socket.on('connect_error', (error) => {
        if (!error.data) {
          handler(false);
        }
      });
    },

    close() {
      socket.close();
    },
  };
}
