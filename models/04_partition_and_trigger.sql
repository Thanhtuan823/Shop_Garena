-- PostgreSQL 16. Run after 01_ddl_init_db.sql as the object owner.
BEGIN;

CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_lich_su (
    ma_dh varchar(15) NOT NULL,
    ma_kh varchar(10) NOT NULL,
    ma_nick varchar(15) NOT NULL,
    ngay_tao timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tong_tien numeric(15, 2) CHECK (tong_tien > 0),
    PRIMARY KEY (ma_dh, ngay_tao)
) PARTITION BY RANGE (ngay_tao);

CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_2025
PARTITION OF quan_ly_shop.don_hang_lich_su
FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE IF NOT EXISTS quan_ly_shop.don_hang_2026
PARTITION OF quan_ly_shop.don_hang_lich_su
FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- Call explicitly or from a scheduler. Each call discounts eligible rows again.
-- Invalid/missing dates are skipped; the minimum price respects gia_ban > 0.
CREATE OR REPLACE FUNCTION quan_ly_shop.fn_giam_gia_nick_ton_kho()
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, quan_ly_shop
AS $function$
BEGIN
    UPDATE quan_ly_shop.tai_khoan_game
    SET gia_ban = greatest(50000::numeric, round(gia_ban * 0.95 / 1000) * 1000)
    WHERE trang_thai = 'Chua_ban' AND gia_ban > 50000
      AND CASE
          WHEN pg_input_is_valid(thong_tin_chi_tiet ->> 'ngay_nhap_kho', 'date')
          THEN (thong_tin_chi_tiet ->> 'ngay_nhap_kho')::date
          ELSE NULL::date
      END < CURRENT_DATE - 30;
END;
$function$;

-- Compatibility with the earlier controller/function name.
CREATE OR REPLACE FUNCTION quan_ly_shop.fn_ai_tu_dong_ha_gia_ton_kho()
RETURNS void LANGUAGE sql AS $$
    SELECT quan_ly_shop.fn_giam_gia_nick_ton_kho();
$$;

CREATE OR REPLACE FUNCTION quan_ly_shop.fn_notify_ai_nick_moi()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, quan_ly_shop
AS $function$
BEGIN
    PERFORM pg_notify('kenh_ai_garena', json_build_object(
        'event', 'NEW_NICK_INSERTED',
        'ma_nick', NEW.ma_nick,
        'ma_game', NEW.ma_game,
        'anh_url', NEW.anh_dinh_kem_url
    )::text);
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_notify_ai_nick_moi ON quan_ly_shop.tai_khoan_game;
CREATE TRIGGER trg_notify_ai_nick_moi
AFTER INSERT ON quan_ly_shop.tai_khoan_game
FOR EACH ROW EXECUTE FUNCTION quan_ly_shop.fn_notify_ai_nick_moi();

COMMIT;
