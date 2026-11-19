from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template_string, abort
from flask_socketio import SocketIO, emit
from os import path, listdir, getenv

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
        emit("message", {"topic": "game-ready", "message": {"assignment": "1"}}, to=opponent_sid)
        emit("message", {"topic": "game-ready", "message": {"assignment": "2"}}, to=request.sid)


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    opponent_sid = lobby.leave(request.sid)
    if opponent_sid is not None:
        emit("message", {"topic": "opponent-disconnected", "message": {}}, to=opponent_sid)


@socketio.on("message")
def handle_message(message):
    opponent_sid = lobby.opponent(request.sid)
    if opponent_sid is None:
        emit("error", {"error": "No opponent connected"})
        return
    emit("message", message, to=opponent_sid)


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
