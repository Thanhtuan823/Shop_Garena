# GarenaShop_DB — Đặc tả hệ thống

Ứng dụng demo Fullstack MVC: PostgreSQL 16/17, Python 3.12+, FastAPI,
psycopg2, HTML/CSS và JavaScript thuần. SePay/thẻ cào là mô phỏng.
Tài liệu hiện hành nằm trong sáu file đánh số của `docs/`; bản đặc tả ban đầu
và báo cáo cũ được bảo quản trong `docs/archive/`.

## Cấu trúc và trách nhiệm

- `database/`: DDL, views, RBAC, RLS, indexes, partitioning, triggers và bảo trì.
- `config/database.py`: SimpleConnectionPool 1–20, lock/semaphore, transaction.
- `config/auth.py`: PBKDF2, bearer token và kiểm tra vai trò.
- `controllers/shop_service.py`: ví, giỏ hàng, checkout, đối soát idempotent.
- `controllers/ai1_*.py` đến `ai8_*.py`: tám phân hệ có đầu vào/đầu ra rõ ràng.
- `views/`: ba HTML; `css/` và `js/` tách riêng; ảnh nội bộ dưới `assets/`.
- `scripts/`: khởi tạo/seed và vẽ artwork bằng Pillow.
- `tests/`: nghiệp vụ CSDL, HTTP/Chrome theo role, tám AI, MIME/static delivery.

## Ma trận vai trò

| Chức năng | Guest | User | Staff | Admin |
|---|---|---|---|---|
| Kho nick mở bán, AI4 | Có | Có | Có | Có |
| Wishlist, ví, giữ chỗ 15 phút, checkout | Không | Dữ liệu của mình | Không | Không |
| Credentials | Không | Nick đã mua, không tranh chấp | Không | Qua quản trị |
| Tạo nick | Không | Không | Có | Có |
| Sửa nick | Không | Không | Giá, trạng thái, metadata, ảnh | Toàn bộ trường API cho phép |
| Xóa nick | Không | Không | Không | Có, chịu FK RESTRICT |
| Đối soát nạp tiền vắn tắt, AI6 | Không | Không | Có | Có |
| Sửa trực tiếp số dư khách | Không | Không | Không | Không có endpoint CRUD ví |
| ETL, AI2/3/5/7/8, VACUUM | Không | Không | Không | Có |

Admin/Staff đăng nhập từ trang chủ được chuyển sang `/admin.html` và
`/staff.html`. User đăng nhập trên Client được cập nhật trạng thái tại chỗ;
đổi sang User từ trang nội bộ được đưa về `/index.html`. Backend kiểm tra phiên trước khi trả
HTML nội bộ; sai phiên/role chuyển về `/index.html?error=unauthorized`. Guard frontend
kiểm tra lại phiên và che nội dung trong lúc xác thực.

Navbar mặc định chỉ có Kho nick và Đăng nhập. User có Kho nick, ví, nạp tiền,
lịch sử và Đăng xuất; Staff có Kho nick và Bàn làm việc Staff; Admin có đầy đủ
Kho nick/Staff/Admin/API. Menu nội bộ ẩn sẵn trong HTML, chỉ hiện sau xác thực.
`renderNavbarByRole()` cập nhật menu khi tải trang, đăng nhập và đăng xuất.

## Quy tắc bảo mật và dữ liệu

Public catalog luôn che mật khẩu và email khôi phục. Credentials dùng RLS
trên bảng gốc, nhận danh tính từ phiên đã xác thực qua transaction-local
`app.current_user_id`. Chỉ service được truy cập DB, không cung cấp SQL/GUC
cho người dùng cuối. Pool rollback và reset ROLE/GUC/LISTEN khi trả kết nối.

Nạp tiền dùng mã giao dịch duy nhất và fingerprint thẻ. Checkout khóa dòng
ví, giỏ, nick trong cùng transaction; không ghi đơn/trừ tiền một phần.
ETL không ghi đè số dư khi upsert; OCR merge JSONB để giữ ngày nhập kho.
Logout thu hồi token/cookie, xóa các khóa `shop_` trong cả hai storage,
dọn DOM và hủy/loại phản hồi riêng tư cũ, rồi về trang chủ.

## Zero-Raw-JSON và ảnh nội bộ

JSON vẫn là giao thức API, không phải nội dung trình bày cho người dùng.
Chatbot trả card; OCR dùng form Rank/Skin/Vũ khí và badges; AI6 matching
cards; AI7 thanh tỷ lệ dòng chết; AI8 risk bar và card đề xuất.
Biên lai/credentials dùng nhãn thông tin. Lỗi API dùng toast, xác nhận dùng
modal. Nội dung động luôn được escape trước khi chèn HTML.

`generate_product_images.py --sync-db` vẽ banner, ba logo minh họa và ảnh
theo metadata từng nick, cập nhật URL `/assets/products/...`. Không sửa giá,
ví hoặc mật khẩu. Thumbnail là minh họa, không phải ảnh OCR chứng minh nick.
Ảnh gốc OCR được nhập/upload riêng; không tự OCR lại thumbnail sinh sẵn.

## Giới hạn triển khai

Phiên lưu trong bộ nhớ, hết hạn sau một giờ, phục vụ một process localhost.
AI4 là parser hữu hạn; AI6/AI8 là quy tắc hỗ trợ người vận hành. AI8 chỉ
đề xuất hoàn tiền, không tự chuyển tiền. AI7 thống kê dead tuples, không
khẳng định đo bloat vật lý. Không cam kết thời gian truy vấn dưới 1ms.
