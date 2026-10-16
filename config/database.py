"""Bounded, thread-safe leasing around the requested SimpleConnectionPool."""
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
_pool = None
_lock = threading.RLock()
_slots = threading.BoundedSemaphore(20)


def _get_pool():
    global _pool
    with _lock:
        if _pool is None:
            _pool = SimpleConnectionPool(
                1, 20, host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME", "GarenaShop_DB"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD"), connect_timeout=5,
                options="-c statement_timeout=15000 -c lock_timeout=5000",
            )
        return _pool


class PooledConnection:
    """Legacy close() returns a clean lease instead of leaking pool slots."""
    def __init__(self, raw):
        self._raw = raw
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._raw, name)

    @property
    def closed(self):
        return self._returned or self._raw.closed

    @property
    def autocommit(self):
        return self._raw.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._raw.autocommit = value

    def close(self):
        if self._returned:
            return
        discard = bool(self._raw.closed)
        try:
            if not discard:
                self._raw.rollback()
                self._raw.autocommit = True
                with self._raw.cursor() as cur:
                    cur.execute("UNLISTEN *")
                    cur.execute("RESET ROLE")
                    cur.execute("RESET ALL")
                    cur.execute("SELECT set_config('app.current_user_id', '', false)")
                self._raw.notifies.clear()
                self._raw.set_session(autocommit=False, readonly=False,
                                      isolation_level='READ COMMITTED',
                                      deferrable=False)
        except Exception:
            discard = True
        finally:
            self._returned = True
            with _lock:
                _get_pool().putconn(self._raw, close=discard)
            _slots.release()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.rollback() if kind else self.commit()
        finally:
            self.close()


def get_db_connection():
    if not _slots.acquire(timeout=10):
        raise TimeoutError("Database pool exhausted")
    try:
        with _lock:
            raw = _get_pool().getconn()
        return PooledConnection(raw)
    except Exception:
        _slots.release()
        raise


@contextmanager
def transaction(role=None, customer=None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if role:
                cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            cur.execute("SELECT set_config('app.current_user_id', %s, true)",
                        (customer or "",))
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
