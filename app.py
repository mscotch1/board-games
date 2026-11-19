import random
from os import getenv, path

from dotenv import load_dotenv
from flask import Flask, abort, redirect, request, send_from_directory
# python-socketio only passes a refusal reason on to the client for its own exception
from flask_socketio import ConnectionRefusedError, SocketIO, emit

import rules
from game import MAX_PATH_LENGTH, Game, IllegalMove
from lobby import JoinResult, Lobby
from variants import DEFAULT_VARIANT, VARIANTS

load_dotenv()

BASE_DIR = path.dirname(path.abspath(__file__))
MAX_CHAT_LENGTH = 500


def allowed_origins():
    """Origins allowed to open a socket, from CORS_ALLOWED_ORIGINS (comma separated or "*").

    By default only the page's own origin is allowed, which is enough unless a
    proxy rewrites the Host header.
    """
    value = getenv("CORS_ALLOWED_ORIGINS")
    if not value:
        return None
    return "*" if value.strip() == "*" else [o.strip() for o in value.split(",") if o.strip()]


app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET_KEY")
app.config["STATIC_DIR"] = path.abspath(getenv("STATIC_DIR", path.join(BASE_DIR, "client", "dist")))
# Threading mode (with simple-websocket) works under gunicorn's gthread worker
# without monkey patching. Game state is in process memory, so run one worker.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins=allowed_origins())

lobby = Lobby()
sessions = {}  # sid -> (Game, side), for players currently paired
requested_sides = {}  # sid -> side the waiting player asked for
requested_variants = {}  # sid -> variant the waiting player asked for


def valid_square(value, size):
    return type(value) is int and 0 <= value < size


def valid_path(value, size):
    return isinstance(value, list) and len(value) <= MAX_PATH_LENGTH and all(valid_square(v, size) for v in value)


@socketio.on("connect")
def handle_connect(auth=None):
    auth = auth if isinstance(auth, dict) else {}
    game_code = auth.get("code")
    if not isinstance(game_code, str) or not game_code.strip() or len(game_code) > 64:
        raise ConnectionRefusedError("Missing game code", {"code": "missing-code"})
    game_code = game_code.strip()

    # Only the player who creates the game gets to choose the variant; whoever joins plays it.
    variant_key = auth.get("variant")
    if variant_key is not None and (not isinstance(variant_key, str) or variant_key not in VARIANTS):
        raise ConnectionRefusedError("Unknown game variant", {"code": "unknown-variant"})

    # Whoever gets here first picks a side; anything else means "random". This is
    # recorded before joining so a quick opponent can't pair up before it is stored.
    requested_sides[request.sid] = auth.get("side") if auth.get("side") in (rules.WHITE, rules.BLACK) else None
    requested_variants[request.sid] = VARIANTS.get(variant_key)
    result, opponent_sid = lobby.join(game_code, request.sid)

    if result is JoinResult.FULL:
        requested_sides.pop(request.sid, None)
        requested_variants.pop(request.sid, None)
        # Refusing the connection tells the client why via connect_error: the message
        # becomes error.message and the data error.data (which a network failure lacks).
        raise ConnectionRefusedError("Game already full", {"code": "full"})

    if result is JoinResult.WAITING:
        return

    requested_sides.pop(request.sid, None)
    requested_variants.pop(request.sid, None)
    variant = requested_variants.pop(opponent_sid, None) or DEFAULT_VARIANT
    creator_side = requested_sides.pop(opponent_sid, None) or random.choice((rules.WHITE, rules.BLACK))
    game = Game(variant)
    sessions[opponent_sid] = (game, creator_side)
    sessions[request.sid] = (game, rules.other(creator_side))
    for sid, (_, side) in ((opponent_sid, sessions[opponent_sid]), (request.sid, sessions[request.sid])):
        emit("message", {"topic": "game-ready", "message": {"side": side, "state": game.snapshot()}}, to=sid)


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    sessions.pop(request.sid, None)
    requested_sides.pop(request.sid, None)
    requested_variants.pop(request.sid, None)
    opponent_sid = lobby.leave(request.sid)
    if opponent_sid is not None:
        sessions.pop(opponent_sid, None)
        emit("message", {"topic": "opponent-disconnected", "message": {}}, to=opponent_sid)


@socketio.on("message")
def handle_message(message):
    opponent_sid = lobby.opponent(request.sid)
    session = sessions.get(request.sid)
    if opponent_sid is None or session is None:
        emit("error", {"error": "No opponent connected"})
        return

    topic = message.get("topic") if isinstance(message, dict) else None
    body = message.get("message") if isinstance(message, dict) else None
    body = body if isinstance(body, dict) else {}

    if topic == "end-turn":
        handle_end_turn(body, session, opponent_sid)
    elif topic in ("offer-draw", "respond-draw", "claim-draw"):
        handle_draw(topic, body, session, opponent_sid)
    elif topic == "preview" and valid_path(body.get("moves"), session[0].variant.size):
        emit("message", {"topic": "opponent-preview", "message": {"moves": body["moves"]}}, to=opponent_sid)
    elif topic == "hover" and (body.get("index") is None or valid_square(body.get("index"), session[0].variant.size)):
        emit("message", {"topic": "opponent-hover", "message": {"index": body.get("index")}}, to=opponent_sid)
    elif topic == "chat" and isinstance(body.get("text"), str):
        text = body["text"].strip()[:MAX_CHAT_LENGTH]
        if text:
            emit("message", {"topic": "chat", "message": {"text": text}}, to=opponent_sid)
    # anything else is dropped: clients can't speak for the server


def handle_end_turn(body, session, opponent_sid):
    game, side = session

    try:
        game.play_turn(side, body.get("moves"))
    except IllegalMove as e:
        emit("message", {"topic": "move-rejected", "message": {"error": str(e)}})
        return

    broadcast_state(game, opponent_sid)


def broadcast_state(game, opponent_sid):
    update = {"topic": "game-state", "message": {"state": game.snapshot()}}
    emit("message", update)
    emit("message", update, to=opponent_sid)


def handle_draw(topic, body, session, opponent_sid):
    """Offers, answers to offers, and claims, in variants where the game can be drawn."""
    game, side = session
    declined = False

    try:
        if topic == "offer-draw":
            game.offer_draw(side)
        elif topic == "claim-draw":
            game.claim_draw(side)
        else:
            accept = body.get("accept") is True
            game.respond_to_draw(side, accept)
            declined = not accept
    except IllegalMove as e:
        emit("message", {"topic": "draw-rejected", "message": {"error": str(e)}})
        return

    broadcast_state(game, opponent_sid)
    if declined:
        emit("message", {"topic": "draw-declined", "message": {}}, to=opponent_sid)


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/", defaults={"filename": ""})
@app.get("/<path:filename>")
def serve_file(filename):
    static_dir = app.config["STATIC_DIR"]
    target = path.join(static_dir, filename)

    if path.isdir(target):
        if filename and not request.path.endswith("/"):
            return redirect(request.path + "/")
        filename = path.join(filename, "index.html")

    # build output under assets/ is content-hashed, so it can be cached forever
    max_age = 31536000 if filename.startswith("assets/") else None
    try:
        return send_from_directory(static_dir, filename, max_age=max_age)
    except FileNotFoundError:
        abort(404)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=True, allow_unsafe_werkzeug=True)
