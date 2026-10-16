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
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ShopGuest') THEN
        CREATE ROLE "ShopGuest" NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ShopAdmin') THEN
        CREATE ROLE "ShopAdmin" NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA quan_ly_shop TO "ShopGuest", "ShopAdmin";
GRANT USAGE ON SCHEMA ai_analytics TO "ShopAdmin";
GRANT ALL ON ALL TABLES IN SCHEMA quan_ly_shop, ai_analytics TO "ShopAdmin";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA quan_ly_shop, ai_analytics TO "ShopAdmin";
-- Authentication data remains accessible only to the trusted service login.
REVOKE ALL ON quan_ly_shop.app_principals FROM "ShopAdmin";

CREATE OR REPLACE VIEW quan_ly_shop.vw_catalog_nick
WITH (security_barrier = true) AS
SELECT nick.ma_nick, nick.ma_game, game.ten_game, nick.ma_ncc,
       nick.gia_ban, nick.trang_thai, nick.thong_tin_chi_tiet,
       nick.anh_dinh_kem_url, NULL::varchar(100) AS mat_khau_game,
       NULL::varchar(100) AS email_khoi_phuc
FROM quan_ly_shop.tai_khoan_game nick
JOIN quan_ly_shop.danh_muc_game game USING (ma_game)
WHERE nick.trang_thai != 'Khoa_tranh_chap';
GRANT SELECT ON quan_ly_shop.vw_catalog_nick, quan_ly_shop.danh_muc_game
TO "ShopGuest", "KhachHangRole", "NhanVienSale";

CREATE OR REPLACE VIEW quan_ly_shop.vw_lich_su_bien_dong_vi
WITH (security_barrier = true) AS
SELECT n.ma_giao_dich AS ma_gd, n.ma_kh, 'NAP_TIEN'::text AS loai_gd,
       n.phuong_thuc, n.so_tien, '+'::text AS chieu_bien_dong,
       n.trang_thai, n.ngay_tao, n.thong_tin_giao_dich AS chi_tiet
FROM quan_ly_shop.lich_su_nap_tien n
WHERE n.ma_kh = current_setting('app.current_user_id', true)
UNION ALL
SELECT d.ma_dh, d.ma_kh, 'MUA_NICK', 'SO_DU_VI', d.tong_tien, '-',
       'Thanh_cong', d.ngay_tao, jsonb_build_object('ma_nick', d.ma_nick)
FROM quan_ly_shop.don_hang d
WHERE d.ma_kh = current_setting('app.current_user_id', true);
CREATE OR REPLACE VIEW quan_ly_shop.vw_lich_su_nap_staff AS
SELECT ma_giao_dich, ma_kh, so_tien, phuong_thuc, trang_thai, ngay_tao
FROM quan_ly_shop.lich_su_nap_tien;
GRANT SELECT ON quan_ly_shop.vw_lich_su_bien_dong_vi TO "KhachHangRole";
GRANT SELECT ON quan_ly_shop.vw_lich_su_nap_staff TO "NhanVienSale";

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON quan_ly_shop.khach_hang
FROM "NhanVienSale";
REVOKE UPDATE (so_du_vi) ON quan_ly_shop.khach_hang FROM "NhanVienSale";
REVOKE UPDATE, DELETE, TRUNCATE ON quan_ly_shop.tai_khoan_game FROM "NhanVienSale";
-- Clear any historical sensitive column UPDATE grants as well.
REVOKE UPDATE (mat_khau_game, email_khoi_phuc, ma_nick, ma_game, ma_ncc)
ON quan_ly_shop.tai_khoan_game FROM "NhanVienSale";
GRANT INSERT ON quan_ly_shop.tai_khoan_game TO "NhanVienSale";
GRANT UPDATE (gia_ban, trang_thai, thong_tin_chi_tiet, anh_dinh_kem_url)
ON quan_ly_shop.tai_khoan_game TO "NhanVienSale";
-- Financial writes and order creation must go through the service transaction.
REVOKE INSERT ON quan_ly_shop.don_hang FROM "NhanVienSale";
COMMIT;
