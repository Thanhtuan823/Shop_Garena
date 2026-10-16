"""AI5: transparent inactivity heuristic and idempotent voucher upsert."""
from config.database import transaction


def run_marketing():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ai_analytics.khach_hang_marketing
                (ma_kh, churn_risk_score, ma_voucher_tang, ngay_tao)
            SELECT ma_kh, LEAST(100, 100.0 *
                   EXTRACT(DAY FROM CURRENT_TIMESTAMP - MAX(ngay_tao))/120),
                   'TRIAN20PCT', CURRENT_DATE
            FROM quan_ly_shop.don_hang_lich_su
            GROUP BY ma_kh HAVING MAX(ngay_tao) < CURRENT_TIMESTAMP - INTERVAL '60 days'
            ON CONFLICT (ma_kh) DO UPDATE SET
                churn_risk_score=EXCLUDED.churn_risk_score,
                ma_voucher_tang=EXCLUDED.ma_voucher_tang, ngay_tao=CURRENT_DATE
            RETURNING ma_kh, churn_risk_score, ma_voucher_tang
        """)
        result = [dict(zip(('ma_kh', 'churn_risk_score', 'voucher'), row))
                  for row in cur.fetchall()]
    return result
