"""Integration demo for PostgreSQL 16; run against a test database.

Run from the project root: python tests/run_full_demo_test.py
Requires models/01..04 and a superuser configured through .env.
Fixtures are committed for cross-connection tests, then removed in finally.
The suite never creates/replaces application policies or disables RLS.
"""

from __future__ import annotations

import json
import select
import sys
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import tempfile



def configure_output() -> None:
    """Prevent Windows console encoding errors, including dependency prints."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass


def safe_print(text: object = "") -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        rendered = str(text).encode(encoding, "backslashreplace")
        print(rendered.decode(encoding), flush=True)


configure_output()
# Supports direct invocation from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psycopg2
    from psycopg2 import errors, sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import Json

    from config.db_connection import get_db_connection, transaction
    from controllers import shop_service as shop
    from controllers.ai3_fraud_guard_controller import check_and_lock_fraud
    from controllers import ai4_nl2sql_chatbot_controller as chatbot
except ImportError as exc:
    safe_print(f"FAIL: thiếu dependency/module: {exc}")
    safe_print("Chạy: python -m pip install -r requirements.txt")
    raise SystemExit(1) from exc


def require(condition: bool, message: str) -> None:
    """An assertion that remains active even under python -O."""
    if not condition:
        raise AssertionError(message)


@dataclass
class Result:
    name: str
    passed: bool
    elapsed: float
    detail: str


class RecordingCursor:
    """Delegate to a real cursor, recording the SQL actually executed."""

    def __init__(self, cursor, statements):
        self.cursor = cursor
        self.statements = statements

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, query, parameters=None):
        self.statements.append((query, parameters))
        return self.cursor.execute(query, parameters)


class RecordingConnection:
    def __init__(self, connection, statements):
        self.connection = connection
        self.statements = statements

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def cursor(self, *args, **kwargs):
        return RecordingCursor(
            self.connection.cursor(*args, **kwargs), self.statements
        )


def plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes(child)


class DemoSuite:
    def __init__(self):
        self.conn = None
        self.results = []
        token = uuid.uuid4().hex[:8]
        self.customer = "k" + token  # Fits VARCHAR(10), also the role name.
        self.other_customer = "o" + token
        self.game = "g" + token
        self.game_name = "Liên Quân Test " + token
        self.employee = "v" + token
        self.nicks = {
            name: prefix + token for name, prefix in (
                ("owned", "own"), ("other", "oth"), ("match", "yes"),
                ("expensive", "exp"), ("wrong_skin", "bad"),
                ("boundary", "lim"), ("event", "evt"),
            )
        }
        self.orders = ["d1" + token, "d2" + token]
        self.role_created = False

    def run_case(self, name, function):
        started = time.perf_counter()
        passed = False
        detail = ""
        try:
            detail = function() or "Đúng kỳ vọng"
            passed = True
        except Exception as exc:
            state = getattr(exc, "pgcode", None)
            detail = f"{type(exc).__name__}: {exc}"
            if state:
                detail = f"SQLSTATE={state}; {detail}"
        finally:
            # Reset transactions AND SET ROLE/SET LOCAL even after SQL errors.
            if self.conn is not None and not self.conn.closed:
                try:
                    self.conn.rollback()
                except psycopg2.Error as exc:
                    passed = False
                    detail += f"; rollback thất bại: {exc}"
        result = Result(name, passed, time.perf_counter() - started, detail)
        self.results.append(result)
        safe_print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        safe_print(f"  {detail}")
        return passed

    def prepare(self):
        self.conn = get_db_connection()
        self.conn.set_client_encoding("UTF8")
        with self.conn.cursor() as cur:
            cur.execute("SET statement_timeout = '15s'")
            cur.execute("SET lock_timeout = '5s'")
            cur.execute("SELECT current_setting('server_version_num')::int")
            version = cur.fetchone()[0]
            require(version >= 160000, "Cần PostgreSQL 16 trở lên")
            safe_print(f"  Server version: {version}; DB: "
                       f"{self.conn.info.dbname}")
            cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s",
                        (self.conn.info.user,))
            require(cur.fetchone()[0], "Suite cần kết nối bằng superuser")
            cur.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN "
                "('NhanVienSale', 'KhachHangRole')"
            )
            require(len(cur.fetchall()) == 2, "Thiếu role; chạy models/02")
            cur.execute(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE oid = 'quan_ly_shop.tai_khoan_game'::regclass"
            )
            require(cur.fetchone()[0], "RLS chưa được bật; chạy models/03")
            cur.execute(sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS"
            ).format(sql.Identifier(self.customer)))
            cur.execute(sql.SQL(
                'GRANT "KhachHangRole" TO {} WITH INHERIT TRUE'
            ).format(sql.Identifier(self.customer)))
            cur.execute(
                "INSERT INTO quan_ly_shop.danh_muc_game VALUES (%s, %s)",
                (self.game, self.game_name),
            )
            cur.executemany(
                "INSERT INTO quan_ly_shop.khach_hang "
                "(ma_kh, ho_ten, so_du_vi) VALUES (%s, %s, 0)",
                [(self.customer, "KHÁCH TEST"),
                 (self.other_customer, "KHÁCH TEST KHÁC")],
            )
            cur.execute(
                "INSERT INTO quan_ly_shop.nhan_vien "
                "(ma_nv, ho_ten, luong, mat_khau) VALUES (%s, %s, %s, %s)",
                (self.employee, "NHÂN VIÊN TEST", 10000000, "test_only"),
            )
            for name, price, status, skins in (
                ("owned", 350000, "Da_ban", ["Raz Muay Thai"]),
                ("other", 350000, "Da_ban", ["Raz Muay Thai"]),
                ("match", 350000, "Chua_ban", ["Raz Muay Thai"]),
                ("expensive", 500000, "Chua_ban", ["Raz Muay Thai"]),
                ("wrong_skin", 250000, "Chua_ban", ["Skin khác"]),
                ("boundary", 400000, "Chua_ban", ["Raz Muay Thai"]),
            ):
                self.insert_nick(cur, self.nicks[name], price, status, skins)
            cur.executemany(
                "INSERT INTO quan_ly_shop.don_hang "
                "(ma_dh, ma_kh, ma_nick, tong_tien) VALUES (%s, %s, %s, %s)",
                [(self.orders[0], self.customer, self.nicks["owned"], 350000),
                 (self.orders[1], self.other_customer,
                  self.nicks["other"], 350000)],
            )
        self.conn.commit()
        self.role_created = True
        return f"Fixture đã commit; role khách tạm: {self.customer}"

    def insert_nick(self, cur, nick, price, status, skins, image=None):
        cur.execute(
            "INSERT INTO quan_ly_shop.tai_khoan_game "
            "(ma_nick, ma_game, gia_ban, trang_thai, thong_tin_chi_tiet, "
            "mat_khau_game, anh_dinh_kem_url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (nick, self.game, price, status,
             Json({"SkinHiem": skins}), "test_password_" + nick, image),
        )

    def expect_error(self, query, params, error_type, state, table=None):
        with self.conn.cursor() as cur:
            cur.execute("SAVEPOINT expected_failure")
            try:
                cur.execute(query, params)
            except psycopg2.Error as exc:
                cur.execute("ROLLBACK TO SAVEPOINT expected_failure")
                require(isinstance(exc, error_type),
                        f"Sai loại lỗi: {type(exc).__name__}")
                require(exc.pgcode == state, f"Sai SQLSTATE: {exc.pgcode}")
                if table:
                    require(
                        exc.diag.table_name == table,
                        f"Lỗi ở bảng khác: {exc.diag.table_name}",
                    )
                if state in {"23514", "23503"}:
                    require(bool(exc.diag.constraint_name),
                            "Lỗi không chỉ ra constraint")
                return f"{error_type.__name__}; SQLSTATE={state}"
            else:
                cur.execute("ROLLBACK TO SAVEPOINT expected_failure")
                raise AssertionError("SQL thành công trong khi phải bị chặn")
            finally:
                cur.execute("RELEASE SAVEPOINT expected_failure")

    def invalid_phone(self):
        return self.expect_error(
            "INSERT INTO quan_ly_shop.khach_hang "
            "(ma_kh, ho_ten, so_dien_thoai) VALUES (%s, %s, %s)",
            ("b" + self.customer[1:], "SAI SĐT", "12345"),
            errors.CheckViolation, "23514", "khach_hang",
        )

    def negative_price(self):
        return self.expect_error(
            "INSERT INTO quan_ly_shop.tai_khoan_game "
            "(ma_nick, ma_game, gia_ban, mat_khau_game) "
            "VALUES (%s, %s, %s, %s)",
            ("neg" + self.customer[1:], self.game, -50000, "test_only"),
            errors.CheckViolation, "23514", "tai_khoan_game",
        )

    def restricted_delete(self):
        return self.expect_error(
            "DELETE FROM quan_ly_shop.khach_hang WHERE ma_kh = %s",
            (self.customer,), errors.ForeignKeyViolation, "23503",
            "don_hang",
        )

    def denied_column(self, table, column):
        with self.conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE "NhanVienSale"')
            # Positive control: ensure the role can read allowed columns.
            allowed = "ma_nv" if table == "nhan_vien" else "ma_nick"
            cur.execute(sql.SQL("SELECT {} FROM quan_ly_shop.{} LIMIT 1")
                        .format(sql.Identifier(allowed),
                                sql.Identifier(table)))
            require(cur.fetchone() is not None, "Không đọc được cột cho phép")
        return self.expect_error(
            sql.SQL("SELECT {} FROM quan_ly_shop.{}").format(
                sql.Identifier(column), sql.Identifier(table)
            ), None, errors.InsufficientPrivilege, "42501",
        )

    def select_owned(self, cur):
        cur.execute(
            "SELECT ma_nick, mat_khau_game "
            "FROM quan_ly_shop.tai_khoan_game WHERE ma_nick = ANY(%s)",
            ([self.nicks["owned"], self.nicks["other"]],),
        )
        return cur.fetchall()

    def row_security(self):
        with self.conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE "KhachHangRole"')
            cur.execute("SELECT set_config('app.current_user_id', %s, true)",
                        (self.customer,))
            require(self.select_owned(cur) == [
                (self.nicks['owned'], 'test_password_' + self.nicks['owned'])
            ], 'RLS không phân biệt chủ đơn')
            cur.execute('SELECT mat_khau_game FROM quan_ly_shop.tai_khoan_game '
                        'WHERE ma_nick=%s', (self.nicks['match'],))
            require(cur.fetchall() == [], 'Bảng gốc lộ mật khẩu nick chưa bán')
            cur.execute('SELECT mat_khau_game,email_khoi_phuc FROM '
                        'quan_ly_shop.vw_catalog_nick WHERE ma_nick=%s',
                        (self.nicks['match'],))
            require(cur.fetchone() == (None, None), 'Public view chưa mask pass')
            cur.execute("SELECT set_config('app.current_user_id', %s, true)",
                        (self.other_customer,))
            require(self.select_owned(cur) == [
                (self.nicks['other'], 'test_password_' + self.nicks['other'])
            ], 'Ngữ cảnh khách thứ hai bị rò')
        with transaction('KhachHangRole', self.customer) as leased:
            with leased.cursor() as cur:
                cur.execute("SELECT current_user")
        with transaction() as leased, leased.cursor() as cur:
            cur.execute("SELECT current_user=session_user, "
                        "current_setting('app.current_user_id',true)")
            same, setting = cur.fetchone()
            require(same and setting in ('', None), 'Pool làm rò role/ma_kh')
        return 'GUC identity, owner-only RLS, public NULL, pool reset: đúng'

    def fraud_lock(self):
        check_and_lock_fraud(self.nicks['owned'])
        try:
            with transaction('KhachHangRole', self.customer) as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT mat_khau_game FROM '
                                'quan_ly_shop.tai_khoan_game WHERE ma_nick=%s',
                                (self.nicks['owned'],))
                    require(cur.fetchall() == [], 'AI3 chưa thu hồi credentials')
        finally:
            with transaction() as conn, conn.cursor() as cur:
                cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET "
                            "trang_thai='Da_ban' WHERE ma_nick=%s",
                            (self.nicks['owned'],))
        return 'Đã gọi controller AI3 thật và kiểm chứng RLS'

    def explain(self, query, params=None, forced=False):
        with self.conn.cursor() as cur:
            cur.execute("SET LOCAL enable_seqscan = " +
                        ("off" if forced else "on"))
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query,
                        params)
            plan = cur.fetchone()[0][0]
        nodes = list(plan_nodes(plan["Plan"]))
        names = [node["Index Name"] for node in nodes if "Index Name" in node]
        safe_print(
            f"  {'Minh họa index' if forced else 'Planner tự nhiên'}: "
            f"{plan['Plan']['Node Type']}; indexes={names}; "
            f"Execution Time={plan['Execution Time']:.3f} ms"
        )
        return nodes

    def verify_index(self, query, params, name):
        natural = self.explain(query, params)
        eligible = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}

        def found(nodes):
            return any(node.get("Index Name") == name and
                       node.get("Node Type") in eligible for node in nodes)

        if found(natural):
            return "planner tự nhiên"
        forced = self.explain(query, params, forced=True)
        require(found(forced), f"Không thấy {name} trong execution plan")
        return "enable_seqscan=off (khả năng dùng index, không đo tăng tốc)"

    def partial_index(self):
        mode = self.verify_index(
            "SELECT * FROM quan_ly_shop.tai_khoan_game "
            "WHERE trang_thai = 'Chua_ban'", None, "idx_nick_san_co",
        )
        return f"idx_nick_san_co được sử dụng: {mode}"

    def gin_and_chatbot(self):
        statements = []
        connections = []

        def recorded_connect():
            connection = get_db_connection()
            connections.append(connection)
            return RecordingConnection(connection, statements)

        try:
            with patch.object(chatbot, "get_db_connection", recorded_connect):
                rows = chatbot.nl2sql_translate_and_execute(
                    "Tìm nick Liên Quân dưới 400k có skin Raz Muay Thai"
                )
            require(isinstance(rows, list) and all(
                isinstance(row, dict) for row in rows
            ), "Controller phải trả danh sách dict")
            require(any(isinstance(query, str) and
                        "nick.thong_tin_chi_tiet @> %s::jsonb" in query
                        for query, _ in statements),
                    "SQL thực thi không dùng JSONB @> với tham số")
            fixture_ids = set(self.nicks.values())
            returned = {row["ma_nick"] for row in rows}
            require(returned & fixture_ids == {self.nicks["match"]},
                    "Sai nick: cần loại nick đã bán, sai skin, >= 400k")
            for row in rows:
                require(row["trang_thai"] == "Chua_ban" and
                        Decimal(row["gia_ban"]) < 400000 and
                        "liên quân" in row["ten_game"].casefold() and
                        "Raz Muay Thai" in
                        row["thong_tin_chi_tiet"].get("SkinHiem", []),
                        f"Kết quả ngoài điều kiện: {row['ma_nick']}")
        finally:
            for connection in connections:
                if not connection.closed:
                    connection.close()
        mode = self.verify_index(
            "SELECT ma_nick FROM quan_ly_shop.tai_khoan_game "
            "WHERE thong_tin_chi_tiet @> %s::jsonb",
            (Json({"SkinHiem": ["Raz Muay Thai"]}),),
            "idx_gin_thong_tin_nick",
        )
        return f"AI4 trả đúng nick/điều kiện; GIN được sử dụng: {mode}"

    def notification(self):
        listener = None
        try:
            listener = get_db_connection()
            listener.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with listener.cursor() as cur:
                cur.execute("LISTEN kenh_ai_garena")
            with self.conn.cursor() as cur:
                self.insert_nick(cur, self.nicks["event"], 320000,
                                 "Chua_ban", ["Raz Muay Thai"])
            self.conn.commit()  # NOTIFY is delivered only after commit.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                listener.poll()
                while listener.notifies:
                    notify = listener.notifies.pop(0)
                    try:
                        payload = json.loads(notify.payload)
                    except (json.JSONDecodeError, UnicodeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("ma_nick") != self.nicks["event"]:
                        continue  # Other writers can share this channel.
                    require(notify.channel == "kenh_ai_garena", "Sai kênh")
                    require(payload.get("event") == "NEW_NICK_INSERTED",
                            "Sai event trong payload")
                    require(payload.get("ma_game") == self.game,
                            "Sai ma_game trong payload")
                    require("anh_url" in payload, "Payload thiếu anh_url")
                    require("mat_khau_game" not in payload,
                            "Notification làm lộ mật khẩu")
                    return f"Đã nhận payload đúng cho {self.nicks['event']}"
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    select.select([listener], [], [], min(remaining, 1))
            raise AssertionError("Hết 10 giây, chưa nhận NOTIFY đúng nick")
        finally:
            if listener is not None:
                listener.close()

    def staff_rbac(self):
        self.denied_column('nhan_vien', 'luong')
        self.conn.rollback()
        self.denied_column('tai_khoan_game', 'mat_khau_game')
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE "NhanVienSale"')
        for query in (
            'DELETE FROM quan_ly_shop.tai_khoan_game WHERE false',
            'UPDATE quan_ly_shop.khach_hang SET so_du_vi=0 WHERE false',
            "UPDATE quan_ly_shop.tai_khoan_game SET mat_khau_game='bad' WHERE false",
        ):
            self.expect_error(query, None, errors.InsufficientPrivilege, '42501')
        with self.conn.cursor() as cur:
            cur.execute('UPDATE quan_ly_shop.tai_khoan_game SET gia_ban=gia_ban '
                        'WHERE ma_nick=%s', (self.nicks['match'],))
            require(cur.rowcount == 1, 'Staff không sửa được giá public')
            self.insert_nick(cur, 's'+self.customer, 60000, 'Chua_ban', [])
        return 'Sale bị cấm lương/pass/DELETE/ví; được INSERT và UPDATE giá'

    def cart_business(self):
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('UPDATE quan_ly_shop.khach_hang SET so_du_vi=1000000 '
                        'WHERE ma_kh=ANY(%s)',
                        ([self.customer, self.other_customer],))
            cur.execute('INSERT INTO quan_ly_shop.danh_sach_yeu_thich '
                        '(ma_kh,ma_nick) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                        (self.customer, self.nicks['match']))
            cur.execute('SELECT count(*) FROM quan_ly_shop.danh_sach_yeu_thich '
                        'WHERE ma_kh=%s AND ma_nick=%s',
                        (self.customer, self.nicks['match']))
            require(cur.fetchone()[0] == 1, 'Wishlist chưa được ghi')
        barrier = threading.Barrier(2)
        def compete(customer):
            barrier.wait(timeout=5)
            try:
                shop.add_cart(customer, self.nicks['match'])
                return customer
            except shop.ShopError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(compete, c) for c in
                       (self.customer, self.other_customer)]
            winners = [f.result(timeout=20) for f in futures]
        require(sum(w is not None for w in winners) == 1,
                'Race condition: phải đúng một người giữ được nick')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('SELECT EXTRACT(EPOCH FROM(han_giu_cho-thoi_gian_tao)) '
                        'FROM quan_ly_shop.gio_hang WHERE ma_nick=%s',
                        (self.nicks['match'],))
            require(cur.fetchone()[0] == 900, 'Không giữ đúng 15 phút')
            cur.execute("UPDATE quan_ly_shop.gio_hang SET han_giu_cho="
                        "CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE ma_nick=%s",
                        (self.nicks['match'],))
        shop.expire_cart()
        shop.add_cart(self.customer, self.nicks['match'])
        result = shop.checkout(self.customer)
        require(result['total'] == 350000 and result['balance'] == 650000,
                'Checkout sai tiền')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM quan_ly_shop.don_hang_lich_su '
                        'WHERE ma_nick=%s', (self.nicks['match'],))
            require(cur.fetchone()[0] == 1, 'Không ghi lịch sử phân mảnh')
        shop.add_cart(self.customer, self.nicks['expensive'])
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('UPDATE quan_ly_shop.khach_hang SET so_du_vi=0 '
                        'WHERE ma_kh=%s', (self.customer,))
        try:
            shop.checkout(self.customer)
        except shop.ShopError:
            pass
        else:
            raise AssertionError('Checkout cho phép mua khi thiếu tiền')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM quan_ly_shop.don_hang '
                        'WHERE ma_nick=%s', (self.nicks['expensive'],))
            require(cur.fetchone()[0] == 0, 'Checkout lỗi vẫn tạo đơn')
        shop.remove_cart(self.customer, self.nicks['expensive'])
        return 'Wishlist, race 2 connections, TTL=900s, expiry, ACID checkout: đúng'

    def wallet_business(self):
        event = 'pay'+self.customer
        result = shop.deposit(self.customer, 100000, 'SEPAY_QR', event,
                              description='NAP '+self.customer)
        require(not result['duplicate'], 'Giao dịch mới bị đánh dấu trùng')
        require(shop.deposit(self.customer, 100000, 'SEPAY_QR', event,
                             description='NAP '+self.customer)['duplicate'],
                'Replay SePay chưa idempotent')
        serial = '#GARENA*'+str(int(self.customer[1:],16)).zfill(8)[-8:]
        card = '$CARD&'+str(int(self.customer[1:],16)).zfill(10)[-10:]
        shop.deposit(self.customer, 50000, 'THE_CAO', 'card'+self.customer,
                     serial=serial, card=card)
        for args in (
            (self.customer, 50000, 'THE_CAO', 'bad'+self.customer, 'wrong', card),
            (self.other_customer, 50000, 'THE_CAO', 'dup'+self.customer, serial, card),
        ):
            try:
                shop.deposit(*args)
            except shop.ShopError:
                pass
            else:
                raise AssertionError('Thẻ sai/trùng vẫn được nạp')
        pending = 'pending'+self.customer
        shop.deposit(self.customer, 20000, 'SEPAY_QR', pending,
                     description='NPA '+self.customer)
        shop.recheck_sepay(pending, self.customer)
        require(shop.recheck_sepay(pending, self.customer)['duplicate'],
                'Staff duyệt lặp gây cộng tiền lần hai')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('SELECT so_du_vi FROM quan_ly_shop.khach_hang '
                        'WHERE ma_kh=%s', (self.customer,))
            require(cur.fetchone()[0] == 170000, 'Sai số dư sau nạp và replay')
        with transaction('NhanVienSale') as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM quan_ly_shop.vw_lich_su_nap_staff '
                        'WHERE ma_kh=%s', (self.customer,))
            require(len(cur.fetchall()) == 3, 'View Staff thiếu giao dịch')
            require({d.name for d in cur.description} == {
                'ma_giao_dich','ma_kh','so_tien','phuong_thuc','trang_thai','ngay_tao'
            }, 'View Staff làm lộ dữ liệu thẻ/số dư')
        overflow_event = 'overflow'+self.customer
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('UPDATE quan_ly_shop.khach_hang SET '
                        'so_du_vi=9999999999999.99 WHERE ma_kh=%s',
                        (self.customer,))
        try:
            try:
                shop.deposit(self.customer, 10000, 'SEPAY_QR', overflow_event,
                             description='NAP '+self.customer)
            except errors.NumericValueOutOfRange:
                pass
            else:
                raise AssertionError('Ví vượt precision vẫn được cộng tiền')
            with transaction() as conn, conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM quan_ly_shop.lich_su_nap_tien '
                            'WHERE ma_giao_dich=%s', (overflow_event,))
                require(cur.fetchone()[0] == 0, 'Nạp lỗi vẫn ghi ledger thành công')
        finally:
            with transaction() as conn, conn.cursor() as cur:
                cur.execute('UPDATE quan_ly_shop.khach_hang SET so_du_vi=170000 '
                            'WHERE ma_kh=%s', (self.customer,))
        return 'SePay/thẻ/replay/ACID rollback; ví=170000; view Staff 6 cột'

    def api_regressions(self):
        from fastapi.testclient import TestClient
        from app import app
        from config.auth import hash_password
        from controllers.etl_cleaner_controller import etl_clean_customers
        from controllers import ai1_vision_ocr_controller as ocr
        from controllers.ai6_reconcile_controller import reconcile_assistant
        from controllers.ai7_dba_optimizer_controller import diagnostics
        from controllers.ai8_dispute_controller import evaluate_dispute
        from controllers import ai2_pricing_controller as ai2
        from controllers import ai5_marketing_controller as ai5
        password = uuid.uuid4().hex
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('INSERT INTO quan_ly_shop.app_principals '
                        '(username,password_hash,app_role,ma_kh) VALUES '
                        '(%s,%s,%s,%s),(%s,%s,%s,NULL),(%s,%s,%s,NULL)',
                        (self.customer, hash_password(password),'user',self.customer,
                         'a'+self.customer,hash_password(password),'admin',
                         's'+self.customer,hash_password(password),'staff'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'customer.csv'
            path.write_text('ma_kh,ho_ten,so_dien_thoai,so_du_vi\n'+
                            self.customer+', updated name ,0901234567,0\n',
                            encoding='utf-8')
            require(etl_clean_customers(path)['loaded'] == 1, 'ETL thất bại')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute('SELECT so_du_vi FROM quan_ly_shop.khach_hang '
                        'WHERE ma_kh=%s', (self.customer,))
            require(cur.fetchone()[0] == 170000, 'ETL ghi đè tiền ví')
            cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET "
                        "thong_tin_chi_tiet=jsonb_build_object('ngay_nhap_kho',"
                        "(CURRENT_DATE-40)::text),gia_ban=51000 WHERE ma_nick=%s",
                        (self.nicks['wrong_skin'],))
        # Isolate OCR inference for this DB merge regression, not an OCR accuracy test.
        with patch.object(ocr, 'extract_game_data', return_value={'Rank':'TEST'}):
            ocr.process_game_screenshot(self.nicks['wrong_skin'],
                                        'https://example.com/image.png',self.game)
        with self.conn.cursor() as cur:
            cur.execute('SELECT quan_ly_shop.fn_giam_gia_nick_ton_kho()')
            cur.execute("SELECT gia_ban,thong_tin_chi_tiet->>'ngay_nhap_kho' "
                        'FROM quan_ly_shop.tai_khoan_game WHERE ma_nick=%s',
                        (self.nicks['wrong_skin'],))
            price, imported = cur.fetchone()
            require(price == 50000 and imported, 'Sai sàn giá/merge OCR')
        self.conn.rollback()  # No persistent discount to unrelated inventory.
        @contextmanager
        def isolated_transaction(*args, **kwargs):
            yield self.conn
        with patch.object(ai2, 'transaction', isolated_transaction):
            require('message' in ai2.run_pricing(), 'Controller AI2 lỗi')
        self.conn.rollback()
        with self.conn.cursor() as cur:
            # Existing recent purchase is moved back inside this rolled-back test.
            cur.execute("UPDATE quan_ly_shop.don_hang_lich_su SET ngay_tao="
                        "CURRENT_TIMESTAMP-INTERVAL '70 days' WHERE ma_kh=%s",
                        (self.customer,))
        with patch.object(ai5, 'transaction', isolated_transaction):
            vouchers = ai5.run_marketing()
            require(any(row['ma_kh'] == self.customer and
                        row['voucher'] == 'TRIAN20PCT' for row in vouchers),
                    'AI5 chưa cấp voucher cho khách >60 ngày')
        self.conn.rollback()
        require(reconcile_assistant('NAP '+self.customer)['automatic_credit'] is False,
                'AI6 tự ý cộng tiền')
        require(isinstance(diagnostics(), list), 'AI7 thiếu diagnostics')
        require(evaluate_dispute(self.nicks['owned'],5,True,True)
                ['recommend_refund'], 'AI8 không đề xuất cho điểm cao')
        client = TestClient(app)  # No lifespan workers during isolated API tests.
        try:
            require(client.get('/api/user/cart').status_code == 401,
                    'API thiếu xác thực')
            client.cookies.clear()  # Independent bearer sessions for each role.
            response = client.post('/api/auth/login', json={
                'username':self.customer,'password':password})
            require(response.status_code == 200, 'Đăng nhập user thất bại')
            headers = {'Authorization':'Bearer '+response.json()['token']}
            require(client.get('/api/accounts/'+self.nicks['owned']+
                               '/credentials',headers=headers).status_code == 200,
                    'API RLS không trả credentials chủ đơn')
            require(client.get('/api/accounts/'+self.nicks['other']+
                               '/credentials',headers=headers).status_code == 403,
                    'API lộ credentials khách khác')
            require(client.post('/api/admin/run-etl',headers=headers).status_code == 403,
                    'User gọi được API admin')
            require(client.get('/api/user/profile/'+self.other_customer,
                               headers=headers).status_code == 403, 'API IDOR profile')
            root = client.get('/')
            require(root.status_code == 200 and
                    root.headers['content-type'].startswith('text/html') and
                    '<!doctype html>' in root.text.lower(), 'Sai MIME/HTML trang chủ')
            for page in ('/staff.html','/admin.html'):
                require(client.get(page, follow_redirects=False).status_code == 403,
                        'Role User đọc được trang nội bộ '+page)
            public = client.get('/api/accounts').json()
            require(all(n['mat_khau_game'] is None for n in public),
                    'API public lộ mật khẩu')
            client.cookies.clear()  # Independent bearer sessions for each role.
            response = client.post('/api/auth/login', json={
                'username':'a'+self.customer,'password':password})
            admin = {'Authorization':'Bearer '+response.json()['token']}
            require(client.delete('/api/admin/accounts/'+self.nicks['owned']+
                                  '/delete',headers=admin).status_code == 409,
                    'API DELETE không trả lỗi RESTRICT')
            require(client.get('/api/admin/ai7-diagnostics',headers=admin)
                    .status_code == 200, 'API AI7 lỗi')
            client.cookies.clear()  # Independent bearer sessions for each role.
            response = client.post('/api/auth/login', json={
                'username':'s'+self.customer,'password':password})
            require(response.status_code == 200, 'Đăng nhập Staff thất bại')
            staff = {'Authorization':'Bearer '+response.json()['token']}
            self.nicks['api_created'] = 'api'+self.customer[1:]
            nick = self.nicks['api_created']
            response = client.post('/api/accounts/create',headers=staff,json={
                'ma_nick':nick,'ma_game':self.game,'gia_ban':60000,
                'thong_tin_chi_tiet':{'ngay_nhap_kho':'2026-01-01'}})
            require(response.status_code == 200, 'API Staff INSERT lỗi')
            require(client.put('/api/accounts/'+nick+'/update',headers=staff,
                               json={'gia_ban':65000}).status_code == 200,
                    'API Staff UPDATE giá lỗi')
            require(client.put('/api/accounts/'+nick+'/update',headers=staff,
                               json={'mat_khau_game':'forbidden'})
                    .status_code == 403, 'Staff API sửa được pass')
            require(client.delete('/api/admin/accounts/'+nick+'/delete',
                                  headers=staff).status_code == 403,
                    'Staff API xóa được nick')
            with patch.object(ocr, 'extract_game_data',
                              return_value={'Rank':'API_OCR'}):
                response = client.post('/api/accounts/'+nick+'/ocr',
                                       headers=staff,
                                       json={'image_url':'https://example.com/x'})
                require(response.status_code == 200, 'API Staff OCR merge lỗi')
            staff_rows = client.get('/api/staff/transactions',headers=staff)
            require(staff_rows.status_code == 200 and all(
                set(item) == {'ma_giao_dich','ma_kh','so_tien','phuong_thuc',
                              'trang_thai','ngay_tao'}
                for item in staff_rows.json()), 'API Staff lộ dữ liệu nhạy cảm')
            event = 'http'+self.customer
            body = {'event_id':event,'amount':'10000',
                    'description':'NAP '+self.customer}
            require(client.post('/api/user/deposit/sepay',headers=headers,
                                json=body).status_code == 200,
                    'API SePay lỗi')
            replay = client.post('/api/user/deposit/sepay',headers=headers,json=body)
            require(replay.status_code == 200 and replay.json()['duplicate'],
                    'API SePay replay lỗi')
            require(client.post('/api/user/cart/add',headers=headers,
                                json={'ma_nick':nick}).status_code == 200,
                    'API thêm giỏ lỗi')
            require(client.post('/api/user/cart/checkout',headers=headers)
                    .status_code == 200, 'API checkout lỗi')
            require(client.get('/api/accounts/'+nick+'/credentials',
                               headers=headers).status_code == 200,
                    'API credentials sau checkout lỗi')
            transactions = client.get('/api/user/transactions/'+self.customer,
                                      headers=headers)
            require(transactions.status_code == 200 and
                    any(r['ma_gd'] == event for r in transactions.json()),
                    'API lịch sử ví thiếu giao dịch')
            require(client.get('/api/user/transaction-detail/'+event,
                               headers=headers).status_code == 200,
                    'API biên lai lỗi')
        finally:
            client.close()
        return 'API auth/RLS/IDOR/static/FK; ETL ví, OCR merge, sàn giá, AI6/7/8: đúng'

    def cleanup(self):
        if self.conn is None:
            return "Chưa tạo fixture"
        if self.conn.closed:
            self.conn = get_db_connection()
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("RESET ROLE")
            cur.execute(
                "DELETE FROM ai_analytics.log_ai_ocr WHERE ma_nick = ANY(%s)",
                (list(self.nicks.values()),),
            )
            cur.execute('DELETE FROM quan_ly_shop.app_principals '
                        'WHERE ma_kh=ANY(%s) OR username=ANY(%s)',
                        ([self.customer, self.other_customer],
                         ['a'+self.customer, 's'+self.customer]))
            cur.execute('DELETE FROM quan_ly_shop.don_hang_lich_su '
                        'WHERE ma_kh=ANY(%s)',
                        ([self.customer, self.other_customer],))
            cur.execute('DELETE FROM quan_ly_shop.lich_su_nap_tien '
                        'WHERE ma_kh=ANY(%s)',
                        ([self.customer, self.other_customer],))
            cur.execute('DELETE FROM quan_ly_shop.don_hang WHERE ma_kh=ANY(%s)',
                        ([self.customer, self.other_customer],))
            cur.execute("DELETE FROM quan_ly_shop.don_hang "
                        "WHERE ma_dh = ANY(%s)", (self.orders,))
            cur.execute("DELETE FROM quan_ly_shop.tai_khoan_game "
                        "WHERE ma_nick = ANY(%s)",
                        (list(self.nicks.values()),))
            cur.execute("DELETE FROM quan_ly_shop.khach_hang "
                        "WHERE ma_kh = ANY(%s)",
                        ([self.customer, self.other_customer],))
            cur.execute("DELETE FROM quan_ly_shop.nhan_vien WHERE ma_nv = %s",
                        (self.employee,))
            cur.execute("DELETE FROM quan_ly_shop.danh_muc_game "
                        "WHERE ma_game = %s", (self.game,))
            if self.role_created:
                cur.execute(sql.SQL("DROP ROLE {}").format(
                    sql.Identifier(self.customer)
                ))
        self.conn.commit()
        return "Đã xóa dữ liệu/role tạm, không thay đổi policy của ứng dụng"

    def summary(self):
        safe_print("\n" + "=" * 96)
        safe_print(f"{'Tên bài kiểm tra':<66} | Trạng thái | Thời gian")
        safe_print("-" * 96)
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            safe_print(f"{result.name:<66} | {status:^10} | "
                       f"{result.elapsed:>8.3f}s")
        business = [r for r in self.results if r.name[:1].isdigit()]
        passed = sum(r.passed for r in business)
        safe_print(f"\nNghiệp vụ: {passed}/{len(business)} PASS; "
                   f"{len(business) - passed} FAIL")
        return 0 if all(result.passed for result in self.results) else 1

    def run(self):
        safe_print("GARENASHOP_DB / AUTOMATED DEMO & TEST / PostgreSQL 16")
        safe_print("DB thử nghiệm: đã chạy models/01..04; .env: superuser.")
        safe_print("Tắt listener OCR bên ngoài trước khi chạy suite.")
        tests = [
            ('1 Regex SĐT / 23514', self.invalid_phone),
            ('2 Giá âm / 23514', self.negative_price),
            ('3 FK RESTRICT / 23503', self.restricted_delete),
            ('4 Staff RBAC / cột & CRUD', self.staff_rbac),
            ('5 RLS / ownership, masking, pool', self.row_security),
            ('6 AI3 khóa tranh chấp / RLS', self.fraud_lock),
            ('7 Partial Index / execution plan', self.partial_index),
            ('8 AI4 NL2SQL & GIN / JSONB', self.gin_and_chatbot),
            ('9 LISTEN/NOTIFY / real socket', self.notification),
            ('10 Wishlist & Cart / 15p, race, checkout', self.cart_business),
            ('11 Wallet / SePay, thẻ, ACID, Staff view', self.wallet_business),
            ('12 API/Auth & ETL/OCR/Pricing/AI regressions', self.api_regressions),
        ]
        ready = False
        interrupted = False
        try:
            ready = self.run_case(
                "Chuẩn bị môi trường & fixture", self.prepare
            )
            for name, function in tests:
                if ready:
                    self.run_case(name, function)
                else:
                    self.results.append(Result(
                        name, False, 0, "Không chạy được: chuẩn bị thất bại"
                    ))
                    safe_print(f"[FAIL] {name}: chuẩn bị thất bại")
        except KeyboardInterrupt:
            interrupted = True
            self.results.append(Result("Ngắt bởi người dùng", False, 0,
                                       "KeyboardInterrupt"))
        finally:
            if ready or self.role_created:
                self.run_case("Dọn dữ liệu & role tạm", self.cleanup)
            if self.conn is not None:
                self.conn.close()
        exit_code = self.summary()
        return 1 if interrupted else exit_code


if __name__ == "__main__":
    raise SystemExit(DemoSuite().run())
