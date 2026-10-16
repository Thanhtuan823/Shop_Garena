# Live demo bốn bước

## Chuẩn bị

1. Điền `.env`, chạy `python scripts/init_database.py --seed-demo`.
2. Lưu mật khẩu được in khi tạo admin/staff/user lần đầu.
3. Chạy `python app.py`, mở `http://127.0.0.1:8000/`.
4. SQL tương tác cho pgAdmin nằm trong `docs/live_demo_queries.sql`;
   chỉ chạy từng khối trên DB demo, các câu lỗi cố ý chạy riêng với autocommit.

## Bước 1 — Toàn vẹn và fail-safe

Chứng minh CHECK SĐT sai/giá âm trả 23514; xóa khách hoặc nick đã có đơn trả
23503. Dữ liệu hợp lệ vẫn còn nguyên. Suite nghiệp vụ kiểm tra trực tiếp
SQLSTATE, không coi mọi exception là PASS.

## Bước 2 — RBAC, RLS và tài chính

Guest chỉ thấy Kho nick và Đăng nhập; thử giữ chỗ/credentials sẽ được yêu cầu
đăng nhập. Login User cập nhật Client tại chỗ và hiện ví/nạp tiền/lịch sử trên
Navbar; nạp mock, thả tim, giữ chỗ 15 phút, checkout và xem biên lai.
Thử credentials trước mua bị chặn; sau mua hiển thị nhãn mật khẩu riêng tư.
Logout dọn dữ liệu và quay về trang chủ.

Login Staff tự vào bàn làm việc: chỉ chỉnh thông tin công khai, không thấy
password/lương/số dư và không có nút xóa. Nhập ảnh OCR có chữ Raz Muay Thai,
kiểm tra badge, lưu lại và xác nhận Skin vẫn còn. Tra cứu nạp tiền theo mã
khách/giao dịch; AI6 hiện matching card, không tự tăng tiền.

Login Admin, khóa nick đã mua bằng AI3. User đăng nhập lại sẽ không đọc được
credentials do RLS. Thử DELETE nick có đơn để quan sát FK RESTRICT.

## Bước 3 — Index và tám AI

Chạy EXPLAIN ANALYZE của partial/GIN trong script SQL. Với bảng nhỏ planner
có thể chọn sequential scan; nhánh ép index chỉ minh họa index dùng được.
Chat AI4 trả card có ảnh local và skin phù hợp, không in SQL/JSON thô.

Admin kích hoạt Pricing, Marketing, ETL, chẩn đoán AI7 và VACUUM ANALYZE.
AI7 hiển thị thanh tỷ lệ dòng chết. AI8 nhập bằng chứng để thấy risk bar và
card đề xuất hoàn tiền; điểm cao không tự thực hiện giao dịch tài chính.

## Bước 4 — Event-driven

INSERT nick có ảnh nguồn hợp lệ: trigger gửi NEW_NICK_INSERTED trên
kenh_ai_garena sau commit; listener ghi log và gọi OCR. Nick dùng thumbnail
minh họa sinh tự động được bỏ qua OCR nền; chạy AI1 từ ảnh gốc bằng UI.
LISTEN/NOTIFY không lưu hàng đợi khi listener offline.

## Chạy kiểm chứng tự động

```powershell
python tests/test_database_business.py
python tests/test_role_and_ui.py
python tests/test_all_ai_modules.py
python tests/check_html_delivery.py
```

Suite role/UI và AI tự tạo DB tạm rồi dọn trong finally. Suite nghiệp vụ
dùng DB trong `.env`, tạo và xóa fixture; nên chạy trên DB thử nghiệm.
