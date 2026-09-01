# Lời dẫn thuyết trình — MediCheck

## 1. Mở đầu

Giới thiệu MediCheck là AI Agent hỗ trợ kiểm tra tương tác thuốc, nhấn mạnh đây không phải bác sĩ ảo.

## 2. Bài toán

Nêu ba nỗi đau: bệnh nhân dùng nhiều thuốc, thông tin phân mảnh, dược sĩ thiếu thời gian.

## 3. Giải pháp

Trình bày pipeline từ nhập thuốc đến guardrail và review; nhấn mạnh dữ liệu trước, AI sau.

## 4. Người dùng

So sánh mục tiêu của bệnh nhân và dược sĩ; giải thích vòng phản hồi hai chiều.

## 5. Trải nghiệm

Demo landing page: nhập tên, autocomplete, tra cứu nhanh, đăng nhập khi cần lưu lịch sử.

## 6. Kết quả

Giải thích đồ thị và màu mức độ; nhắc disclaimer không tự đổi hoặc ngừng thuốc.

## 7. HITL

Cho thấy ca rủi ro đi từ bệnh nhân sang hàng đợi dược sĩ và quay lại dưới dạng xác nhận.

## 8. Kiến trúc

Đi qua bốn lớp: Next.js, FastAPI, LangGraph, dữ liệu; DeepSeek chỉ sinh giải thích.

## 9. AI Agent

Giới thiệu 5 node và các lớp an toàn: DDInter, citation, guardrail, dược sĩ.

## 10. Kỹ thuật

Tóm tắt tech stack và đường triển khai Docker → staging → production.

## 11. Phân tích

Trình bày SWOT ngắn và roadmap ưu tiên đo lường, pilot, hardening rồi mới mở rộng.

## 12. Kết

Giới thiệu team, nhắc lại thông điệp và mời Q&A.
