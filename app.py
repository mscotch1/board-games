from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template_string, abort
from flask_socketio import SocketIO, emit
from os import path, listdir, getenv

from game import Game, IllegalMove
from lobby import JoinResult, Lobby

load_dotenv()

WEB_DIR = path.abspath(path.join(__file__, path.pardir, "web"))
GAMES_DIR = path.abspath(path.join(WEB_DIR, "games"))

# Simple HTML template for the index page
INDEX_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Monka-Games | Game Index</title>

    <script src="/modules/jquery.min.js"></script>
    <script src="/modules/bootstrap.bundle.min.js"></script>
    <link href="/modules/bootstrap.min.css" rel="stylesheet">
    <script src="/modules/socket.io.js"></script>
</head>

<body>
    <h1>Start or join a new game</h1>
    <ul class="list-group" style="max-width: 400px">
        {% for game in games %}
        <li class="list-group-item"><a href="/games/{{ game }}/index.html">{{ game }}</a></li>
        {% endfor %}
    </ul>
</body>
</html>
"""

app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET_KEY")
# Threading mode (with simple-websocket) works under gunicorn's gthread worker
# without monkey patching. Game state is in process memory, so run one worker.
socketio = SocketIO(app, async_mode="threading")

lobby = Lobby()
sessions = {}  # sid -> (Game, player), for players currently paired

# The server owns the board, turn and winner. Clients may only relay these
# channels to their opponent; everything else arrives via validated end-turn.
RELAYED_CHANNELS = {"chat", "board/interact/hovercell", "board/turn/move"}
SERVER_SIGNATURE = "server"


def state_dispatch(channel, type_, payload=None):
    action = {"channel": channel, "type": type_, "payload": payload}
    return {"topic": "state-dispatch", "message": {"action": action, "signature": SERVER_SIGNATURE}}


def turn_actions(game):
    actions = [
        state_dispatch("board/pieces", "SET", game.board),
        state_dispatch("game/turn", "SET", game.turn),
    ]
    if game.winner is not None:
        actions.append(state_dispatch("game/winner", "FINISH", {"winner": game.winner}))
    actions.append(state_dispatch("board/turn/move", "RESET"))
    return actions


@socketio.on("connect")
def handle_connect(auth=None):
    game_code = request.headers.get("Game-Code")
    if not game_code:
        raise ConnectionRefusedError({"error": "Missing Game-Code header"})

    result, opponent_sid = lobby.join(game_code, request.sid)

    if result is JoinResult.FULL:
        # Refusing the connection tells the client why via connect_error.
        raise ConnectionRefusedError({"error": "Game already full"})
    if result is JoinResult.PAIRED:
        game = Game()
        sessions[opponent_sid] = (game, "1")
        sessions[request.sid] = (game, "2")
        emit("message", {"topic": "game-ready", "message": {"assignment": "1"}}, to=opponent_sid)
        emit("message", {"topic": "game-ready", "message": {"assignment": "2"}}, to=request.sid)


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    sessions.pop(request.sid, None)
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
    if topic == "end-turn":
        handle_end_turn(message.get("message"), session, opponent_sid)
    elif topic == "state-dispatch" and is_relayable(message.get("message")):
        emit("message", message, to=opponent_sid)
    # anything else is dropped: clients can't speak for the server


def is_relayable(payload):
    action = payload.get("action") if isinstance(payload, dict) else None
    return isinstance(action, dict) and action.get("channel") in RELAYED_CHANNELS


def handle_end_turn(payload, session, opponent_sid):
    game, player = session
    moves = payload.get("moves") if isinstance(payload, dict) else None

    try:
        game.play_turn(player, moves)
    except IllegalMove as e:
        emit("message", {"topic": "move-rejected", "message": {"error": str(e)}})
        return

    for action in turn_actions(game):
        emit("message", action)
        emit("message", action, to=opponent_sid)


@app.route("/", methods=["GET"])
def home():
    games = listdir(GAMES_DIR)
    return render_template_string(INDEX_TEMPLATE, games=games)


@app.route("/<path:filename>", methods=["GET"])
def serve_file(filename):
    try:
        return send_from_directory(WEB_DIR, filename)
    except FileNotFoundError:
        abort(404)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=True, allow_unsafe_werkzeug=True)
