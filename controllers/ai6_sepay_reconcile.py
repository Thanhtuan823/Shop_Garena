"""AI6: fuzzy suggestions only; staff must confirm before money is credited."""
from difflib import SequenceMatcher
import re
from config.database import transaction


def reconcile_assistant(description):
    normalized = re.sub(r'[^A-Z0-9]', '', description.upper())
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT ma_kh, ho_ten FROM quan_ly_shop.khach_hang")
        customers = cur.fetchall()
    matches = []
    for customer, name in customers:
        target = re.sub(r'[^A-Z0-9]', '', 'NAP' + customer.upper())
        score = SequenceMatcher(None, normalized, target).ratio()
        matches.append({'ma_kh': customer, 'ho_ten': name,
                        'confidence': round(score * 100, 1)})
    matches.sort(key=lambda item: item['confidence'], reverse=True)
    return {'candidates': matches[:3], 'automatic_credit': False,
            'reply': 'Vui lòng gửi mã giao dịch và xác nhận mã khách hàng. '
                     'Nhân viên sẽ đối soát trước khi cộng tiền.'}
