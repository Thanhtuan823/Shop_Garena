"""Draw deterministic, local demo artwork with Pillow; never download images.

python scripts/generate_product_images.py             # sample accounts only
python scripts/generate_product_images.py --sync-db   # current DB + image URLs
Artwork is illustrative, not an actual screenshot or an official game logo.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont

ASSETS = ROOT / 'views/assets'
GAMES = {'lq': ('LIÊN QUÂN', '#e50914'), 'ff': ('FREE FIRE', '#ef8e29'),
         'fco': ('FC ONLINE', '#26b88c')}


def font(size, bold=False):
    candidates = ['C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                  '/Library/Fonts/Arial.ttf']
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def game_key(value):
    value = value.upper()
    return 'ff' if 'FF' in value or 'FREE' in value else 'fco' if 'FC' in value else 'lq'


def product_filename(account_id):
    if re.fullmatch(r'[A-Za-z0-9_-]{1,50}', account_id):
        return account_id + '.png'
    return 'nick_' + hashlib.sha256(account_id.encode()).hexdigest()[:24] + '.png'


def save_image(path, title, subtitle, accent, details=(), size=(960, 540)):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGB', size, '#121212')
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.polygon([(w*.65, 0), (w, 0), (w, h), (w*.3, h)], fill='#252029')
    draw.line([(w*.65, 0), (w*.3, h)], fill=accent, width=7)
    draw.rounded_rectangle((28, 28, w-28, h-28), radius=20, outline=accent, width=2)
    if not title:
        image.save(path, 'PNG', optimize=True)
        return
    draw.text((55, 55), 'GARENA / SHOP', font=font(23, True), fill=accent)
    draw.text((55, h*.31), title[:32], font=font(46, True), fill='white')
    draw.text((57, h*.47), subtitle[:55], font=font(26), fill='#e0ced7')
    y = int(h*.62)
    for detail in details[:3]:
        draw.text((57, y), str(detail)[:58], font=font(21), fill='#ffbb8c')
        y += 36
    draw.text((57, h-64), 'ẢNH MINH HỌA NỘI BỘ • KHÔNG PHẢI ẢNH TÀI KHOẢN THẬT',
              font=font(13), fill='#aaa3af')
    image.save(path, 'PNG', optimize=True)


def ensure_product_image(account):
    key = game_key(account.get('ten_game', account['ma_game']))
    title, accent = GAMES[key]
    info = account.get('thong_tin_chi_tiet') or {}
    details = [f"Rank: {info.get('Rank', 'Chưa cập nhật')}"]
    for field in ('SkinHiem', 'VuKhi', 'DoiHinh'):
        values = info.get(field, [])
        if isinstance(values, list):
            details.extend(str(value) for value in values)
    filename = product_filename(account['ma_nick'])
    save_image(ASSETS / 'products' / filename, title, '#' + account['ma_nick'],
               accent, details)
    return '/assets/products/' + filename


def generate(sync_db=False):
    # The HTML supplies the accessible headline; avoid duplicate text behind it.
    save_image(ASSETS / 'banners/hero_banner.png', '', '', '#e50914', size=(1440, 540))
    for key, (title, accent) in GAMES.items():
        save_image(ASSETS / 'games' / ('logo_' + key + '.png'), title,
                   'DEMO GAME COLLECTION', accent, size=(640, 360))
    if sync_db:
        from config.database import transaction
        from psycopg2.extras import RealDictCursor
        with transaction('ShopAdmin') as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT ma_nick,ma_game,thong_tin_chi_tiet '
                        'FROM quan_ly_shop.tai_khoan_game ORDER BY ma_nick')
            accounts = [dict(row) for row in cur.fetchall()]
            for account in accounts:
                url = ensure_product_image(account)
                cur.execute('UPDATE quan_ly_shop.tai_khoan_game SET anh_dinh_kem_url=%s '
                            'WHERE ma_nick=%s', (url, account['ma_nick']))
    else:
        accounts = json.loads((ROOT / 'data_files/sample_game_accounts.json').read_text(encoding='utf-8'))
        for account in accounts:
            ensure_product_image(account)
    return len(accounts)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync-db', action='store_true')
    args = parser.parse_args()
    print(f'Generated banner, 3 game logos, {generate(args.sync_db)} product images.')
