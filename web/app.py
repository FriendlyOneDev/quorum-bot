"""Flask app factory for the quorum-bot web frontend.

Player-side v1: calendar view, list view, per-game detail with
join/leave/interested buttons for logged-in users. GM operations stay in
Telegram.
"""
import logging
import os
import secrets
from datetime import datetime, timedelta

# Side-effect import: monkey-patches db.get_conn to use a ThreadedConnectionPool.
# MUST be imported before data_utils in this process's lifetime.
from web import db_pool  # noqa: F401

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, flash, abort, make_response,
)
from itsdangerous import BadSignature, SignatureExpired
from dotenv import load_dotenv

import data_utils
from web import auth, actions

load_dotenv()

logger = logging.getLogger(__name__)


CSRF_KEY = "csrf_token"


def _fmt_date_display(game_date_str):
    """Human-friendly 'Пн 25.07 18:00' rendering; matches the bot's style."""
    if not game_date_str:
        return "—"
    try:
        dt = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return game_date_str
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    return f"{day_names[dt.weekday()]} {dt.strftime('%d.%m')} {dt.strftime('%H:%M')}"


def _player_display(user_row):
    if not user_row:
        return "?"
    return (
        user_row.get("custom_name")
        or user_row.get("display_name")
        or user_row.get("username")
        or str(user_row.get("user_id", "?"))
    )


def _iso_local(game_date_str):
    """ISO 8601 without timezone suffix — FullCalendar interprets in its own TZ."""
    try:
        dt = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None
    return dt.isoformat()


def _parse_iso_naive(s):
    if not s:
        return None
    # FullCalendar sends ISO with tz offset; strip it.
    s = s.split("+")[0].split("Z")[0]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _ensure_csrf():
    if CSRF_KEY not in session:
        session[CSRF_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_KEY]


def _check_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get(CSRF_KEY, "")
    if not submitted or not expected or not secrets.compare_digest(submitted, expected):
        abort(400, description="CSRF token missing or invalid.")


def _game_status(game):
    """Classify a game for template styling."""
    if game.get("cancelled"):
        return "cancelled"
    players = len(game.get("players", []))
    if players >= game.get("max_players", 0):
        return "full"
    return "open"


def create_app():
    app = Flask(__name__)

    secret = os.getenv("WEB_SECRET_KEY")
    if not secret:
        raise RuntimeError("WEB_SECRET_KEY environment variable is not set")
    app.secret_key = secret
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

    app.jinja_env.filters["display_date"] = _fmt_date_display

    @app.context_processor
    def inject_globals():
        uid = auth.current_user_id()
        current_user = data_utils.get_user(uid) if uid else None
        return {
            "current_user": current_user,
            "current_user_id": uid,
            "csrf_token": _ensure_csrf(),
        }

    # ------------------------------------------------------------------ views

    @app.get("/")
    def index():
        return redirect(url_for("calendar_view"))

    @app.get("/calendar")
    def calendar_view():
        return render_template("calendar.html", timezone=str(data_utils.TIMEZONE))

    @app.get("/api/events.json")
    def api_events():
        start = _parse_iso_naive(request.args.get("start"))
        end = _parse_iso_naive(request.args.get("end"))
        events = []
        for g in data_utils.get_all_games():
            if not g.get("game_date"):
                continue
            try:
                dt = datetime.strptime(g["game_date"], "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if start and dt < start:
                continue
            if end and dt > end:
                continue
            status = _game_status(g)
            players = len(g.get("players", []))
            title = g["title"]
            if status == "cancelled":
                title = f"[СКАСОВАНО] {title}"
            elif status == "full":
                title = f"[повна] {title}"
            events.append({
                "id": g["game_id"],
                "title": f"{title} ({players}/{g['max_players']})",
                "start": _iso_local(g["game_date"]),
                "url": url_for("game_detail", game_id=g["game_id"]),
                "classNames": [f"status-{status}"],
            })
        return jsonify(events)

    @app.get("/games")
    def games_list():
        now = datetime.now(data_utils.TIMEZONE).replace(tzinfo=None)
        upcoming, past = [], []
        for g in data_utils.get_all_games():
            gd = g.get("game_date")
            try:
                dt = datetime.strptime(gd, "%Y-%m-%d %H:%M") if gd else None
            except ValueError:
                dt = None
            g["_dt"] = dt
            g["_status"] = _game_status(g)
            if dt and dt >= now:
                upcoming.append(g)
            else:
                past.append(g)
        upcoming.sort(key=lambda x: x["_dt"] or datetime.max)
        past.sort(key=lambda x: x["_dt"] or datetime.min, reverse=True)
        return render_template("games_list.html", upcoming=upcoming, past=past)

    @app.get("/game/<game_id>")
    def game_detail(game_id):
        game = data_utils.get_game(game_id)
        if not game:
            abort(404)

        creator = data_utils.get_user(game["creator_id"]) if game.get("creator_id") else None
        gm_name = _player_display(creator) if creator else "?"

        players = []
        for pid in game.get("players", []):
            players.append({"user_id": pid, "name": _player_display(data_utils.get_user(pid))})

        interested = []
        for uid in game.get("interested", []):
            interested.append({"user_id": uid, "name": _player_display(data_utils.get_user(uid))})

        status = _game_status(game)
        uid = auth.current_user_id()
        is_joined = uid in game.get("players", []) if uid else False
        is_interested = uid in game.get("interested", []) if uid else False

        started = False
        gd = game.get("game_date")
        if gd:
            try:
                dt = datetime.strptime(gd, "%Y-%m-%d %H:%M")
                started = dt.replace(tzinfo=data_utils.TIMEZONE) <= datetime.now(data_utils.TIMEZONE)
            except ValueError:
                pass

        return render_template(
            "game_detail.html",
            game=game, gm_name=gm_name, players=players, interested=interested,
            status=status, is_joined=is_joined, is_interested=is_interested,
            started=started,
        )

    # --------------------------------------------------------------- actions

    @app.post("/game/<game_id>/join")
    @auth.login_required
    def game_join(game_id):
        _check_csrf()
        result = actions.join_game(game_id, auth.current_user_id())
        flash(result.message, result.category)
        return redirect(url_for("game_detail", game_id=game_id))

    @app.post("/game/<game_id>/leave")
    @auth.login_required
    def game_leave(game_id):
        _check_csrf()
        result = actions.leave_game(game_id, auth.current_user_id())
        flash(result.message, result.category)
        return redirect(url_for("game_detail", game_id=game_id))

    @app.post("/game/<game_id>/interested")
    @auth.login_required
    def game_interested(game_id):
        _check_csrf()
        result = actions.toggle_interested(game_id, auth.current_user_id())
        flash(result.message, result.category)
        return redirect(url_for("game_detail", game_id=game_id))

    # --------------------------------------------------------------- auth

    @app.get("/login")
    def login():
        bot_username = os.getenv("BOT_USERNAME", "")
        deep_link = f"https://t.me/{bot_username}?start=weblogin" if bot_username else None
        next_url = request.args.get("next") or url_for("calendar_view")
        return render_template("login.html", deep_link=deep_link, next_url=next_url)

    @app.get("/auth")
    def auth_verify():
        token = request.args.get("token", "")
        if not token:
            flash("Немає токена входу.", "error")
            return redirect(url_for("login"))
        try:
            user_id = auth.verify_token(token)
        except SignatureExpired:
            flash("Посилання застаріло. Запросіть нове через бот.", "warning")
            return redirect(url_for("login"))
        except BadSignature:
            flash("Недійсне посилання.", "error")
            return redirect(url_for("login"))

        user = data_utils.get_user(user_id)
        if not user:
            flash("Користувача не знайдено.", "error")
            return redirect(url_for("login"))

        session.permanent = True
        session[auth.SESSION_KEY] = user_id
        flash(f"Вітаємо, {_player_display(user)}!", "success")
        return redirect(request.args.get("next") or url_for("calendar_view"))

    @app.post("/logout")
    def logout():
        _check_csrf()
        session.pop(auth.SESSION_KEY, None)
        flash("Ви вийшли.", "info")
        return redirect(url_for("calendar_view"))

    @app.errorhandler(404)
    def not_found(_e):
        resp = make_response(render_template("error.html", code=404, message="Не знайдено"), 404)
        return resp

    @app.errorhandler(400)
    def bad_request(e):
        resp = make_response(
            render_template("error.html", code=400, message=str(e.description or "Bad request")), 400
        )
        return resp

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8080")), debug=True)
