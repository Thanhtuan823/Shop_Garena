-- PostgreSQL 16. Run after 02_views_and_rbac.sql as the table owner.
BEGIN;

ALTER TABLE quan_ly_shop.tai_khoan_game ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_khach_xem_mat_khau_nick_da_mua
ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_khach_xem_mat_khau_nick_da_mua
ON quan_ly_shop.tai_khoan_game
FOR SELECT TO "KhachHangRole"
USING (
    trang_thai != 'Khoa_tranh_chap'
    AND ma_nick IN (
            SELECT ma_nick FROM quan_ly_shop.don_hang
            WHERE ma_kh = current_setting('app.current_user_id', true)
        )
);

-- RLS otherwise denies every row to Sale despite its column grants.
DROP POLICY IF EXISTS policy_sale_xem_nick ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_sale_xem_nick ON quan_ly_shop.tai_khoan_game
FOR SELECT TO "NhanVienSale" USING (true);

CREATE INDEX IF NOT EXISTS idx_kh_sdt
ON quan_ly_shop.khach_hang USING btree (so_dien_thoai);

CREATE INDEX IF NOT EXISTS idx_nick_san_co
ON quan_ly_shop.tai_khoan_game USING btree (ma_nick, gia_ban)
WHERE trang_thai = 'Chua_ban';

CREATE INDEX IF NOT EXISTS idx_gin_thong_tin_nick
ON quan_ly_shop.tai_khoan_game USING gin (thong_tin_chi_tiet);

DROP POLICY IF EXISTS policy_sale_insert ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_sale_insert ON quan_ly_shop.tai_khoan_game
FOR INSERT TO "NhanVienSale" WITH CHECK (trang_thai = 'Chua_ban');
DROP POLICY IF EXISTS policy_sale_update ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_sale_update ON quan_ly_shop.tai_khoan_game
FOR UPDATE TO "NhanVienSale"
USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS policy_admin_all ON quan_ly_shop.tai_khoan_game;
CREATE POLICY policy_admin_all ON quan_ly_shop.tai_khoan_game
TO "ShopAdmin" USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_wishlist_kh ON quan_ly_shop.danh_sach_yeu_thich(ma_kh);
CREATE INDEX IF NOT EXISTS idx_cart_kh ON quan_ly_shop.gio_hang(ma_kh);
CREATE INDEX IF NOT EXISTS idx_nap_tien_kh ON quan_ly_shop.lich_su_nap_tien(ma_kh);
-- The RLS subquery must not expose other customers' order identifiers.
ALTER TABLE quan_ly_shop.don_hang ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS policy_order_customer ON quan_ly_shop.don_hang;
CREATE POLICY policy_order_customer ON quan_ly_shop.don_hang
FOR SELECT TO "KhachHangRole"
USING (ma_kh = current_setting('app.current_user_id', true));
DROP POLICY IF EXISTS policy_order_staff ON quan_ly_shop.don_hang;
CREATE POLICY policy_order_staff ON quan_ly_shop.don_hang
FOR SELECT TO "NhanVienSale" USING (true);
DROP POLICY IF EXISTS policy_order_admin ON quan_ly_shop.don_hang;
CREATE POLICY policy_order_admin ON quan_ly_shop.don_hang
TO "ShopAdmin" USING (true) WITH CHECK (true);
COMMIT;
