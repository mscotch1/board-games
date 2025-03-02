from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template_string, abort
from flask_socketio import SocketIO, emit, send
from os import path, listdir, getenv

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
socketio = SocketIO(app)

clients = {}
new_game_codes = {}


@socketio.on("connect")
def handle_connect(socket):
    game_code = request.headers["Game-Code"]

    if game_code not in clients or game_code not in new_game_codes:
        emit("error", {"error": "Game code not found or game already full"})

    if game_code in new_game_codes:
        opponent_sid = new_game_codes.pop(game_code)
        clients[request.sid] = opponent_sid
        clients[opponent_sid] = request.sid
        emit("message", {"topic": "game-ready", "message": {"assignment": "1"}}, to=opponent_sid)
        emit("message", {"topic": "game-ready", "message": {"assignment": "2"}}, to=request.sid)
    else:
        new_game_codes[game_code] = request.sid
    print(clients)


@socketio.on("disconnect")
def handle_disconnect():
    print("disconnect")
    if request.sid in clients:
        emit("message", "disconnected", to=clients[request.sid])
        del clients[request.sid]

        keys_to_remove = [key for key, value in new_game_codes.items() if value == request.sid]
        for key in keys_to_remove:
            del new_game_codes[key]
    print(clients)


@socketio.on("message")
def handle_message(message):
    print("Received message: " + str(message))
    emit("message", message, to=clients[request.sid])


@app.route("/", methods=["GET", "POST"])
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
