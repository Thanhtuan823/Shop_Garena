# Báo cáo nghiệm thu sau tái cấu trúc

Ngày kiểm chứng: 16/10/2026. Phạm vi: workspace GarenaShop_DB, cấu trúc thư mục mới và UI Zero-Raw-JSON.

## Kết quả đã chạy

| Bộ kiểm thử | Kết quả |
|---|---|
| Nghiệp vụ CSDL (được role suite gọi trên DB tạm) | 12/12 PASS |
| Role / HTTP / Chrome / SQL | 79/79 PASS |
| Tám phân hệ AI độc lập, AI1 EasyOCR thật | 8/8 PASS |
| HTML/MIME, tách CSS/JS, asset, page guards | 6/6 PASS |

Exit code các suite: 0. JavaScript kiểm tra bằng node --check; Python parse theo grammar 3.12. Không sửa policy hoặc tắt RLS để đạt PASS.

## Môi trường và máy chủ

Windows; Python thực chạy 3.14.3, PostgreSQL 17.11; Chrome headless; EasyOCR CPU. Chưa chạy runtime Python 3.12/PostgreSQL 16 trực tiếp.

Server mới đang phục vụ cổng 8000. / và /index.html trả HTML UTF-8; /css, /js, /assets trả đúng MIME. Guest mở trang nội bộ bị chuyển về /index.html?error=unauthorized. Chrome trên cổng thật tải card và ảnh thành công, không có lỗi JavaScript.

## Các hạng mục hoàn tất

- Đổi models thành database, đổi tên controller/config/scripts/tests và cập nhật import.
- Tách bốn CSS và bốn JS; ba HTML không còn CSS/script logic inline.
- Navbar theo role: Guest/User ẩn Staff/Admin/API; Staff ẩn Admin/API. Ví, nạp tiền và lịch sử nằm trên Navbar User.
- Admin/Staff login chuyển trang ngay; User login trên Client cập nhật tại chỗ, đổi từ trang nội bộ về /index.html. Logout thu hồi phiên, dọn DOM/storage ứng dụng và về trang chủ.
- Ảnh Pillow: một banner, ba logo minh họa, tám thumbnail cho tám nick hiện hữu; 8/8 URL ảnh DB là local.
- AI4 cards; OCR form/badges; AI6 matching cards; AI7 health bars; AI8 risk/verdict; biên lai/credentials dùng nhãn.
- Xóa .runtime và cache source; model/DLL/browser QA cần thiết giữ dưới .venv và được gitignore.
- Bản đặc tả gốc và báo cáo cũ được lưu tại docs/archive; không còn file mock/SQL demo trong views.

## Phạm vi và giới hạn

SePay/thẻ cào là mock; QR động dùng dịch vụ ngoài, không thực hiện chuyển tiền thật. AI8 chỉ đề xuất hoàn tiền. AI7 thống kê dead tuples, không đo physical bloat. Test index có nhánh ép planner để minh họa, không chứng minh tăng tốc trên dữ liệu lớn. Phiên lưu trong bộ nhớ của một process. Partition hiện có cho 2025/2026.

## Bằng chứng

- docs/test_results/role_ui.json: kết quả role/UI có cấu trúc.
- docs/test_results/ai_modules.json: kết quả tám AI.
- tests/artifacts/role_ui/baseline.log: 12 nhóm nghiệp vụ và cleanup.
- tests/artifacts/role_ui/: screenshots/log Chrome và server.
- tests/artifacts/live-port8000.png: ảnh chụp server đang phục vụ thực tế.

Artifacts test được gitignore; có thể sinh lại bằng các lệnh trong README.

## Chi tiết role / UI

| STT | Role | Kiểm tra | Kết quả |
|---:|---|---|---|
| 1 | BASELINE | Existing business suite | PASS |
| 2 | GUEST | Only Chua_ban in public catalog | PASS |
| 3 | GUEST | Public credentials masked | PASS |
| 4 | ASSETS | Catalog uses existing local product images | PASS |
| 5 | ROLE | Wrong role redirects without exposing protected HTML | PASS |
| 6 | GUEST | Protected API denies anonymous | PASS |
| 7 | GUEST | Internal pages redirect/deny | PASS |
| 8 | USER | Insufficient funds rolls back | PASS |
| 9 | NAV | Guest only sees catalog and login | PASS |
| 10 | GUEST | UI login gate heart | PASS |
| 11 | GUEST | UI login gate cart | PASS |
| 12 | GUEST | Wallet actions hidden until customer login | PASS |
| 13 | GUEST | AI4 browser chat | PASS |
| 14 | UI | AI4 renders product cards with local thumbnails | PASS |
| 15 | ROLE | Automatic login routing user | PASS |
| 16 | ROLE | Customer login updates Client without reloading | PASS |
| 17 | NAV | User only sees catalog and customer actions | PASS |
| 18 | USER | Profile displays customer id | PASS |
| 19 | USER | QR parameters and deposit modal | PASS |
| 20 | USER | SePay UI updates wallet immediately | PASS |
| 21 | USER | SePay replay idempotency | PASS |
| 22 | USER | Invalid card red API error | PASS |
| 23 | USER | Valid card credits denomination | PASS |
| 24 | USER | Wishlist toggle persists | PASS |
| 25 | USER | Cart countdown visible | PASS |
| 26 | USER | Held nick hidden from other visitors | PASS |
| 27 | USER | Checkout state and wallet | PASS |
| 28 | USER | Owned credentials modal | PASS |
| 29 | USER | Unowned credentials denied | PASS |
| 30 | USER | History filters and receipt dialogs | PASS |
| 31 | UI | Client no horizontal overflow 1440 | PASS |
| 32 | UI | Client no horizontal overflow 390 | PASS |
| 33 | USER | Credentials cleared on logout | PASS |
| 34 | NAV | Logout restores Guest navbar and clears token | PASS |
| 35 | ROLE | Automatic login routing staff | PASS |
| 36 | NAV | Staff sees workspace without Admin or API | PASS |
| 37 | STAFF | No delete/password controls | PASS |
| 38 | STAFF | OCR button accepts pasted image URL | PASS |
| 39 | STAFF | Actual upload OCR -> JSONB | PASS |
| 40 | STAFF | OCR refreshes editable JSONB | PASS |
| 41 | UI | OCR attributes use form fields and badges | PASS |
| 42 | STAFF | Saving after OCR preserves extracted data | PASS |
| 43 | STAFF | Sanitized reconciliation view | PASS |
| 44 | STAFF | Lookup filter by customer/transaction | PASS |
| 45 | STAFF | AI6 fuzzy UI suggestions | PASS |
| 46 | UI | Staff no horizontal overflow 1440 | PASS |
| 47 | UI | Staff no horizontal overflow 390 | PASS |
| 48 | STAFF | Reconciliation cleared on logout | PASS |
| 49 | ROLE | Automatic login routing admin | PASS |
| 50 | NAV | Admin sees all navigation links | PASS |
| 51 | ROLE | Staff cannot navigate to Admin page | PASS |
| 52 | ADMIN | Eight AI cards in central UI | PASS |
| 53 | ADMIN | Editor exposes all mutable columns | PASS |
| 54 | UI | AI7 renders health bars | PASS |
| 55 | UI | AI8 renders risk bar and verdict card | PASS |
| 56 | UI | Admin no horizontal overflow 1440 | PASS |
| 57 | UI | Admin no horizontal overflow 390 | PASS |
| 58 | ROLE | Account switch redirects to staff | PASS |
| 59 | ROLE | Account switch redirects to user | PASS |
| 60 | NAV | Switching to User removes all internal links | PASS |
| 61 | ROLE | User login on index refreshes identity without navigation | PASS |
| 62 | NAV | User logout returns to Guest home | PASS |
| 63 | UI | No uncaught browser JavaScript exceptions | PASS |
| 64 | STAFF | DB deny SELECT | PASS |
| 65 | STAFF | DB deny SELECT | PASS |
| 66 | STAFF | DB deny DELETE | PASS |
| 67 | STAFF | DB deny UPDATE | PASS |
| 68 | STAFF | DELETE API denied | PASS |
| 69 | STAFF | Password UPDATE API denied | PASS |
| 70 | STAFF | SePay manual reconcile idempotent | PASS |
| 71 | ADMIN | Create/update credentials/delete unsold/FK sold | PASS |
| 72 | ADMIN | ETL CSV validation | PASS |
| 73 | ADMIN | AI2 floor 50000 and aged inventory | PASS |
| 74 | ADMIN | AI3 revokes paid credentials | PASS |
| 75 | ADMIN | AI5 churn voucher | PASS |
| 76 | ADMIN | AI7 diagnostics and VACUUM | PASS |
| 77 | ADMIN | AI8 risk >80 proposes full refund | PASS |
| 78 | ADMIN | Terminal HTTP action logs | PASS |
| 79 | ADMIN | Actor-attributed audit trail for each action | PASS |
