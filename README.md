# GarenaShop_DB — Fullstack MVC / PostgreSQL / 8 AI

Demo gaming shop dùng Python 3.12+, PostgreSQL 16/17, FastAPI và Vanilla JS.
SePay/thẻ cào là mô phỏng, không nhận tiền thật.

## Khởi động

```powershell
python -m pip install -r requirements.txt
# Sao chép .env.example thành .env và điền kết nối PostgreSQL.
python scripts/init_database.py --seed-demo
python app.py
```

Init tạo DB nếu chưa có, áp dụng `database/01..04`, seed và sinh banner/logo/thumbnail
nội bộ. Không tự chạy VACUUM FULL, backup/restore hoặc ghi đè ví khách cũ.
Cần tài khoản DB owner/superuser cho demo tạo role và SET ROLE.

Seed in mật khẩu admin/staff/user khi tạo lần đầu; lưu lại thông tin đó.
Có thể đặt `DEMO_ADMIN_PASSWORD`, `DEMO_STAFF_PASSWORD`, `DEMO_USER_PASSWORD`
trước khi seed. Chạy lại không đổi mật khẩu hay số dư hiện hữu.

- Client: http://127.0.0.1:8000/ hoặc `/index.html`.
- Staff: `/staff.html`; Admin: `/admin.html`; OpenAPI: `/docs`.
- Login tự chuyển theo role; logout dọn dữ liệu riêng tư và về trang chủ.
- Navbar chỉ hiện menu được phép: Guest/User không thấy Staff/Admin/API;
  Staff không thấy Admin/API. User đăng nhập trên Client cập nhật tại chỗ.
- Có thể đổi cổng bằng biến `PORT`.

## Cấu trúc

```text
config/       database.py (pool), auth.py (phiên và RBAC)
database/     01_init_tables.sql → 05_maintenance_vacuum.sql
controllers/  ETL, tám AI, event listener và shop_service.py
views/        index.html, staff.html, admin.html
  css/        common.css, client.css, staff.css, admin.css
  js/         auth.js, client.js, staff.js, admin.js
  assets/     banners/, games/, products/
scripts/      init_database.py, generate_product_images.py, check_ocr.py
data_files/   raw_khach_hang.csv, sample_game_accounts.json
tests/        test_database_business.py, test_role_and_ui.py,
              test_all_ai_modules.py, check_html_delivery.py
docs/         sáu tài liệu đánh số, SQL demo và kết quả kiểm thử
```

`staff.js` cung cấp editor kho chung; trang Admin nạp thêm `admin.js` cho
dashboard riêng. `auth.js` cung cấp phiên, API, toast/modal và các renderer
an toàn dùng chung. Không nhúng logic sự kiện hoặc CSS trong ba HTML.
API trả JSON; UI hiển thị card, badges, bảng và thanh đo thay vì JSON thô.

## Ảnh nội bộ và OCR

```powershell
# Chỉ sinh bộ ảnh từ dữ liệu mẫu, không sửa DB:
python scripts/generate_product_images.py
# Sinh ảnh cho tất cả nick hiện hữu và cập nhật URL ảnh local trong DB:
python scripts/generate_product_images.py --sync-db
python scripts/check_ocr.py
```

Ảnh Pillow là artwork minh họa, không phải screenshot thật hoặc logo chính
thức của game. OCR dùng EasyOCR thật; chọn file hoặc dán HTTPS domain nằm
trong `OCR_ALLOWED_HOSTS`. Thumbnail không tự đưa ngược vào OCR nền.
Model cache nằm ở `.venv/ocr_models/`; lần tải model đầu cần Internet.

Windows có lỗi c10.dll/MSVC có thể cài runtime app-local, không sửa DLL hệ thống:

```powershell
python -m pip install --target .venv/ocr_runtime msvc-runtime
```

## Kiểm thử

```powershell
python tests/test_database_business.py
python -m pip install --target .venv/qa playwright
python tests/test_role_and_ui.py
python tests/test_all_ai_modules.py
python tests/check_html_delivery.py
```

Suite nghiệp vụ gồm 12 nhóm, tạo/xóa fixture trong database `.env`; nên dùng
DB thử nghiệm và tắt listener ngoài suite. Suite role/UI và AI tự tạo DB tạm
rồi dọn trong finally. Role/UI cần Google Chrome (Windows mặc định) và Internet
cho ảnh OCR HTTPS công khai. Có thể đặt `CHROME_EXECUTABLE` cho Chrome ở vị trí
khác. Artifacts ở `tests/artifacts/` được gitignore; kết quả máy đọc ở
`docs/test_results/`. Không vô hiệu RLS hoặc sửa policy để làm test PASS.

## Tài liệu

1. [Đặc tả và role matrix](docs/01_SYSTEM_SPECIFICATION.md)
2. [Thiết kế CSDL, ERD, RLS và index](docs/02_DATABASE_DESIGN.md)
3. [Luồng ETL và tám AI](docs/03_AI_PIPELINE_GUIDE.md)
4. [REST API](docs/04_API_SPECIFICATION.md)
5. [Kịch bản live demo](docs/05_LIVE_DEMO_SCRIPT.md)
6. [Báo cáo nghiệm thu](docs/06_ACCEPTANCE_TEST_REPORT.md)

## Giới hạn demo

Finance dùng transaction/khóa dòng/idempotency; public view che credentials;
RLS dùng `app.current_user_id` theo transaction. Token lưu sessionStorage,
phiên trong bộ nhớ một process, mất khi restart. Ảnh QR SePay động vẫn lấy
từ dịch vụ ngoài; không được dùng để chuyển tiền thật.

AI4 là parser từ khóa; AI6 fuzzy matching cần xác minh; AI7 tính dead-tuple
ratio ước lượng, không đo bloat vật lý; AI8 chỉ đề xuất hoàn tiền, chưa tự
chuyển tiền. Range partitions hiện dành cho năm 2025/2026. Triển khai Internet
cần hoàn thiện session store, HTTPS, phân quyền service DB và webhook thật.
