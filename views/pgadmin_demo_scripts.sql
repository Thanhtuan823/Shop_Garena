-- ============================================================================
-- LIVE DEMO / PGADMIN 4 QUERY TOOL / POSTGRESQL 16
-- ============================================================================
-- Điều kiện: đã chạy models/01..04 trong GarenaShop_DB.
-- Kết nối bằng superuser (ví dụ postgres) để tạo role demo và SET ROLE.
-- Chỉ dùng database thử nghiệm. ID demo_* và kh_demo* dành riêng cho file này.
-- Bật Auto-commit. Bôi đen từng khối được chỉ dẫn rồi Execute/F5.
-- KHÔNG chạy toàn file: các câu lỗi cố ý sẽ dừng batch và ảnh hưởng transaction.
-- Mỗi câu dự kiến lỗi phải chạy RIÊNG để PostgreSQL trả lỗi đỏ cho pgAdmin.
-- Nếu pgAdmin còn transaction lỗi (25P02), chạy riêng ROLLBACK; RESET ROLE;
-- rồi bật Auto-commit trước khi tiếp tục. Lệnh ROLLBACK bỏ thay đổi chưa commit.

-- ============================================================================
-- CHUẨN BỊ: CHẠY TOÀN BỘ KHỐI BEGIN ... COMMIT NÀY MỘT LẦN
-- ============================================================================
RESET ROLE;
BEGIN;

-- Policy dùng ma_kh = current_user. Role khách cá nhân cần tên khớp ma_kh.
-- NOLOGIN đủ cho SET ROLE khi demo; không cấp mật khẩu đăng nhập thực.
DO $demo_roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kh_demo01') THEN
        CREATE ROLE kh_demo01 NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END;
$demo_roles$;
GRANT "KhachHangRole" TO kh_demo01 WITH INHERIT TRUE;

INSERT INTO quan_ly_shop.danh_muc_game (ma_game, ten_game)
VALUES ('demo_lq', 'Liên Quân Mobile')
ON CONFLICT (ten_game) DO NOTHING;

INSERT INTO quan_ly_shop.khach_hang (ma_kh, ho_ten, so_du_vi)
VALUES ('kh_demo01', 'KHÁCH DEMO MỘT', 500000),
       ('kh_demo02', 'KHÁCH DEMO HAI', 500000)
ON CONFLICT (ma_kh) DO NOTHING;

INSERT INTO quan_ly_shop.nhan_vien (ma_nv, ho_ten, phong_ban, luong, mat_khau)
VALUES ('nv_demo01', 'NHÂN VIÊN DEMO', 'Sale', 10000000, 'demo_only_not_real')
ON CONFLICT (ma_nv) DO NOTHING;

-- 3 nick: một của khách 1, một của khách 2, một chưa bán để đối chiếu policy.
INSERT INTO quan_ly_shop.tai_khoan_game (
    ma_nick, ma_game, gia_ban, trang_thai, thong_tin_chi_tiet, mat_khau_game
)
SELECT fixture.ma_nick, game.ma_game, fixture.gia_ban, fixture.trang_thai,
       '{"Rank":"Cao Thủ 25 Sao","SkinHiem":["Raz Muay Thai"]}'::jsonb,
       'demo_password_' || fixture.ma_nick
FROM (VALUES
    ('demo_owned', 350000, 'Da_ban'),
    ('demo_other', 280000, 'Da_ban'),
    ('demo_unsold', 300000, 'Chua_ban')
) AS fixture(ma_nick, gia_ban, trang_thai)
CROSS JOIN quan_ly_shop.danh_muc_game AS game
WHERE game.ten_game = 'Liên Quân Mobile'
ON CONFLICT (ma_nick) DO UPDATE
SET trang_thai = EXCLUDED.trang_thai,
    gia_ban = EXCLUDED.gia_ban,
    thong_tin_chi_tiet = EXCLUDED.thong_tin_chi_tiet;

INSERT INTO quan_ly_shop.don_hang (ma_dh, ma_kh, ma_nick, ma_nv, tong_tien)
VALUES ('dh_demo01', 'kh_demo01', 'demo_owned', 'nv_demo01', 350000),
       ('dh_demo02', 'kh_demo02', 'demo_other', 'nv_demo01', 280000)
ON CONFLICT (ma_dh) DO NOTHING;

COMMIT;
-- Chuẩn bị cũng phát NOTIFY cho những nick vừa INSERT. Bật listener sau khối
-- này nếu muốn chỉ nhìn thấy sự kiện Bước 4. Các nick chuẩn bị không có ảnh.

-- ============================================================================
-- BƯỚC 1 / FAIL-SAFE: CHẠY RIÊNG TỪNG CÂU INSERT HOẶC DELETE
-- ============================================================================
-- 1A. Kỳ vọng SQLSTATE 23514: CHECK regex SĐT ^0[0-9]{9}$ thất bại.
INSERT INTO quan_ly_shop.khach_hang (ma_kh, ho_ten, so_dien_thoai, so_du_vi)
VALUES ('bad_phone', 'KHÁCH SAI SỐ', '09A-123', 0);

-- 1B. Kỳ vọng SQLSTATE 23514: CHECK gia_ban > 0 thất bại.
INSERT INTO quan_ly_shop.tai_khoan_game (
    ma_nick, ma_game, gia_ban, trang_thai, mat_khau_game
)
SELECT 'bad_price', ma_game, -100000, 'Chua_ban', 'demo_only'
FROM quan_ly_shop.danh_muc_game
WHERE ten_game = 'Liên Quân Mobile';

-- 1C. Kỳ vọng SQLSTATE 23503: khách đã có đơn, FK ON DELETE RESTRICT chặn.
DELETE FROM quan_ly_shop.khach_hang WHERE ma_kh = 'kh_demo01';

-- ============================================================================
-- BƯỚC 2 / SECURITY & RLS
-- ============================================================================
-- 2A. Chạy SET ROLE và truy vấn cột được phép cùng nhau: thành công.
SET ROLE "NhanVienSale";
SELECT current_user, session_user;
SELECT ma_nv, ho_ten, phong_ban
FROM quan_ly_shop.nhan_vien WHERE ma_nv = 'nv_demo01';

-- Chạy RIÊNG: kỳ vọng SQLSTATE 42501, không có quyền SELECT luong.
SELECT ma_nv, luong FROM quan_ly_shop.nhan_vien WHERE ma_nv = 'nv_demo01';

-- Chạy RIÊNG: kỳ vọng SQLSTATE 42501, không có quyền SELECT mat_khau_game.
SELECT ma_nick, mat_khau_game FROM quan_ly_shop.tai_khoan_game;

-- 2B. Chạy khối này: kiểm tra quyền nhóm KhachHangRole.
RESET ROLE;
SET ROLE "KhachHangRole";
SELECT current_user, session_user;
SELECT ma_nick, trang_thai, mat_khau_game
FROM quan_ly_shop.tai_khoan_game
WHERE ma_nick IN ('demo_owned', 'demo_other', 'demo_unsold')
ORDER BY ma_nick;
-- Kỳ vọng CHỈ demo_unsold. current_user = 'KhachHangRole' không khớp mã khách.
-- Không thể tạo ma_kh = 'KhachHangRole' vì cột ma_kh chỉ VARCHAR(10).
-- Policy hiện tại cho đọc mật khẩu nick Chua_ban; đây là hành vi của model,
-- không phải cơ chế "chỉ chủ đơn được xem" đối với mọi trạng thái.

-- 2C. Chạy khối này: role cá nhân kế thừa quyền nhóm, tên khớp mã khách.
RESET ROLE;
SET ROLE kh_demo01;
SELECT current_user, session_user;
SELECT ma_nick, trang_thai, mat_khau_game
FROM quan_ly_shop.tai_khoan_game
WHERE ma_nick IN ('demo_owned', 'demo_other')
ORDER BY ma_nick;
-- Kỳ vọng một dòng demo_owned; demo_other đã bán cho kh_demo02 nên bị ẩn.
-- SELECT chạy dưới role cá nhân, không dưới superuser/chủ bảng (bypass RLS).

-- 2D. Chạy khối này để quản trị viên khóa tranh chấp và commit ngay.
RESET ROLE;
UPDATE quan_ly_shop.tai_khoan_game
SET trang_thai = 'Khoa_tranh_chap' WHERE ma_nick = 'demo_owned';

-- Chạy khối này: dù là chủ đơn, khách không thấy nick đang tranh chấp.
SET ROLE kh_demo01;
SELECT ma_nick, trang_thai, mat_khau_game
FROM quan_ly_shop.tai_khoan_game WHERE ma_nick = 'demo_owned';
-- Kỳ vọng 0 dòng. RLS lọc dòng; không tự mã hóa/giải mã cột mật khẩu.

-- Kết thúc Bước 2, khôi phục trạng thái fixture cho lần demo tiếp theo.
RESET ROLE;
UPDATE quan_ly_shop.tai_khoan_game
SET trang_thai = 'Da_ban' WHERE ma_nick = 'demo_owned';

-- ============================================================================
-- BƯỚC 3 / PERFORMANCE: CHẠY BẰNG QUẢN TRỊ VIÊN
-- ============================================================================
RESET ROLE;
ANALYZE quan_ly_shop.tai_khoan_game;

-- 3A. Kế hoạch tự nhiên cho catalog còn hàng. Predicate khớp partial index.
-- Index có thứ tự (ma_nick, gia_ban); bộ lọc chỉ giá không tối ưu như index
-- có gia_ban đứng đầu. ORDER BY ma_nick giúp minh họa thứ tự của index hiện có.
EXPLAIN (ANALYZE, BUFFERS)
SELECT ma_nick, gia_ban
FROM quan_ly_shop.tai_khoan_game
WHERE trang_thai = 'Chua_ban' AND gia_ban <= 400000
ORDER BY ma_nick;

-- 3B. JSONB containment tương thích GIN idx_gin_thong_tin_nick.
EXPLAIN (ANALYZE, BUFFERS)
SELECT ma_nick, gia_ban, thong_tin_chi_tiet
FROM quan_ly_shop.tai_khoan_game
WHERE trang_thai = 'Chua_ban'
  AND thong_tin_chi_tiet @> '{"SkinHiem":["Raz Muay Thai"]}'::jsonb;

-- Bảng ít dòng thường dùng Seq Scan vì rẻ hơn; đó không phải index bị lỗi.
-- Đọc Execution Time, actual rows và BUFFERS, không cam kết tăng tốc từ 3 dòng.
-- 3C. CHẠY CẢ KHỐI: giảm ưu tiên Seq Scan chỉ để minh họa khả năng dùng index.
-- SET LOCAL tự hết hiệu lực khi COMMIT. Đây không phải benchmark production.
BEGIN;
SET LOCAL enable_seqscan = off;

-- Tìm Index Only Scan/Index Scan using idx_nick_san_co trong Explain.
EXPLAIN (ANALYZE, BUFFERS)
SELECT ma_nick, gia_ban FROM quan_ly_shop.tai_khoan_game
WHERE trang_thai = 'Chua_ban' ORDER BY ma_nick;

-- Bỏ predicate trạng thái trong truy vấn minh họa riêng này để planner không
-- chọn partial index cạnh tranh; tìm Bitmap Index Scan idx_gin_thong_tin_nick.
EXPLAIN (ANALYZE, BUFFERS)
SELECT ma_nick FROM quan_ly_shop.tai_khoan_game
WHERE thong_tin_chi_tiet @> '{"SkinHiem":["Raz Muay Thai"]}'::jsonb;

COMMIT;

-- ============================================================================
-- BƯỚC 4 / EVENT-DRIVEN TRIGGER: INSERT -> COMMIT -> NOTIFY -> OCR
-- ============================================================================
-- Trước khi chạy, mở terminal ở thư mục gốc dự án:
--   python -m controllers.realtime_notify_listener
-- Listener phải dùng cùng database GarenaShop_DB và phải LISTEN trước INSERT.
-- Nếu muốn quan sát trong pgAdmin: mở Query Tool THỨ HAI, Auto-commit bật,
-- chạy LISTEN kenh_ai_garena; rồi xem Notifications (có thể chạy SELECT 1
-- trong cửa sổ đó sau COMMIT để client đọc socket). Không đặt LISTEN trong
-- transaction chưa commit. Đừng gửi LISTEN và INSERT trong cùng batch.
--
-- 4A. Chạy CẢ KHỐI: mỗi lần sinh mã mới <= 15 ký tự để INSERT luôn phát event.
-- Notification chỉ được gửi sau COMMIT, không phải ngay khi trigger chạy.
-- URL dưới đây là placeholder; thay bằng ảnh thật khi OCR xử lý ảnh thực tế.
-- Controller OCR hiện có là mock và có thể cập nhật JSONB sau khi nhận event.
RESET ROLE;
BEGIN;
INSERT INTO quan_ly_shop.tai_khoan_game (
    ma_nick, ma_game, gia_ban, trang_thai, thong_tin_chi_tiet,
    mat_khau_game, anh_dinh_kem_url
)
SELECT 'evt' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 12),
       ma_game, 320000, 'Chua_ban',
       jsonb_build_object('ngay_nhap_kho', CURRENT_DATE::text),
       'demo_only_not_real', 'https://example.com/demo-nick.png'
FROM quan_ly_shop.danh_muc_game
WHERE ten_game = 'Liên Quân Mobile'
RETURNING ma_nick, ma_game, anh_dinh_kem_url;
COMMIT;
-- Terminal kỳ vọng: nick mới nhập kho -> gọi process_game_screenshot().
-- Kênh kenh_ai_garena chứa event, ma_nick, ma_game, anh_url; không có mật khẩu.

-- 4B. Chạy sau khi listener xử lý để xem kết quả và log OCR mới nhất.
SELECT ma_nick, thong_tin_chi_tiet
FROM quan_ly_shop.tai_khoan_game WHERE ma_nick LIKE 'evt%';
SELECT id, ma_nick, url_anh, confidence_score, thoi_gian
FROM ai_analytics.log_ai_ocr ORDER BY id DESC LIMIT 5;

-- Kết thúc demo, luôn trả session về role ban đầu.
RESET ROLE;
