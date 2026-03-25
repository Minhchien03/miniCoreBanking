import asyncio
import httpx
import time

# Chú ý: Đổi port hoặc URL nếu bạn cấu hình prefix khác trong main.py
# API_URL = "http://127.0.0.1:8000/api/v1/transfer" 
# NUM_REQUESTS = 1000

# OUTPUT_FILE = "stress_test_results.md"

# PAYLOAD = {
#     "sender_id": "cc4540b5-5d32-4c02-9d2d-664a4ab73cf1", 
#     "receiver_id": "acdfa4f7-3b6e-4c94-8ea1-da62a7748911",
#     "amount": 100000 
# }

API_URL = "http://127.0.0.1:8000/api/v1/transfer" 
NUM_REQUESTS = 1000

OUTPUT_FILE = "stress_test_results.md"

PAYLOAD = {
    "sender_id": "cc4540b5-5d32-4c02-9d2d-664a4ab73cf1", 
    "receiver_id": "acdfa4f7-3b6e-4c94-8ea1-da62a7748911",
    "amount": 100000 
}

async def make_request(client: httpx.AsyncClient, req_id: int):
    try:
        response = await client.post(API_URL, json=PAYLOAD)
        if response.status_code == 200:
            return f" [Req {req_id}] THÀNH CÔNG: Đã trừ 10.000đ"
        else:
            return f"[Req {req_id}] TỪ CHỐI: {response.json().get('detail')}"
    except Exception as e:
        return f"[Req {req_id:03d}] LỖI MẠNG: {str(e)}"

async def main():
    print(f"Bắn {NUM_REQUESTS} request cùng lúc vào API...")
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Tạo 100 task chạy đồng thời
        tasks = [make_request(client, i) for i in range(NUM_REQUESTS)]
        results = await asyncio.gather(*tasks)
    elapsed_time = time.time() - start_time
    
    # ---------------------------------------------------------
    # BƯỚC 2: TÍNH TOÁN THỐNG KÊ & GHI RA FILE MARKDOWN
    # ---------------------------------------------------------
    success_count = sum(1 for r in results if "✅" in r)
    fail_count = sum(1 for r in results if "❌" in r)
    
    print(f"Xong! Thời gian: {elapsed_time:.2f}s")
    print(f" Đang lưu báo cáo ra file {OUTPUT_FILE}...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# Báo cáo Stress Test: {OUTPUT_FILE}\n\n")
        f.write("### Thống kê tổng quan\n")
        f.write(f"- **Tổng số request:** {NUM_REQUESTS}\n")
        f.write(f"- **Thành công (Trừ tiền):** {success_count} \n")
        f.write(f"- **Bị từ chối (Chặn lại):** {fail_count} \n")
        f.write(f"- **Thời gian thực thi:** {elapsed_time:.2f} giây\n\n")
        
        f.write("### Chi tiết Terminal Log\n")
        f.write("```text\n")
        for res in results:
            f.write(res + "\n")
        f.write("```\n")
        
    print(f"⏱️ Tổng thời gian tấn công: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())