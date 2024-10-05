import { uuidv4 } from './socket.js';

const STATE_MANAGEMENT_CHANNEL = 'state-dispatch';

export default new class StateManager {
    constructor() {
        this.socket = null;
        this.signature = uuidv4();

        this.subscribers = {};  // Store subscribers keyed by channel
        this.reducers = {};     // Reducers keyed by channel
        this.state = {};  // Initial state object
    }

    connect(socket) {
        this.socket = socket;

        this.socket.subscribe(STATE_MANAGEMENT_CHANNEL, ({ action, signature }) => {
            this.dispatch(action, true, signature);
        });
    }

    // Subscribe to a channel
    subscribe(channel, callback) {
        if (!this.subscribers[channel]) {
            this.subscribers[channel] = [];
        }
        this.subscribers[channel].push(callback);
    }

    // Unsubscribe from a channel
    unsubscribe(channel, callback) {
        if (!this.subscribers[channel]) return;
        this.subscribers[channel] = this.subscribers[channel].filter(cb => cb !== callback);
        if (this.subscribers[channel].length === 0) {
            delete this.subscribers[channel];
        }
    }

    // Register a reducer for a specific channel
    registerReducer(channel, reducer, initialState = null) {
        this.reducers[channel] = reducer;
        this.state[channel] = initialState;
    }

    // Dispatch an action to modify the state via a reducer
    dispatch(action, shared = true, signature = this.signature) {
        if (signature === this.signature && shared) {
            // send dispatch to other client
            this.socket?.publish(STATE_MANAGEMENT_CHANNEL, { action, signature });
        }

        const { channel, type, payload } = action;
        if (!this.reducers[channel]) {
            console.warn(`No reducer found for channel: ${channel}`);
            return;
        }

        // Call the reducer to get the new state for the channel
        const currentState = this.state[channel];
        const newState = this.reducers[channel](currentState, { type, payload }, signature);

        // If the state has changed, update it and notify subscribers
        if (newState !== currentState) {
            this.state[channel] = newState;
            this.notifySubscribers(channel, newState);
        }
    }

    // Get the current state of a specific channel
    getState(channel) {
        return this.state[channel];
    }

    // Notify all relevant subscribers, including prefixes
    notifySubscribers(channel, value) {
        for (let subChannel in this.subscribers) {
            if (this.isPrefix(subChannel, channel)) {
                this.subscribers[subChannel].forEach(callback => callback(value, channel));
            }
        }
    }

    // Utility to check if subChannel is a prefix of another channel
    isPrefix(subChannel, channel) {
        const subParts = subChannel.split('/');
        const channelParts = channel.split('/');

        return subParts.every((part, i) => channelParts[i] === part);
    }
}()
