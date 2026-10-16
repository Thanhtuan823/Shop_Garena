# Nghiệm thu sau sửa lỗi HTML và 16 tiêu chí role/UI

Ngày: 2026-10-16. Kết quả: **58/58 PASS, 0 FAIL, exit 0**.
Trước sửa: 42/58 PASS, 16 FAIL. Không bỏ tiêu chí FAIL nào.

## Bản sửa

- app.py dùng FileResponse/HTMLResponse UTF-8 cho từng trang; ép MIME đúng cho
  CSS/JS, thêm nosniff/no-store. Không phụ thuộc registry MIME của Windows.
- Guest được chuyển hướng 303 khỏi Staff/Admin; User sai role nhận 403.
  Cookie HttpOnly SameSite strict phục vụ điều hướng trang; API vẫn yêu cầu
  bearer token. /assets và /static chỉ chứa assets, không mở lại HTML nội bộ.
- Logout/đổi tài khoản xóa password, receipt, history, bảng Staff và state riêng;
  đóng dialog, hủy request và dùng identity epoch để loại phản hồi cũ.
- Catalog chỉ trả Chua_ban. Nick giữ chỗ vẫn ở giỏ của chủ giữ nhưng không còn
  hiện trong catalog người khác. Header hiển thị ma_kh.
- OCR chấp nhận file hoặc URL HTTPS thuộc allowlist; trả JSONB đã merge,
  đồng bộ editor và chặn Lưu trong lúc OCR. Lưu tiếp không xóa skin vừa nhận diện.
- Staff có tra cứu chính xác mã KH/mã GD; view vẫn đúng 6 cột không chứa dữ
  liệu thẻ/số dư. Admin có đủ 8 thẻ AI, ETL/VACUUM và field ma_ncc.
- Mobile dùng grid children min-width:0 và scroll container cho bảng; document
  không tràn ngang ở 390px. Guest không còn lỗi JS khi yêu cầu đăng nhập.
- Log thao tác có actor, role, request_id, method, target, status; không ghi
  token, mật khẩu hoặc mã thẻ.

## Bằng chứng thực thi

1. tests/test_database_business.py: **12/12 nhóm nghiệp vụ PASS**, setup/cleanup PASS.
2. tests/test_role_and_ui.py: **58/58 PASS** trên PostgreSQL trắng, HTTP và Chrome.
   Có OCR URL HTTPS công khai thật và OCR upload PNG thật. Có kiểm tra
   OCR -> textarea -> Lưu -> đọc lại DB. Có phản hồi credentials giả lập đến
   muộn sau logout, bỏ qua AbortSignal: client vẫn loại bỏ phản hồi đó.
3. tests/check_html_delivery.py: **4/4 PASS**, gồm giả lập MIME .html/.js/.css
   bị map sai sang text/plain và kiểm tra đường static không bypass bảo mật.
4. Cổng 8000: xác minh server cũ chạy bằng project .venv; dừng đúng tiến trình,
   khởi động bản mới bằng .venv/Scripts/python.exe app.py. Chrome xác nhận
   document.contentType=text/html, h1 hiển thị, CSS dark mode áp dụng đúng.
   Request trang nội bộ Guest trả 303. Token hết hạn được xóa và catalog vẫn tải.
5. Staff/Admin mobile sau sửa: full-page screenshot rộng đúng 390px, không còn
   765px/458px như trước. 1440px desktop cũng đạt.

Môi trường: Windows, PostgreSQL 17.11, Python 3.14.3, Chrome; chưa chứng nhận
runtime Python 3.12/Firefox/Safari trong lần kiểm thử này.

## Tính toàn vẹn của test

- Giữ đủ 58 phép kiểm tra. Phần test cũ ghi hardcode FAIL cho OCR URL đã được
  thay bằng request/response với ảnh HTTPS thật của EasyOCR; không mock OCR.
- Page test cũ mong Guest/User nhận 200 được sửa sang 303/403 theo yêu cầu mới.
- Login API của từng role có cookie jar riêng để mô phỏng các phiên độc lập;
  hành vi đổi tài khoản trong cùng trình duyệt vẫn thu hồi phiên trước.
- Đợi nút OCR kết thúc trước khi đọc textarea, không đọc quá sớm khi request
  refresh editor còn chạy. Test vẫn kiểm chứng JSONB lưu trong DB.
- Không hạ quyền RLS/RBAC, không tắt CHECK/FK, không đổi kết quả tài chính để
  làm test PASS. Database audit riêng và server 8137 đã được dọn.

## Tệp và cách kiểm tra lại

- docs/role_audit_results_before_fixes.json: kết quả 42/58 trước sửa.
- docs/role_audit_results.json: kết quả 58/58 hiện tại.
- .runtime/role_audit/: ảnh Chrome, baseline.log, server.log, port8000.png.

```powershell
python tests/test_database_business.py
python tests/check_html_delivery.py
python tests/test_role_and_ui.py
python app.py
```

Role audit cần Chrome và QA dependency trong .runtime/qa như README; luồng URL
OCR cần Internet và domain được cấu hình trong OCR_ALLOWED_HOSTS. Trong nghiệm
thu dùng raw.githubusercontent.com. Model OCR dùng cache trong .runtime.

Bản server mới trên 8000 thay cho tiến trình cũ. Nếu đã mở tab từ trước, dùng
Ctrl+F5 và đăng nhập lại (phiên trong RAM không tồn tại qua restart). Không chạy
thêm server trên cùng cổng khi tiến trình này còn hoạt động.

Giới hạn: SePay/thẻ cào vẫn là mock, AI quy tắc/heuristic được giữ nguyên; 58/58
là đạt checklist đã kiểm tra, không phải chứng nhận an toàn production hay độ
chính xác OCR trên mọi ảnh. Không dùng public Internet trước các bước hardening
đã ghi trong README.
