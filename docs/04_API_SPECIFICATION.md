# REST API

Xem schema OpenAPI đầy đủ tại `/docs` hoặc `/openapi.json` khi server chạy.
API riêng tư dùng `Authorization: Bearer <token>`. Cookie HttpOnly chỉ hỗ trợ
điều hướng HTML, không thay bearer cho API. Không nhận role/ma_kh giả lập từ UI.

| Method | Endpoint | Quyền / payload chính |
|---|---|---|
| POST | `/api/auth/register` | Public: username, password (>=8), ho_ten, so_dien_thoai |
| POST | `/api/auth/login` | Public: username, password; trả token và principal |
| GET | `/api/auth/me` | Đã đăng nhập |
| POST | `/api/auth/logout` | Thu hồi bearer/cookie hiện tại |
| GET | `/api/games`, `/api/accounts` | Public; catalog chỉ Chua_ban và che credentials |
| GET | `/api/manage/accounts` | Staff/Admin; Staff không có cột bí mật |
| POST | `/api/accounts/create` | Staff/Admin: ma_nick, ma_game, gia_ban, metadata và ảnh tùy chọn |
| PUT | `/api/accounts/{ma_nick}/update` | Staff chỉ cột public; Admin được đổi credentials |
| DELETE | `/api/admin/accounts/{ma_nick}/delete` | Admin; FK RESTRICT trả 409 |
| POST | `/api/accounts/{ma_nick}/ocr` | Staff/Admin: image_url (HTTPS/base64/local) |
| GET | `/api/accounts/{ma_nick}/credentials` | User sở hữu đơn, kiểm tra RLS |
| POST | `/api/user/deposit/sepay` | User: amount, event_id, description=`NAP <ma_kh>` |
| POST | `/api/user/deposit/card` | User: amount, event_id, serial=`#GARENA*...`, card=`$CARD&...` |
| GET | `/api/user/profile/{ma_kh}` | User đúng chủ hồ sơ |
| GET | `/api/user/transactions/{ma_kh}` | User đúng chủ; biến động ví |
| GET | `/api/user/transaction-detail/{ma_gd}` | User đúng chủ biên lai |
| GET | `/api/user/orders` | User: đơn của mình |
| GET/POST | `/api/user/wishlist` | User; POST ma_nick |
| DELETE | `/api/user/wishlist/{ma_nick}` | User |
| GET | `/api/user/cart` | User; deadline và seconds_left |
| POST | `/api/user/cart/add` | User: ma_nick; giữ chỗ 15 phút |
| DELETE | `/api/user/cart/{ma_nick}` | User bỏ giữ chỗ |
| POST | `/api/user/cart/checkout` | User; server tự tính tổng và tạo đơn ACID |
| POST | `/api/chat/nl2sql` | Public: prompt; trả list thông tin nick công khai |
| GET | `/api/staff/transactions` | Staff/Admin; lọc ma_kh, ma_giao_dich |
| POST | `/api/staff/recheck-sepay` | Staff/Admin: event_id, ma_kh; idempotent |
| POST | `/api/staff/ai6-reconcile-assistant` | Staff/Admin: prompt |
| POST | `/api/admin/run-etl`, `/run-pricing`, `/run-marketing` | Admin; prefix `/api/admin` cho từng route |
| POST | `/api/admin/lock-fraud/{ma_nick}` | Admin |
| GET | `/api/admin/ai7-diagnostics` | Admin |
| POST | `/api/admin/ai8-evaluate-dispute` | Admin: ma_nick, evidence_count, seller_unresponsive, recovery_changed |
| POST | `/api/admin/run-vacuum` | Admin: table trong allowlist |

Ví dụ nạp tiền mock:

```json
{"amount":"100000","event_id":"demo-transfer-unique-01","description":"NAP KH_DEMO"}
```

Giữ nguyên event_id khi retry; đổi số tiền/nội dung cần event_id mới. Nội dung
SePay sai được lưu Cho_duyet, chưa tăng ví. Cặp serial/card không dùng lại.

Mã phản hồi: 400/422 dữ liệu sai, 401 hết/thiếu phiên, 403 thiếu quyền,
409 xung đột nghiệp vụ/FK/CHECK/duplicate, 503 OCR chưa sẵn sàng.
UI chuyển lỗi thành toast; không đổ payload lỗi JSON lên màn hình.

HTML `/`, `/index.html`, `/staff.html`, `/admin.html` dùng UTF-8.
Static chỉ mount `/css`, `/js`, `/assets`, không mount toàn bộ `views/`.
