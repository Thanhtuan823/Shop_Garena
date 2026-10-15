Đặc tả kỹ thuật hoàn chỉnh đã được cập nhật trực tiếp vào ghi chú/tệp **`PROJECT_SPECIFICATION_FOR_CODEX.md`**, đồng thời bổ sung chi tiết:

* **Quyền CRUD của Admin:** Tạo, Sửa toàn bộ, Xóa (có kiểm tra ràng buộc `ON DELETE RESTRICT`).


* **Quyền CRUD của Staff:** Tạo nick mới (tích hợp AI 1 OCR), Sửa thông tin mở bán, **Cấm xóa** và **Cấm truy cập mật khẩu**.


* **Đặc tả 8 Phân hệ AI** và cấu trúc API/Views liên quan.



---

### 📄 Nội dung tệp đặc tả (Sao chép và lưu thành file `.md`):

```markdown
# 📘 PROJECT_SPECIFICATION_FOR_CODEX.md
# HỆ THỐNG GARENASHOP_DB FULLSTACK MVC TÍCH HỢP 8 PHÂN HỆ AI & POSTGRESQL NÂNG CAO

> **Chỉ dẫn cho Codex / AI Engineer:**
> Hãy đọc toàn bộ bản đặc tả kỹ thuật này để tiến hành sinh và cấu trúc mã nguồn cho dự án `GarenaShop_DB`. Toàn bộ các ràng buộc CSDL (ACID, CHECK, Regex, RLS, GIN/Partial Index, Triggers), logic API Backend (FastAPI), CRUD Acc Game theo Role, 8 phân hệ AI, và giao diện người dùng (4 Roles) phải được triển khai đồng bộ, chính xác theo đúng cấu trúc bên dưới.

---

## 1. TỔNG QUAN KIẾN TRÚC & PHÂN QUYỀN CRUD SẢN PHẨM (ROLES)
- **Hệ thống**: GarenaShop_DB
- **Mô hình**: Fullstack MVC kết hợp Event-Driven thời gian thực (`LISTEN / NOTIFY`).
- **Nền tảng công nghệ**:
  - **Database Engine (Model)**: PostgreSQL 16/17 (Relational, NoSQL `JSONB`, RLS, GIN & Partial Index, Range Partitioning).
  - **Backend Controller**: Python 3.12 + FastAPI + `psycopg2-binary` (Connection Pool, REST API, Logging Terminal).
  - **Frontend (View)**: Single-Page Apps (HTML5, Vanilla JS, CSS3).
- **Phân định quyền CRUD Sản phẩm Acc Game (`tai_khoan_game`):**
  - **Admin**: Toàn quyền `CREATE` (Thêm), `READ` (Xem), `UPDATE` (Sửa toàn bộ trường), `DELETE` (Xóa nick chưa phát sinh đơn hàng, nếu đã có đơn thì chặn bởi `ON DELETE RESTRICT`).
  - **Staff (`NhanVienSale`)**: Có quyền `CREATE` (Nhập nick mới có AI 1 OCR hỗ trợ), `READ` (Xem kho nick), `UPDATE` (Sửa giá bán, trạng thái, ảnh... **nhưng bị cấm sửa `mat_khau_game`**). **Bị cấm quyền `DELETE` hoàn toàn**.
  - **User**: Xem nick mở bán (`Chua_ban`), Mua nick, Wishlist, Giỏ hàng giữ chỗ 15p, Nạp tiền (SePay / Thẻ cào mock), Xem lịch sử biến động số dư, **Xem mật khẩu nick đã mua qua RLS**.
  - **Guest**: Xem danh sách nick mở bán, tra cứu qua Chatbot AI 4 NL2SQL.

---

## 2. CẤU TRÚC THƯ MỤC CHUẨN MÃ NGUỒN
```text
GarenaShop_MVC_Project/
├── app.py                             # Máy chủ Backend trung tâm (FastAPI, API Routers, Logging Terminal)
├── config/
│   ├── __init__.py
│   └── db_connection.py               # Kết nối PostgreSQL SimpleConnectionPool (psycopg2)
├── controllers/                       # Tầng Controller: 8 Phân hệ AI, ETL và Event Listener
│   ├── __init__.py
│   ├── etl_cleaner_controller.py      # Làm sạch CSV, lọc lỗi Regex SĐT, in hoa tên khách
│   ├── ai1_vision_ocr_controller.py   # AI 1: Vision OCR bóc tách ảnh nick game vào JSONB
│   ├── ai2_pricing_controller.py      # AI 2: Dynamic Pricing định giá & hạ giá tồn kho > 30 ngày
│   ├── ai3_fraud_guard_controller.py  # AI 3: Fraud Guard phát hiện gian lận & kích hoạt RLS phong tỏa
│   ├── ai4_nl2sql_chatbot_controller.py # AI 4: NL2SQL Chatbot dịch tiếng Việt -> SQL JSONB (@>)
│   ├── ai5_marketing_controller.py    # AI 5: Phân tích Churn Risk bảng phân mảnh & phát Voucher
│   ├── ai6_reconcile_controller.py    # AI 6: Copilot hỗ trợ Staff gỡ nghẽn đối soát nạp tiền SePay
│   ├── ai7_dba_optimizer_controller.py# AI 7: Auto-DBA chẩn đoán Dead Tuples, Table Bloat, VACUUM
│   ├── ai8_dispute_controller.py      # AI 8: Trọng tài thẩm định khiếu nại tranh chấp tài khoản
│   └── realtime_notify_listener.py    # Lắng nghe sự kiện ngầm LISTEN kenh_ai_garena
├── models/                            # Tầng Model: Toàn bộ kịch bản DDL/DCL/Security SQL
│   ├── 01_ddl_init_db.sql             # Khởi tạo 9 bảng core, ràng buộc CHECK, Regex, FK RESTRICT
│   ├── 02_views_and_rbac.sql          # Views báo cáo, View vắn tắt cho Staff, phân quyền GRANT/REVOKE
│   ├── 03_rls_and_indexes.sql         # Security Policy RLS, Partial Index & GIN Index
│   ├── 04_partition_and_trigger.sql   # Range Partitioning don_hang_lich_su, Trigger NOTIFY
│   └── 05_maintenance_backup.sql      # Kịch bản VACUUM FULL, ANALYZE, bảo trì CSDL
├── views/                             # Tầng View: Giao diện người dùng
│   ├── index.html                     # Giao diện Client: Kho nick, Wishlist, Cart 15p, Nạp tiền, Chatbot
│   ├── staff.html                     # Bàn làm việc Staff: Quản lý kho, Thêm/Sửa nick, AI 1 OCR, Đối soát vắn tắt
│   └── admin.html                     # Bảng điều khiển Admin: CRUD Acc Game, Điều khiển 8 AI, Sức khỏe CSDL
├── data_files/
│   ├── raw_khach_hang.csv             # Dữ liệu mẫu chứa dòng hợp lệ và vi phạm để test ETL
│   └── raw_tai_khoan_game.json
├── tests/
│   └── run_full_demo_test.py          # Kịch bản kiểm thử tự động toàn diện (12/12 PASS)
├── requirements.txt
└── .env

```

---

## 3. THIẾT KẾ CƠ SỞ DỮ LIỆU POSTGRESQL (MODEL LAYER)

### 3.1. DDL Khởi tạo 9 Bảng Nghiệp vụ Core (`quan_ly_shop`)

```sql
CREATE SCHEMA IF NOT EXISTS quan_ly_shop;
CREATE SCHEMA IF NOT EXISTS ai_analytics;

-- 1. Danh mục game
CREATE TABLE IF NOT EXISTS quan_ly_shop.danh_muc_game (
    ma_game VARCHAR(10) PRIMARY KEY,
    ten_game VARCHAR(100) NOT NULL UNIQUE
);

-- 2. Nhà cung cấp / Đại lý
CREATE TABLE IF NOT EXISTS quan_ly_shop.nha_cung_cap (
    ma_ncc VARCHAR(10) PRIMARY KEY,
    ten_ncc VARCHAR(150) NOT NULL,
    so_dien_thoai VARCHAR(15) UNIQUE CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
    email VARCHAR(100) UNIQUE
);

-- 3. Nhân viên (Bảo mật mức cột)
CREATE TABLE IF NOT EXISTS quan_ly_shop.nhan_vien (
    ma_nv VARCHAR(20) PRIMARY KEY,
    ho_ten VARCHAR(100) NOT NULL,
    phong_ban VARCHAR(50),
    luong NUMERIC(15, 2) CHECK (luong > 0),
    mat_khau VARCHAR(100) NOT NULL
);

-- 4. Khách hàng
CREATE TABLE IF NOT EXISTS quan_ly_shop.khach_hang (
    ma_kh VARCHAR(10) PRIMARY KEY,
    ho_ten VARCHAR(100) NOT NULL,
    so_dien_thoai VARCHAR(15) UNIQUE CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
    so_du_vi NUMERIC(15, 2) DEFAULT 0 CHECK (so_du_vi >= 0),
    ngay_tao DATE DEFAULT CURRENT_DATE
);

-- 5. Kho tài khoản game (NoSQL JSONB)
CREATE TABLE IF NOT EXISTS quan_ly_shop.tai_khoan_game (
    ma_nick VARCHAR(15) PRIMARY KEY,
    ma_game VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.danh_muc_game(ma_game) ON DELETE RESTRICT,
    ma_ncc VARCHAR(10) REFERENCES quan_ly_shop.nha_cung_cap(ma_ncc) ON DELETE SET NULL,
    gia_ban NUMERIC(15, 2) CHECK (gia_ban > 0),
    trang_thai VARCHAR(20) DEFAULT 'Chua_ban' CHECK (trang_thai IN ('Chua_ban', 'Dang_giu_cho', 'Da_ban', 'Khoa_tranh_chap')),
    thong_tin_chi_tiet JSONB DEFAULT '{}'::jsonb,
    mat_khau_game VARCHAR(100) NOT NULL,
    email_khoi_phuc VARCHAR(100),
    anh_dinh_kem_url VARCHAR(255)
);

-- 6. Đơn hàng (Khóa ngoại chặn xóa cha)
CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang (
    ma_dh VARCHAR(15) PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang(ma_kh) ON DELETE RESTRICT,
    ma_nick VARCHAR(15) NOT NULL UNIQUE REFERENCES quan_ly_shop.tai_khoan_game(ma_nick) ON DELETE RESTRICT,
    ma_nv VARCHAR(20) REFERENCES quan_ly_shop.nhan_vien(ma_nv) ON DELETE SET NULL,
    ngay_tao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tong_tien NUMERIC(15, 2) CHECK (tong_tien > 0)
);

-- 7. Danh sách yêu thích (Wishlist N-N)
CREATE TABLE IF NOT EXISTS quan_ly_shop.danh_sach_yeu_thich (
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang(ma_kh) ON DELETE CASCADE,
    ma_nick VARCHAR(15) NOT NULL REFERENCES quan_ly_shop.tai_khoan_game(ma_nick) ON DELETE CASCADE,
    ngay_them TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ma_kh, ma_nick)
);

-- 8. Giỏ hàng giữ chỗ 15 phút
CREATE TABLE IF NOT EXISTS quan_ly_shop.gio_hang (
    ma_gio_hang SERIAL PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang(ma_kh) ON DELETE CASCADE,
    ma_nick VARCHAR(15) NOT NULL UNIQUE REFERENCES quan_ly_shop.tai_khoan_game(ma_nick) ON DELETE CASCADE,
    thoi_gian_tao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    han_giu_cho TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '15 minutes')
);

-- 9. Lịch sử nạp tiền (SePay VietQR & Thẻ cào)
CREATE TABLE IF NOT EXISTS quan_ly_shop.lich_su_nap_tien (
    ma_giao_dich VARCHAR(40) PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang(ma_kh) ON DELETE RESTRICT,
    so_tien NUMERIC(15, 2) NOT NULL CHECK (so_tien > 0),
    phuong_thuc VARCHAR(20) NOT NULL CHECK (phuong_thuc IN ('SEPAY_QR', 'THE_CAO')),
    thong_tin_giao_dich JSONB DEFAULT '{}'::jsonb,
    trang_thai VARCHAR(20) DEFAULT 'Thanh_cong',
    ngay_tao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

### 3.2. Bảng Phân mảnh & Schema Phân tích AI (`ai_analytics`)

```sql
-- Range Partitioning theo năm
CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_lich_su (
    ma_dh VARCHAR(15),
    ma_kh VARCHAR(10),
    ma_nick VARCHAR(15),
    ngay_tao TIMESTAMP NOT NULL,
    tong_tien NUMERIC(15, 2)
) PARTITION BY RANGE (ngay_tao);

CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_2025 PARTITION OF quan_ly_shop.don_hang_lich_su
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_2026 PARTITION OF quan_ly_shop.don_hang_lich_su
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- Log OCR
CREATE TABLE IF NOT EXISTS ai_analytics.log_ai_ocr (
    id SERIAL PRIMARY KEY,
    ma_nick VARCHAR(15),
    url_anh VARCHAR(255),
    ket_qua_raw_json JSONB,
    confidence_score NUMERIC(5, 2),
    ngay_tao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Churn Marketing
CREATE TABLE IF NOT EXISTS ai_analytics.khach_hang_marketing (
    ma_kh VARCHAR(10),
    churn_risk_score NUMERIC(5, 2),
    ma_voucher_tang VARCHAR(50),
    ngay_tao DATE DEFAULT CURRENT_DATE
);

```

### 3.3. Views, Indexes & Bảo mật RBAC / RLS

```sql
-- Indexes
CREATE INDEX IF NOT EXISTS idx_nick_san_co 
ON quan_ly_shop.tai_khoan_game(ma_nick, gia_ban) 
WHERE trang_thai = 'Chua_ban';

CREATE INDEX IF NOT EXISTS idx_gin_thong_tin_nick 
ON quan_ly_shop.tai_khoan_game USING GIN (thong_tin_chi_tiet);

CREATE INDEX IF NOT EXISTS idx_wishlist_kh ON quan_ly_shop.danh_sach_yeu_thich(ma_kh);
CREATE INDEX IF NOT EXISTS idx_cart_kh ON quan_ly_shop.gio_hang(ma_kh);
CREATE INDEX IF NOT EXISTS idx_nap_tien_kh ON quan_ly_shop.lich_su_nap_tien(ma_kh);

-- View hợp nhất biến động số dư cho User
CREATE OR REPLACE VIEW quan_ly_shop.vw_lich_su_bien_dong_vi AS
SELECT 
    n.ma_giao_dich AS ma_gd,
    n.ma_kh,
    'NAP_TIEN' AS loai_gd,
    n.phuong_thuc,
    n.so_tien,
    '+' AS chieu_bien_dong,
    n.trang_thai,
    n.ngay_tao,
    n.thong_tin_giao_dich AS chi_tiet
FROM quan_ly_shop.lich_su_nap_tien n
UNION ALL
SELECT 
    d.ma_dh AS ma_gd,
    d.ma_kh,
    'MUA_NICK' AS loai_gd,
    'SO_DU_VI' AS phuong_thuc,
    d.tong_tien AS so_tien,
    '-' AS chieu_bien_dong,
    'Thanh_cong' AS trang_thai,
    d.ngay_tao,
    jsonb_build_object('ma_nick', d.ma_nick, 'ma_nv_duyet', COALESCE(d.ma_nv, 'AUTO')) AS chi_tiet
FROM quan_ly_shop.don_hang d;

-- View vắn tắt cho Staff (Ẩn thông tin nhạy cảm)
CREATE OR REPLACE VIEW quan_ly_shop.vw_lich_su_nap_staff AS
SELECT ma_giao_dich, ma_kh, so_tien, phuong_thuc, trang_thai, ngay_tao
FROM quan_ly_shop.lich_su_nap_tien;

-- RBAC
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'KhachHangRole') THEN
        CREATE ROLE "KhachHangRole";
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'NhanVienSale') THEN
        CREATE ROLE "NhanVienSale";
    END IF;
END $$;

GRANT USAGE ON SCHEMA quan_ly_shop TO "NhanVienSale", "KhachHangRole";
GRANT SELECT ON quan_ly_shop.vw_lich_su_nap_staff TO "NhanVienSale";

-- Staff: Được INSERT nick mới, UPDATE thuộc tính public, nhưng CẤM DELETE và CẤM xem mat_khau_game
GRANT INSERT ON quan_ly_shop.tai_khoan_game TO "NhanVienSale";
GRANT UPDATE (gia_ban, trang_thai, thong_tin_chi_tiet, anh_dinh_kem_url) ON quan_ly_shop.tai_khoan_game TO "NhanVienSale";
REVOKE DELETE ON quan_ly_shop.tai_khoan_game FROM "NhanVienSale";
REVOKE SELECT (luong, mat_khau) ON quan_ly_shop.nhan_vien FROM "NhanVienSale";
REVOKE UPDATE (so_du_vi) ON quan_ly_shop.khach_hang FROM "NhanVienSale";

-- Row-Level Security (RLS)
ALTER TABLE quan_ly_shop.tai_khoan_game ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_khach_xem_mat_khau_nick_da_mua ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_khach_xem_mat_khau_nick_da_mua
ON quan_ly_shop.tai_khoan_game
FOR SELECT
TO "KhachHangRole"
USING (
    trang_thai != 'Khoa_tranh_chap' 
    AND (
        trang_thai = 'Chua_ban' 
        OR ma_nick IN (
            SELECT ma_nick FROM quan_ly_shop.don_hang 
            WHERE ma_kh = current_setting('app.current_user_id', true)
        )
    )
);

-- Trigger Event-Driven NOTIFY
CREATE OR REPLACE FUNCTION quan_ly_shop.fn_notify_ai_nick_moi()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('kenh_ai_garena', json_build_object(
        'event', 'NEW_NICK_INSERTED',
        'ma_nick', NEW.ma_nick,
        'ma_game', NEW.ma_game,
        'anh_url', NEW.anh_dinh_kem_url
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_ai_nick_moi ON quan_ly_shop.tai_khoan_game;
CREATE TRIGGER trg_notify_ai_nick_moi
AFTER INSERT ON quan_ly_shop.tai_khoan_game
FOR EACH ROW
EXECUTE FUNCTION quan_ly_shop.fn_notify_ai_nick_moi();

```

---

## 4. CHI TIẾT 8 PHÂN HỆ AI (CONTROLLER MODULES)

1. **Python ETL Pipeline (`etl_cleaner_controller.py`):** Lọc bỏ dòng CSV có SĐT sai Regex `^0[0-9]{9}$` hoặc `so_du_vi < 0`, tự động viết in hoa họ tên khách hàng trước khi nạp vào CSDL.
2. **AI 1: Vision OCR Engine (`ai1_vision_ocr_controller.py`):** Dùng EasyOCR nhận diện từ khóa (Rank, Tướng, Skin) từ link ảnh, đóng gói JSONB nạp vào `thong_tin_chi_tiet` và ghi nhật ký vào `log_ai_ocr`.
3. **AI 2: Dynamic Pricing (`ai2_pricing_controller.py`):** Quét các nick `Chua_ban` tồn kho quá 30 ngày, tự động giảm 5% giá bán, làm tròn đến hàng nghìn (sàn tối thiểu 50.000 VNĐ).
4. **AI 3: Fraud Guard (`ai3_fraud_guard_controller.py`):** Phát hiện nguy cơ lừa đảo / back nick, cập nhật `trang_thai = 'Khoa_tranh_chap'`, kích hoạt RLS phong tỏa mật khẩu ngay tức thì.
5. **AI 4: Matchmaker Chatbot NL2SQL (`ai4_nl2sql_chatbot_controller.py`):** Dịch câu thoại tiếng Việt tự nhiên thành câu lệnh SQL JSONB chứa toán tử `@>`, chạy trực tiếp trên `GIN Index` dưới 1ms.
6. **AI 5: Smart Marketing (`ai5_marketing_controller.py`):** Quét bảng phân mảnh `don_hang_lich_su`, tìm khách hàng > 60 ngày chưa mua và phát sinh mã voucher giảm 20% vào `khach_hang_marketing`.
7. **AI 6: CSKH & Reconcile Copilot (`ai6_reconcile_controller.py` - Cho Staff):** Bắt cặp Fuzzy Matching đối soát giao dịch chuyển khoản sai cú pháp, tạo câu phản hồi mẫu cho CSKH và hỗ trợ kích hoạt khớp lệnh tự động.
8. **AI 7: Auto-DBA Optimizer (`ai7_dba_optimizer_controller.py` - Cho Admin):** Đọc thống kê `pg_stat_user_tables`, phát hiện Table Bloat / Dead Tuples do MVCC sinh ra và đề xuất/chạy `VACUUM ANALYZE`.
9. **AI 8: Dispute Arbiter (`ai8_dispute_controller.py` - Cho Admin/Staff):** Thẩm định lịch sử khiếu nại, tính điểm `risk_score` (0-100%), nếu > 80% thì đề xuất khóa tài khoản người bán và tạo lệnh hoàn tiền ví 100% cho người mua.

---

## 5. MÔ PHỎNG NẠP TIỀN SEPAY & THẺ CÀO (RULE CHUẨN DEMO)

* **Cổng SePay QR:** Tạo mã VietQR động qua link `https://qr.sepay.vn/img?acc=0987654321&bank=MBBank&amount={SO_TIEN}&des=NAP%20{MA_KH}`. Có nút bấm giả lập Webhook ghi nhận giao dịch ACID.
* **Cổng Thẻ Cào Game:**
* Quy tắc Số Seri: Bắt buộc bắt đầu bằng `#GARENA*` + 8 chữ số ngẫu nhiên bất kỳ (VD: `#GARENA*98231456`).
* Quy tắc Mã Thẻ: Bắt buộc bắt đầu bằng `$CARD&` + 10 chữ số ngẫu nhiên bất kỳ (VD: `$CARD&1234567890`).
* Nhập đúng quy tắc tiền tố và đủ độ dài số thì nạp tiền ảo thành công theo đúng mệnh giá đã chọn.


* **Lịch sử Giao dịch:** Nằm trong mục Hồ sơ bên cạnh Số dư tài khoản, hiển thị dạng danh sách (List View), có bộ lọc (*Tất cả*, *Nạp tiền [+]*, *Mua nick [-]*) và nút *Chi tiết* mở biên lai giao dịch.

---

## 6. BACKEND SERVER CONTROLLER (`app.py`)

Mã nguồn `app.py` phải thực thi đầy đủ:

* Cấu hình logging `StreamHandler(sys.stdout)` in mọi thao tác người dùng ra Terminal theo mẫu:
`2026-10-15 19:00:00 [INFO] [ADMIN_ACTION] Kích hoạt luồng Python ETL...`
* **CRUD Acc Game Endpoints:**
* `POST /api/accounts/create` (Admin & Staff đều có quyền thêm)
* `PUT /api/accounts/{ma_nick}/update` (Admin sửa toàn bộ; Staff sửa thông tin mở bán, không sửa pass)
* `DELETE /api/admin/accounts/{ma_nick}/delete` (Độc quyền Admin; bắt lỗi RESTRICT nếu đã có đơn hàng)


* **Nghiệp vụ Client & AI Endpoints:**
* `POST /api/user/deposit/sepay`
* `POST /api/user/deposit/card`
* `GET /api/user/profile/{ma_kh}`
* `GET /api/user/transactions/{ma_kh}`
* `POST /api/user/cart/add` (giữ chỗ 15 phút, đổi trạng thái `Dang_giu_cho`)
* `POST /api/user/cart/checkout` (Giao dịch ACID trừ tiền ví, tạo đơn hàng, đổi `Da_ban`)
* `GET /api/accounts/{ma_nick}/credentials` (Kiểm tra RLS)
* `POST /api/chat/nl2sql` (AI 4)
* `GET /api/staff/transactions` (Xem vắn tắt, kết nối `vw_lich_su_nap_staff`)
* `POST /api/staff/recheck-sepay`
* `POST /api/staff/ai6-reconcile-assistant` (AI 6)
* `POST /api/admin/run-etl`
* `POST /api/admin/run-pricing` (AI 2)
* `POST /api/admin/lock-fraud/{ma_nick}` (AI 3)
* `POST /api/admin/run-marketing` (AI 5)
* `GET /api/admin/ai7-diagnostics` (AI 7)
* `POST /api/admin/ai8-evaluate-dispute` (AI 8)


* Static files mounting: `app.mount("/", StaticFiles(directory="views", html=True), name="views")`.

---

## 7. GIAO DIỆN NGƯỜI DÙNG (VIEWS)

* **`views/index.html`:** Khách hàng (Header có nút `+ Nạp tiền`, Menu hồ sơ hiển thị `Số dư ví` & `Lịch sử giao dịch`, Giỏ hàng giữ chỗ 15p, Nút Xem Mật Khẩu qua RLS, Widget AI 4 Chatbot).
* **`views/staff.html`:** Nhân viên (Form tạo/sửa nick kèm nút bấm chạy AI 1 OCR, Bảng tra cứu vắn tắt đối soát nạp tiền, Khung hỗ trợ AI 6 Reconcile).
* **`views/admin.html`:** Quản trị viên (Bảng quản trị CRUD nick game đầy đủ chức năng Thêm/Sửa/Xóa, Admin AI Control Center gồm các thẻ kích hoạt ETL, AI 1, 2, 3, 5, 7, 8 và bảo trì VACUUM CSDL).

---

## 8. BỘ KIỂM THỬ TỰ ĐỘNG CHỐT HẠ (`tests/run_full_demo_test.py`)

Mọi chức năng phải vượt qua bộ kiểm thử tự động đạt kết quả **12/12 PASS (0 FAIL)**:

1. Regex SĐT (`SQLSTATE 23514`)
2. Giá âm (`SQLSTATE 23514`)
3. FK RESTRICT (`SQLSTATE 23503`)
4. Sale cấm đọc lương (`SQLSTATE 42501`)
5. Sale cấm đọc pass nick (`SQLSTATE 42501`)
6. RLS nick đã mua
7. Fraud Guard phong tỏa mật khẩu
8. Partial Index (`< 1ms`)
9. AI 4 NL2SQL & GIN Index (`@>`)
10. LISTEN / NOTIFY Socket Realtime
11. Giỏ hàng giữ chỗ 15 phút (Race Condition Prevention)
12. Giao dịch nạp tiền SePay & Thẻ cào ACID

