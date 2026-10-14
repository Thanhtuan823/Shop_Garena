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
