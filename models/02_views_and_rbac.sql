-- PostgreSQL 16. Run after 01_ddl_init_db.sql as the object owner
-- with CREATEROLE privilege. Quoted role names preserve the requested case.
BEGIN;

CREATE OR REPLACE VIEW quan_ly_shop.vw_bao_cao_doanh_thu AS
SELECT dh.ma_dh, kh.ho_ten, game.ten_game, dh.tong_tien
FROM quan_ly_shop.don_hang AS dh
JOIN quan_ly_shop.khach_hang AS kh ON kh.ma_kh = dh.ma_kh
JOIN quan_ly_shop.tai_khoan_game AS nick ON nick.ma_nick = dh.ma_nick
JOIN quan_ly_shop.danh_muc_game AS game ON game.ma_game = nick.ma_game;

-- Only public catalog fields are stored in the homepage snapshot.
CREATE MATERIALIZED VIEW IF NOT EXISTS quan_ly_shop.mv_nick_hot_trang_chu AS
SELECT ma_nick, ma_game, ma_ncc, gia_ban, trang_thai,
       thong_tin_chi_tiet, anh_dinh_kem_url
FROM quan_ly_shop.tai_khoan_game
WHERE trang_thai = 'Chua_ban' AND gia_ban <= 300000
WITH DATA;

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'BanGiamDoc') THEN
        CREATE ROLE "BanGiamDoc" NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'NhanVienSale') THEN
        CREATE ROLE "NhanVienSale" NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'KhachHangRole') THEN
        CREATE ROLE "KhachHangRole" NOLOGIN;
    END IF;
END;
$roles$;

GRANT USAGE ON SCHEMA quan_ly_shop
TO "BanGiamDoc", "NhanVienSale", "KhachHangRole";
GRANT SELECT ON quan_ly_shop.vw_bao_cao_doanh_thu TO "BanGiamDoc";
GRANT SELECT ON quan_ly_shop.mv_nick_hot_trang_chu TO "KhachHangRole";

GRANT SELECT, INSERT ON quan_ly_shop.don_hang TO "NhanVienSale";
REVOKE DELETE ON quan_ly_shop.don_hang FROM "NhanVienSale";

-- Remove direct table-level SELECT before granting an explicit column list.
REVOKE SELECT ON quan_ly_shop.nhan_vien FROM "NhanVienSale";
REVOKE SELECT (luong, mat_khau) ON quan_ly_shop.nhan_vien FROM "NhanVienSale";
GRANT SELECT (ma_nv, ho_ten, phong_ban)
ON quan_ly_shop.nhan_vien TO "NhanVienSale";

REVOKE SELECT ON quan_ly_shop.tai_khoan_game FROM "NhanVienSale";
REVOKE SELECT (mat_khau_game, email_khoi_phuc)
ON quan_ly_shop.tai_khoan_game FROM "NhanVienSale";
GRANT SELECT (ma_nick, ma_game, ma_ncc, gia_ban, trang_thai,
              thong_tin_chi_tiet, anh_dinh_kem_url)
ON quan_ly_shop.tai_khoan_game TO "NhanVienSale";

-- Required by the customer policy's subquery and credential access.
GRANT SELECT (ma_nick, ma_kh) ON quan_ly_shop.don_hang TO "KhachHangRole";
GRANT SELECT ON quan_ly_shop.tai_khoan_game TO "KhachHangRole";
-- Keep group memberships separate: inherited privileges are additive.
COMMIT;
