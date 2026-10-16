"""Apply models 01..04; optional seed data for the local acceptance demo."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.auth import hash_password
from config.db_connection import get_db_connection, transaction


def migrate():
    conn = get_db_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_lock(708321)')
            try:
                for path in sorted((ROOT / 'models').glob('0[1-4]_*.sql')):
                    cur.execute(path.read_text(encoding='utf-8'))
                    print('APPLIED', path.name)
            finally:
                conn.rollback()
                cur.execute('SELECT pg_advisory_unlock(708321)')
    finally:
        conn.close()


def seed():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO quan_ly_shop.khach_hang (ma_kh,ho_ten) "
                    "VALUES ('KH_DEMO','KHÁCH DEMO') ON CONFLICT DO NOTHING")
        for role, customer in [('admin', None), ('staff', None), ('user', 'KH_DEMO')]:
            password = os.getenv('DEMO_' + role.upper() + '_PASSWORD') or secrets.token_urlsafe(12)
            cur.execute('INSERT INTO quan_ly_shop.app_principals '
                        '(username,password_hash,app_role,ma_kh) VALUES (%s,%s,%s,%s) '
                        'ON CONFLICT DO NOTHING RETURNING username',
                        (role, hash_password(password), role, customer))
            if cur.fetchone():
                print('DEMO LOGIN:', role, '| password:', password)
            else:
                print('DEMO LOGIN:', role, '| existing password unchanged')
        data = json.loads((ROOT / 'data_files/raw_tai_khoan_game.json').read_text(encoding='utf-8'))
        for item in data:
            cur.execute('INSERT INTO quan_ly_shop.danh_muc_game (ma_game,ten_game) '
                        'VALUES (%s,%s) ON CONFLICT (ten_game) DO NOTHING',
                        (item['ma_game'], item['ten_game']))
            cur.execute('SELECT ma_game FROM quan_ly_shop.danh_muc_game WHERE ten_game=%s',
                        (item['ten_game'],))
            game = cur.fetchone()[0]
            cur.execute("""INSERT INTO quan_ly_shop.tai_khoan_game
                (ma_nick,ma_game,gia_ban,thong_tin_chi_tiet,mat_khau_game)
                VALUES (%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING""",
                        (item['ma_nick'], game, item['gia_ban'],
                         json.dumps(item['thong_tin_chi_tiet']), secrets.token_urlsafe(12)))
        cur.execute('REFRESH MATERIALIZED VIEW quan_ly_shop.mv_nick_hot_trang_chu')
    print('Seed complete; no existing wallet balances were overwritten.')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed-demo', action='store_true')
    args = parser.parse_args()
    migrate()
    if args.seed_demo:
        seed()
