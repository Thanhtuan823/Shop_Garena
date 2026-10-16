"""GarenaShop local fullstack demo. Start with: python app.py."""
import logging
import os
import secrets
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date
from typing import Literal

import psycopg2
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from config.auth import current_user, hash_password, login, logout, roles, session_user
from config.db_connection import transaction
from controllers import shop_service as shop
from controllers.ai1_vision_ocr_controller import process_game_screenshot
from controllers.ai2_pricing_controller import run_pricing
from controllers.ai3_fraud_guard_controller import check_and_lock_fraud
from controllers.ai4_nl2sql_chatbot_controller import nl2sql_translate_and_execute
from controllers.ai5_marketing_controller import run_marketing
from controllers.ai6_reconcile_controller import reconcile_assistant
from controllers.ai7_dba_optimizer_controller import diagnostics, run_vacuum
from controllers.ai8_dispute_controller import evaluate_dispute
from controllers.etl_cleaner_controller import etl_clean_customers
from controllers.realtime_notify_listener import listen_for_new_nicks

ROOT = Path(__file__).resolve().parent
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='backslashreplace')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)], force=True)


def background(stop):
    while not stop.is_set():
        try:
            shop.expire_cart()
        except Exception:
            logging.exception('[CART] Expiration worker failed')
        stop.wait(15)


def notification_worker(stop):
    while not stop.is_set():
        try:
            listen_for_new_nicks(stop)
        except Exception:
            logging.exception('[LISTENER] Reconnecting in 3s')
            stop.wait(3)


@asynccontextmanager
async def lifespan(application):
    stop = threading.Event()
    workers = [threading.Thread(target=background, args=(stop,), daemon=True),
               threading.Thread(target=notification_worker, args=(stop,), daemon=True)]
    for worker in workers:
        worker.start()
    logging.info('[SERVER] Local demo ready: http://127.0.0.1:8000')
    yield
    stop.set()
    for worker in workers:
        worker.join(timeout=6)


app = FastAPI(title='GarenaShop MVC / 8 AI', lifespan=lifespan)


@app.middleware('http')
async def request_log(request: Request, call_next):
    token = request.headers.get('authorization', '').removeprefix('Bearer ')
    actor = session_user(token or request.cookies.get('shop_page_session'))
    request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    logging.info('[AUDIT] request_id=%s actor=%s role=%s method=%s target=%s status=%s',
                 request_id, actor['username'] if actor else 'guest',
                 actor['role'] if actor else 'guest', request.method,
                 request.url.path, response.status_code)
    return response


@app.exception_handler(shop.ShopError)
async def business_error(request, exc):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.exception_handler(ValueError)
async def validation_error(request, exc):
    return JSONResponse(status_code=400, content={'detail': str(exc)})


@app.exception_handler(psycopg2.Error)
async def database_error(request, exc):
    logging.error('[DB] %s %s', request.url.path, exc.pgcode)
    messages = {'23503': 'Không thể xóa: dữ liệu đã được tham chiếu (FK RESTRICT)',
                '23505': 'Dữ liệu hoặc giao dịch đã tồn tại',
                '23514': 'Dữ liệu vi phạm ràng buộc CHECK',
                '42501': 'Role không có quyền thực hiện thao tác',
                '55P03': 'Dữ liệu đang bận; vui lòng thử lại'}
    status = 403 if exc.pgcode == '42501' else 409
    return JSONResponse(status_code=status,
                        content={'detail': messages.get(exc.pgcode,
                                 'Lỗi database; xem terminal'), 'sqlstate': exc.pgcode})


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LoginBody(StrictBody):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class RegisterBody(LoginBody):
    ho_ten: str = Field(min_length=1, max_length=100)
    so_dien_thoai: str = Field(pattern=r'^0[0-9]{9}$')


class Question(StrictBody):
    prompt: str = Field(min_length=1, max_length=500)


class DepositBody(StrictBody):
    amount: str
    event_id: str = Field(min_length=1, max_length=40)
    description: str = Field(default='', max_length=250)
    serial: str = Field(default='', max_length=30)
    card: str = Field(default='', max_length=30)


class NickBody(StrictBody):
    ma_nick: str = Field(min_length=1, max_length=15)
    ma_game: str = Field(min_length=1, max_length=10)
    ma_ncc: str | None = None
    gia_ban: float = Field(gt=0, le=9999999999999)
    trang_thai: Literal['Chua_ban', 'Dang_giu_cho', 'Da_ban', 'Khoa_tranh_chap'] = 'Chua_ban'
    thong_tin_chi_tiet: dict = Field(default_factory=dict)
    anh_dinh_kem_url: str | None = Field(default=None, max_length=255)
    mat_khau_game: str = Field(default_factory=lambda: secrets.token_urlsafe(16), min_length=1, max_length=100)
    email_khoi_phuc: str | None = Field(default=None, max_length=100)


class PatchNick(StrictBody):
    gia_ban: float | None = Field(default=None, gt=0, le=9999999999999)
    trang_thai: str | None = None
    thong_tin_chi_tiet: dict | None = None
    anh_dinh_kem_url: str | None = Field(default=None, max_length=255)
    mat_khau_game: str | None = Field(default=None, min_length=1, max_length=100)
    email_khoi_phuc: str | None = Field(default=None, max_length=100)
    ma_game: str | None = Field(default=None, max_length=10)
    ma_ncc: str | None = Field(default=None, max_length=10)


class NickId(StrictBody):
    ma_nick: str = Field(min_length=1, max_length=15)


class OCRBody(StrictBody):
    image_url: str = Field(min_length=1, max_length=7500000)


class RecheckBody(StrictBody):
    event_id: str = Field(max_length=40)
    ma_kh: str = Field(max_length=10)


class DisputeBody(NickId):
    evidence_count: int = Field(default=0, ge=0, le=100)
    seller_unresponsive: bool = False
    recovery_changed: bool = False


class VacuumBody(StrictBody):
    table: str = 'tai_khoan_game'


def rows(query, params=None, role=None, customer=None):
    with transaction(role, customer) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def own(user, customer):
    if user['role'] != 'user' or user['ma_kh'] != customer:
        raise HTTPException(403, 'Chỉ được xem dữ liệu của chính mình')


@app.post('/api/auth/login')
def authenticate(body: LoginBody, request: Request, response: Response):
    result = login(body.username, body.password)
    logout(request.cookies.get('shop_page_session'))
    response.set_cookie('shop_page_session', result['token'], httponly=True,
                        samesite='strict', max_age=3600,
                        secure=request.url.scheme == 'https')
    logging.info('[AUTH] actor=%s role=%s action=login', body.username,
                 result['principal']['role'])
    return result


@app.post('/api/auth/register')
def register(body: RegisterBody):
    if len(body.password) < 8:
        raise HTTPException(400, 'Mật khẩu cần ít nhất 8 ký tự')
    customer = 'U' + secrets.token_hex(4)
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('INSERT INTO quan_ly_shop.khach_hang '
                    '(ma_kh,ho_ten,so_dien_thoai) VALUES (%s,%s,%s)',
                    (customer, body.ho_ten.strip().upper(), body.so_dien_thoai))
        cur.execute('INSERT INTO quan_ly_shop.app_principals '
                    '(username,password_hash,app_role,ma_kh) VALUES (%s,%s,%s,%s)',
                    (body.username, hash_password(body.password), 'user', customer))
    return {'ma_kh': customer, 'message': 'Đăng ký thành công; hãy đăng nhập'}


@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return user


@app.post('/api/auth/logout')
def signout(request: Request, response: Response):
    logout(request.headers.get('authorization', '').removeprefix('Bearer '))
    logout(request.cookies.get('shop_page_session'))
    response.delete_cookie('shop_page_session', httponly=True, samesite='strict')
    return {'message': 'Đã đăng xuất'}


@app.get('/api/games')
def games():
    return rows('SELECT * FROM quan_ly_shop.danh_muc_game ORDER BY ten_game',
                role='ShopGuest')


@app.get('/api/accounts')
def catalog():
    return rows("SELECT * FROM quan_ly_shop.vw_catalog_nick WHERE trang_thai "
                "= 'Chua_ban' ORDER BY gia_ban,ma_nick LIMIT 200",
                role='ShopGuest')


@app.get('/api/manage/accounts')
def manage_accounts(user=Depends(roles('admin', 'staff'))):
    fields = '*' if user['role'] == 'admin' else (
        'ma_nick,ma_game,ma_ncc,gia_ban,trang_thai,thong_tin_chi_tiet,anh_dinh_kem_url')
    return rows('SELECT ' + fields + ' FROM quan_ly_shop.tai_khoan_game ORDER BY ma_nick',
                role='ShopAdmin' if user['role'] == 'admin' else 'NhanVienSale')


@app.post('/api/accounts/create')
def create_account(body: NickBody, user=Depends(roles('admin', 'staff'))):
    data = body.model_dump()
    data['gia_ban'] = shop.money(data['gia_ban'])
    data['thong_tin_chi_tiet'].setdefault('ngay_nhap_kho', date.today().isoformat())
    data['thong_tin_chi_tiet'] = Json(data['thong_tin_chi_tiet'])
    columns = list(data)
    with transaction('ShopAdmin' if user['role'] == 'admin' else 'NhanVienSale') as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL('INSERT INTO quan_ly_shop.tai_khoan_game ({}) VALUES ({})')
                        .format(sql.SQL(',').join(map(sql.Identifier, columns)),
                                sql.SQL(',').join(sql.Placeholder() for _ in columns)),
                        list(data.values()))
    logging.info('[%s_ACTION] Created nick %s', user['role'].upper(), body.ma_nick)
    return {'ma_nick': body.ma_nick}


@app.put('/api/accounts/{ma_nick}/update')
def update_account(ma_nick: str, body: PatchNick, user=Depends(roles('admin', 'staff'))):
    data = body.model_dump(exclude_unset=True)
    allowed = {'gia_ban', 'trang_thai', 'thong_tin_chi_tiet', 'anh_dinh_kem_url'}
    if user['role'] == 'staff' and set(data) - allowed:
        raise HTTPException(403, 'Staff không được sửa mật khẩu/email hoặc khóa định danh')
    if not data:
        raise HTTPException(400, 'Chưa có trường cập nhật')
    if 'trang_thai' in data and data['trang_thai'] not in {
        'Chua_ban', 'Dang_giu_cho', 'Da_ban', 'Khoa_tranh_chap'
    }:
        raise HTTPException(400, 'Trạng thái không hợp lệ')
    if 'gia_ban' in data:
        data['gia_ban'] = shop.money(data['gia_ban'])
    if 'thong_tin_chi_tiet' in data:
        if data['thong_tin_chi_tiet'] is None:
            raise HTTPException(400, 'JSONB không được null')
        data['thong_tin_chi_tiet'] = Json(data['thong_tin_chi_tiet'])
    with transaction('ShopAdmin' if user['role'] == 'admin' else 'NhanVienSale') as conn:
        with conn.cursor() as cur:
            assignments = sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in data)
            cur.execute(sql.SQL('UPDATE quan_ly_shop.tai_khoan_game SET {} WHERE ma_nick=%s')
                        .format(assignments), list(data.values()) + [ma_nick])
            if not cur.rowcount:
                raise HTTPException(409, 'Nick không tồn tại hoặc không còn được sửa')
    return {'message': 'Đã cập nhật'}


@app.delete('/api/admin/accounts/{ma_nick}/delete')
def delete_account(ma_nick: str, user=Depends(roles('admin'))):
    with transaction('ShopAdmin') as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM quan_ly_shop.tai_khoan_game WHERE ma_nick=%s', (ma_nick,))
        if not cur.rowcount:
            raise HTTPException(404, 'Không tìm thấy nick')
    return {'message': 'Đã xóa'}


@app.post('/api/accounts/{ma_nick}/ocr')
def ocr(ma_nick: str, body: OCRBody, user=Depends(roles('admin', 'staff'))):
    data = rows('SELECT ma_game FROM quan_ly_shop.tai_khoan_game WHERE ma_nick=%s',
                (ma_nick,), role='NhanVienSale')
    if not data:
        raise HTTPException(404, 'Không tìm thấy nick')
    try:
        result = process_game_screenshot(ma_nick, body.image_url, data[0]['ma_game'],
                                        'ShopAdmin' if user['role'] == 'admin' else 'NhanVienSale')
        result['thong_tin_chi_tiet'] = rows(
            'SELECT thong_tin_chi_tiet FROM quan_ly_shop.tai_khoan_game WHERE ma_nick=%s',
            (ma_nick,), role='NhanVienSale')[0]['thong_tin_chi_tiet']
        return result
    except (ImportError, OSError) as exc:
        logging.exception('[AI1] OCR runtime unavailable')
        raise HTTPException(503, 'OCR chưa sẵn sàng: kiểm tra EasyOCR/PyTorch '
                            'và Python 3.12; xem terminal để biết lỗi DLL/model') from exc


@app.get('/api/accounts/{ma_nick}/credentials')
def credentials(ma_nick: str, user=Depends(roles('user'))):
    data = rows('SELECT ma_nick,mat_khau_game,email_khoi_phuc '
                'FROM quan_ly_shop.tai_khoan_game WHERE ma_nick=%s',
                (ma_nick,), 'KhachHangRole', user['ma_kh'])
    if not data:
        raise HTTPException(403, 'Chưa mua nick hoặc nick bị khóa tranh chấp (RLS)')
    return data[0]


@app.post('/api/user/deposit/sepay')
def sepay(body: DepositBody, user=Depends(roles('user'))):
    return shop.deposit(user['ma_kh'], body.amount, 'SEPAY_QR', body.event_id,
                        description=body.description)


@app.post('/api/user/deposit/card')
def card(body: DepositBody, user=Depends(roles('user'))):
    return shop.deposit(user['ma_kh'], body.amount, 'THE_CAO', body.event_id,
                        serial=body.serial, card=body.card)


@app.get('/api/user/profile/{ma_kh}')
def profile(ma_kh: str, user=Depends(roles('user'))):
    own(user, ma_kh)
    return rows('SELECT ma_kh,ho_ten,so_du_vi FROM quan_ly_shop.khach_hang WHERE ma_kh=%s',
                (ma_kh,))[0]


@app.get('/api/user/transactions/{ma_kh}')
def transactions(ma_kh: str, user=Depends(roles('user'))):
    own(user, ma_kh)
    return rows('SELECT * FROM quan_ly_shop.vw_lich_su_bien_dong_vi ORDER BY ngay_tao DESC',
                role='KhachHangRole', customer=ma_kh)


@app.get('/api/user/transaction-detail/{ma_gd}')
def receipt(ma_gd: str, user=Depends(roles('user'))):
    data = rows('SELECT * FROM quan_ly_shop.vw_lich_su_bien_dong_vi WHERE ma_gd=%s',
                (ma_gd,), 'KhachHangRole', user['ma_kh'])
    if not data:
        raise HTTPException(404, 'Không tìm thấy biên lai của bạn')
    return data[0]


@app.get('/api/user/orders')
def orders(user=Depends(roles('user'))):
    return rows('SELECT d.ma_dh,d.ma_nick,d.tong_tien,d.ngay_tao,n.trang_thai '
                'FROM quan_ly_shop.don_hang d JOIN quan_ly_shop.tai_khoan_game n '
                'USING(ma_nick) WHERE d.ma_kh=%s ORDER BY d.ngay_tao DESC', (user['ma_kh'],))


@app.post('/api/user/cart/add')
def cart_add(body: NickId, user=Depends(roles('user'))):
    return shop.add_cart(user['ma_kh'], body.ma_nick)


@app.delete('/api/user/cart/{ma_nick}')
def cart_remove(ma_nick: str, user=Depends(roles('user'))):
    return shop.remove_cart(user['ma_kh'], ma_nick)


@app.get('/api/user/cart')
def cart_list(user=Depends(roles('user'))):
    shop.expire_cart()
    return rows('SELECT g.ma_nick,g.han_giu_cho,n.gia_ban, '
                'EXTRACT(EPOCH FROM(g.han_giu_cho-CURRENT_TIMESTAMP)) AS seconds_left FROM '
                'quan_ly_shop.gio_hang g JOIN quan_ly_shop.tai_khoan_game n '
                'USING(ma_nick) WHERE ma_kh=%s ORDER BY ma_nick', (user['ma_kh'],))


@app.post('/api/user/cart/checkout')
def cart_checkout(user=Depends(roles('user'))):
    return shop.checkout(user['ma_kh'])


@app.get('/api/user/wishlist')
def wishlist(user=Depends(roles('user'))):
    return rows('SELECT ma_nick FROM quan_ly_shop.danh_sach_yeu_thich WHERE ma_kh=%s',
                (user['ma_kh'],))


@app.post('/api/user/wishlist')
def wishlist_add(body: NickId, user=Depends(roles('user'))):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('INSERT INTO quan_ly_shop.danh_sach_yeu_thich (ma_kh,ma_nick) '
                    'VALUES (%s,%s) ON CONFLICT DO NOTHING', (user['ma_kh'], body.ma_nick))
    return {'message': 'Đã thêm yêu thích'}


@app.delete('/api/user/wishlist/{ma_nick}')
def wishlist_remove(ma_nick: str, user=Depends(roles('user'))):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM quan_ly_shop.danh_sach_yeu_thich WHERE ma_kh=%s AND ma_nick=%s',
                    (user['ma_kh'], ma_nick))
    return {'message': 'Đã bỏ yêu thích'}


@app.post('/api/chat/nl2sql')
def chat(body: Question):
    return nl2sql_translate_and_execute(body.prompt)


@app.get('/api/staff/transactions')
def staff_transactions(ma_kh: str | None = None, ma_giao_dich: str | None = None,
                       user=Depends(roles('staff', 'admin'))):
    return rows('SELECT * FROM quan_ly_shop.vw_lich_su_nap_staff '
                'WHERE (%s IS NULL OR ma_kh=%s) '
                'AND (%s IS NULL OR ma_giao_dich=%s) ORDER BY ngay_tao DESC',
                (ma_kh, ma_kh, ma_giao_dich, ma_giao_dich), role='NhanVienSale')


@app.post('/api/staff/recheck-sepay')
def recheck(body: RecheckBody, user=Depends(roles('staff', 'admin'))):
    return shop.recheck_sepay(body.event_id, body.ma_kh)


@app.post('/api/staff/ai6-reconcile-assistant')
def assistant(body: Question, user=Depends(roles('staff', 'admin'))):
    return reconcile_assistant(body.prompt)


@app.post('/api/admin/run-etl')
def etl(user=Depends(roles('admin'))):
    return etl_clean_customers()


@app.post('/api/admin/run-pricing')
def pricing(user=Depends(roles('admin'))):
    return run_pricing()


@app.post('/api/admin/lock-fraud/{ma_nick}')
def fraud(ma_nick: str, user=Depends(roles('admin'))):
    return check_and_lock_fraud(ma_nick)


@app.post('/api/admin/run-marketing')
def marketing(user=Depends(roles('admin'))):
    return run_marketing()


@app.get('/api/admin/ai7-diagnostics')
def dba(user=Depends(roles('admin'))):
    return diagnostics()


@app.post('/api/admin/ai8-evaluate-dispute')
def dispute(body: DisputeBody, user=Depends(roles('admin'))):
    return evaluate_dispute(**body.model_dump())


@app.post('/api/admin/run-vacuum')
def vacuum(body: VacuumBody, user=Depends(roles('admin'))):
    return run_vacuum(body.table)


def html_file(filename):
    path = ROOT / 'views' / filename
    headers = {'Cache-Control': 'no-store, private',
               'X-Content-Type-Options': 'nosniff'}
    if not path.is_file():
        return HTMLResponse('<h1>404: Không tìm thấy giao diện</h1>', status_code=404,
                            headers=headers, media_type='text/html; charset=utf-8')
    return FileResponse(path, media_type='text/html; charset=utf-8', headers=headers)


def page_access(request, filename, allowed):
    bearer = request.headers.get('authorization', '').removeprefix('Bearer ')
    user = session_user(bearer or request.cookies.get('shop_page_session'))
    if user is None:
        return RedirectResponse('/?next=/' + filename, status_code=303,
                                headers={'Cache-Control': 'no-store'})
    if user['role'] not in allowed:
        return HTMLResponse('<h1>403: Không có quyền truy cập</h1><a href="/">Về Client</a>',
                            status_code=403, headers={'Cache-Control': 'no-store'})
    return html_file(filename)


@app.get('/', response_class=HTMLResponse)
def serve_index():
    return html_file('index.html')


@app.get('/staff.html', response_class=HTMLResponse)
def serve_staff(request: Request):
    return page_access(request, 'staff.html', {'staff', 'admin'})


@app.get('/admin.html', response_class=HTMLResponse)
def serve_admin(request: Request):
    return page_access(request, 'admin.html', {'admin'})


@app.get('/web_chatbot_ui_mock.html', response_class=HTMLResponse)
def serve_mock():
    return html_file('web_chatbot_ui_mock.html')


class AssetFiles(StaticFiles):
    """Explicit MIME types, independent of Windows registry file associations."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        media = {'.js': 'application/javascript; charset=utf-8',
                 '.css': 'text/css; charset=utf-8'}.get(Path(path).suffix.lower())
        if media and response.status_code == 200:
            response.headers['Content-Type'] = media
        return response


# Only assets are mounted: HTML aliases must never bypass the page role checks.
app.mount('/assets', AssetFiles(directory=str(ROOT / 'views/assets')), name='assets')
app.mount('/static', AssetFiles(directory=str(ROOT / 'views/assets')), name='static')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.getenv('PORT', '8000')))
