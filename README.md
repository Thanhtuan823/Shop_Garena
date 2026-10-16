# GarenaShop — Fullstack MVC / PostgreSQL / 8 AI

Ứng dụng demo cục bộ, Python 3.12+, PostgreSQL 16/17, FastAPI và Vanilla JS.
SePay và thẻ cào là mô phỏng, không kết nối cổng thu tiền thật.

## Khởi động

```powershell
python -m pip install -r requirements.txt
# Điền DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD trong .env
python scripts/init_db.py --seed-demo
python tests/run_full_demo_test.py
python app.py
```

CSDL phải tồn tại trước khi chạy init_db. Dùng tài khoản chủ sở hữu/superuser
trong môi trường demo để tạo role và SET ROLE. Script chỉ áp dụng models/01..04;
không tự chạy VACUUM FULL hoặc lệnh khôi phục database. Các lệnh backup nằm ở
models/05_maintenance_backup.sql.

Seed in mật khẩu sinh ngẫu nhiên của ba tài khoản `admin`, `staff`, `user` ra
terminal **khi tạo lần đầu**. Giữ lại mật khẩu đó. Có thể đặt trước biến môi
trường `DEMO_ADMIN_PASSWORD`, `DEMO_STAFF_PASSWORD`, `DEMO_USER_PASSWORD`.
Chạy lại seed không đổi mật khẩu, số dư hoặc nick đã có. Không commit mật khẩu.
User demo gắn với khách KH_DEMO; khách mới có thể đăng ký từ Client.

- Client: http://127.0.0.1:8000/
- Staff: http://127.0.0.1:8000/staff.html
- Admin: http://127.0.0.1:8000/admin.html
- OpenAPI: http://127.0.0.1:8000/docs

## Kịch bản nghiệm thu

1. Đăng nhập `user`, nạp 500.000đ bằng SePay mock với nội dung `NAP KH_DEMO`.
   Nội dung gõ sai vào trạng thái chờ duyệt, chưa cộng tiền.
2. Thử thẻ: seri `#GARENA*98231456`, mã `$CARD&1234567890`, chọn mệnh giá.
   Cặp seri/mã chỉ được dùng một lần. Mã giao dịch giúp replay không cộng trùng.
3. Thả tim, giữ chỗ nick, xem countdown, checkout và lịch sử/biên lai.
   Nick chưa mua trả lỗi credentials; nick đã mua mới đọc qua RLS.
4. Staff nhập/sửa nick public, chọn ảnh rồi chạy AI1; thử đối soát giao dịch chờ
   bằng mã giao dịch và mã khách đã xác minh. AI6 chỉ gợi ý fuzzy matching.
5. Admin thử DELETE nick có đơn để thấy lỗi FK RESTRICT, chạy AI2/AI5, chẩn đoán
   AI7 và VACUUM, chấm điểm AI8; khóa tranh chấp bằng AI3 rồi thử credentials.

## AI và giới hạn demo

- AI1 dùng EasyOCR thực trên ảnh upload base64 hoặc HTTPS công khai; lần đầu
  EasyOCR có thể tải model. URL ảnh cần domain trong biến `OCR_ALLOWED_HOSTS`
  (phân cách bằng dấu phẩy); upload base64 không cần cấu hình domain.
  Không có model/dependency/ảnh hợp lệ sẽ báo lỗi,
  không trả JSON nhận diện giả. JSONB merge bảo toàn ngày nhập kho.
- AI2 là quy tắc giảm 5% tồn >30 ngày, làm tròn nghìn, sàn 50.000đ; mỗi lần
  kích hoạt giảm tiếp. AI3 là hành động khóa sau khi người vận hành xác minh.
- AI4 là parser từ khóa hữu hạn, truy vấn tham số JSONB @>; chưa phải LLM.
- AI5 tính churn từ lịch sử mua >60 ngày, cấp TRIAN20PCT idempotent.
- AI6 dùng SequenceMatcher và cần Staff xác nhận; AI7 đo tỷ lệ dead tuples
  ước lượng từ thống kê, không phải phép đo physical bloat chính xác.
- AI8 là chấm điểm quy tắc có giải thích, chỉ đề xuất hoàn tiền; không tự
  chuyển tiền hoặc khẳng định gian lận.

## Bảo mật và transaction

Public view luôn trả NULL cho password/email. Bảng gốc dùng RLS theo
`current_setting('app.current_user_id', true)` và chỉ trả nick chủ đơn không
tranh chấp. API lấy danh tính từ phiên đăng nhập, không tin ma_kh/role từ body.
Pool dùng SET LOCAL và reset role/GUC/isolation khi trả lease. SimpleConnectionPool
được bọc lock/semaphore để dùng an toàn với worker threads. Finance dùng khóa dòng,
unique transaction/card fingerprint và transaction ACID; server dọn cart mỗi 15s.
Không expose cổng PostgreSQL cho khách hoặc cho khách tự gửi SQL/GUC.

Phiên đăng nhập lưu trong bộ nhớ, hết hạn sau 1 giờ và mất khi restart; token
lưu sessionStorage. Demo chạy một tiến trình trên localhost. Triển khai Internet
cần HTTPS, secret/session store dùng chung, rate limiting, phân tách service DB
login đặc quyền tối thiểu và quy trình thanh toán/webhook được xác thực thật.

## Kiểm thử

`python tests/run_full_demo_test.py` chạy đúng 12 nhóm nghiệp vụ; setup/cleanup
được báo riêng, exit 0 chỉ khi mọi nhóm và cleanup đều thành công. Có race test
hai connection, RLS/masking/pool isolation, ví/idempotency/card, view Staff, API
RBAC/IDOR và regression ETL/OCR JSON merge. Test OCR merge mock riêng khâu suy
luận; chưa chứng minh độ chính xác EasyOCR. Index test báo cả kế hoạch tự nhiên
và enable_seqscan=off, không cam kết tốc độ <1ms cho mọi máy.

Chạy trên database thử nghiệm, tắt server/listener ngoài suite để tránh thay đổi
fixture đồng thời. Không tắt RLS hoặc thay policy để làm test PASS.

### Windows / EasyOCR runtime

Nếu PyTorch báo lỗi `c10.dll` trên máy Windows có MSVC runtime cũ, cài bản
runtime cục bộ (không thay DLL hệ thống), rồi kiểm tra OCR thật:

```powershell
python -m pip install --target .runtime msvc-runtime
python scripts/check_ocr.py
```

Model EasyOCR được tải/lưu trong `.runtime/easyocr/` của dự án. Lệnh smoke OCR
nhận diện ảnh PNG sinh tại chỗ, không thay đổi database. Lần đầu cần Internet.

## Bản sửa nghiệm thu HTML / role / UI

Đã kiểm chứng 58/58 tiêu chí role/UI, 12/12 nhóm nghiệp vụ và 4/4 regression
MIME/page access. Xem [báo cáo sau sửa](docs/role_fix_verification.md).

- HTML có response UTF-8 rõ ràng; CSS/JS được cấp MIME đúng cả khi Windows
  registry gán sai file association. Trang Staff/Admin kiểm tra phiên ở server.
- Không mount toàn bộ views ở /static vì sẽ tạo đường bypass trang nội bộ.
  /assets và /static chỉ phục vụ nội dung thư mục views/assets.
- Cookie HttpOnly chỉ dùng cho page navigation; API vẫn cần Authorization bearer.
  Logout/đổi danh tính xóa dữ liệu riêng tư và loại bỏ response đến muộn.
- Sau khi cập nhật source, dừng server cũ và chạy lại `python app.py`. Nếu cổng
  8000 đang bị chiếm, xác minh đúng tiến trình trước khi dừng. Dùng Ctrl+F5,
  đăng nhập lại; token cũ hết hiệu lực sau restart.

```powershell
python tests/check_html_delivery.py
python -m pip install --target .runtime/qa playwright
python tests/run_role_audit.py
```

Test role URL OCR dùng ảnh HTTPS của EasyOCR, cần Internet. Để dán URL trong
ứng dụng, cấu hình OCR_ALLOWED_HOSTS bằng danh sách domain cho phép; upload file
không cần truy cập domain ngoài. Không tắt bảo vệ địa chỉ mạng nội bộ.
