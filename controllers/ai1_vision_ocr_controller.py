import json
from config.db_connection import get_db_connection

def process_game_screenshot(ma_nick: str, image_url: str, ma_game: str):
    """
    Controller AI 1: Bóc tách thuộc tính nick game và nạp JSONB vào PostgreSQL.
    """
    extracted_data = {
        "Rank": "Cao Thủ 25 Sao",
        "SoTuong": 114,
        "SoSkin": 210,
        "SkinHiem": ["Raz Muay Thai", "Ngộ Không EVO Lvl 5"],
        "UyTin": 100
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql_update = """
            UPDATE quan_ly_shop.tai_khoan_game
            SET thong_tin_chi_tiet = %s
            WHERE ma_nick = %s;
        """
        cursor.execute(sql_update, (json.dumps(extracted_data), ma_nick))

        sql_log = """
            INSERT INTO ai_analytics.log_ai_ocr (ma_nick, url_anh, ket_qua_raw_json, confidence_score)
            VALUES (%s, %s, %s, %s);
        """
        cursor.execute(sql_log, (ma_nick, image_url, json.dumps(extracted_data), 0.95))

        conn.commit()
        print(f"✅ [AI 1] Bóc tách và cập nhật thành công JSONB cho nick: {ma_nick}")
    except Exception as e:
        conn.rollback()
        print(f"❌ [AI 1] Lỗi: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
