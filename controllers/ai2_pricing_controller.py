"""AI2: execute inventory pricing rules with a 50,000 VND floor."""
import logging
from config.db_connection import transaction


def run_pricing():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT quan_ly_shop.fn_giam_gia_nick_ton_kho()")
    logging.info("[AI2] Applied 5% inventory discount; minimum 50,000 VND")
    return {"message": "Đã giảm 5% nick tồn >30 ngày, sàn 50.000đ"}
