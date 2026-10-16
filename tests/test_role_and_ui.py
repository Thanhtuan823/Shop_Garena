"""Read-only application audit via disposable DB, real HTTP and Chrome.

Creates only audit artifacts and test fixtures, never patches application code.
Install QA dependency: python -m pip install --target .venv/qa playwright
Run: python tests/test_role_and_ui.py
"""
import base64
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.venv/qa'))
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
import httpx
import psycopg2
from psycopg2 import sql
from playwright.sync_api import sync_playwright, expect
from PIL import Image, ImageDraw, ImageFont
from config.database import get_db_connection

ARTIFACTS = ROOT / 'tests/artifacts/role_ui'
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RESULTS = []
BASE = 'http://127.0.0.1:8137'


def record(role, test, passed, detail=''):
    RESULTS.append(dict(role=role, test=test, passed=bool(passed), detail=detail))
    print(('PASS' if passed else 'FAIL') + ' | ' + role + ' | ' + test + ' | ' + detail,
          flush=True)


def screenshot(page, name):
    page.screenshot(path=str(ARTIFACTS / (name+'.png')), full_page=True)


def main():
    admin_conn = get_db_connection()
    admin_conn.autocommit = True
    database = 'garena_role_audit_' + uuid.uuid4().hex[:8]
    assert database.startswith('garena_role_audit_') and len(database) == 26
    created = False
    server = None
    db = None
    browser = None
    client = None
    log_file = None
    try:
        with admin_conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(
                sql.Identifier(database)))
            created = True
        passwords = {role: secrets.token_urlsafe(16) for role in ('admin','staff','user')}
        env = dict(os.environ, DB_NAME=database, PORT='8137',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8',
                   OCR_ALLOWED_HOSTS='raw.githubusercontent.com',
                   **{'DEMO_'+role.upper()+'_PASSWORD': value
                      for role,value in passwords.items()})
        init = subprocess.run([sys.executable,'scripts/init_database.py','--seed-demo'],
                              cwd=ROOT, env=env, capture_output=True,
                              encoding='utf-8', errors='backslashreplace', timeout=60)
        if init.returncode:
            raise RuntimeError('Schema/seed failed: '+init.stderr)
        baseline = subprocess.run([sys.executable,'tests/test_database_business.py'],
                                  cwd=ROOT, env=env, capture_output=True,
                                  encoding='utf-8', errors='backslashreplace', timeout=90)
        (ARTIFACTS/'baseline.log').write_text(baseline.stdout+baseline.stderr,encoding='utf-8')
        record('BASELINE','Existing business suite',baseline.returncode==0,
               '12/12 business groups' if baseline.returncode==0 else 'See baseline.log')
        db = psycopg2.connect(host=os.getenv('DB_HOST','localhost'),
                              port=os.getenv('DB_PORT','5432'), dbname=database,
                              user=os.getenv('DB_USER','postgres'),
                              password=os.getenv('DB_PASSWORD'), connect_timeout=5)
        db.autocommit = True
        def query(statement, params=None):
            with db.cursor() as cur:
                cur.execute(statement,params)
                return cur.fetchall() if cur.description else []
        query("INSERT INTO quan_ly_shop.tai_khoan_game "
              "(ma_nick,ma_game,gia_ban,mat_khau_game) VALUES "
              "('QA_HOLD','G_LQ',90000,'QA_HOLD_PASS'),"
              "('QA_OCR','G_LQ',70000,'QA_OCR_PASS'),"
              "('QA_AGED','G_LQ',51000,'QA_AGED_PASS')")
        query("UPDATE quan_ly_shop.tai_khoan_game SET thong_tin_chi_tiet="
              "jsonb_build_object('ngay_nhap_kho',(CURRENT_DATE-40)::text) "
              "WHERE ma_nick='QA_AGED'")
        from scripts.generate_product_images import ensure_product_image
        for nick, game, details in query('SELECT ma_nick,ma_game,thong_tin_chi_tiet '
                                         'FROM quan_ly_shop.tai_khoan_game'):
            url = ensure_product_image(dict(ma_nick=nick, ma_game=game, thong_tin_chi_tiet=details))
            query('UPDATE quan_ly_shop.tai_khoan_game SET anh_dinh_kem_url=%s WHERE ma_nick=%s', (url, nick))
        log_file = (ARTIFACTS/'server.log').open('w',encoding='utf-8')
        flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        server = subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,env=env,
                                  stdout=log_file,stderr=subprocess.STDOUT,
                                  creationflags=flags)
        client = httpx.Client(base_url=BASE,timeout=100)
        for _ in range(80):
            try:
                if client.get('/api/games').status_code==200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Audit server did not start')
        headers = {}
        for role,password in passwords.items():
            client.cookies.clear()  # Separate login sessions, not an account switch.
            response = client.post('/api/auth/login',json={'username':role,'password':password})
            response.raise_for_status()
            headers[role]={'Authorization':'Bearer '+response.json()['token']}
        client.cookies.clear()  # Guest checks must really be anonymous.
        html=client.get('/')
        assert html.headers['content-type'].lower().startswith('text/html; charset=utf-8')
        assert html.text.lower().lstrip().startswith('<!doctype html>')
        assert client.get('/js/auth.js').headers['content-type'].startswith('application/javascript')
        assert client.get('/css/common.css').headers['content-type'].startswith('text/css')
        assert client.get('/static/admin.html').status_code==404
        def request(role, method, url, body=None):
            return client.request(method,url,headers=headers.get(role,{}),json=body)
        held = request('user','POST','/api/user/cart/add',{'ma_nick':'QA_HOLD'})
        assert held.status_code==200
        catalog = client.get('/api/accounts').json()
        record('GUEST','Only Chua_ban in public catalog',
               all(n['trang_thai']=='Chua_ban' for n in catalog),
               'Statuses returned: '+str(sorted({n['trang_thai'] for n in catalog})))
        record('GUEST','Public credentials masked',all(
            n['mat_khau_game'] is None and n['email_khoi_phuc'] is None for n in catalog))
        record('ASSETS','Catalog uses existing local product images',all(
            n['anh_dinh_kem_url'].startswith('/assets/products/') and
            (ROOT/'views'/n['anh_dinh_kem_url'].lstrip('/')).is_file() for n in catalog))
        record('ROLE','Wrong role redirects without exposing protected HTML',all(
            (lambda r:r.status_code==303 and r.headers.get('location')=='/index.html?error=unauthorized')(
                client.get(p,headers=headers['user'])) for p in ['/staff.html','/admin.html']))
        record('GUEST','Protected API denies anonymous',all(
            client.request(method,url,json=body).status_code in (401,403)
            for method,url,body in [
                ('GET','/api/accounts/QA_HOLD/credentials',None),
                ('POST','/api/user/cart/add',{'ma_nick':'QA_OCR'}),
                ('POST','/api/user/wishlist',{'ma_nick':'QA_OCR'}),
                ('POST','/api/user/deposit/sepay',{'amount':'10000','event_id':'guest'})]))
        shell_status={p:client.get(p).status_code for p in ('/staff.html','/admin.html')}
        record('GUEST','Internal pages redirect/deny',all(
            status in (301,302,303,307,308,401,403) for status in shell_status.values()),
            str(shell_status)+'; this is shell exposure, not protected API data access')
        denied=request('user','POST','/api/user/cart/checkout')
        record('USER','Insufficient funds rolls back',denied.status_code==409 and
               query("SELECT so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh='KH_DEMO'")[0][0]==0
               and not query("SELECT 1 FROM quan_ly_shop.don_hang WHERE ma_nick='QA_HOLD'"))

        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,
                executable_path=os.getenv('CHROME_EXECUTABLE',
                    'C:/Program Files/Google/Chrome/Application/chrome.exe'))
            context=browser.new_context(viewport={'width':1440,'height':960})
            # Do not transmit mock transfer data to a third party during audit.
            context.route('https://qr.sepay.vn/**',lambda route:route.abort())
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(BASE,wait_until='networkidle')
            expect(page.locator('#catalog .card').first).to_be_visible()
            def visible_menu():
                return page.locator('.nav-links a:visible').evaluate_all('(links)=>links.map(link=>link.getAttribute("href"))')
            record('NAV','Guest only sees catalog and login',
                   visible_menu()==['/'] and page.locator('#login-button').is_visible()
                   and not page.locator('#logout-button').is_visible())
            for action in ('heart','cart'):
                button=page.locator('[data-action="'+action+'"]').filter(visible=True).first
                if button.is_disabled():
                    button=page.locator('[data-action="'+action+'"]:not(:disabled)').first
                button.click()
                record('GUEST','UI login gate '+action,page.locator('#login-dialog').is_visible())
                page.locator('[data-close="login-dialog"]').click()
            record('GUEST','Wallet actions hidden until customer login',
                   not page.locator('#deposit-button').is_visible() and
                   not page.locator('#history-button').is_visible())
            with page.expect_response(lambda r:'/api/chat/nl2sql' in r.url) as response:
                page.locator('.quick').first.click()
            record('GUEST','AI4 browser chat',response.value.status==200)
            expect(page.locator('#chatlog .card').first).to_be_visible()
            record('UI','AI4 renders product cards with local thumbnails',
                   page.locator('#chatlog .card img').count()>0 and
                   '"SkinHiem"' not in page.locator('#chatlog').inner_text())
            screenshot(page,'guest-desktop')
            def ui_login(role, path='/'):
                page.goto(BASE+path,wait_until='networkidle')
                page.locator('#login-button').click()
                page.locator('#login-user').fill(role)
                page.locator('#login-password').fill(passwords[role])
                page.evaluate('window.__identityPageMarker="same-document"')
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#welcome')).to_contain_text(role+' · '+role,timeout=10000)
                target={'admin':'/admin.html','staff':'/staff.html','user':'/'}[role]
                page.wait_for_url(BASE+target,wait_until='networkidle')
                record('ROLE','Automatic login routing '+role,page.url==BASE+target)
                if role=='user':
                    record('ROLE','Customer login updates Client without reloading',
                           page.evaluate('window.__identityPageMarker')=='same-document')
            ui_login('user')
            expect(page.locator('#balance')).to_contain_text('0')
            record('NAV','User only sees catalog and customer actions',
                   visible_menu()==['/'] and
                   all(page.locator('header '+selector).is_visible() for selector in
                       ['#balance','#deposit-button','#history-button','#logout-button']) and
                   not page.locator('#login-button').is_visible())
            record('USER','Profile displays customer id',
                   'KH_DEMO' in page.locator('header').inner_text() or
                   'KH_DEMO' in page.locator('#balance').inner_text(),
                   'Header: '+page.locator('#welcome').inner_text())
            page.locator('#deposit-button').click()
            page.locator('#deposit-amount').select_option('500000')
            qr=page.locator('#qr-image').get_attribute('src')
            from urllib.parse import urlparse,parse_qs
            values=parse_qs(urlparse(qr).query)
            record('USER','QR parameters and deposit modal',
                   values.get('des')==['NAP KH_DEMO'] and values.get('amount')==['500000'],
                   'URL checked; external QR image deliberately not fetched')
            event=page.locator('#deposit-event').inner_text().split(': ',1)[1]
            page.locator('#deposit-submit').click()
            expect(page.locator('#balance')).to_contain_text('500.000',timeout=10000)
            record('USER','SePay UI updates wallet immediately',True)
            replay=request('user','POST','/api/user/deposit/sepay',
                {'amount':'500000','event_id':event,'description':'NAP KH_DEMO'})
            record('USER','SePay replay idempotency',replay.status_code==200 and replay.json()['duplicate'])
            page.locator('#deposit-button').click()
            page.locator('#deposit-method').select_option('card')
            page.locator('#deposit-amount').select_option('100000')
            page.locator('#card-serial').fill('BAD_SERIAL')
            page.locator('#card-code').fill('$CARD&1234567890')
            with page.expect_response(lambda r:'/api/user/deposit/card' in r.url) as card_error:
                page.locator('#deposit-submit').click()
            expect(page.locator('.toast.error').last).to_contain_text('Seri')
            record('USER','Invalid card red API error',card_error.value.status==409)
            page.locator('#card-serial').fill('#GARENA*98231456')
            page.locator('#deposit-submit').click()
            expect(page.locator('#balance')).to_contain_text('600.000',timeout=10000)
            record('USER','Valid card credits denomination',True)
            heart=page.locator('[data-action=heart][data-id=DEMO_FF1]')
            heart.click();expect(heart).to_have_text('♥')
            one=query("SELECT count(*) FROM quan_ly_shop.danh_sach_yeu_thich WHERE ma_kh='KH_DEMO'")[0][0]
            heart.click();expect(heart).to_have_text('♡')
            zero=query("SELECT count(*) FROM quan_ly_shop.danh_sach_yeu_thich WHERE ma_kh='KH_DEMO'")[0][0]
            record('USER','Wishlist toggle persists',one==1 and zero==0)
            record('USER','Cart countdown visible',page.locator('#cart [data-deadline]').count()==1)
            record('USER','Held nick hidden from other visitors',
                   'QA_HOLD' not in {n['ma_nick'] for n in client.get('/api/accounts').json()},
                   'Catalog hides held nick while owner cart retains countdown')
            page.locator('#checkout-button').click()
            expect(page.locator('#orders [data-credentials=QA_HOLD]')).to_be_visible(timeout=10000)
            record('USER','Checkout state and wallet',
                   query("SELECT trang_thai FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='QA_HOLD'")[0][0]=='Da_ban'
                   and query("SELECT so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh='KH_DEMO'")[0][0]==510000
                   and not query("SELECT 1 FROM quan_ly_shop.gio_hang WHERE ma_kh='KH_DEMO'"))
            page.locator('#orders [data-credentials=QA_HOLD]').click()
            expect(page.locator('#credentials-dialog')).to_be_visible()
            record('USER','Owned credentials modal',
                   'QA_HOLD_PASS' in page.locator('#credentials-content').inner_text())
            page.locator('[data-close=credentials-dialog]').click()
            page.locator('[data-action=credentials][data-id=DEMO_FF1]').click()
            expect(page.locator('.toast.error').last).to_be_visible()
            record('USER','Unowned credentials denied',
                   request('user','GET','/api/accounts/DEMO_FF1/credentials').status_code==403)
            page.locator('#history-button').click()
            expect(page.locator('#history-dialog')).to_be_visible()
            text=page.locator('#history-list').inner_text()
            combined='NAP_TIEN' in text and 'MUA_NICK' in text
            page.locator('#history-filter').select_option('MUA_NICK')
            purchases=page.locator('#history-list .entry').count()==1
            page.locator('#history-filter').select_option('NAP_TIEN')
            deposits=page.locator('#history-list .entry').count()==2
            page.locator('[data-receipt]').first.click()
            expect(page.locator('#receipt-dialog')).to_be_visible()
            record('USER','History filters and receipt dialogs',combined and purchases and deposits)
            page.locator('[data-close=receipt-dialog]').click()
            page.locator('[data-close=history-dialog]').click()
            for width,name in ((1440,'client-desktop'),(390,'client-mobile')):
                page.set_viewport_size({'width':width,'height':960 if width==1440 else 844})
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                record('UI','Client no horizontal overflow '+str(width),not overflow)
                screenshot(page,name)
            page.set_viewport_size({'width':1440,'height':960})
            # Simulate a response that arrives after logout and ignores AbortSignal.
            page.evaluate("""() => {
                window.__auditFetch=window.fetch;
                window.fetch=(url,options)=>String(url).includes('/credentials')
                    ?new Promise(resolve=>setTimeout(()=>resolve(new Response(
                        JSON.stringify({mat_khau_game:'QA_LATE_PRIVATE'}),
                        {headers:{'content-type':'application/json'}})),800))
                    :window.__auditFetch(url,options);
                void showCredentials('QA_HOLD');
            }""")
            page.locator('#logout-button').click()
            page.wait_for_url(BASE+'/',wait_until='networkidle')
            expect(page.locator('#welcome')).to_have_text('Khách tham quan')
            page.wait_for_timeout(1100)
            page.evaluate('if(window.__auditFetch){window.fetch=window.__auditFetch;delete window.__auditFetch}')
            cached=page.locator('#credentials-content').inner_text()
            record('USER','Credentials cleared on logout',
                   'QA_HOLD_PASS' not in cached and 'QA_LATE_PRIVATE' not in cached
                   and not page.locator('#credentials-dialog').is_visible(),
                   'Closed/logged-out DOM empty; delayed private response discarded')
            record('NAV','Logout restores Guest navbar and clears token',
                   visible_menu()==['/'] and page.locator('#login-button').is_visible() and
                   not page.locator('#customer-nav-actions').is_visible() and
                   page.evaluate('sessionStorage.getItem("shop_token")') is None)
            ui_login('staff','/staff.html')
            record('NAV','Staff sees workspace without Admin or API',visible_menu()==['/','/staff.html'])
            expect(page.locator('#stock [data-edit=QA_OCR]')).to_be_visible(timeout=10000)
            record('STAFF','No delete/password controls',
                   page.locator('[data-delete]').count()==0 and
                   page.locator('[name=mat_khau_game]').count()==0)
            page.locator('[data-edit=QA_OCR]').click()
            page.locator('summary').click()
            image_url='https://raw.githubusercontent.com/JaidedAI/EasyOCR/master/examples/english.png'
            page.locator('[name=anh_dinh_kem_url]').fill(image_url)
            with page.expect_response(lambda r:r.url.endswith('/QA_OCR/ocr'),timeout=180000) as url_response:
                page.locator('#ocr-button').click()
            url_result=url_response.value.json()
            record('STAFF','OCR button accepts pasted image URL',
                   url_response.value.status==200 and bool(url_result.get('ocr_text')),
                   'Real HTTPS download + EasyOCR; status='+str(url_response.value.status))
            image=Image.new('RGB',(1000,220),'white')
            font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',70)
            ImageDraw.Draw(image).text((40,60),'Raz Muay Thai',font=font,fill='black')
            image_path=ARTIFACTS/'ocr.png';image.save(image_path)
            page.locator('[name=anh_dinh_kem_url]').fill('')
            page.locator('#ocr-file').set_input_files(str(image_path))
            with page.expect_response(lambda r:r.url.endswith('/QA_OCR/ocr'),timeout=120000) as response:
                page.locator('#ocr-button').click()
            data=query("SELECT thong_tin_chi_tiet FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='QA_OCR'")[0][0]
            record('STAFF','Actual upload OCR -> JSONB',
                   response.value.status==200 and 'Raz Muay Thai' in data.get('SkinHiem',[]))
            expect(page.locator('#ocr-button')).to_be_enabled(timeout=10000)
            field=page.locator('[name=skin_names]').input_value()
            record('STAFF','OCR refreshes editable JSONB', 'Raz Muay Thai' in field,
                   'Editable JSONB must contain the freshly extracted skin')
            record('UI','OCR attributes use form fields and badges',
                   page.locator('[name=thong_tin_chi_tiet]').count()==0 and
                   page.locator('#attribute-preview .chip').count()>0)
            page.locator('#nick-form button[type=submit]').click()
            expect(page.locator('#operation-output')).to_contain_text('Đã cập nhật')
            after=query("SELECT thong_tin_chi_tiet FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='QA_OCR'")[0][0]
            record('STAFF','Saving after OCR preserves extracted data',
                   'Raz Muay Thai' in after.get('SkinHiem',[]),
                   'Before save SkinHiem='+str(data.get('SkinHiem'))+'; after='+str(after.get('SkinHiem')))
            page.locator('#refresh-transactions').click()
            expect(page.locator('#staff-transactions tr').first).to_be_visible()
            staff_response=request('staff','GET','/api/staff/transactions').json()
            expected={'ma_giao_dich','ma_kh','so_tien','phuong_thuc','trang_thai','ngay_tao'}
            record('STAFF','Sanitized reconciliation view',all(set(r)==expected for r in staff_response))
            filtered=request('staff','GET','/api/staff/transactions?ma_kh=DOES_NOT_EXIST').json()
            event_id=staff_response[0]['ma_giao_dich']
            page.locator('#filter-customer').fill('KH_DEMO')
            page.locator('#filter-event').fill(event_id)
            with page.expect_response(lambda r:'/api/staff/transactions?' in r.url):
                page.locator('#transaction-filter button[type=submit]').click()
            expect(page.locator('#staff-transactions tr')).to_have_count(1)
            record('STAFF','Lookup filter by customer/transaction',len(filtered)==0,
                   'API negative filter returns empty; UI finds exact customer/event')
            page.locator('#transaction-filter').evaluate('(form)=>form.reset()')
            page.locator('#refresh-transactions').click()
            expect(page.locator('#staff-transactions tr').first).to_be_visible()
            page.locator('#copilot-input').fill('NPA KH_DEMO')
            page.locator('#copilot-form button').click()
            expect(page.locator('#operation-output .matching-card').first).to_be_visible()
            record('STAFF','AI6 fuzzy UI suggestions',True)
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':960 if width==1440 else 844})
                record('UI','Staff no horizontal overflow '+str(width),
                       not page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                screenshot(page,'staff-'+str(width))
            page.set_viewport_size({'width':1440,'height':960})
            page.locator('#logout-button').click()
            page.wait_for_url(BASE+'/',wait_until='networkidle')
            expect(page.locator('#welcome')).to_have_text('Khách tham quan')
            record('STAFF','Reconciliation cleared on logout',
                   page.locator('#staff-transactions tr').count()==0 and page.url==BASE+'/',
                   'No prior reconciliation rows may remain after logout')
            ui_login('admin','/admin.html')
            record('NAV','Admin sees all navigation links',
                   visible_menu()==['/','/staff.html','/admin.html','/docs'])
            staff_page=request('staff','GET','/admin.html')
            record('ROLE','Staff cannot navigate to Admin page',
                   staff_page.status_code==303 and
                   staff_page.headers.get('location')=='/index.html?error=unauthorized')
            expect(page.locator('#stock [data-edit=QA_HOLD]')).to_be_visible()
            record('ADMIN','Eight AI cards in central UI',page.locator('.tools button').count()>=8,
                   'Tools buttons='+str(page.locator('.tools button').count())+
                   '; AI1..8 cards available in Admin')
            record('ADMIN','Editor exposes all mutable columns',
                   page.locator('[name=ma_ncc]').count()==1,
                   'Supplier field ma_ncc is editable through UI/API')
            page.locator('[data-ai="/api/admin/ai7-diagnostics"]').click()
            expect(page.locator('#operation-output .health-bar').first).to_be_visible()
            record('UI','AI7 renders health bars',
                   '"dead_ratio_pct"' not in page.locator('#operation-output').inner_text())
            page.locator('#dispute-form [name=ma_nick]').fill('QA_HOLD')
            page.locator('#dispute-form [name=evidence_count]').fill('5')
            page.locator('#dispute-form [name=seller_unresponsive]').check()
            page.locator('#dispute-form [name=recovery_changed]').check()
            page.locator('#dispute-form button').click()
            expect(page.locator('#operation-output .risk-bar')).to_be_visible()
            record('UI','AI8 renders risk bar and verdict card',
                   page.locator('#operation-output .verdict-card').count()==1 and
                   '"risk_score"' not in page.locator('#operation-output').inner_text())
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':960 if width==1440 else 844})
                record('UI','Admin no horizontal overflow '+str(width),
                       not page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                screenshot(page,'admin-'+str(width))
            # Exercise the actual account-switch modal on protected pages.
            page.set_viewport_size({'width':1440,'height':960})
            for role,target in [('staff','/staff.html'),('user','/index.html')]:
                page.locator('#login-button').click()
                page.locator('#login-user').fill(role)
                page.locator('#login-password').fill(passwords[role])
                page.locator('#login-form button[type=submit]').click()
                page.wait_for_url(BASE+target,wait_until='networkidle')
                expect(page.locator('#welcome')).to_contain_text(role+' · '+role)
                record('ROLE','Account switch redirects to '+role,page.url==BASE+target)
            record('NAV','Switching to User removes all internal links',visible_menu()==['/'])
            # Account switching on Client must preserve the current document.
            page.evaluate("document.getElementById('login-dialog').showModal();window.__identityPageMarker='client-switch'")
            page.locator('#login-user').fill('user')
            page.locator('#login-password').fill(passwords['user'])
            with page.expect_response(lambda r:r.url.endswith('/api/auth/login')):
                page.locator('#login-form button[type=submit]').click()
            expect(page.locator('#login-dialog')).not_to_be_visible()
            record('ROLE','User login on index refreshes identity without navigation',
                   page.url==BASE+'/index.html' and
                   page.evaluate('window.__identityPageMarker')=='client-switch')
            page.locator('#logout-button').click()
            page.wait_for_url(BASE+'/',wait_until='networkidle')
            record('NAV','User logout returns to Guest home',visible_menu()==['/'] and
                   page.locator('#login-button').is_visible())
            record('UI','No uncaught browser JavaScript exceptions',not errors,str(errors))
            browser.close();browser=None

        for statement in (
            'SELECT luong FROM quan_ly_shop.nhan_vien',
            'SELECT mat_khau_game FROM quan_ly_shop.tai_khoan_game',
            'DELETE FROM quan_ly_shop.tai_khoan_game WHERE false',
            'UPDATE quan_ly_shop.khach_hang SET so_du_vi=0 WHERE false',
        ):
            db.autocommit=False
            try:
                with db.cursor() as cur:
                    cur.execute('SET LOCAL ROLE "NhanVienSale"')
                    cur.execute(statement)
                record('STAFF','DB deny '+statement.split()[0],False,statement)
            except psycopg2.Error as exc:
                record('STAFF','DB deny '+statement.split()[0],exc.pgcode=='42501',
                       'SQLSTATE='+str(exc.pgcode)+'; '+statement)
            finally:
                db.rollback();db.autocommit=True
        record('STAFF','DELETE API denied',request('staff','DELETE','/api/admin/accounts/QA_OCR/delete').status_code==403)
        record('STAFF','Password UPDATE API denied',request('staff','PUT','/api/accounts/QA_OCR/update',
               {'mat_khau_game':'forbidden'}).status_code==403)
        request('user','POST','/api/user/deposit/sepay',
                {'event_id':'qa_pending','amount':'20000','description':'NPA KH_DEMO'})
        before=query("SELECT so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh='KH_DEMO'")[0][0]
        first=request('staff','POST','/api/staff/recheck-sepay',{'event_id':'qa_pending','ma_kh':'KH_DEMO'})
        second=request('staff','POST','/api/staff/recheck-sepay',{'event_id':'qa_pending','ma_kh':'KH_DEMO'})
        after=query("SELECT so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh='KH_DEMO'")[0][0]
        record('STAFF','SePay manual reconcile idempotent',first.status_code==200 and
               second.json().get('duplicate') and after-before==20000)
        free=request('admin','POST','/api/accounts/create',
                     {'ma_nick':'QA_FREE','ma_game':'G_LQ','gia_ban':80000,
                      'mat_khau_game':'oldpass'})
        updated=request('admin','PUT','/api/accounts/QA_FREE/update',
                        {'mat_khau_game':'newpass','email_khoi_phuc':'qa@example.com',
                         'gia_ban':85000,'ma_ncc':None})
        values=query("SELECT mat_khau_game,email_khoi_phuc FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='QA_FREE'")
        deleted=request('admin','DELETE','/api/admin/accounts/QA_FREE/delete')
        restricted=request('admin','DELETE','/api/admin/accounts/QA_HOLD/delete')
        record('ADMIN','Create/update credentials/delete unsold/FK sold',free.status_code==200 and
               updated.status_code==200 and values==[('newpass','qa@example.com')] and
               deleted.status_code==200 and restricted.status_code==409 and
               restricted.json().get('sqlstate')=='23503')
        etl=request('admin','POST','/api/admin/run-etl')
        record('ADMIN','ETL CSV validation',etl.status_code==200 and
               etl.json().get('loaded')==5 and etl.json().get('rejected')==3)
        pricing=request('admin','POST','/api/admin/run-pricing')
        record('ADMIN','AI2 floor 50000 and aged inventory',pricing.status_code==200 and
               query("SELECT gia_ban FROM quan_ly_shop.tai_khoan_game WHERE ma_nick='QA_AGED'")[0][0]==50000)
        locked=request('admin','POST','/api/admin/lock-fraud/QA_HOLD')
        record('ADMIN','AI3 revokes paid credentials',locked.status_code==200 and
               request('user','GET','/api/accounts/QA_HOLD/credentials').status_code==403)
        query("INSERT INTO quan_ly_shop.khach_hang(ma_kh,ho_ten) VALUES('QA_CHURN','QA CHURN')")
        query("INSERT INTO quan_ly_shop.don_hang_lich_su "
              "(ma_dh,ma_kh,ma_nick,ngay_tao,tong_tien) VALUES "
              "('QA_HISTORY','QA_CHURN','QA_OLD',CURRENT_TIMESTAMP-INTERVAL '70 days',100000)")
        marketing=request('admin','POST','/api/admin/run-marketing')
        record('ADMIN','AI5 churn voucher',marketing.status_code==200 and
               query("SELECT ma_voucher_tang FROM ai_analytics.khach_hang_marketing WHERE ma_kh='QA_CHURN'")==[('TRIAN20PCT',)])
        diagnostics=request('admin','GET','/api/admin/ai7-diagnostics')
        vacuum=request('admin','POST','/api/admin/run-vacuum',{'table':'tai_khoan_game'})
        record('ADMIN','AI7 diagnostics and VACUUM',diagnostics.status_code==200 and
               isinstance(diagnostics.json(),list) and vacuum.status_code==200)
        dispute=request('admin','POST','/api/admin/ai8-evaluate-dispute',
                        {'ma_nick':'QA_HOLD','evidence_count':5,
                         'seller_unresponsive':True,'recovery_changed':True})
        verdict=dispute.json()
        record('ADMIN','AI8 risk >80 proposes full refund',dispute.status_code==200 and
               verdict.get('risk_score',0)>80 and verdict.get('recommend_refund') and
               float(verdict.get('proposed_refund',0))==90000 and not verdict.get('executed'))
        log_file.flush()
        text=(ARTIFACTS/'server.log').read_text(encoding='utf-8')
        record('ADMIN','Terminal HTTP action logs',all(
            route in text for route in ['/api/admin/run-etl','/api/admin/run-pricing',
                                       '/api/admin/run-marketing','/api/admin/run-vacuum']))
        audit_routes=['/api/admin/run-etl','/api/admin/run-pricing',
                      '/api/admin/run-marketing','/api/admin/run-vacuum',
                      '/api/admin/lock-fraud/QA_HOLD','/api/admin/ai8-evaluate-dispute']
        record('ADMIN','Actor-attributed audit trail for each action',
               all(any('actor=admin ' in line and 'request_id=' in line and
                       'target='+route+' ' in line and 'status=200' in line
                       for line in text.splitlines()) for route in audit_routes),
               'Authenticated actor, role, request_id, method, target and status')
    except Exception as exc:
        record('HARNESS','Audit completed',False,type(exc).__name__+': '+str(exc))
        if browser:
            try:
                browser.close()
            except Exception:
                pass
    finally:
        if client:
            client.close()
        if server:
            server.terminate()
            try:
                server.wait(timeout=12)
            except subprocess.TimeoutExpired:
                server.kill();server.wait()
        if log_file:
            log_file.close()
        if db:
            db.close()
        if created:
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
            print('Disposable audit database removed',flush=True)
        admin_conn.close()
        from scripts.generate_product_images import product_filename
        for nick in ['QA_HOLD','QA_OCR','QA_AGED','QA_NEW','QA_FREE']:
            (ROOT/'views/assets/products'/product_filename(nick)).unlink(missing_ok=True)
        output=ROOT/'docs/test_results/role_ui.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Results:',output,flush=True)
    return int(any(not result['passed'] for result in RESULTS))


if __name__=='__main__':
    raise SystemExit(main())
