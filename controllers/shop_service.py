"""Atomic wallet/cart operations shared by API and integration tests."""
import hashlib
import re
import uuid
from decimal import Decimal

from psycopg2.extras import Json, RealDictCursor
from config.db_connection import transaction


class ShopError(ValueError):
    pass


def money(value):
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise ShopError('Số tiền không hợp lệ') from exc
    if (not amount.is_finite() or amount <= 0 or
            amount > Decimal('9999999999999.99') or
            amount != amount.quantize(Decimal('0.01'))):
        raise ShopError('Số tiền phải dương, tối đa 2 chữ số thập phân')
    return amount


def deposit(customer, amount, method, event_id, serial='', card='',
            description='', pending=False):
    amount = money(amount)
    if method not in {'THE_CAO', 'SEPAY_QR'}:
        raise ShopError('Phương thức không hợp lệ')
    if not event_id or len(event_id) > 40:
        raise ShopError('Mã giao dịch phải có 1–40 ký tự')
    detail = {'description': description, 'mock': True}
    if method == 'THE_CAO':
        if not re.fullmatch(r'#GARENA\*[0-9]{8}', serial):
            raise ShopError('Seri cần #GARENA* và đúng 8 chữ số')
        if not re.fullmatch(r'\$CARD&[0-9]{10}', card):
            raise ShopError('Mã thẻ cần $CARD& và đúng 10 chữ số')
        if amount not in {10000, 20000, 50000, 100000, 200000, 500000}:
            raise ShopError('Mệnh giá thẻ không hợp lệ')
        detail['card_fingerprint'] = hashlib.sha256(
            (serial + ':' + card).encode()).hexdigest()
    elif description.strip().upper() != ('NAP ' + customer).upper():
        pending = True
    status = 'Cho_duyet' if pending else 'Thanh_cong'
    with transaction() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT ma_kh FROM quan_ly_shop.khach_hang '
                    'WHERE ma_kh=%s FOR UPDATE', (customer,))
        if not cur.fetchone():
            raise ShopError('Khách hàng không tồn tại')
        cur.execute("""INSERT INTO quan_ly_shop.lich_su_nap_tien
            (ma_giao_dich, ma_kh, so_tien, phuong_thuc,
             thong_tin_giao_dich, trang_thai) VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING RETURNING ma_giao_dich""",
                    (event_id, customer, amount, method, Json(detail), status))
        inserted = cur.fetchone()
        if not inserted:
            cur.execute('SELECT * FROM quan_ly_shop.lich_su_nap_tien '
                        'WHERE ma_giao_dich=%s', (event_id,))
            previous = cur.fetchone()
            if (not previous or previous['ma_kh'] != customer or
                    previous['so_tien'] != amount or
                    previous['phuong_thuc'] != method or
                    previous['thong_tin_giao_dich'] != detail):
                raise ShopError('Mã giao dịch/thẻ đã được dùng cho yêu cầu khác')
            return {'ma_giao_dich': event_id, 'duplicate': True,
                    'trang_thai': previous['trang_thai']}
        if status == 'Thanh_cong':
            cur.execute('UPDATE quan_ly_shop.khach_hang '
                        'SET so_du_vi=so_du_vi+%s WHERE ma_kh=%s',
                        (amount, customer))
    return {'ma_giao_dich': event_id, 'duplicate': False, 'trang_thai': status}


def recheck_sepay(event_id, customer):
    with transaction() as conn, conn.cursor() as cur:
        # Same customer -> transaction lock order as deposit.
        cur.execute('SELECT ma_kh FROM quan_ly_shop.khach_hang '
                    'WHERE ma_kh=%s FOR UPDATE', (customer,))
        if cur.fetchone() is None:
            raise ShopError('Khách không tồn tại')
        cur.execute('SELECT ma_kh, so_tien, trang_thai, phuong_thuc '
                    'FROM quan_ly_shop.lich_su_nap_tien '
                    'WHERE ma_giao_dich=%s FOR UPDATE', (event_id,))
        row = cur.fetchone()
        if not row or row[0] != customer or row[3] != 'SEPAY_QR':
            raise ShopError('Sai giao dịch hoặc sai khách hàng; cần đối chiếu lại')
        if row[2] == 'Thanh_cong':
            return {'duplicate': True}
        if row[2] != 'Cho_duyet':
            raise ShopError('Giao dịch không chờ duyệt')
        cur.execute('UPDATE quan_ly_shop.lich_su_nap_tien '
                    "SET trang_thai='Thanh_cong' WHERE ma_giao_dich=%s",
                    (event_id,))
        cur.execute('UPDATE quan_ly_shop.khach_hang '
                    'SET so_du_vi=so_du_vi+%s WHERE ma_kh=%s', (row[1], customer))
    return {'duplicate': False, 'message': 'Đã đối soát và cộng tiền đúng một lần'}


def expire_cart():
    # Lock nick first in every cart operation; SKIP LOCKED avoids blocking buyers.
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""SELECT n.ma_nick FROM quan_ly_shop.tai_khoan_game n
            JOIN quan_ly_shop.gio_hang g USING(ma_nick)
            WHERE g.han_giu_cho <= CURRENT_TIMESTAMP ORDER BY n.ma_nick
            FOR UPDATE OF n SKIP LOCKED""")
        ids = [row[0] for row in cur.fetchall()]
        for nick in ids:
            cur.execute('DELETE FROM quan_ly_shop.gio_hang WHERE ma_nick=%s '
                        'AND han_giu_cho<=CURRENT_TIMESTAMP RETURNING ma_nick',
                        (nick,))
            if cur.fetchone():
                cur.execute('UPDATE quan_ly_shop.tai_khoan_game '
                            "SET trang_thai='Chua_ban' WHERE ma_nick=%s "
                            "AND trang_thai='Dang_giu_cho'", (nick,))
    return len(ids)


def add_cart(customer, nick):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('SELECT trang_thai FROM quan_ly_shop.tai_khoan_game '
                    'WHERE ma_nick=%s FOR UPDATE', (nick,))
        row = cur.fetchone()
        if not row:
            raise ShopError('Không tìm thấy nick')
        cur.execute('SELECT ma_kh, han_giu_cho, han_giu_cho>CURRENT_TIMESTAMP '
                    'FROM quan_ly_shop.gio_hang WHERE ma_nick=%s FOR UPDATE',
                    (nick,))
        existing = cur.fetchone()
        if existing and existing[2]:
            if existing[0] != customer:
                raise ShopError('Nick đang được khách khác giữ chỗ')
            return {'ma_nick': nick, 'han_giu_cho': existing[1]}
        if row[0] not in ('Chua_ban', 'Dang_giu_cho'):
            raise ShopError('Nick không thể mở bán/giữ chỗ')
        if row[0] == 'Dang_giu_cho' and not existing:
            raise ShopError('Trạng thái giữ chỗ không hợp lệ')
        cur.execute('DELETE FROM quan_ly_shop.gio_hang WHERE ma_nick=%s', (nick,))
        cur.execute('INSERT INTO quan_ly_shop.gio_hang (ma_kh,ma_nick) '
                    'VALUES (%s,%s) RETURNING han_giu_cho', (customer, nick))
        deadline = cur.fetchone()[0]
        cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET trang_thai="
                    "'Dang_giu_cho' WHERE ma_nick=%s", (nick,))
    return {'ma_nick': nick, 'han_giu_cho': deadline}


def remove_cart(customer, nick):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('SELECT ma_nick FROM quan_ly_shop.tai_khoan_game '
                    'WHERE ma_nick=%s FOR UPDATE', (nick,))
        cur.execute('DELETE FROM quan_ly_shop.gio_hang '
                    'WHERE ma_kh=%s AND ma_nick=%s RETURNING ma_nick',
                    (customer, nick))
        if cur.fetchone():
            cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET trang_thai="
                        "'Chua_ban' WHERE ma_nick=%s AND trang_thai='Dang_giu_cho'",
                        (nick,))
    return {'message': 'Đã bỏ giữ chỗ'}


def checkout(customer):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('SELECT so_du_vi FROM quan_ly_shop.khach_hang '
                    'WHERE ma_kh=%s FOR UPDATE', (customer,))
        wallet = cur.fetchone()
        if not wallet:
            raise ShopError('Khách không tồn tại')
        cur.execute('SELECT ma_nick FROM quan_ly_shop.gio_hang '
                    'WHERE ma_kh=%s ORDER BY ma_nick', (customer,))
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            raise ShopError('Giỏ hàng trống')
        total = Decimal(0)
        purchases = []
        for nick in ids:
            cur.execute('SELECT gia_ban, trang_thai FROM '
                        'quan_ly_shop.tai_khoan_game WHERE ma_nick=%s FOR UPDATE',
                        (nick,))
            price, status = cur.fetchone()
            cur.execute('SELECT han_giu_cho>CURRENT_TIMESTAMP FROM '
                        'quan_ly_shop.gio_hang WHERE ma_kh=%s AND ma_nick=%s '
                        'FOR UPDATE', (customer, nick))
            hold = cur.fetchone()
            if not hold or not hold[0] or status != 'Dang_giu_cho':
                raise ShopError('Giữ chỗ hết hạn hoặc nick bị khóa')
            total += price
            purchases.append((nick, price))
        if wallet[0] < total:
            raise ShopError('Số dư không đủ; giao dịch đã hoàn tác')
        orders = []
        for nick, price in purchases:
            order = 'D' + uuid.uuid4().hex[:14]
            cur.execute('INSERT INTO quan_ly_shop.don_hang '
                        '(ma_dh,ma_kh,ma_nick,tong_tien) VALUES (%s,%s,%s,%s) '
                        'RETURNING ngay_tao', (order, customer, nick, price))
            created = cur.fetchone()[0]
            # Explicit archival write in the same transaction, no lost history.
            cur.execute('INSERT INTO quan_ly_shop.don_hang_lich_su '
                        '(ma_dh,ma_kh,ma_nick,ngay_tao,tong_tien) '
                        'VALUES (%s,%s,%s,%s,%s)',
                        (order, customer, nick, created, price))
            cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET trang_thai="
                        "'Da_ban' WHERE ma_nick=%s", (nick,))
            cur.execute('DELETE FROM quan_ly_shop.gio_hang '
                        'WHERE ma_kh=%s AND ma_nick=%s', (customer, nick))
            orders.append(order)
        cur.execute('UPDATE quan_ly_shop.khach_hang SET so_du_vi=so_du_vi-%s '
                    'WHERE ma_kh=%s', (total, customer))
    return {'orders': orders, 'total': total, 'balance': wallet[0] - total}
