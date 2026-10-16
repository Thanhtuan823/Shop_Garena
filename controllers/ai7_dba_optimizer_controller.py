"""AI7: dead-tuple estimate, not a physical bloat measurement."""
from psycopg2 import sql
from config.db_connection import get_db_connection, transaction

ALLOWED_TABLES = {'tai_khoan_game', 'don_hang', 'gio_hang', 'lich_su_nap_tien'}


def diagnostics():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""SELECT relname, n_live_tup, n_dead_tup,
            last_autovacuum, last_autoanalyze FROM pg_stat_user_tables
            WHERE schemaname='quan_ly_shop' ORDER BY n_dead_tup DESC""")
        rows = cur.fetchall()
    result = []
    for name, live, dead, vacuum, analyze in rows:
        ratio = 100 * dead / max(live + dead, 1)
        result.append({'table': name, 'live': live, 'dead': dead,
                       'dead_ratio_pct': round(ratio, 2),
                       'recommendation': 'VACUUM ANALYZE' if ratio > 10 else 'OK',
                       'last_autovacuum': vacuum, 'last_autoanalyze': analyze})
    return result


def run_vacuum(table='tai_khoan_game'):
    if table not in ALLOWED_TABLES:
        raise ValueError('Bảng không nằm trong danh sách bảo trì')
    conn = get_db_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql.SQL('VACUUM ANALYZE quan_ly_shop.{}').format(
                sql.Identifier(table)))
        return {'table': table, 'message': 'VACUUM ANALYZE hoàn tất'}
    finally:
        conn.close()
