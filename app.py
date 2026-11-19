import logging
import re
import time
from os import getenv, path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, request, send_from_directory

# python-socketio only passes a refusal reason on to the client for its own exception
from flask_socketio import ConnectionRefusedError, SocketIO, emit

from game import MAX_PATH_LENGTH, IllegalMove
from ratelimit import RateLimiter
from registry import Refused, Registry
from store import open_store
from variants import VARIANTS

load_dotenv()

log = logging.getLogger(__name__)

BASE_DIR = path.dirname(path.abspath(__file__))
MAX_CHAT_LENGTH = 500
# tokens are made by the browser (or by the server when there isn't one): url-safe base64 of random bytes
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")


def allowed_origins():
    """Origins allowed to open a socket, from CORS_ALLOWED_ORIGINS (comma separated or "*").

    By default only the page's own origin is allowed, which is enough unless a
    proxy rewrites the Host header.
    """
    value = getenv("CORS_ALLOWED_ORIGINS")
    if not value:
        return None
    return "*" if value.strip() == "*" else [o.strip() for o in value.split(",") if o.strip()]


def ttl_from_environment():
    """How long games may sit unchanged before they are deleted (see registry.DEFAULT_TTL)."""
    settings = {
        "waiting": ("WAITING_TTL_HOURS", 3600),
        "playing": ("GAME_TTL_DAYS", 24 * 3600),
        "finished": ("FINISHED_TTL_HOURS", 3600),
    }
    ttl = {}
    for status, (name, unit) in settings.items():
        value = getenv(name)
        if value:
            ttl[status] = float(value) * unit
    return ttl


app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET_KEY")
app.config["STATIC_DIR"] = path.abspath(getenv("STATIC_DIR", path.join(BASE_DIR, "client", "dist")))
# Threading mode (with simple-websocket) works under gunicorn's gthread worker
# without monkey patching. Games are kept in this process's memory (and saved to
# DATA_DIR), so run one worker.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins=allowed_origins())

def int_from_environment(name, default):
    value = getenv(name)
    return int(value) if value not in (None, "") else default


# Limits that keep a public server from being filled with junk (0 turns a limit off)
NEW_GAMES_PER_HOUR = int_from_environment("NEW_GAMES_PER_HOUR", 30)  # per client address
MAX_GAMES = int_from_environment("MAX_GAMES", 5000)  # games saved at once, in total
MESSAGES_PER_SECOND = 50  # per connection, sustained; short bursts of twice that are fine
# Behind a proxy every request comes from the proxy, so the real address is in a header
# (Cloudflare uses CF-Connecting-IP). Only set this when the proxy is trusted to set it.
CLIENT_IP_HEADER = getenv("CLIENT_IP_HEADER") or None

new_game_limiter = (
    RateLimiter(NEW_GAMES_PER_HOUR / 3600, burst=min(NEW_GAMES_PER_HOUR, 10)) if NEW_GAMES_PER_HOUR > 0 else None
)
message_limiter = RateLimiter(MESSAGES_PER_SECOND, burst=2 * MESSAGES_PER_SECOND)

# DATA_DIR is where games are saved so they survive a restart; set it empty to keep them in memory only
registry = Registry(
    open_store(getenv("DATA_DIR", path.join(BASE_DIR, "data"))),
    ttl=ttl_from_environment(),
    max_games=MAX_GAMES or None,
)


def client_address():
    """Who this request is from, for rate limiting."""
    if CLIENT_IP_HEADER:
        forwarded = request.headers.get(CLIENT_IP_HEADER, "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def guard_new_game():
    """Called before a brand-new game is made: one address can't make them without limit."""
    if new_game_limiter is not None and not new_game_limiter.allow(client_address()):
        raise Refused("You have started a lot of games. Please wait a while before starting another.", "rate-limited")


# Which build this is. The Docker image sets these (see the Dockerfile); elsewhere they are "dev".
BUILD = {
    "version": getenv("APP_VERSION") or "dev",
    "commit": getenv("APP_COMMIT") or "",
    "built": getenv("APP_BUILT") or "",
}
STARTED_AT = time.time()


def valid_square(value, size):
    return type(value) is int and 0 <= value < size


def valid_path(value, size):
    return isinstance(value, list) and len(value) <= MAX_PATH_LENGTH and all(valid_square(v, size) for v in value)


# --- talking to players -------------------------------------------------------


def send_to_player(record, token, payload):
    """Send to every connection the player holding `token` has open."""
    for sid in registry.sids(record, token):
        emit("message", payload, to=sid)


def ready_message(record, token):
    """The whole game as one player sees it: sent when a game starts and whenever they come back."""
    opponent = registry.opponent_token(record, token)
    return {
        "topic": "game-ready",
        "message": {
            "side": registry.seat_of(record, token),
            "token": token,
            "state": record.game.snapshot(),
            "chat": record.chat,
            "opponentConnected": registry.online(record, opponent),
        },
    }


def presence_message(connected):
    return {"topic": "opponent-status", "message": {"connected": connected}}


def broadcast_state(record):
    update = {"topic": "game-state", "message": {"state": record.game.snapshot()}}
    for token in record.seats.values():
        send_to_player(record, token, update)


# --- connecting ---------------------------------------------------------------


@socketio.on("connect")
def handle_connect(auth=None):
    auth = auth if isinstance(auth, dict) else {}

    game_code = auth.get("code")
    if not isinstance(game_code, str) or not game_code.strip() or len(game_code) > 64:
        raise ConnectionRefusedError("Missing game code", {"code": "missing-code"})
    game_code = game_code.strip()

    token = auth.get("token")
    if token is not None and not (isinstance(token, str) and TOKEN_PATTERN.fullmatch(token)):
        raise ConnectionRefusedError("Invalid player token", {"code": "bad-token"})

    # Only the player who creates the game gets to choose the variant; whoever joins plays it.
    variant_key = auth.get("variant")
    if variant_key is not None and (not isinstance(variant_key, str) or variant_key not in VARIANTS):
        raise ConnectionRefusedError("Unknown game variant", {"code": "unknown-variant"})

    try:
        attached = registry.attach(
            request.sid,
            game_code,
            token=token,
            resume=auth.get("resume") is True,
            side=auth.get("side"),
            variant_key=variant_key,
            before_create=guard_new_game,
        )
    except Refused as refusal:
        # Refusing the connection tells the client why via connect_error: the message
        # becomes error.message and the data error.data (which a network failure lacks).
        raise ConnectionRefusedError(refusal.message, {"code": refusal.code})

    record, token = attached.record, attached.token

    if attached.kind == "waiting":
        emit("message", {"topic": "waiting", "message": {"token": token}})
    elif attached.kind == "started":
        # the creator may have been waiting on any number of connections (or none, if they have left)
        send_to_player(record, record.creator_token, ready_message(record, record.creator_token))
        emit("message", ready_message(record, token))
    else:
        emit("message", ready_message(record, token))
        opponent = registry.opponent_token(record, token)
        if attached.first_connection and opponent:
            send_to_player(record, opponent, presence_message(True))


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    # Leaving doesn't end the game: the player can come back with their token.
    # Their opponent is just told they are away.
    message_limiter.forget(request.sid)
    detached = registry.detach(request.sid)
    if detached and detached.offline and detached.record.game:
        opponent = registry.opponent_token(detached.record, detached.token)
        if opponent:
            send_to_player(detached.record, opponent, presence_message(False))


# --- messages -----------------------------------------------------------------


@socketio.on("message")
def handle_message(message):
    if not message_limiter.allow(request.sid):
        return  # a client sending this much is broken or hostile; ignore the excess

    session = registry.session(request.sid)
    if session is None:
        emit("error", {"error": "Not in a game"})
        return

    topic = message.get("topic") if isinstance(message, dict) else None
    body = message.get("message") if isinstance(message, dict) else None
    body = body if isinstance(body, dict) else {}
    record = session.record

    if topic == "cancel-game":
        if registry.cancel(request.sid):
            emit("message", {"topic": "game-cancelled", "message": {}})
        return

    game = record.game
    if game is None:
        emit("error", {"error": "No opponent connected"})
        return

    seat = session.seat
    opponent = registry.opponent_token(record, session.token)
    size = game.variant.size

    if topic == "end-turn":
        handle_end_turn(record, seat, body)
    elif topic in ("offer-draw", "respond-draw", "claim-draw"):
        handle_draw(topic, record, seat, opponent, body)
    elif topic == "resign":
        handle_resign(record, seat)
    elif topic == "preview" and valid_path(body.get("moves"), size):
        send_to_player(record, opponent, {"topic": "opponent-preview", "message": {"moves": body["moves"]}})
    elif topic == "hover" and (body.get("index") is None or valid_square(body.get("index"), size)):
        send_to_player(record, opponent, {"topic": "opponent-hover", "message": {"index": body.get("index")}})
    elif topic == "chat" and isinstance(body.get("text"), str):
        text = body["text"].strip()[:MAX_CHAT_LENGTH]
        if text:
            record.add_chat(seat, text)
            registry.save(record)
            send_to_player(record, opponent, {"topic": "chat", "message": {"text": text}})
    # anything else is dropped: clients can't speak for the server


def handle_end_turn(record, seat, body):
    try:
        record.game.play_turn(seat, body.get("moves"))
    except IllegalMove as e:
        emit("message", {"topic": "move-rejected", "message": {"error": str(e)}})
        return

    registry.save(record)
    broadcast_state(record)


def handle_draw(topic, record, seat, opponent, body):
    """Offers, answers to offers, and claims, in variants where the game can be drawn."""
    game = record.game
    declined = False

    try:
        if topic == "offer-draw":
            game.offer_draw(seat)
        elif topic == "claim-draw":
            game.claim_draw(seat)
        else:
            accept = body.get("accept") is True
            game.respond_to_draw(seat, accept)
            declined = not accept
    except IllegalMove as e:
        emit("message", {"topic": "draw-rejected", "message": {"error": str(e)}})
        return

    registry.save(record)
    broadcast_state(record)
    if declined:
        send_to_player(record, opponent, {"topic": "draw-declined", "message": {}})


def handle_resign(record, seat):
    try:
        record.game.resign(seat)
    except IllegalMove as e:
        emit("message", {"topic": "action-rejected", "message": {"error": str(e)}})
        return

    registry.save(record)
    broadcast_state(record)


# --- security headers ---------------------------------------------------------

# Strict transport security only makes sense once the site is served over HTTPS, which a
# proxy such as Cloudflare usually does, so it is opt-in: set HSTS_MAX_AGE (seconds).
HSTS_MAX_AGE = int_from_environment("HSTS_MAX_AGE", 0)


# what a Host header may look like before it is put into the policy (it is chosen by the client)
HOST_PATTERN = re.compile(r"[A-Za-z0-9.-]+(:[0-9]{1,5})?")


def content_security_policy(host):
    """Only this site's own scripts, styles, fonts and images (plus the data: images the
    stylesheet draws its patterns with), and sockets back to this same host. Nothing inline."""
    # 'self' covers same-origin sockets in current browsers; naming the host helps older ones
    sockets = f" ws://{host} wss://{host}" if HOST_PATTERN.fullmatch(host or "") else ""
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            f"connect-src 'self'{sockets}",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


@app.after_request
def add_security_headers(response):
    headers = response.headers
    headers.setdefault("Content-Security-Policy", content_security_policy(request.host))
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
    if HSTS_MAX_AGE > 0:
        headers.setdefault("Strict-Transport-Security", f"max-age={HSTS_MAX_AGE}")
    return response


# --- serving the client -------------------------------------------------------


def no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/version")
def version():
    return no_store(jsonify(BUILD))


@app.get("/healthz")
def healthz():
    """For load balancers and `docker ps`: 200 when the server can read its saved games."""
    try:
        stats = registry.stats()
    except Exception:
        log.exception("health check failed")
        return no_store(jsonify({"status": "error", **BUILD})), 503

    return no_store(jsonify({"status": "ok", **BUILD, "uptimeSeconds": int(time.time() - STARTED_AT), **stats}))


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
