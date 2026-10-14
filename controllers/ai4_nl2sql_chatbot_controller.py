"""Deterministic Vietnamese catalog search using parameterized JSONB SQL.

JSON convention: SkinHiem and VuKhi are arrays of canonical item names.
Examples: "Tìm nick Liên Quân dưới 400k có skin Raz Muay Thai",
          "Lọc nick Free Fire có AK Rồng Xanh".
Unknown games/items are rejected rather than silently dropping a filter.
"""

import logging
import re
import unicodedata
from decimal import Decimal

from psycopg2.extras import Json, RealDictCursor

from config.db_connection import get_db_connection

LOGGER = logging.getLogger(__name__)
ITEMS = {
    "raz muay thai": ("SkinHiem", "Raz Muay Thai"),
    "ngo khong evo lvl 5": ("SkinHiem", "Ngộ Không EVO Lvl 5"),
    "ak rong xanh": ("VuKhi", "AK Rồng Xanh"),
}
PRICE_PATTERN = re.compile(
    r"\b(duoi|khong qua|toi da)\s*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(k|nghin|ngan|trieu|tr|vnd|dong)?\b"
)


def normalize_text(value: str) -> str:
    """Normalize Vietnamese accents for keyword matching only."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_accents = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.replace("đ", "d").split())


def build_catalog_query(user_prompt: str) -> tuple[str, list]:
    """Build fixed SQL fragments; all user-derived values remain parameters."""
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("Câu hỏi không được để trống")
    prompt = normalize_text(user_prompt)
    games = [name for keyword, name in (
        ("lien quan", "Liên Quân"), ("free fire", "Free Fire")
    ) if keyword in prompt]
    if len(games) != 1:
        raise ValueError("Hãy chỉ định một game: Liên Quân hoặc Free Fire")

    conditions = ["nick.trang_thai = 'Chua_ban'", "game.ten_game ILIKE %s"]
    parameters = [f"%{games[0]}%"]
    prices = list(PRICE_PATTERN.finditer(prompt))
    if len(prices) > 1:
        raise ValueError("Chỉ hỗ trợ một điều kiện giá tối đa")
    if prices:
        price = prices[0]
        amount = Decimal(price.group(2).replace(",", "."))
        unit = price.group(3)
        if unit in {"k", "nghin", "ngan"}:
            amount *= 1000
        elif unit in {"trieu", "tr"}:
            amount *= 1000000
        if amount <= 0:
            raise ValueError("Giá tối đa phải lớn hơn 0")
        operator = "<" if price.group(1) == "duoi" else "<="
        conditions.append(f"nick.gia_ban {operator} %s")
        parameters.append(amount)
    elif re.search(r"\b(duoi|gia|khong qua|toi da|tren)\b", prompt):
        raise ValueError(
            "Giá chưa hỗ trợ; dùng 'dưới 400k' hoặc 'tối đa 1 triệu'"
        )

    attributes = {}
    remaining = prompt
    for keyword, (key, canonical_name) in ITEMS.items():
        if keyword in prompt:
            attributes.setdefault(key, []).append(canonical_name)
            remaining = remaining.replace(keyword, "")
    # Reject residual requests, including unknown items alongside known items.
    residual = re.sub(r"\b(skin|vu khi|sung)\b", "", remaining)
    residual = re.sub(r"\b(lien quan|free fire)\b", "", residual)
    residual = PRICE_PATTERN.sub("", residual)
    residual = re.sub(r"\b(tim|loc|nick|tai khoan|game|co|va|cho|toi|cac)\b",
                      "", residual)
    if residual.strip(" .,!?;:"):
        raise ValueError("Từ khóa chưa hỗ trợ; bổ sung tên vật phẩm vào ITEMS")
    if re.search(r"\b(skin|vu khi|sung|co)\b", prompt) and not attributes:
        raise ValueError("Chưa nhận diện được tên skin hoặc vũ khí")
    if attributes:
        conditions.append("nick.thong_tin_chi_tiet @> %s::jsonb")
        parameters.append(Json(attributes))

    sql = """
        SELECT nick.ma_nick, nick.ma_game, game.ten_game,
               nick.gia_ban, nick.trang_thai,
               nick.thong_tin_chi_tiet, nick.anh_dinh_kem_url
        FROM quan_ly_shop.tai_khoan_game AS nick
        JOIN quan_ly_shop.danh_muc_game AS game
          ON game.ma_game = nick.ma_game
        WHERE {conditions}
        ORDER BY nick.gia_ban, nick.ma_nick
    """.format(conditions=" AND ".join(conditions))
    return sql, parameters


def nl2sql_translate_and_execute(user_prompt: str) -> list[dict]:
    """Return catalog dictionaries; gia_ban retains its exact Decimal value."""
    conn = None
    try:
        sql, parameters = build_catalog_query(user_prompt)
        conn = get_db_connection()
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, parameters)
            results = [dict(row) for row in cursor.fetchall()]
        conn.commit()
        return results
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        LOGGER.exception("Không thể thực hiện truy vấn chatbot")
        raise
    finally:
        if conn is not None:
            conn.close()
if __name__ == '__main__':
    test_prompt = "Tìm nick Liên Quân dưới 400k có skin Raz Muay Thai"
    print("\n" + "=" * 50)
    print(f"[TEST AI 4] Cau hoi kiem thu: '{test_prompt}'")
    print("=" * 50)

    try:
        if 'nl2sql_translate_and_execute' in globals():
            results = nl2sql_translate_and_execute(test_prompt)
        elif 'ask_chatbot' in globals():
            results = ask_chatbot(test_prompt)
        else:
            print("Khong tim thay ham chatbot phu hop trong file.")
            results = []

        print(f"\n[Ket qua CSDL]: Tim thay {len(results)} nick phu hop:")
        for item in results:
            print(f"- {item}")
    except Exception as e:
        print(f"Loi thuc thi: {e}")