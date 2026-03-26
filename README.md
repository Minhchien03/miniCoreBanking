
# 🏦 Hệ thống Mini Core Banking

**Mini Core Banking** là một dự án mô phỏng hệ thống ngân hàng cốt lõi (Core Banking System) thu nhỏ. Dự án được thiết kế để mô phỏng các chức năng chuyển tiền, nạp tiền vào tài khoản. Tập trung vào tính toàn vẹn của dữ liệu khi giao dịch, ngăn chặn các lỗi đồng thời (concurrency issues) và cung cấp khả năng truy xuất nguồn gốc rõ ràng cho mọi biến động số dư, tuân thủ nghiêm ngặt các nguyên tắc ACID

## 🌟 Tính năng chính

* **Tuân thủ ACID**: Đảm bảo tất cả các giao dịch tài chính hoàn toàn tuân thủ các nguyên tắc ACID bằng cách sử dụng các khối giao dịch (transaction blocks) ở cấp độ cơ sở dữ liệu.
  
* **Kiểm soát đồng thời (Chống chi tiêu kép - Anti-Double Spending)**: Áp dụng cơ chế **Khóa bi quan (Pessimistic Locking)** (`SELECT ... FOR UPDATE`) để xử lý an toàn các yêu cầu chuyển tiền đồng thời và ngăn chặn tình trạng tương tranh (race conditions).
  
* **Sổ cái kép (Double-Entry Ledger)**: Các biến động tài chính được ghi lại dưới dạng các bút toán sổ cái (nợ/có) chỉ ghi thêm (append-only) không thể thay đổi, đảm bảo khả năng kiểm toán toàn diện.
  
* **Quản lý lỗi tập trung**: Tầng router (điều hướng) gọn gàng đạt được bằng cách định tuyến tất cả các lỗi logic nghiệp vụ thông qua một trình xử lý `BusinessException` tập trung.
  
* **Truy vết phân tán & Khả năng quan sát (Observability)**: `TraceIDMiddleware` tùy chỉnh tạo ra một UUID duy nhất cho mỗi request, UUID này tự động được đính kèm vào tất cả các log của ứng dụng giúp quá trình gỡ lỗi (debugging) diễn ra liền mạch.
  
* **Kiến trúc bất đồng bộ**: Tương tác với cơ sở dữ liệu hoàn toàn bất đồng bộ sử dụng `SQLAlchemy Async` và `asyncpg` để đạt thông lượng (throughput) tối đa.
  
* **Kiểm thử tự động (Automated Testing)**: Bộ test `pytest` mô phỏng các tình trạng race condition, concurrent attacks, database failures, and transaction rollbacks

## 🛠️ Công nghệ sử dụng (Tech Stack)

* **Framework**: FastAPI (Python)
* **Cơ sở dữ liệu**: PostgreSQL
* **ORM**: SQLAlchemy 2.0 (Async)
* **Container**: Docker & Docker Compose
* **Testing**: Pytest & HTTPX
* **Tích hợp AI**: Dự án có sử dụng AI Agents (CrewAI, LLM).

## 🚀 Hướng dẫn cài đặt

### Yêu cầu hệ thống

* Đã cài đặt Docker và Docker Compose trên máy của bạn.
* Python 3.10+ (nếu chạy test ở máy local không dùng Docker).
* postgreSQL 16.13

### Cài đặt & Chạy ứng dụng

1.  **Clone repository:**
    ```bash
    git clone https://github.com/Minhchien03/miniCoreBanking
    cd mini-core-banking
    ```

2.  **Biến môi trường (Environment Variables):**
    Tạo một file `.env` ở thư mục gốc và cấu hình thông tin đăng nhập cơ sở dữ liệu của bạn:
    ```env
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=your_secure_password
    POSTGRES_DB=core_banking_db
    GEMINI_API_KEY=your_gemini_api_key_here # Dành cho các tính năng AI Agent (tùy chọn)
    ```

3.  **Khởi chạy bằng Docker Compose:**
    ```bash
    docker-compose up -d --build
    ```
    Lệnh này sẽ khởi chạy backend FastAPI, cơ sở dữ liệu PostgreSQL và các instance Redis.

4.  **API Documentation:**
    * Swagger UI: http://localhost:8000/docs`
    * ReDoc: http://localhost:8000/redoc`

## 📖 Tài liệu API

Các endpoint cốt lõi xoay quanh các hoạt động ngân hàng cơ bản:

* `POST /api/v1/accounts`: Tạo tài khoản ngân hàng mới.
* `POST /api/v1/deposit`: Nạp tiền vào tài khoản (tạo ra một bút toán Có/Credit trong sổ cái).
* `POST /api/v1/transfer`: Chuyển tiền an toàn giữa hai tài khoản.
* `POST /api/v1/transfer_bad`: *API dùng để minh họa* - Một endpoint cố tình được viết kém, không có logic rollback để chứng minh những hậu quả thảm khốc của việc lỗi hệ thống trong quá trình giao dịch.

## 🧪 Kiểm thử (Testing)

Dự án bao gồm một bộ kiểm thử nghiêm ngặt được thiết kế để "phá" hệ thống và chứng minh khả năng phục hồi của nó trước các kịch bản thực tế.

Để chạy các bài test ở local:
```bash
pip install -r requirements.txt
pytest test_cases/ -v
```

### Các kịch bản kiểm thử đáng chú ý:
* **`test_race_condition.py`**: Bắn nhiều yêu cầu chuyển tiền đồng thời tại cùng một phần nghìn giây. Khẳng định rằng chỉ có 1 request thành công và phần còn lại bị chặn, chứng minh hiệu quả của cơ chế khóa bi quan (pessimistic locking) trong việc chống chi tiêu kép.
* **`test_transfer_sad_path_db_rollback`**: Cố ý phá hỏng kết nối cơ sở dữ liệu giữa chừng giao dịch để chứng minh cơ chế tự động rollback hoạt động và không có đồng tiền nào của người dùng bị "bốc hơi".
* **`test_transfer_bad_no_rollback_disaster`**: Thể hiện chế độ lỗi của endpoint `/transfer_bad` nơi tiền bị trừ nhưng việc ghi sổ cái thất bại, khiến hệ thống rơi vào trạng thái dữ liệu không nhất quán.
