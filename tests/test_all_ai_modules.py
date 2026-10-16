"""Eight independent AI integration checks in a disposable PostgreSQL database.

Run: python tests/test_all_ai_modules.py
AI1 performs actual CPU EasyOCR. No paid APIs or external image downloads.
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config.database import get_db_connection, transaction
from psycopg2 import sql


@unittest.skipUnless(os.environ.get('GARENA_AI_TEST_WORKER') == '1',
                     'Run this script directly to create an isolated test database')
class AllAiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO quan_ly_shop.khach_hang(ma_kh,ho_ten) "
                        "VALUES('AI_KH','AI TEST')")
            cur.execute("INSERT INTO quan_ly_shop.danh_muc_game VALUES('G_LQ','Liên Quân Mobile')")
            for nick in ['AI_OCR', 'AI_PRICE', 'AI_FLOOR', 'AI_FRAUD', 'AI_SEARCH', 'AI_DISPUTE']:
                cur.execute("INSERT INTO quan_ly_shop.tai_khoan_game "
                            "(ma_nick,ma_game,gia_ban,mat_khau_game,thong_tin_chi_tiet) "
                            "VALUES(%s,'G_LQ',%s,'INTEGRATION_ONLY', "
                            "jsonb_build_object('ngay_nhap_kho',(CURRENT_DATE-40)::text, "
                            "'SkinHiem',jsonb_build_array('Raz Muay Thai')))",
                            (nick, 51000 if nick == 'AI_FLOOR' else 100000))

    def test_01_vision_ocr_actual_and_merge(self):
        from PIL import Image, ImageDraw
        from scripts.generate_product_images import font
        from controllers.ai1_vision_ocr import process_game_screenshot
        image = Image.new('RGB', (1000, 220), 'white')
        ImageDraw.Draw(image).text((40, 60), 'Raz Muay Thai', fill='black', font=font(70, True))
        data = io.BytesIO()
        image.save(data, 'PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode()
        result = process_game_screenshot('AI_OCR', uri, 'G_LQ')
        self.assertIn('Raz Muay Thai', result['SkinHiem'])
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT thong_tin_chi_tiet->>'ngay_nhap_kho'="
                        "(CURRENT_DATE-40)::text FROM quan_ly_shop.tai_khoan_game "
                        "WHERE ma_nick='AI_OCR'")
            self.assertTrue(cur.fetchone()[0])

    def test_02_pricing_and_floor(self):
        from controllers.ai2_dynamic_pricing import run_pricing
        run_pricing()
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT ma_nick,gia_ban FROM quan_ly_shop.tai_khoan_game "
                        "WHERE ma_nick IN ('AI_PRICE','AI_FLOOR')")
            self.assertEqual(dict(cur.fetchall()), {'AI_PRICE': 95000, 'AI_FLOOR': 50000})

    def test_03_fraud_lock(self):
        from controllers.ai3_fraud_guard import check_and_lock_fraud
        check_and_lock_fraud('AI_FRAUD')
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT trang_thai FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='AI_FRAUD'")
            self.assertEqual(cur.fetchone()[0], 'Khoa_tranh_chap')

    def test_04_nl2sql_containment(self):
        from controllers.ai4_nl2sql_chatbot import build_catalog_query, nl2sql_translate_and_execute
        prompt = 'Tìm nick Liên Quân dưới 400k có skin Raz Muay Thai'
        query, params = build_catalog_query(prompt)
        self.assertIn('@>', query)
        result = nl2sql_translate_and_execute(prompt)
        self.assertIn('AI_SEARCH', {row['ma_nick'] for row in result})
        self.assertTrue(all(float(row['gia_ban']) < 400000 for row in result))

    def test_05_churn_voucher_idempotency(self):
        from controllers.ai5_smart_marketing import run_marketing
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO quan_ly_shop.don_hang_lich_su "
                        "VALUES('AI_OLD','AI_KH','AI_OLD_NICK',CURRENT_TIMESTAMP-INTERVAL '70 days',100000)")
        for _ in range(2):
            self.assertTrue(any(row['ma_kh'] == 'AI_KH' and row['voucher'] == 'TRIAN20PCT'
                                for row in run_marketing()))
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ai_analytics.khach_hang_marketing WHERE ma_kh='AI_KH'")
            self.assertEqual(cur.fetchone()[0], 1)

    def test_06_fuzzy_reconcile_no_credit(self):
        from controllers.ai6_sepay_reconcile import reconcile_assistant
        result = reconcile_assistant('NPA AI_KH')
        self.assertEqual(result['candidates'][0]['ma_kh'], 'AI_KH')
        self.assertFalse(result['automatic_credit'])

    def test_07_diagnostics_and_vacuum(self):
        from controllers.ai7_auto_dba import diagnostics, run_vacuum
        self.assertTrue(any(row['table'] == 'tai_khoan_game' for row in diagnostics()))
        self.assertIn('hoàn tất', run_vacuum()['message'])
        with self.assertRaises(ValueError):
            run_vacuum('tai_khoan_game; DROP SCHEMA quan_ly_shop CASCADE')

    def test_08_dispute_recommendation_not_payment(self):
        from controllers.ai8_dispute_arbiter import evaluate_dispute
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO quan_ly_shop.don_hang(ma_dh,ma_kh,ma_nick,tong_tien) "
                        "VALUES('AI_ORDER','AI_KH','AI_DISPUTE',100000)")
        result = evaluate_dispute('AI_DISPUTE', 5, True, True)
        self.assertGreater(result['risk_score'], 80)
        self.assertTrue(result['recommend_refund'])
        self.assertEqual(result['proposed_refund'], 100000)
        self.assertFalse(result['executed'])
        with transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh='AI_KH'")
            self.assertEqual(cur.fetchone()[0], 0)


def main():
    conn = get_db_connection()
    conn.autocommit = True
    database = 'garena_ai_test_' + uuid.uuid4().hex[:8]
    created = False
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(database)))
        created = True
        env = dict(os.environ, DB_NAME=database, GARENA_AI_TEST_WORKER='1',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        init = subprocess.run([sys.executable, 'scripts/init_database.py'], cwd=ROOT,
                              env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        if init.returncode:
            print(init.stderr)
            return 1
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
                              cwd=ROOT, env=env, timeout=240).returncode
    finally:
        if created:
            with conn.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        conn.close()


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    if '--worker' in sys.argv:
        if not os.environ.get('DB_NAME', '').startswith('garena_ai_test_'):
            raise SystemExit('Worker requires a disposable garena_ai_test_ database')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AllAiTests)
        names = [test.id() for test in suite]
        started = time.perf_counter()
        outcome = unittest.TextTestRunner(verbosity=2).run(suite)
        failed = {test.id() for test, detail in outcome.failures + outcome.errors}
        output = ROOT / 'docs/test_results/ai_modules.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'passed': outcome.testsRun - len(failed),
                                     'total': outcome.testsRun,
                                     'elapsed_seconds': round(time.perf_counter() - started, 3),
                                     'cases': [{'name': name, 'passed': name not in failed}
                                               for name in names]},
                                    ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit(0 if outcome.wasSuccessful() else 1)
    raise SystemExit(main())
