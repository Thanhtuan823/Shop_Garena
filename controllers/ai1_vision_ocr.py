"""AI1: real EasyOCR extraction, preserving existing JSONB metadata."""
import base64
import io
import ipaddress
import json
import logging
import os
import re
import unicodedata
import socket
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from config.database import transaction

_reader = None
_reader_lock = threading.Lock()
MAX_IMAGE = 5 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
_dll_handles = []


def prepare_ocr_runtime():
    """Optional app-local MSVC runtime; never replace Windows system DLLs."""
    if os.name == 'nt' and not _dll_handles:
        for folder in (ROOT / '.venv/ocr_runtime',):
            if folder.is_dir():
                _dll_handles.append(os.add_dll_directory(str(folder)))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Không hỗ trợ URL ảnh chuyển hướng; dùng ảnh tải lên')


def read_image(image_url):
    if image_url.startswith('/assets/products/'):
        product_root = (ROOT / 'views/assets/products').resolve()
        image_path = (ROOT / 'views' / image_url.lstrip('/')).resolve()
        if not image_path.is_relative_to(product_root) or image_path.suffix != '.png':
            raise ValueError('Đường dẫn ảnh sản phẩm không hợp lệ')
        if image_path.stat().st_size > MAX_IMAGE:
            raise ValueError('Ảnh vượt quá 5MB')
        return image_path.read_bytes()
    if image_url.startswith('data:image/'):
        header, encoded = image_url.split(',', 1)
        if ';base64' not in header or len(encoded) > MAX_IMAGE * 1.4:
            raise ValueError('Ảnh base64 không hợp lệ hoặc quá lớn')
        return base64.b64decode(encoded, validate=True)
    url = urllib.parse.urlparse(image_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.port:
        raise ValueError('Chỉ hỗ trợ ảnh HTTPS công khai hoặc upload base64')
    allowed = {host.strip().lower() for host in
               os.getenv('OCR_ALLOWED_HOSTS', '').split(',') if host.strip()}
    if url.hostname.lower() not in allowed:
        raise ValueError('Hãy upload ảnh hoặc cấu hình domain trong OCR_ALLOWED_HOSTS')
    addresses = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global
                            for a in addresses):
        raise ValueError('Không được truy cập ảnh trên mạng nội bộ')
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(image_url, timeout=10) as response:
        data = response.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise ValueError('Ảnh vượt quá 5MB')
    return data


def extract_game_data(image_url):
    global _reader
    prepare_ocr_runtime()
    import numpy as np
    from PIL import Image
    import easyocr

    image = Image.open(io.BytesIO(read_image(image_url)))
    if image.width * image.height > 20000000:
        raise ValueError('Ảnh vượt quá 20 megapixel')
    image = image.convert('RGB')
    with _reader_lock:
        if _reader is None:
            _reader = easyocr.Reader(
                ['vi', 'en'], gpu=False, verbose=False,
                model_storage_directory=str(ROOT / '.venv/ocr_models/model'),
                user_network_directory=str(ROOT / '.venv/ocr_models/network'),
            )
        lines = _reader.readtext(np.array(image), detail=0)
    text = ' '.join(lines)
    def normalized(value):
        return ''.join(char for char in unicodedata.normalize('NFD', value.casefold())
                       if unicodedata.category(char) != 'Mn').replace('đ', 'd')
    lowered = normalized(text)
    result = {'ocr_text': text, 'SkinHiem': [], 'VuKhi': []}
    for item in ['Raz Muay Thai', 'Ngộ Không EVO Lvl 5']:
        if normalized(item) in lowered:
            result['SkinHiem'].append(item)
    if 'ak rong xanh' in lowered:
        result['VuKhi'].append('AK Rồng Xanh')
    for rank in ['Thách Đấu', 'Cao Thủ', 'Tinh Anh', 'Kim Cương', 'Huyền Thoại']:
        if normalized(rank) in lowered:
            result['Rank'] = rank
            break
    for key, keyword in [('SoTuong', 'tuong'), ('SoSkin', 'skin')]:
        match = re.search(r'\b(?:so\s+)?' + keyword + r'\s*[:\-]?\s*(\d+)', lowered)
        if match:
            result[key] = int(match.group(1))
    return result


def process_game_screenshot(ma_nick: str, image_url: str, ma_game: str,
                            role='ShopAdmin'):
    extracted = extract_game_data(image_url)
    # Raw screenshot text is private OCR evidence, not public catalog metadata.
    public_attributes = {key: value for key, value in extracted.items()
                         if key != 'ocr_text'}
    with transaction(role=role) as conn, conn.cursor() as cur:
        cur.execute("UPDATE quan_ly_shop.tai_khoan_game SET thong_tin_chi_tiet="
                    "COALESCE(thong_tin_chi_tiet, '{}'::jsonb) || %s::jsonb "
                    "WHERE ma_nick=%s AND ma_game=%s RETURNING ma_nick",
                    (json.dumps(public_attributes), ma_nick, ma_game))
        if not cur.fetchone():
            raise ValueError('Nick không tồn tại hoặc role không được sửa')
        # Keep the update and log atomic; only this trusted service can reset role.
        cur.execute('RESET ROLE')
        cur.execute('INSERT INTO ai_analytics.log_ai_ocr '
                    '(ma_nick,url_anh,ket_qua_raw_json,confidence_score) '
                    'VALUES (%s,%s,%s,NULL)',
                    (ma_nick, image_url[:255], json.dumps(extracted)))
    logging.info('[AI1] OCR updated %s; existing inventory date preserved', ma_nick)
    return extracted
