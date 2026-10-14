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

    from config.db_connection import get_db_connection
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
            require(self.select_owned(cur) == [],
                    "Role nhóm không có đơn nhưng thấy nick đã bán")
            cur.execute("RESET ROLE")
            cur.execute(sql.SQL("SET LOCAL ROLE {}").format(
                sql.Identifier(self.customer)
            ))
            cur.execute("SELECT current_user")
            require(cur.fetchone()[0] == self.customer,
                    "current_user không khớp ma_kh")
            require(self.select_owned(cur) == [
                (self.nicks["owned"], "test_password_" + self.nicks["owned"])
            ], "RLS phải chỉ trả nick đã bán thuộc khách hiện tại")
            # Explicitly verify the existing policy's unsold branch too.
            cur.execute(
                "SELECT ma_nick FROM quan_ly_shop.tai_khoan_game "
                "WHERE ma_nick = %s", (self.nicks["match"],),
            )
            require(cur.fetchone() is not None,
                    "Nhánh Chua_ban không hoạt động")
        return "Nick đã bán: chỉ chủ đơn thấy; vẫn cho đọc nick Chua_ban"

    def fraud_lock(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE quan_ly_shop.tai_khoan_game "
                "SET trang_thai = 'Khoa_tranh_chap' WHERE ma_nick = %s",
                (self.nicks["owned"],),
            )
            require(cur.rowcount == 1, "Không cập nhật được nick fixture")
            cur.execute(sql.SQL("SET LOCAL ROLE {}").format(
                sql.Identifier(self.customer)
            ))
            require(self.select_owned(cur) == [],
                    "Nick tranh chấp vẫn hiện cho chủ đơn")
        return "Nick chủ đơn bị ẩn hoàn toàn sau khóa; rollback sau test"

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
        passed = sum(result.passed for result in self.results)
        safe_print(f"\nTổng: {passed}/{len(self.results)} PASS; "
                   f"{len(self.results) - passed} FAIL")
        return 0 if all(result.passed for result in self.results) else 1

    def run(self):
        safe_print("GARENASHOP_DB / AUTOMATED DEMO & TEST / PostgreSQL 16")
        safe_print("DB thử nghiệm: đã chạy models/01..04; .env: superuser.")
        safe_print("Tắt listener OCR bên ngoài trước khi chạy suite.")
        tests = [
            ("1.1 Regex SĐT / 23514", self.invalid_phone),
            ("1.2 Giá âm / 23514", self.negative_price),
            ("1.3 FK RESTRICT / 23503", self.restricted_delete),
            ("2.1a Sale bị cấm đọc luong / 42501",
             lambda: self.denied_column("nhan_vien", "luong")),
            ("2.1b Sale bị cấm đọc mat_khau_game / 42501",
             lambda: self.denied_column("tai_khoan_game", "mat_khau_game")),
            ("2.2 RLS / nick đã mua", self.row_security),
            ("2.3 Fraud Guard / ẩn nick tranh chấp", self.fraud_lock),
            ("3.1 Partial Index / execution plan", self.partial_index),
            ("3.2 AI4 NL2SQL & GIN / JSONB @>", self.gin_and_chatbot),
            ("4 LISTEN/NOTIFY / event và ma_nick", self.notification),
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
