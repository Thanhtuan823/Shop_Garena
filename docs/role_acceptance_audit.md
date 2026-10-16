> Bản audit trước sửa, giữ để đối chiếu. Kết quả mới: **58/58 PASS**; xem [role_fix_verification.md](role_fix_verification.md).

# Báo cáo nghiệm thu theo 4 roles — GarenaShop_DB

Ngày kiểm tra: 2026-10-16. Kết luận: **CHƯA ĐẠT 100% checklist nghiệm thu**.

## 1. Phạm vi và phương pháp

- Đối chiếu Spec_for_project.md với views/, app.py, controllers/, models/.
- Tạo database PostgreSQL trắng riêng, áp dụng models/01..04 và seed demo.
- Chạy bộ test hiện có: **12/12 nhóm nghiệp vụ PASS**, setup/cleanup PASS.
- Chạy bổ sung HTTP thật, Chrome headless và SQL kiểm chứng RBAC theo role.
- Tổng **58 phép kiểm tra: 42 PASS / 16 FAIL**. Một số FAIL cùng nguyên nhân;
  đây không phải 16 lỗ hổng độc lập. Audit runner trả exit code 1 đúng kỳ vọng.
- Môi trường: Windows, Python 3.14.3, PostgreSQL 17.11, Chrome sẵn có;
  viewport desktop 1440x960 và mobile 390x844. Không chứng nhận runtime Python 3.12
  hoặc browser khác từ lần audit này.
- Không sửa mã ứng dụng. Chỉ thêm tests/run_role_audit.py, báo cáo và bằng chứng.
- Server audit chạy cổng 8137; đã dừng. Database tạm đã xóa. Không chạy ETL,
  pricing, VACUUM hay giao dịch thử trên dữ liệu GarenaShop_DB hiện có.

## 2. Bảng đánh giá theo role

| Role | Phép kiểm tra riêng | Kết luận | Chức năng đã đạt | Điểm chưa đạt |
|---|---|---|---|---|
| Guest | 6 PASS / 2 FAIL | Chưa đạt toàn bộ | Public NULL password/email; API nhạy cảm 401/403; UI yêu cầu login; AI4 chat chạy qua browser | Catalog chứa Dang_giu_cho; staff/admin HTML trả 200 không redirect/deny |
| User | 12 PASS / 3 FAIL | Chưa đạt toàn bộ | Ví cập nhật, SePay replay, thẻ hợp lệ/lỗi đỏ, wishlist bật/tắt, countdown, checkout, RLS, lịch sử và biên lai | Thiếu mã KH ở hồ sơ/header; nick giữ chỗ vẫn public; password cũ còn trong DOM sau logout |
| Staff | 11 PASS / 5 FAIL | Chưa đạt toàn bộ | Không có nút xóa/pass; DB chặn SELECT pass/lương, DELETE và UPDATE ví bằng 42501; API chặn sửa pass/xóa; OCR upload thật; view 6 cột; AI6; đối soát idempotent | OCR từ URL không chạy bằng nút; textarea không cập nhật sau OCR; Lưu tiếp làm mất OCR; thiếu tra cứu lọc; bảng đối soát còn hiển thị sau logout |
| Admin | 8 PASS / 3 FAIL | Chưa đạt toàn bộ | CRUD API/pass/email, xóa nick chưa bán, FK RESTRICT, ETL, AI2/3/5/7/8 và VACUUM thật | Không đủ 8 card tập trung; form thiếu ma_ncc; log chưa gắn actor cho từng thao tác |

7 phép kiểm tra UI dùng chung: 4 PASS / 3 FAIL; 1 phép baseline PASS.
Không cộng các lỗi UI dùng chung vào số riêng của từng role trong bảng trên.

## 3. Findings ưu tiên

### F01 — P1: Thông tin nhạy cảm không được xóa khi logout

- Client đã mở credentials QA_HOLD, đóng modal và logout: #credentials-content
  vẫn chứa QA_HOLD_PASS. Modal đóng không đồng nghĩa dữ liệu đã được xóa.
- Staff tải bảng đối soát, logout: #staff-transactions vẫn hiển thị các giao dịch
  trước đó. Đây là dữ liệu còn trên trang sau khi mất phiên, không phải API
  đã cho Guest quyền truy cập dữ liệu mới.
- Nguồn: views/assets/common.js:33; client.js:15,27; manage.js:30.
- Cần xóa dữ liệu riêng tư, đóng modal và hủy/loại kết quả request cũ khi đổi
  danh tính/logout. Kiểm tra lại cả đổi tài khoản trên cùng tab.

### F02 — P1: Lưu form sau OCR ghi đè mất kết quả OCR

- Browser upload ảnh thật có Raz Muay Thai: API OCR 200; DB có
  SkinHiem=['Raz Muay Thai'].
- Textarea vẫn là JSON cũ trước OCR. Bấm Lưu nick: API update 200, DB mất SkinHiem.
- Nguồn: views/assets/manage.js:16,18. Handler chỉ refreshStock(), không đưa
  JSONB đã merge từ server trở lại editor đang mở.
- Cần đồng bộ editor sau OCR và tránh ghi toàn bộ object cũ lên dữ liệu mới.

### F03 — P2: Catalog không chỉ chứa Chua_ban

- Sau khi giữ QA_HOLD, cả Guest/User vẫn nhận QA_HOLD với Dang_giu_cho từ
  GET /api/accounts. Card vẫn hiển thị, chỉ nút giữ chỗ bị disabled.
- Nguồn: app.py:234 dùng IN ('Chua_ban','Dang_giu_cho').
- Chưa đúng yêu cầu ẩn nick đang giữ chỗ. Cũng không thể suy ra toàn truy vấn
  này dùng partial index WHERE trang_thai='Chua_ban'.

### F04 — P2: Trang nội bộ không redirect/deny Guest

- GET /staff.html và /admin.html đều 200, hiển thị shell/form nội bộ.
- Protected APIs vẫn từ chối Guest; chưa phát hiện bypass quyền dữ liệu qua
  hai URL này trong phạm vi kiểm thử.
- Nguồn: app.py:469 mount toàn bộ views/; manage.js chỉ hiển thị thông báo quyền.

### F05 — P2: Mobile Staff/Admin bị tràn ngang

- Viewport 390px: Staff full-page rộng 765px, Admin rộng 458px.
- Client không tràn ngang ở 390px; cả ba trang không tràn ở 1440px.
- Bằng chứng: .runtime/role_audit/staff-390.png, admin-390.png.
- Cần kiểm tra min-width của grid children và giới hạn chiều rộng scroll/table.

### F06 — P2: Nút OCR không dùng URL ảnh đã dán

- Điền URL ảnh, không chọn file rồi bấm Chạy AI1: thông báo
  “Chọn nick đã lưu và một ảnh để OCR”.
- Nguồn: manage.js:18 chỉ đọc #ocr-file và không lấy giá trị URL.
- API hỗ trợ image_url nhưng URL ngoài còn cần OCR_ALLOWED_HOSTS. Upload file
  thật đã được kiểm chứng thành công, không được đánh đồng với luồng URL.

### F07 — P2: Chưa có tra cứu đối soát theo mã KH/mã GD

- UI chỉ có nút tải toàn bộ bảng và form duyệt giao dịch; chưa có form lọc.
- GET /api/staff/transactions?ma_kh=DOES_NOT_EXIST vẫn trả toàn bộ giao dịch.
- Nguồn: app.py staff_transactions(); manage.js:20.
- Bảo mật view đúng: chỉ 6 cột, không có seri/mã thẻ/chi tiết hay số dư khách.

### F08 — P2: Guest bấm nạp tiền tạo uncaught JavaScript error

- Login dialog vẫn mở đúng, nhưng Chrome pageerror ghi nhận
  “Hãy đăng nhập bằng tài khoản khách hàng”.
- requireCustomer() throw trong onclick đồng bộ của nút nạp tiền; listener
  unhandledrejection chỉ xử lý Promise rejection, không xử lý lỗi đồng bộ đó.
- Nguồn: client.js:5,47; common.js:39.

### F09 — P2: Logging chưa đầy đủ dấu vết kiểm toán

- Terminal có HTTP method/path/status cho các endpoint Admin, đã xác minh log.
- Chưa có actor/username gắn với mỗi action, request id hoặc biến động trước/sau.
  Không thể từ log chung hiện tại chứng minh ai đã kích hoạt từng nghiệp vụ.
- Nguồn: app.py:79–83; một số controller chỉ ghi tên thao tác.

### F10 — P3: Các thiếu hụt UI theo checklist

- Header hiển thị `user · user` và số dư, chưa hiển thị KH_DEMO/menu Hồ sơ.
- Admin có 6 nút trong .tools: ETL, AI2, AI3, AI5, AI7, VACUUM; AI8 là form
  riêng, AI1 ở form OCR, AI4 ở Client, AI6 ở Staff. Chưa có 8 card tập trung.
- Form Admin thiếu ma_ncc dù API hỗ trợ; chưa đạt sửa đầy đủ thuộc tính qua UI.
- Giỏ hàng hiện là panel, không phải modal popup.

## 4. UI/UX checklist thực tế

| Nội dung | Kết quả |
|---|---|
| Login gate Guest cho giỏ/yêu thích/nạp tiền | PASS, riêng nút nạp tiền còn uncaught error nêu trên |
| Modal nạp tiền mở/đóng, SePay/card | PASS trên Chrome desktop |
| QR động | Tham số amount/des đúng; không tải ảnh từ dịch vụ QR trong audit để không gửi dữ liệu thử ra ngoài |
| Lỗi thẻ sai, credentials sai quyền | Toast màu đỏ hiển thị trong browser |
| Số dư sau SePay và thẻ | 0 -> 500000 -> 600000 đúng, không cần reload |
| Checkout thiếu tiền | 409, không tạo đơn hoặc trừ ví |
| Checkout đủ tiền | Mua 90000 -> ví 510000; trạng thái Da_ban, có đơn, giỏ trống |
| Credentials đã mua | Modal hiện đúng dữ liệu; RLS là lọc dòng, không phải thuật toán giải mã |
| Credentials chưa mua/tranh chấp | 403; AI3 khóa lập tức thu hồi đường đọc |
| Lịch sử ví và biên lai | Có cả +/-; bộ lọc NAP_TIEN/MUA_NICK và dialog biên lai hoạt động |
| Giỏ hàng | Panel và countdown hoạt động; TTL/race/rollback cũng đạt trong baseline |
| Layout desktop | Không tràn ngang cả 3 trang tại 1440px |
| Layout mobile | Client PASS; Staff/Admin FAIL tại 390px |
| Sau logout | FAIL: cần xóa password cache và bảng Staff |
| URL OCR | FAIL ở nút UI; upload OCR thực PASS |

## 5. Kết luận và thứ tự xử lý

**Chưa thể nghiệm thu 100% để bảo vệ theo toàn bộ checklist.** Các đường giao
 dịch cốt lõi và chốt DB đã hoạt động trong phạm vi test, nhưng hai lỗi P1
(còn dữ liệu nhạy cảm sau logout; mất dữ liệu OCR khi Lưu) cần được sửa trước.

Thứ tự đề nghị:
1. Xóa state/DOM nhạy cảm và chống stale request khi logout/đổi tài khoản.
2. Đồng bộ JSONB editor sau OCR, thêm regression OCR -> Lưu -> đọc lại DB.
3. Lọc catalog chỉ Chua_ban; bảo vệ/redirect trang nội bộ theo yêu cầu.
4. Sửa mobile layout, UI OCR URL, form tra cứu Staff và lỗi console Guest.
5. Bổ sung mã KH/menu, field Admin/card điều khiển còn thiếu và audit logging.
6. Chạy lại baseline và role audit; chỉ kết luận đạt khi các tiêu chí bắt buộc
   được kiểm chứng lại. Không sửa code chỉ để ép test trả PASS.

## 6. Chạy lại và bằng chứng

```powershell
python -m pip install --target .runtime/qa playwright
python tests/run_role_audit.py
```

Runner dùng Chrome ở đường dẫn Windows sẵn có; tạo/xóa database riêng và cần
quyền CREATE DATABASE như môi trường demo hiện tại. Exit 1 phản ánh các tiêu chí
FAIL đã phát hiện, không phải lỗi harness. Không có HARNESS failure trong lần này.

- Kết quả từng phép kiểm tra: docs/role_audit_results.json.
- Browser screenshots, log server, baseline: .runtime/role_audit/.
- Giới hạn: một browser/hai viewport; chưa có kiểm thử accessibility đầy đủ,
  dịch vụ QR bên ngoài, mọi ảnh OCR hoặc kiểm thử tải/đa tiến trình.
- Các AI/Admin được chạy qua HTTP thật và đối chiếu wiring JS; không tuyên bố
  đã bấm mọi nút Admin bằng Chrome. Các luồng Client và OCR/đối soát Staff có
  kiểm tra thao tác trình duyệt như kết quả bên trên.
