# MediCheck Presentation

## Bản thuyết trình hoàn chỉnh

- `pitch_deck_medicheck_vi.pptx` — deck PowerPoint 12 slide, có thể chỉnh sửa.
- `pitch_deck_medicheck_vi.pdf` — bản PDF để xem hoặc gửi nhanh.
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

## Tạo lại file PowerPoint

```powershell
npm install --prefix presentation --no-package-lock --no-save pptxgenjs
node presentation/generate_pitch_deck.js
```

Ảnh minh họa được lấy trực tiếp từ `docs/screenshots/` của dự án.
