import { io } from 'socket.io-client';

/**
 * A connection to the game server. Everything travels as `{ topic, message }`
 * on a single socket event, and each topic has at most one handler.
 *
 * Reconnecting is turned off on purpose: the server forgets a game when either
 * player disconnects, so a silently reconnected socket would be in a new,
 * empty game that the page knows nothing about.
 */
export function connect(auth) {
  const socket = io({ auth, reconnection: false });
  const handlers = new Map();

  socket.on('message', ({ topic, message }) => handlers.get(topic)?.(message ?? {}));

  return {
    on(topic, handler) {
      handlers.set(topic, handler);
    },

    send(topic, message = {}) {
      socket.emit('message', { topic, message });
    },

    /** The server refused the connection (e.g. the game is full), or couldn't be reached. */
    onRefused(handler) {
      socket.on('connect_error', (error) => handler(error.data ? error.message : 'Could not reach the server'));
    },

    /** An established connection dropped. */
    onLost(handler) {
      socket.on('disconnect', (reason) => {
        if (reason !== 'io client disconnect') {
          handler(reason);
        }
      });
    },

    close() {
      socket.close();
    },
  };
}
