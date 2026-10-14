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
    AND (
        trang_thai = 'Chua_ban'
        OR ma_nick IN (
            SELECT ma_nick FROM quan_ly_shop.don_hang
            WHERE ma_kh = current_user
        )
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

COMMIT;
