"""Magic-link auth: the bot issues a signed token URL, the web verifies it,
sets a Flask session cookie. No external identity provider, no DB session table.
"""
import os
from functools import wraps

from flask import session, redirect, url_for, request, flash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

TOKEN_TTL_SECONDS = 10 * 60  # magic link valid for 10 minutes
SESSION_KEY = "user_id"
_SALT = "quorum-web-login-v1"


def _serializer(secret: str = None) -> URLSafeTimedSerializer:
    secret = secret or os.getenv("WEB_SECRET_KEY")
    if not secret:
        raise RuntimeError("WEB_SECRET_KEY environment variable is not set")
    return URLSafeTimedSerializer(secret, salt=_SALT)


def issue_token(user_id: int, secret: str = None) -> str:
    """Called from the bot process to mint a magic-link token for a user."""
    return _serializer(secret).dumps({"uid": int(user_id)})


def verify_token(token: str) -> int:
    """Return the user_id if token is valid and unexpired; raise on failure."""
    data = _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
    return int(data["uid"])


def current_user_id():
    return session.get(SESSION_KEY)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user_id() is None:
            flash("Увійдіть, щоб виконати цю дію.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


__all__ = [
    "TOKEN_TTL_SECONDS",
    "SESSION_KEY",
    "issue_token",
    "verify_token",
    "current_user_id",
    "login_required",
    "BadSignature",
    "SignatureExpired",
]
