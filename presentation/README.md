# MediCheck Presentation

> **Deck nộp cho BTC (Deliverable #7) là [`../docs/pitch-deck.pdf`](../docs/pitch-deck.pdf)**
> — 17 trang, bản trình bày phase 2 (có khảo sát 113 người dùng, benchmark OCR và
> scorecard đánh giá LLM). Thư mục này giữ **file nguồn**: deck dựng bằng code và các
> slide lẻ dùng để ghép vào deck chính.

## Deck dựng bằng code (phase 1)

- `pitch_deck.pptx` — deck PowerPoint 12 slide, có thể chỉnh sửa.
- `pitch_deck.pdf` — bản PDF để xem hoặc gửi nhanh.
- `speaker_notes_vi.md` — lời dẫn ngắn theo từng slide.
- `generate_pitch_deck.js` — mã nguồn tạo lại deck.

## Nội dung 12 slide

1. Giới thiệu MediCheck
2. Bài toán và khoảng trống
3. Giải pháp
4. Hai nhóm người dùng
5. Trải nghiệm tra cứu
6. Kết quả tương tác
7. Human-in-the-loop
8. Kiến trúc hệ thống
9. Pipeline AI Agent và an toàn
10. Nền tảng kỹ thuật
11. SWOT và roadmap
12. Team và Q&A

## Slide lẻ tạo riêng

Mỗi file dựng đúng 1 slide (không cắt từ deck đầy đủ — cắt mảng slide nội bộ làm
file pptx hỏng, xem đầu `generate_eval_slide.js`), dùng để dán vào deck chính:

- `generate_architecture_slide.js` → `07_kien_truc_slide.pptx` — sơ đồ kiến trúc,
  vẽ theo code thật (có ocr-service trên Modal, Supabase + CockroachDB nằm ngoài
  Docker, DeepSeek do tầng dịch vụ gọi chứ không phải LangGraph gọi).
- `generate_eval_slide.js` → `08_danh_gia_llm_slide.pptx` — scorecard đánh giá LLM.
- `generate_survey_slide.js` → `01_khao_sat_nguoi_dung_slide.pptx` — khảo sát người dùng.

## Tạo lại file PowerPoint

```powershell
npm install --prefix presentation --no-package-lock --no-save pptxgenjs
node presentation/generate_pitch_deck.js
node presentation/generate_architecture_slide.js
```

Đóng file .pptx trong PowerPoint trước khi chạy, nếu không script báo `EBUSY`.

Ảnh minh họa được lấy trực tiếp từ `docs/screenshots/` của dự án.

## Logo trong slide kiến trúc

`logos/*.png` là logo hãng lấy từ [Simple Icons](https://simpleicons.org) (SVG một
path, màu thương hiệu) rồi rasterize sang PNG nền trong suốt. Tải lại khi cần:

```powershell
npm install --prefix presentation --no-package-lock --no-save pptxgenjs sharp
node -e "const fs=require('fs'),sharp=require('presentation/node_modules/sharp');(async()=>{for(const s of ['nextdotjs','docker','fastapi','langgraph','postgresql','deepseek','supabase','cockroachlabs','modal','vercel','render']){const b=Buffer.from(await (await fetch('https://cdn.simpleicons.org/'+s)).arrayBuffer());await sharp(b,{density:600}).resize({height:256}).png().toFile('presentation/logos/'+s+'.png');}})()"
```

`langgraph` và `modal` được lấy ở mã màu đậm hơn (`/1C3C3C`, `/2E9E4F`) vì màu
thương hiệu gốc quá nhạt trên nền trắng. Thiếu file logo nào thì khối tương ứng
trong slide tự lùi về chỉ hiển thị chữ, script vẫn chạy bình thường.
