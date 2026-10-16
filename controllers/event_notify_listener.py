"""Listen for committed nick insert notifications.

Run: python -m controllers.event_notify_listener
LISTEN/NOTIFY is transient: events sent while disconnected are not replayed.
"""

import json
import logging
import select

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config.database import get_db_connection
from controllers.ai1_vision_ocr import process_game_screenshot

LOGGER = logging.getLogger(__name__)


def handle_notification(payload: str, conn=None) -> None:
    """Validate a trigger payload and dispatch it to the existing OCR API."""
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Payload phải là JSON object")
    if data.get("event") != "NEW_NICK_INSERTED":
        LOGGER.debug("Bỏ qua sự kiện không hỗ trợ")
        return
    for key in ("ma_nick", "ma_game"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Payload thiếu {key}")
    game_title = data["ma_game"]
    if conn is not None:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT ten_game FROM quan_ly_shop.danh_muc_game "
                "WHERE ma_game = %s", (data["ma_game"],),
            )
            game = cursor.fetchone()
            if game:
                game_title = game[0]
    LOGGER.info(
        "Nick mới nhập kho: %s | game: %s (%s)",
        data["ma_nick"], game_title, data["ma_game"],
    )
    image_url = data.get("anh_url")
    if not isinstance(image_url, str) or not image_url.strip():
        LOGGER.warning("Nick %s chưa có ảnh; bỏ qua OCR", data["ma_nick"])
        return
    if image_url.startswith('/assets/products/'):
        # Generated thumbnails summarize existing metadata; OCR must use source
        # evidence instead of feeding the shop's own illustration back into it.
        LOGGER.info('Nick %s dùng thumbnail minh họa; OCR ảnh gốc bằng nút AI1', data['ma_nick'])
        return
    process_game_screenshot(data["ma_nick"], image_url, data["ma_game"])


def listen_for_new_nicks(stop_event=None) -> None:
    """Block until interrupted; an individual OCR failure keeps listening."""
    conn = None
    try:
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cursor:
            cursor.execute("LISTEN kenh_ai_garena;")
        LOGGER.info("Đang lắng nghe kenh_ai_garena")
        while stop_event is None or not stop_event.is_set():
            readable, _, _ = select.select([conn], [], [], 5)
            if not readable:
                continue
            conn.poll()
            pending = conn.notifies[:]
            conn.notifies.clear()
            for notify in pending:
                try:
                    handle_notification(notify.payload, conn)
                except Exception:
                    LOGGER.exception("Không xử lý được thông báo nick mới")
    except KeyboardInterrupt:
        LOGGER.info("Đã dừng listener")
    except Exception:
        LOGGER.exception("Listener mất kết nối hoặc không thể khởi động")
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    listen_for_new_nicks()
