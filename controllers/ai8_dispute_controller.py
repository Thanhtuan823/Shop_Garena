"""AI8: explainable dispute triage; recommendations require human review."""
from config.db_connection import transaction


def evaluate_dispute(ma_nick, evidence_count=0, seller_unresponsive=False,
                     recovery_changed=False):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT n.trang_thai, d.ma_dh, d.tong_tien "
                    "FROM quan_ly_shop.tai_khoan_game n LEFT JOIN "
                    "quan_ly_shop.don_hang d USING(ma_nick) WHERE ma_nick=%s",
                    (ma_nick,))
        row = cur.fetchone()
    if row is None:
        raise ValueError('Không tìm thấy nick')
    status, order, amount = row
    score = min(100, min(max(evidence_count, 0), 5) * 10
                + (25 if seller_unresponsive else 0)
                + (35 if recovery_changed else 0)
                + (10 if status == 'Khoa_tranh_chap' else 0))
    return {'ma_nick': ma_nick, 'risk_score': score,
            'recommend_refund': score > 80 and order is not None,
            'proposed_refund': amount if score > 80 and order else 0,
            'executed': False, 'requires_human_review': True,
            'reason': 'Điểm quy tắc: bằng chứng 0–50, mất liên lạc 25, '
                      'đổi khôi phục 35, đang tranh chấp 10; không phải xác suất ML.'}
