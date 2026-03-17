import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal, engine

async def test_connection():
    print("--- Đang kiểm tra kết nối Database ---")
    try:
        # Thử mở một session và thực hiện câu lệnh đơn giản
        async with AsyncSessionLocal() as session:
            # Câu lệnh 'SELECT 1' là cách nhanh nhất để check xem DB còn sống không
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            
            if value == 1:
                print("✅ KẾT NỐI THÀNH CÔNG!")
                print(f"Cơ sở dữ liệu đã sẵn sàng tại: {engine.url}")
            else:
                print("❓ Kết nối được nhưng kết quả trả về không xác định.")
                
    except Exception as e:
        print("❌ KẾT NỐI THẤT BẠI!")
        print(f"Lỗi chi tiết: {str(e)}")
        
        # Gợi ý xử lý dựa trên lỗi
        if "password authentication failed" in str(e):
            print("👉 Lời khuyên: Kiểm tra lại MẬT KHẨU trong file .env (nhớ mã hóa @ thành %40).")
        elif "does not exist" in str(e):
            print("👉 Lời khuyên: Kiểm tra lại TÊN DATABASE trong file .env.")
        elif "is not accepting connections" in str(e):
            print("👉 Lời khuyên: Đảm bảo dịch vụ PostgreSQL đang CHẠY (Start trong Services).")

if __name__ == "__main__":
    asyncio.run(test_connection())