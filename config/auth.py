"""PBKDF2 authentication and short-lived, server-side demo sessions."""
import hashlib
import hmac
import secrets
import threading
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from config.db_connection import transaction

_sessions = {}
_lock = threading.Lock()
_bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000)
    return salt + ':' + digest.hex()


def verify_password(password, encoded):
    try:
        salt, digest = encoded.split(':')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000)
        return hmac.compare_digest(digest, actual.hex())
    except (ValueError, AttributeError):
        return False


def login(username, password):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('SELECT password_hash, app_role, ma_kh FROM '
                    'quan_ly_shop.app_principals WHERE username=%s', (username,))
        row = cur.fetchone()
    if row is None or not verify_password(password, row[0]):
        raise HTTPException(401, 'Sai tài khoản hoặc mật khẩu')
    token = secrets.token_urlsafe(32)
    principal = {'username': username, 'role': row[1], 'ma_kh': row[2]}
    with _lock:
        now = time.time()
        for key in list(_sessions):
            if _sessions[key][0] < now:
                del _sessions[key]
        _sessions[token] = (now + 3600, principal)
    return {'token': token, 'principal': principal, 'expires_in': 3600}


def current_user(auth: HTTPAuthorizationCredentials = Depends(_bearer)):
    principal = session_user(auth.credentials if auth else None)
    if principal is None:
        raise HTTPException(401, 'Vui lòng đăng nhập lại')
    return principal


def session_user(token):
    """Read identity for page navigation and audit logs, without trusting input roles."""
    with _lock:
        session = _sessions.get(token) if token else None
        if not session:
            return None
        if session[0] < time.time():
            _sessions.pop(token, None)
            return None
        return dict(session[1])


def roles(*allowed):
    def dependency(user=Depends(current_user)):
        if user['role'] not in allowed:
            raise HTTPException(403, 'Không có quyền thực hiện thao tác')
        return user
    return dependency


def logout(token):
    with _lock:
        _sessions.pop(token, None)
