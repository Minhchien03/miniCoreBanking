from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()

# Cấu hình bộ não Gemini [cite: 16, 45]
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# 1. Agent Trưởng phòng (Planner) - Điều phối lộ trình 4 tuần 
planner = Agent(
    role='Lead Project Manager',
    goal='Điều phối các Agent khác hoàn thành đúng tiến độ dự án MiniCore',
    backstory='Chuyên gia quản lý dự án Fintech, đảm bảo mọi task tuân thủ tính ACID và Ledger[cite: 12, 19].',
    llm=llm
)

# 2. Agent Backend (Developer) - Thực thi code [cite: 26, 27]
developer = Agent(
    role='Senior Backend Developer',
    goal='Viết code FastAPI sạch, Async và xử lý logic Sổ cái[cite: 11, 26].',
    backstory='Bậc thầy Python 3.12, luôn sử dụng decimal cho tiền tệ[cite: 10, 13].',
    llm=llm
)

# 3. Agent Kiến trúc sư (Architect/Auditor) - Kiểm soát lỗi [cite: 28, 34]
architect = Agent(
    role='DB & Security Architect',
    goal='Xử lý Race Condition và Audit giao dịch[cite: 29, 42].',
    backstory='Chuyên gia PostgreSQL, người sẽ cài đặt SELECT FOR UPDATE ở Tuần 2[cite: 12, 34].',
    llm=llm
)

# Nhiệm vụ đầu tiên: Lập kế hoạch chuyển từ Tuần 1 sang Tuần 2 
task_transition = Task(
    description="""
    Review lại code hiện tại (database.py, models.py, transfer.py).
    Lên kế hoạch chi tiết để triển khai Tuần 2: Tấn công Hệ thống & Xử lý Race Condition.
    Yêu cầu chuẩn bị script stress_test.py[cite: 32, 50].
    """,
    expected_output="Bản kế hoạch triển khai kỹ thuật cho Tuần 2 và các chỉnh sửa cần thiết cho Tuần 1.",
    agent=planner
)

# Khởi tạo Crew
mini_core_dept = Crew(
    agents=[planner, developer, architect],
    tasks=[task_transition],
    process=Process.sequential
)

print(mini_core_dept.kickoff())