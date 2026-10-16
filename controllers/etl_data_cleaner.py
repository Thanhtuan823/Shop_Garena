"""Clean customer CSV data and upsert it into PostgreSQL.

Run from the project root: python -m controllers.etl_data_cleaner
"""

import csv
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg2

from config.database import get_db_connection

LOGGER = logging.getLogger(__name__)
DEFAULT_CSV = (
    Path(__file__).resolve().parents[1] / "data_files/raw_khach_hang.csv"
)
REQUIRED_COLUMNS = {"ma_kh", "ho_ten", "so_dien_thoai", "so_du_vi"}
UPSERT_SQL = """
    INSERT INTO quan_ly_shop.khach_hang
        (ma_kh, ho_ten, so_dien_thoai, so_du_vi)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (ma_kh) DO UPDATE SET
        ho_ten = EXCLUDED.ho_ten,
        ngay_cap_nhat = CURRENT_TIMESTAMP
"""


def clean_customer(row: dict) -> tuple[str, str, str, Decimal]:
    """Validate one row; accept Vietnamese +84/84 phone prefixes."""
    ma_kh = (row.get("ma_kh") or "").strip()
    ho_ten = (row.get("ho_ten") or "").strip().upper()
    if not ma_kh or len(ma_kh) > 10:
        raise ValueError("ma_kh phải có từ 1 đến 10 ký tự")
    if not ho_ten or len(ho_ten) > 100:
        raise ValueError("ho_ten phải có từ 1 đến 100 ký tự")

    phone = re.sub(r"[^0-9]", "", row.get("so_dien_thoai") or "")
    if phone.startswith("84") and len(phone) == 11:
        phone = "0" + phone[2:]
    if not re.fullmatch(r"0[0-9]{9}", phone):
        raise ValueError("SĐT phải gồm 10 chữ số và bắt đầu bằng 0")

    try:
        balance = Decimal((row.get("so_du_vi") or "").strip())
    except InvalidOperation as exc:
        raise ValueError("Số dư ví không phải số hợp lệ") from exc
    if not balance.is_finite() or balance < 0:
        raise ValueError("Số dư ví phải hữu hạn và không âm")
    if balance > Decimal("9999999999999.99"):
        raise ValueError("Số dư ví vượt giới hạn NUMERIC(15, 2)")
    if balance != balance.quantize(Decimal("0.01")):
        raise ValueError("Số dư ví chỉ được có tối đa hai chữ số thập phân")
    return ma_kh, ho_ten, phone, balance


def etl_clean_customers(csv_path: str | Path = DEFAULT_CSV) -> dict[str, int]:
    """Return committed row counts; abort on connection failures."""
    stats = {"total": 0, "valid": 0, "loaded": 0, "rejected": 0}
    conn = None
    try:
        with Path(csv_path).open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
                raise ValueError("CSV thiếu các cột khách hàng bắt buộc")
            conn = get_db_connection()
            with conn.cursor() as cursor:
                for row in reader:
                    stats["total"] += 1
                    try:
                        if None in row:
                            raise ValueError("Dòng CSV có dư cột")
                        customer = clean_customer(row)
                    except ValueError as exc:
                        stats["rejected"] += 1
                        LOGGER.warning(
                            "Loại dòng %s: %s", reader.line_num, exc
                        )
                        continue
                    stats["valid"] += 1
                    cursor.execute("SAVEPOINT customer_row")
                    try:
                        cursor.execute(UPSERT_SQL, customer)
                    except (
                        psycopg2.IntegrityError, psycopg2.DataError
                    ) as exc:
                        cursor.execute("ROLLBACK TO SAVEPOINT customer_row")
                        stats["rejected"] += 1
                        LOGGER.warning(
                            "Loại dòng %s do ràng buộc DB (SQLSTATE %s)",
                            reader.line_num, exc.pgcode,
                        )
                    else:
                        stats["loaded"] += 1
                    finally:
                        cursor.execute("RELEASE SAVEPOINT customer_row")
            conn.commit()
        LOGGER.info(
            "ETL: tổng=%s, hợp lệ=%s, đã nạp=%s, bị loại=%s",
            stats["total"], stats["valid"], stats["loaded"], stats["rejected"],
        )
        return stats
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        LOGGER.exception(
            "ETL thất bại; giao dịch chưa commit đã được hoàn tác"
        )
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    etl_clean_customers()
