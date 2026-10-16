"""AI3: explicit fraud escalation; does not invent a model verdict."""
import logging
from config.database import transaction


def check_and_lock_fraud(ma_nick):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("UPDATE quan_ly_shop.tai_khoan_game "
                    "SET trang_thai='Khoa_tranh_chap' WHERE ma_nick=%s "
                    "RETURNING ma_nick", (ma_nick,))
        if cur.fetchone() is None:
            raise ValueError("Không tìm thấy nick")
    logging.info("[AI3] Locked disputed nick %s", ma_nick)
    return {"ma_nick": ma_nick, "trang_thai": "Khoa_tranh_chap"}
