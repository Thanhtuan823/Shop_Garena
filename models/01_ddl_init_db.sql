-- ============================================================
-- SCRIPT KHỞI TẠO HỆ THỐNG CSDL GARENASHOP_DB (PostgreSQL 16)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS quan_ly_shop;
CREATE SCHEMA IF NOT EXISTS ai_analytics;

-- 1. Bảng Khách hàng
CREATE TABLE IF NOT EXISTS quan_ly_shop.khach_hang (
    ma_kh VARCHAR(10) PRIMARY KEY,
    ho_ten VARCHAR(100) NOT NULL,
    so_dien_thoai VARCHAR(15) UNIQUE CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
    so_du_vi NUMERIC(15, 2) DEFAULT 0 CHECK (so_du_vi >= 0),
    ngay_tao DATE DEFAULT CURRENT_DATE
);

-- 2. Bảng Danh mục Game
CREATE TABLE IF NOT EXISTS quan_ly_shop.danh_muc_game (
    ma_game VARCHAR(10) PRIMARY KEY,
    ten_game VARCHAR(100) NOT NULL UNIQUE
);

-- 3. Bảng Nhà cung cấp
CREATE TABLE IF NOT EXISTS quan_ly_shop.nha_cung_cap (
    ma_ncc VARCHAR(10) PRIMARY KEY,
    ten_ncc VARCHAR(150) NOT NULL,
    so_dien_thoai VARCHAR(15) UNIQUE CHECK (so_dien_thoai ~ '^0[0-9]{9}$'),
    email VARCHAR(100) UNIQUE
);

-- 4. Bảng Nhân viên
CREATE TABLE IF NOT EXISTS quan_ly_shop.nhan_vien (
    ma_nv VARCHAR(20) PRIMARY KEY,
    ho_ten VARCHAR(100) NOT NULL,
    phong_ban VARCHAR(50),
    luong NUMERIC(15, 2) CHECK (luong > 0),
    mat_khau VARCHAR(50) NOT NULL
);

-- 5. Bảng Tài khoản Game (NoSQL JSONB)
CREATE TABLE IF NOT EXISTS quan_ly_shop.tai_khoan_game (
    ma_nick VARCHAR(15) PRIMARY KEY,
    ma_game VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.danh_muc_game(ma_game) ON DELETE RESTRICT,
    ma_ncc VARCHAR(10) REFERENCES quan_ly_shop.nha_cung_cap(ma_ncc) ON DELETE SET NULL,
    gia_ban NUMERIC(15, 2) CHECK (gia_ban > 0),
    trang_thai VARCHAR(20) DEFAULT 'Chua_ban' CHECK (trang_thai IN ('Chua_ban', 'Dang_giu_cho', 'Da_ban', 'Khoa_tranh_chap')),
    thong_tin_chi_tiet JSONB,
    mat_khau_game VARCHAR(100) NOT NULL,
    email_khoi_phuc VARCHAR(100),
    anh_dinh_kem_url VARCHAR(255)
);

-- 6. Bảng Đơn hàng
CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang (
    ma_dh VARCHAR(15) PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang(ma_kh) ON DELETE RESTRICT,
    ma_nick VARCHAR(15) NOT NULL UNIQUE REFERENCES quan_ly_shop.tai_khoan_game(ma_nick) ON DELETE RESTRICT,
    ma_nv VARCHAR(20) REFERENCES quan_ly_shop.nhan_vien(ma_nv) ON DELETE SET NULL,
    ngay_tao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tong_tien NUMERIC(15, 2) CHECK (tong_tien > 0)
);

-- 7. Bảng Nhật ký AI OCR
CREATE TABLE IF NOT EXISTS ai_analytics.log_ai_ocr (
    id SERIAL PRIMARY KEY,
    ma_nick VARCHAR(15),
    url_anh VARCHAR(255),
    ket_qua_raw_json JSONB,
    confidence_score NUMERIC(3, 2),
    thoi_gian TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE quan_ly_shop.khach_hang
ADD COLUMN IF NOT EXISTS ngay_cap_nhat TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS quan_ly_shop.danh_sach_yeu_thich (
    ma_kh VARCHAR(10) REFERENCES quan_ly_shop.khach_hang ON DELETE CASCADE,
    ma_nick VARCHAR(15) REFERENCES quan_ly_shop.tai_khoan_game ON DELETE CASCADE,
    ngay_them TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ma_kh, ma_nick)
);
CREATE TABLE IF NOT EXISTS quan_ly_shop.gio_hang (
    ma_gio_hang SERIAL PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang ON DELETE CASCADE,
    ma_nick VARCHAR(15) NOT NULL UNIQUE REFERENCES quan_ly_shop.tai_khoan_game ON DELETE CASCADE,
    thoi_gian_tao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    han_giu_cho TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '15 minutes')
);
CREATE TABLE IF NOT EXISTS quan_ly_shop.lich_su_nap_tien (
    ma_giao_dich VARCHAR(40) PRIMARY KEY,
    ma_kh VARCHAR(10) NOT NULL REFERENCES quan_ly_shop.khach_hang ON DELETE RESTRICT,
    so_tien NUMERIC(15,2) NOT NULL CHECK (so_tien > 0),
    phuong_thuc VARCHAR(20) NOT NULL CHECK (phuong_thuc IN ('SEPAY_QR', 'THE_CAO')),
    thong_tin_giao_dich JSONB NOT NULL DEFAULT '{}'::jsonb,
    trang_thai VARCHAR(20) NOT NULL DEFAULT 'Thanh_cong'
        CHECK (trang_thai IN ('Cho_duyet','Thanh_cong','Tu_choi')),
    ngay_tao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- A redeemed mock card can never credit two customers/transactions.
CREATE UNIQUE INDEX IF NOT EXISTS idx_redeemed_card
ON quan_ly_shop.lich_su_nap_tien ((thong_tin_giao_dich->>'card_fingerprint'))
WHERE phuong_thuc = 'THE_CAO';

CREATE TABLE IF NOT EXISTS ai_analytics.khach_hang_marketing (
    ma_kh VARCHAR(10) PRIMARY KEY REFERENCES quan_ly_shop.khach_hang ON DELETE CASCADE,
    churn_risk_score NUMERIC(5,2) CHECK (churn_risk_score BETWEEN 0 AND 100),
    ma_voucher_tang VARCHAR(50),
    ngay_tao DATE DEFAULT CURRENT_DATE
);
-- Local demo authentication: PBKDF2 password hashes, never plaintext passwords.
CREATE TABLE IF NOT EXISTS quan_ly_shop.app_principals (
    username VARCHAR(50) PRIMARY KEY,
    password_hash TEXT NOT NULL,
    app_role VARCHAR(10) NOT NULL CHECK (app_role IN ('admin','staff','user')),
    ma_kh VARCHAR(10) REFERENCES quan_ly_shop.khach_hang ON DELETE RESTRICT,
    CHECK ((app_role = 'user') = (ma_kh IS NOT NULL))
);
