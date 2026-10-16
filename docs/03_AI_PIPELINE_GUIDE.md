# Hướng dẫn ETL và tám phân hệ AI

| Module | Đầu vào → xử lý → đầu ra |
|---|---|
| `etl_data_cleaner` | CSV → trim/uppercase, chuẩn SĐT, Decimal không âm → upsert tên/SĐT/ngày cập nhật, giữ ví hiện hữu |
| `ai1_vision_ocr` | Upload base64, HTTPS allowlist hoặc ảnh sản phẩm local hợp lệ → EasyOCR CPU → Rank/Skin/Vũ khí, merge JSONB và ghi log trong cùng transaction |
| `ai2_dynamic_pricing` | Hàm SQL → tồn >30 ngày, chưa bán → giảm 5%, làm tròn nghìn, sàn 50.000đ |
| `ai3_fraud_guard` | Mã nick → khóa tranh chấp → RLS từ chối credentials ngay |
| `ai4_nl2sql_chatbot` | Tiếng Việt → parser game/giá/skin/vũ khí → SQL tham số với JSONB `@>`, chỉ nick chưa bán |
| `ai5_smart_marketing` | Lịch sử mua phân mảnh → không mua >60 ngày → churn score và upsert voucher TRIAN20PCT |
| `ai6_sepay_reconcile` | Nội dung chuyển khoản → chuẩn hóa, SequenceMatcher → ba ứng viên và câu trả lời gợi ý, không cộng tiền |
| `ai7_auto_dba` | `pg_stat_user_tables` → tỷ lệ dead tuples >10% → khuyến nghị VACUUM ANALYZE; thực thi chỉ bảng allowlist |
| `ai8_dispute_arbiter` | Mã nick và bằng chứng → điểm quy tắc 0–100 → đề xuất hoàn đủ tiền đơn nếu >80, chưa tự thực hiện |

## OCR

Model cache đặt tại `.venv/ocr_models/`; Windows DLL app-local tùy chọn ở
`.venv/ocr_runtime/`. Chúng là dependency, không phải source. Lần tải model
đầu tiên cần Internet. `python scripts/check_ocr.py` kiểm chứng OCR thật trên
ảnh chữ sinh bằng Pillow, không ghi vào CSDL.

HTTPS phải nằm trong `OCR_ALLOWED_HOSTS`, không redirect và không truy cập
IP mạng nội bộ; ảnh giới hạn 5MB/20 megapixel. Đường dẫn local bị giới hạn
trong `views/assets/products/`, không được dùng để đọc file tùy ý.

Screenshot gốc và thumbnail minh họa có mục đích khác nhau. Listener tự xử lý
ảnh nguồn của nick mới; bỏ qua thumbnail được sinh từ metadata để không tạo
vòng lặp OCR dữ liệu của chính hệ thống. Staff vẫn có thể chọn ảnh và chạy AI1.
Sau OCR form được cập nhật từ DB; lưu lại không làm mất Skin/ngày nhập kho.

## Hiển thị và giới hạn

AI trả dict/list cho API nhưng UI bọc thành cards, nhãn, badges và progress.
AI7 hiển thị tỷ lệ dòng chết ước lượng, không dùng nhãn physical bloat.
Điểm AI8 không phải xác suất ML. AI6/AI8 cần người xác nhận; quyết định hoàn
tiền thật và webhook thanh toán thật không thuộc demo này.

Chạy kiểm thử độc lập: `python tests/test_all_ai_modules.py`. Script tạo DB
tạm, khởi tạo schema, chạy đủ tám module (AI1 thật) rồi drop DB trong finally.
