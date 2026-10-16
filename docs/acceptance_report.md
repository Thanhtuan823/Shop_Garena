# Nghiệm thu kỹ thuật — 2026-10-16

## Môi trường kiểm tra

- PostgreSQL 17.11; mã nguồn hỗ trợ PostgreSQL 16/17.
- Python thực thi: 3.14.3. Đã parse các module bằng grammar Python 3.12.
- FastAPI/Uvicorn đã cài và khởi động bằng `python app.py`.
- Windows PyTorch cần MSVC runtime mới; đã cài app-local trong `.runtime`,
  không thay DLL hệ thống. Model EasyOCR lưu trong thư mục dự án.

## Kết quả thực tế

- Áp dụng models/01..04 thành công trên GarenaShop_DB.
- Tạo database trắng riêng, áp dụng schema và seed thành công; chạy cùng bộ
  test đạt 12/12 PASS, exit 0; database kiểm thử được xóa sau khi hoàn tất.
- Suite trên GarenaShop_DB: 12/12 nhóm nghiệp vụ PASS, setup/cleanup PASS,
  exit 0. Setup/cleanup không tính vào 12 nhóm nghiệp vụ.
- EasyOCR thực nhận diện đúng `Raz Muay Thai` từ ảnh PNG sinh tại chỗ
  bằng `python scripts/check_ocr.py`.
- HTTP thực: `/`, `/staff.html`, `/admin.html`, `/api/accounts`,
  `/openapi.json`, `/assets/client.js` đều trả 200. Server smoke đã được dừng.
- JavaScript syntax: common.js/client.js/manage.js hợp lệ bằng `node --check`.

## Phạm vi 12 nhóm kiểm thử

1. Regex SĐT — SQLSTATE 23514.
2. Giá âm — SQLSTATE 23514.
3. FK RESTRICT — SQLSTATE 23503.
4. RBAC Staff: cấm lương/pass/DELETE/sửa ví, cho INSERT và UPDATE giá.
5. RLS theo GUC, chủ đơn, public masking NULL, pool reset role/danh tính.
6. Gọi controller AI3 thật, kiểm chứng thu hồi credentials.
7. Partial Index: execution plan tự nhiên và minh họa index khi cần.
8. AI4: SQL tham số JSONB @>, kết quả khớp, GIN execution plan.
9. LISTEN/NOTIFY trên hai connection, xác minh event và mã nick sau commit.
10. Wishlist, giữ chỗ đúng 900 giây, race hai kết nối, hết hạn và checkout ACID.
11. SePay/thẻ cào mock, replay, thẻ dùng lại, đối soát idempotent, view Staff
    đúng 6 cột; lỗi overflow ví hoàn tác cả ledger.
12. API đăng nhập/RBAC/IDOR/CRUD Staff/OCR merge/credentials/static/checkout/
    biên lai; ETL giữ tiền ví; giá sàn; AI2/5/6/7/8 regressions.

## Giới hạn kết luận

- OCR smoke chứng minh pipeline hoạt động trên một ảnh mẫu; không đại diện
  độ chính xác trên mọi ảnh game. Regression JSONB riêng mock khâu suy luận.
- Chưa chạy kiểm thử tương tác/hiển thị bằng trình duyệt tự động.
- Index test không chứng minh mọi truy vấn đạt <1ms trên mọi máy/dữ liệu.
- SePay/thẻ cào là mock. AI2/3/5/6/7/8 dùng quy tắc/heuristic minh bạch;
  AI8 chỉ đề xuất, không tự chuyển tiền hoặc kết luận gian lận.
- Ứng dụng phục vụ demo localhost một tiến trình; các bước triển khai Internet
  được liệt kê riêng trong README, không nằm trong kết quả nghiệm thu này.
