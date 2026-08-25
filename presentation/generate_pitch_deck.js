const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Team MediCheck — VMEC-12';
pptx.subject = 'Giới thiệu và phân tích dự án MediCheck';
pptx.title = 'MediCheck — Tra cứu thông minh, dùng thuốc an toàn';
pptx.company = 'AI20K Build Phase — Cohort 3';
pptx.lang = 'vi-VN';
pptx.theme = {
  headFontFace: 'Aptos Display',
  bodyFontFace: 'Aptos',
  lang: 'vi-VN',
};
pptx.defineSlideMaster({
  title: 'MEDICHECK',
  background: { color: 'F5F8FD' },
  objects: [
    { rect: { x: 0, y: 0, w: 13.333, h: 0.06, fill: { color: '4D73C9' }, line: { color: '4D73C9' } } },
    { text: { text: 'MEDICHECK  /  VMEC-12', options: { x: 0.55, y: 7.12, w: 3.0, h: 0.18, fontFace: 'Aptos', fontSize: 7.5, bold: true, color: '73829E', charSpacing: 1.4, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.08, w: 0.55, h: 0.22, color: '73829E', fontFace: 'Aptos', fontSize: 8, align: 'right', margin: 0 },
});

const C = {
  navy: '11284C',
  blue: '4D73C9',
  blue2: '7899E8',
  pale: 'E9F0FF',
  sky: 'D9E8FF',
  white: 'FFFFFF',
  bg: 'F5F8FD',
  text: '253B5F',
  muted: '667792',
  green: '2C9A83',
  greenPale: 'E1F5EF',
  amber: 'C68A2E',
  amberPale: 'FFF1D9',
  red: 'D54B4B',
  redPale: 'FFE5E2',
  purple: '8156BF',
  line: 'CBD8ED',
  dark: '071326',
};

const root = path.resolve(__dirname, '..');
const shots = {
  landing: path.join(root, 'docs', 'screenshots', 'landing-page.png'),
  result: path.join(root, 'docs', 'screenshots', 'interaction-result.png'),
  patient: path.join(root, 'docs', 'screenshots', 'patient-dashboard.png'),
  pharmacist: path.join(root, 'docs', 'screenshots', 'pharmacist-dashboard.png'),
  logo: path.join(root, 'frontend', 'public', 'Bộ nhận diện y tế', '2-cropped.png'),
};

function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString('ascii', 1, 4) !== 'PNG') throw new Error(`Không phải PNG: ${file}`);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

function contain(file, x, y, w, h) {
  const s = pngSize(file);
  const r = Math.min(w / s.w, h / s.h);
  const iw = s.w * r;
  const ih = s.h * r;
  return { path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih };
}

function cover(file, x, y, w, h) {
  return { path: file, x, y, w, h, sizing: { type: 'cover', w, h } };
}

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: opts.fontFace || 'Aptos',
    fontSize: opts.fontSize || 18,
    color: opts.color || C.text,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || 'left',
    valign: opts.valign || 'mid',
    margin: opts.margin === undefined ? 0 : opts.margin,
    breakLine: false,
    fit: 'shrink',
    lineSpacingMultiple: opts.lineSpacingMultiple || 1.0,
    paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
    bullet: opts.bullet,
    charSpacing: opts.charSpacing,
    isTextBox: true,
  });
}

function rect(slide, x, y, w, h, fill, radius = 0.16, line = fill) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: radius,
    fill: { color: fill },
    line: { color: line, width: line === fill ? 0 : 1 },
  });
}

function circle(slide, x, y, d, fill, line = fill) {
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill }, line: { color: line, width: line === fill ? 0 : 1 } });
}

function line(slide, x1, y1, x2, y2, color = C.line, width = 1.5, dash = 'solid') {
  slide.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width, dashType: dash, beginArrowType: 'none', endArrowType: 'none' } });
}

function arrow(slide, x1, y1, x2, y2, color = C.blue, width = 2) {
  if (x2 >= x1) {
    slide.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width, beginArrowType: 'none', endArrowType: 'triangle' } });
  } else {
    slide.addShape(pptx.ShapeType.line, { x: x2, y: y2, w: x1 - x2, h: y1 - y2, line: { color, width, beginArrowType: 'triangle', endArrowType: 'none' } });
  }
}

function title(slide, kicker, heading, subtitle) {
  addText(slide, kicker.toUpperCase(), 0.58, 0.34, 5.2, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.8 });
  addText(slide, heading, 0.58, 0.72, 12.1, 0.58, { fontSize: 27, bold: true, color: C.navy });
  if (subtitle) addText(slide, subtitle, 0.58, 1.31, 12.0, 0.42, { fontSize: 12.5, color: C.muted });
}

function badge(slide, text, x, y, w, fill = C.pale, color = C.blue) {
  rect(slide, x, y, w, 0.34, fill, 0.17);
  addText(slide, text, x + 0.1, y + 0.01, w - 0.2, 0.3, { fontSize: 9, bold: true, color, align: 'center' });
}

function card(slide, x, y, w, h, heading, body, accent = C.blue, index = '') {
  rect(slide, x, y, w, h, C.white, 0.18, C.line);
  slide.addShape(pptx.ShapeType.rect, { x, y, w: 0.08, h, fill: { color: accent }, line: { color: accent, width: 0 } });
  if (index) {
    circle(slide, x + 0.25, y + 0.27, 0.42, accent);
    addText(slide, index, x + 0.25, y + 0.28, 0.42, 0.38, { fontSize: 10, bold: true, color: C.white, align: 'center' });
  }
  addText(slide, heading, x + (index ? 0.82 : 0.28), y + 0.23, w - (index ? 1.02 : 0.56), 0.38, { fontSize: 15, bold: true, color: C.navy });
  addText(slide, body, x + 0.28, y + 0.73, w - 0.56, h - 0.91, { fontSize: 11.2, color: C.muted, valign: 'top', lineSpacingMultiple: 1.05 });
}

function imageFrame(slide, file, x, y, w, h, crop = true) {
  rect(slide, x - 0.04, y - 0.04, w + 0.08, h + 0.08, C.white, 0.16, C.line);
  slide.addImage(contain(file, x, y, w, h));
}

function addNotes(slide, notes) {
  if (typeof slide.addNotes === 'function') slide.addNotes(notes);
}

// Slide 1 — Cover
{
  const slide = pptx.addSlide('MEDICHECK');
  slide.background = { color: C.dark };
  slide.addShape(pptx.ShapeType.rect, { x: 7.15, y: 0, w: 6.183, h: 7.5, fill: { color: 'D8E6FF', transparency: 2 }, line: { color: 'D8E6FF', transparency: 100 } });
  slide.addImage(contain(shots.landing, 7.32, 0.4, 5.85, 6.7));
  slide.addShape(pptx.ShapeType.rect, { x: 6.75, y: 0, w: 1.2, h: 7.5, fill: { color: C.dark, transparency: 12 }, line: { color: C.dark, transparency: 100 } });
  slide.addShape(pptx.ShapeType.rect, { x: 0.58, y: 0.62, w: 1.1, h: 0.07, fill: { color: C.blue2 }, line: { color: C.blue2 } });
  addText(slide, 'VMEC-12  •  AI FOR MEDICATION SAFETY', 0.58, 0.82, 5.7, 0.3, { fontSize: 10, bold: true, color: '9AB6F4', charSpacing: 1.5 });
  addText(slide, 'MediCheck', 0.58, 1.42, 5.8, 0.82, { fontSize: 39, bold: true, color: C.white });
  addText(slide, 'Tra cứu thông minh,\ndùng thuốc an toàn', 0.58, 2.25, 5.9, 1.35, { fontSize: 31, bold: true, color: 'AFC8FF', valign: 'top' });
  addText(slide, 'AI Agent kiểm tra tương tác thuốc, giải thích bằng tiếng Việt và kết nối quy trình xác nhận của dược sĩ.', 0.58, 3.88, 5.75, 0.98, { fontSize: 15, color: 'D6E2F7', valign: 'top', lineSpacingMultiple: 1.05 });
  badge(slide, 'DDInter 2.0', 0.58, 5.28, 1.35, '1C3561', 'BFD2FF');
  badge(slide, 'LangGraph', 2.08, 5.28, 1.35, '1C3561', 'BFD2FF');
  badge(slide, 'Human-in-the-loop', 3.58, 5.28, 1.84, '1C3561', 'BFD2FF');
  addText(slide, 'TEAM MEDICHECK  /  2026', 0.58, 6.65, 3.5, 0.24, { fontSize: 9, bold: true, color: '7F97C4', charSpacing: 1.5 });
  addNotes(slide, 'Xin chào thầy cô và các bạn. Nhóm chúng em xin giới thiệu MediCheck — một trợ lý AI hỗ trợ kiểm tra tương tác thuốc, tập trung vào khả năng giải thích dễ hiểu và bảo đảm luôn có con người trong vòng kiểm soát.');
}

// Slide 2 — Problem
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '01 / Bài toán', 'Khi nhiều nguồn thuốc gặp nhau, rủi ro dễ bị bỏ sót', 'Vấn đề không chỉ là thiếu dữ liệu — mà là thiếu một quy trình tra cứu nhanh, dễ hiểu và có người chịu trách nhiệm xác nhận.');
  card(slide, 0.58, 1.95, 3.85, 2.05, 'Bệnh nhân đa bệnh lý', 'Dùng nhiều thuốc từ nhiều bác sĩ, cộng thêm thuốc OTC hoặc thực phẩm chức năng; khó nhận biết các cặp tương tác.', C.red, '01');
  card(slide, 4.74, 1.95, 3.85, 2.05, 'Thông tin phân mảnh', 'Tờ hướng dẫn dài, kết quả tìm kiếm rời rạc và thuật ngữ chuyên môn khiến người dùng dễ hiểu sai mức độ nghiêm trọng.', C.amber, '02');
  card(slide, 8.9, 1.95, 3.85, 2.05, 'Dược sĩ thiếu thời gian', 'Mỗi lượt tư vấn cần quyết định nhanh nhưng công cụ chuyên môn thường chưa gắn với hồ sơ và lịch sử của bệnh nhân.', C.purple, '03');
  addText(slide, 'Khoảng trống cần giải quyết', 0.58, 4.48, 3.2, 0.34, { fontSize: 14, bold: true, color: C.navy });
  const journey = [
    ['NHẬP THUỐC', 'Biệt dược / tên viết tắt'],
    ['ĐỐI CHIẾU', 'Nguồn dữ liệu có trích dẫn'],
    ['HIỂU RỦI RO', 'Ngôn ngữ tiếng Việt rõ ràng'],
    ['XÁC NHẬN', 'Dược sĩ xem xét khi cần'],
  ];
  journey.forEach((j, i) => {
    const x = 0.58 + i * 3.05;
    rect(slide, x, 5.02, 2.48, 1.08, i === 3 ? C.greenPale : C.pale, 0.16);
    addText(slide, j[0], x + 0.18, 5.17, 2.12, 0.24, { fontSize: 10, bold: true, color: i === 3 ? C.green : C.blue, charSpacing: 0.7 });
    addText(slide, j[1], x + 0.18, 5.49, 2.12, 0.38, { fontSize: 11, color: C.text });
    if (i < 3) arrow(slide, x + 2.53, 5.56, x + 2.93, 5.56, C.blue2, 1.6);
  });
  rect(slide, 0.58, 6.35, 12.17, 0.48, C.navy, 0.14);
  addText(slide, 'MediCheck biến quy trình trên thành một luồng liền mạch — từ tên thuốc đời thường đến cảnh báo có căn cứ.', 0.85, 6.42, 11.63, 0.30, { fontSize: 12, bold: true, color: C.white, align: 'center' });
  addNotes(slide, 'Đối tượng chính là bệnh nhân dùng nhiều thuốc và dược sĩ tại nhà thuốc. Nỗi đau nằm ở việc tên thuốc không chuẩn, nguồn thông tin khó hiểu và thiếu bước xác nhận. Vì vậy sản phẩm phải giải quyết cả dữ liệu, trải nghiệm và trách nhiệm chuyên môn.');
}

// Slide 3 — Solution
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '02 / Giải pháp', 'Một trợ lý an toàn dùng thuốc — không phải bác sĩ ảo', 'AI đảm nhiệm việc chuẩn hóa, tra cứu và diễn giải; dữ liệu nguồn và dược sĩ giữ vai trò kiểm chứng.');
  const steps = [
    ['01', 'Nhập / quét đơn', 'Tên biệt dược, hoạt chất hoặc ảnh đơn thuốc'],
    ['02', 'Chuẩn hóa tên', 'Biệt dược → hoạt chất và alias chuẩn'],
    ['03', 'Tra cứu', 'Đối chiếu các cặp trong DDInter 2.0'],
    ['04', 'Xếp hạng & giải thích', 'Nhẹ / trung bình / nặng, bằng tiếng Việt'],
    ['05', 'Guardrail & review', 'Lọc ngôn ngữ rủi ro, chuyển dược sĩ khi cần'],
  ];
  steps.forEach((s, i) => {
    const x = 0.58 + i * 2.46;
    circle(slide, x + 0.68, 2.02, 0.68, i === 4 ? C.green : C.blue);
    addText(slide, s[0], x + 0.68, 2.06, 0.68, 0.52, { fontSize: 13, bold: true, color: C.white, align: 'center' });
    if (i < 4) arrow(slide, x + 1.42, 2.36, x + 2.30, 2.36, C.line, 1.8);
    addText(slide, s[1], x, 2.84, 2.05, 0.45, { fontSize: 13.2, bold: true, color: C.navy, align: 'center' });
    addText(slide, s[2], x, 3.33, 2.05, 0.86, { fontSize: 10.5, color: C.muted, align: 'center', valign: 'top' });
  });
  rect(slide, 0.58, 4.68, 12.17, 1.47, C.white, 0.18, C.line);
  addText(slide, 'GIÁ TRỊ KHÁC BIỆT', 0.87, 4.92, 2.2, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.3 });
  const values = [
    ['Tiếng Việt dễ hiểu', 'Giảm khoảng cách giữa dữ liệu chuyên môn và người dùng.'],
    ['Nguồn thật, có trích dẫn', 'DDInter 2.0 là nền tảng tra cứu; LLM không tự tạo bằng chứng.'],
    ['Hai vai trò liên thông', 'Bệnh nhân theo dõi lịch sử; dược sĩ xác nhận và ghi nhận.'],
  ];
  values.forEach((v, i) => {
    const x = 3.05 + i * 3.2;
    line(slide, x - 0.22, 4.93, x - 0.22, 5.89, i === 0 ? C.blue : C.line, 2);
    addText(slide, v[0], x, 4.89, 2.75, 0.34, { fontSize: 12.3, bold: true, color: C.navy });
    addText(slide, v[1], x, 5.30, 2.75, 0.6, { fontSize: 10.2, color: C.muted, valign: 'top' });
  });
  addText(slide, 'NGUYÊN TẮC AN TOÀN', 0.72, 6.38, 1.86, 0.26, { fontSize: 9.2, bold: true, color: C.red, charSpacing: 1.0 });
  addText(slide, 'Không chẩn đoán  •  Không tự khuyên đổi/ngừng thuốc  •  Cảnh báo chỉ mang tính tham khảo', 2.58, 6.34, 9.76, 0.34, { fontSize: 11.4, bold: true, color: C.navy });
  addNotes(slide, 'MediCheck không cố thay thế bác sĩ. Hệ thống phân công đúng việc: cơ sở dữ liệu cung cấp sự thật, AI giúp diễn giải, guardrail chặn lời khuyên nguy hiểm và dược sĩ xác nhận trong tình huống cần chuyên môn.');
}

// Slide 4 — Personas
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '03 / Người dùng', 'Hai trải nghiệm, một vòng an toàn khép kín', 'MediCheck tạo giá trị cho bệnh nhân tại thời điểm tra cứu và cho dược sĩ tại thời điểm cần ra quyết định.');
  rect(slide, 0.58, 1.92, 5.88, 4.55, C.white, 0.2, C.line);
  rect(slide, 6.87, 1.92, 5.88, 4.55, C.white, 0.2, C.line);
  circle(slide, 0.9, 2.25, 0.78, C.pale);
  addText(slide, 'BN', 0.9, 2.3, 0.78, 0.52, { fontSize: 15, bold: true, color: C.blue, align: 'center' });
  addText(slide, 'BỆNH NHÂN', 1.86, 2.25, 2.5, 0.25, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.4 });
  addText(slide, '“Tôi cần biết khi nào nên lo lắng.”', 1.86, 2.56, 3.9, 0.5, { fontSize: 16.5, bold: true, color: C.navy });
  const pItems = ['Nhập tối đa nhiều đơn thuốc / biệt dược', 'Xem đồ thị tương tác và mức độ ưu tiên', 'Lưu lịch sử và nhận trạng thái dược sĩ xác nhận'];
  pItems.forEach((t, i) => {
    circle(slide, 0.95, 3.37 + i * 0.75, 0.28, C.blue);
    addText(slide, String(i + 1), 0.95, 3.375 + i * 0.75, 0.28, 0.24, { fontSize: 8.5, bold: true, color: C.white, align: 'center' });
    addText(slide, t, 1.4, 3.27 + i * 0.75, 4.55, 0.5, { fontSize: 11.7, color: C.text });
  });
  badge(slide, 'Yên tâm hơn', 0.92, 5.76, 1.32, C.greenPale, C.green);
  badge(slide, 'Chủ động hơn', 2.39, 5.76, 1.43, C.pale, C.blue);
  badge(slide, 'Có lịch sử', 3.98, 5.76, 1.22, 'F0E8FB', C.purple);

  circle(slide, 7.19, 2.25, 0.78, C.greenPale);
  addText(slide, 'DS', 7.19, 2.3, 0.78, 0.52, { fontSize: 15, bold: true, color: C.green, align: 'center' });
  addText(slide, 'DƯỢC SĨ', 8.15, 2.25, 2.5, 0.25, { fontSize: 10, bold: true, color: C.green, charSpacing: 1.4 });
  addText(slide, '“Tôi cần ưu tiên đúng ca cần xử lý.”', 8.15, 2.56, 4.0, 0.5, { fontSize: 16.5, bold: true, color: C.navy });
  const dItems = ['Dashboard gom yêu cầu theo mức độ khẩn', 'Xem chi tiết chuyên môn và nguồn dữ liệu', 'Xác nhận, ghi chú và phản hồi về bệnh nhân'];
  dItems.forEach((t, i) => {
    circle(slide, 7.24, 3.37 + i * 0.75, 0.28, C.green);
    addText(slide, String(i + 1), 7.24, 3.375 + i * 0.75, 0.28, 0.24, { fontSize: 8.5, bold: true, color: C.white, align: 'center' });
    addText(slide, t, 7.69, 3.27 + i * 0.75, 4.55, 0.5, { fontSize: 11.7, color: C.text });
  });
  badge(slide, 'Ưu tiên nhanh', 7.21, 5.76, 1.42, C.redPale, C.red);
  badge(slide, 'Có nguồn', 8.78, 5.76, 1.2, C.pale, C.blue);
  badge(slide, 'Có trách nhiệm', 10.13, 5.76, 1.48, C.greenPale, C.green);
  arrow(slide, 6.36, 4.22, 6.84, 4.22, C.blue, 2.2);
  arrow(slide, 6.84, 4.52, 6.36, 4.52, C.green, 2.2);
  addNotes(slide, 'Bệnh nhân và dược sĩ không phải hai module rời nhau. Bệnh nhân gửi yêu cầu và nhận phản hồi; dược sĩ nhìn thấy ca cần ưu tiên, kiểm tra nguồn và xác nhận. Đây là vòng lặp tạo niềm tin cho sản phẩm.');
}

// Slide 5 — Product demo
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '04 / Trải nghiệm sản phẩm', 'Tra cứu ngay từ landing page — không tạo rào cản ban đầu', 'Người dùng thử nhanh với tối đa 3 thuốc; đăng nhập khi cần lưu lịch sử hoặc kiểm tra chuyên sâu hơn.');
  imageFrame(slide, shots.landing, 0.58, 1.86, 12.17, 4.98, true);
  const calls = [
    [1, 1.08, 2.42, 'Thông điệp rõ: tra cứu và an toàn'],
    [2, 2.02, 5.15, 'Nhập tên thuốc / autocomplete'],
    [3, 10.55, 5.15, 'Hành động chính nổi bật'],
  ];
  calls.forEach(([n, x, y, txt]) => {
    circle(slide, x, y, 0.42, C.blue);
    addText(slide, String(n), x, y + 0.02, 0.42, 0.34, { fontSize: 10, bold: true, color: C.white, align: 'center' });
    rect(slide, x + 0.48, y - 0.02, 2.35, 0.46, C.navy, 0.13);
    addText(slide, txt, x + 0.6, y + 0.015, 2.12, 0.34, { fontSize: 8.8, bold: true, color: C.white, align: 'center' });
  });
  addNotes(slide, 'Đây là điểm vào của sản phẩm. Chúng em giảm ma sát bằng một ô tìm kiếm trực tiếp trên landing page. Người dùng chưa đăng nhập vẫn có thể thử; khi muốn lưu lịch sử hoặc kiểm tra nhiều thuốc hơn, hệ thống mới đề nghị tạo tài khoản.');
}

// Slide 6 — Result
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '05 / Kết quả tra cứu', 'Từ danh sách thuốc thành bản đồ rủi ro có thể hành động', 'Đồ thị giúp nhìn nhanh cặp tương tác; phần giải thích bên dưới cung cấp mức độ, nguồn và ngôn ngữ an toàn.');
  imageFrame(slide, shots.result, 0.58, 1.83, 8.45, 4.96, true);
  const metrics = [
    ['1', 'Nghiêm trọng', C.red, C.redPale],
    ['3', 'Trung bình', C.amber, C.amberPale],
    ['1', 'Nhẹ', C.green, C.greenPale],
  ];
  metrics.forEach((m, i) => {
    const y = 1.88 + i * 1.18;
    rect(slide, 9.37, y, 3.38, 0.93, m[3], 0.16);
    addText(slide, m[0], 9.62, y + 0.12, 0.58, 0.55, { fontSize: 24, bold: true, color: m[2], align: 'center' });
    addText(slide, m[1], 10.37, y + 0.15, 2.05, 0.44, { fontSize: 12.5, bold: true, color: C.navy });
  });
  rect(slide, 9.37, 5.56, 3.38, 1.22, C.navy, 0.16);
  addText(slide, 'Kết quả minh họa', 9.65, 5.72, 2.82, 0.28, { fontSize: 10, bold: true, color: 'AFC8FF', charSpacing: 0.8 });
  addText(slide, 'Không tự đổi hoặc ngừng thuốc. Hãy trao đổi với bác sĩ / dược sĩ.', 9.65, 6.04, 2.82, 0.52, { fontSize: 10.5, bold: true, color: C.white, valign: 'top' });
  addNotes(slide, 'Ví dụ trên màn hình có 5 cặp tương tác: 1 nghiêm trọng, 3 trung bình và 1 nhẹ. Màu sắc và đồ thị giúp định hướng chú ý, nhưng kết quả luôn kèm cảnh báo không tự ý đổi hoặc ngừng thuốc.');
}

// Slide 7 — HITL
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '06 / Human-in-the-loop', 'AI phát hiện — dược sĩ xác nhận — bệnh nhân nhận phản hồi', 'Cơ chế HITL biến một câu trả lời AI thành quy trình kiểm soát rủi ro có trạng thái và lịch sử.');
  imageFrame(slide, shots.patient, 0.58, 1.92, 5.55, 3.64, true);
  imageFrame(slide, shots.pharmacist, 7.20, 1.92, 5.55, 3.64, true);
  badge(slide, 'BỆNH NHÂN', 0.8, 2.12, 1.24, C.pale, C.blue);
  badge(slide, 'DƯỢC SĨ', 7.42, 2.12, 1.16, C.greenPale, C.green);
  circle(slide, 6.32, 2.83, 0.55, C.redPale);
  addText(slide, '!', 6.32, 2.86, 0.55, 0.42, { fontSize: 19, bold: true, color: C.red, align: 'center' });
  arrow(slide, 6.04, 3.64, 7.03, 3.64, C.red, 2.3);
  arrow(slide, 7.03, 4.22, 6.04, 4.22, C.green, 2.3);
  addText(slide, 'Yêu cầu\nreview', 6.18, 3.16, 0.82, 0.45, { fontSize: 9.2, bold: true, color: C.red, align: 'center' });
  addText(slide, 'Xác nhận', 6.18, 4.30, 0.82, 0.28, { fontSize: 9.2, bold: true, color: C.green, align: 'center' });
  const flow = [
    ['01', 'Phát hiện ca cần chú ý'],
    ['02', 'Đưa vào hàng đợi ưu tiên'],
    ['03', 'Dược sĩ xem nguồn & xác nhận'],
    ['04', 'Lưu trạng thái vào lịch sử'],
  ];
  flow.forEach((f, i) => {
    const x = 0.76 + i * 3.05;
    circle(slide, x, 6.05, 0.39, i === 3 ? C.green : C.blue);
    addText(slide, f[0], x, 6.075, 0.39, 0.29, { fontSize: 8.2, bold: true, color: C.white, align: 'center' });
    addText(slide, f[1], x + 0.52, 5.95, 2.22, 0.54, { fontSize: 10.4, bold: true, color: C.navy });
    if (i < 3) arrow(slide, x + 2.57, 6.24, x + 2.89, 6.24, C.line, 1.5);
  });
  addNotes(slide, 'Đây là điểm khác biệt quan trọng: hệ thống không dừng ở màn hình cảnh báo. Ca cần chú ý được đẩy sang dashboard dược sĩ, được ưu tiên, xác nhận và phản hồi lại cho bệnh nhân. Toàn bộ trạng thái được lưu để truy vết.');
}

// Slide 8 — Architecture
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '07 / Kiến trúc hệ thống', 'Kiến trúc phân lớp, tách rõ trải nghiệm — nghiệp vụ — AI — dữ liệu', 'Thiết kế giúp thay đổi mô hình LLM hoặc cơ sở dữ liệu mà không làm xáo trộn toàn bộ sản phẩm.');
  const cols = [
    { x: 0.58, w: 2.16, label: 'GIAO DIỆN', color: C.blue, items: ['Next.js 14', 'Bệnh nhân', 'Dược sĩ', 'Admin'] },
    { x: 3.18, w: 2.16, label: 'BACKEND', color: C.purple, items: ['FastAPI', 'Auth & RBAC', 'Product Resolver', 'REST API'] },
    { x: 5.78, w: 2.16, label: 'AI AGENT', color: C.amber, items: ['LangGraph', '5 nodes', 'Guardrail', 'DeepSeek'] },
    { x: 8.38, w: 2.16, label: 'DỮ LIỆU', color: C.green, items: ['DDInter 2.0', 'PostgreSQL', 'SQLAlchemy', 'Lịch sử'] },
  ];
  cols.forEach((c, ci) => {
    rect(slide, c.x, 1.93, c.w, 4.25, C.white, 0.2, C.line);
    rect(slide, c.x, 1.93, c.w, 0.63, c.color, 0.2);
    slide.addShape(pptx.ShapeType.rect, { x: c.x, y: 2.30, w: c.w, h: 0.26, fill: { color: c.color }, line: { color: c.color, width: 0 } });
    addText(slide, c.label, c.x + 0.15, 2.06, c.w - 0.3, 0.28, { fontSize: 10.5, bold: true, color: C.white, align: 'center', charSpacing: 0.8 });
    c.items.forEach((it, i) => {
      const y = 2.83 + i * 0.72;
      rect(slide, c.x + 0.22, y, c.w - 0.44, 0.5, i === 0 ? c.color : C.bg, 0.13, i === 0 ? c.color : C.line);
      addText(slide, it, c.x + 0.32, y + 0.05, c.w - 0.64, 0.36, { fontSize: 10.7, bold: i === 0, color: i === 0 ? C.white : C.text, align: 'center' });
    });
    if (ci < cols.length - 1) arrow(slide, c.x + c.w + 0.08, 4.05, cols[ci + 1].x - 0.08, 4.05, C.blue2, 1.8);
  });
  rect(slide, 10.98, 2.15, 1.77, 1.58, C.navy, 0.18);
  addText(slide, 'DỊCH VỤ\nBÊN NGOÀI', 11.2, 2.38, 1.33, 0.46, { fontSize: 9.5, bold: true, color: '9AB6F4', align: 'center' });
  addText(slide, 'DeepSeek API', 11.16, 3.08, 1.41, 0.28, { fontSize: 11, bold: true, color: C.white, align: 'center' });
  arrow(slide, 7.96, 3.18, 10.90, 3.18, C.amber, 1.6);
  rect(slide, 10.98, 4.15, 1.77, 2.03, C.pale, 0.18, C.line);
  addText(slide, 'TRIỂN KHAI', 11.18, 4.38, 1.37, 0.26, { fontSize: 9.5, bold: true, color: C.blue, align: 'center', charSpacing: 0.8 });
  addText(slide, 'Docker Compose\nFrontend :3000\nBackend :8000', 11.18, 4.85, 1.37, 0.87, { fontSize: 10.2, color: C.navy, align: 'center', valign: 'top' });
  rect(slide, 0.58, 6.43, 12.17, 0.4, C.navy, 0.13);
  addText(slide, 'Luồng chính: UI → API → Product Resolver → LangGraph → DDInter / LLM → Guardrail → lưu lịch sử → trả kết quả', 0.83, 6.48, 11.67, 0.26, { fontSize: 10.2, bold: true, color: C.white, align: 'center' });
  addNotes(slide, 'Kiến trúc gồm bốn lớp chính. Frontend chỉ giao tiếp qua API. Backend chịu trách nhiệm xác thực và chuyển biệt dược thành hoạt chất. Agent xử lý theo pipeline, còn dữ liệu nguồn nằm ở DDInter và PostgreSQL. DeepSeek chỉ là dịch vụ sinh giải thích, không phải nguồn sự thật.');
}

// Slide 9 — Agent and safety
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '08 / AI Agent', 'Pipeline 5 bước: có dữ liệu trước, có giải thích sau', 'Mỗi node làm một nhiệm vụ rõ ràng; nếu state có lỗi, graph kết thúc sớm thay vì tiếp tục suy đoán.');
  const nodes = [
    ['1', 'NORMALIZE', 'Chuẩn hóa tên và alias', C.blue],
    ['2', 'LOOKUP', 'Tra cặp tương tác DDInter', C.purple],
    ['3', 'RANK', 'Chuẩn hóa mức độ', C.amber],
    ['4', 'EXPLAIN', 'Sinh giải thích tiếng Việt', C.green],
    ['5', 'GUARDRAIL', 'Kiểm citation & ngôn ngữ', C.red],
  ];
  nodes.forEach((n, i) => {
    const x = 0.58 + i * 2.46;
    rect(slide, x, 2.03, 2.05, 2.02, C.white, 0.18, C.line);
    circle(slide, x + 0.69, 2.27, 0.66, n[3]);
    addText(slide, n[0], x + 0.69, 2.31, 0.66, 0.48, { fontSize: 13, bold: true, color: C.white, align: 'center' });
    addText(slide, n[1], x + 0.17, 3.04, 1.71, 0.3, { fontSize: 10.2, bold: true, color: n[3], align: 'center', charSpacing: 0.7 });
    addText(slide, n[2], x + 0.18, 3.42, 1.69, 0.46, { fontSize: 10.1, color: C.text, align: 'center' });
    if (i < 4) arrow(slide, x + 2.08, 3.05, x + 2.38, 3.05, C.line, 1.6);
  });
  const rails = [
    ['Nguồn sự thật', '1.503 thuốc\n15.140 cặp tương tác\nDDInter 2.0', C.blue, C.pale],
    ['Vai trò của LLM', 'Chỉ diễn giải dữ liệu đã tra cứu; không tự tạo tương tác.', C.purple, 'F0E8FB'],
    ['Rào chắn an toàn', 'Bắt buộc citation; lọc khuyến nghị tự đổi/ngừng thuốc.', C.red, C.redPale],
    ['Con người kiểm soát', 'Dược sĩ xem chi tiết chuyên môn và xác nhận ca cần chú ý.', C.green, C.greenPale],
  ];
  rails.forEach((r, i) => {
    const x = 0.58 + i * 3.05;
    rect(slide, x, 4.56, 2.74, 1.74, r[3], 0.16);
    addText(slide, r[0], x + 0.2, 4.79, 2.34, 0.3, { fontSize: 11.3, bold: true, color: r[2], align: 'center' });
    addText(slide, r[1], x + 0.25, 5.23, 2.24, 0.72, { fontSize: 10.1, color: C.text, align: 'center', valign: 'top' });
  });
  addNotes(slide, 'Điểm thiết kế quan trọng là thứ tự: hệ thống tra dữ liệu trước rồi mới gọi LLM để diễn giải. Sau đó guardrail kiểm citation và loại bỏ ngôn ngữ có thể khiến người dùng tự thay đổi thuốc. Với ca cần chuyên môn, dược sĩ là lớp kiểm soát cuối cùng.');
}

// Slide 10 — Engineering
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '09 / Nền tảng kỹ thuật', 'Một MVP full-stack có thể chạy nhất quán bằng Docker', 'Công nghệ được chọn để tối ưu tốc độ phát triển, khả năng kiểm thử và đường nâng cấp lên production.');
  const stack = [
    ['FRONTEND', 'Next.js 14\nReact 18\nTypeScript', C.blue],
    ['BACKEND', 'FastAPI\nPydantic\nUvicorn', C.purple],
    ['AGENT', 'LangGraph\nLangChain\nDeepSeek Chat', C.amber],
    ['DATA', 'PostgreSQL / Neon\nSQLite offline\nSQLAlchemy', C.green],
    ['QUALITY', 'pytest\nSmoke test auth\nSwagger / OpenAPI', C.red],
  ];
  stack.forEach((s, i) => {
    const x = 0.58 + i * 2.46;
    rect(slide, x, 1.97, 2.05, 2.23, C.white, 0.18, C.line);
    slide.addShape(pptx.ShapeType.rect, { x, y: 1.97, w: 2.05, h: 0.08, fill: { color: s[2] }, line: { color: s[2], width: 0 } });
    addText(slide, s[0], x + 0.2, 2.32, 1.65, 0.28, { fontSize: 10, bold: true, color: s[2], align: 'center', charSpacing: 0.9 });
    addText(slide, s[1], x + 0.2, 2.84, 1.65, 0.96, { fontSize: 11.5, bold: true, color: C.navy, align: 'center', valign: 'top' });
  });
  addText(slide, 'ĐƯỜNG TRIỂN KHAI', 0.58, 4.63, 2.5, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.2 });
  const deploy = [
    ['LOCAL', 'Docker Compose', 'Frontend + Backend'],
    ['STAGING', 'HTTPS + PostgreSQL', 'Auth smoke test'],
    ['PRODUCTION', 'CORS / cookie an toàn', 'DB branch riêng'],
  ];
  deploy.forEach((d, i) => {
    const x = 0.58 + i * 4.13;
    rect(slide, x, 5.06, 3.68, 1.22, i === 2 ? C.navy : C.pale, 0.17);
    addText(slide, d[0], x + 0.22, 5.20, 0.86, 0.24, { fontSize: 9.4, bold: true, color: i === 2 ? 'AFC8FF' : C.blue, charSpacing: 0.9 });
    addText(slide, d[1], x + 1.12, 5.17, 2.26, 0.32, { fontSize: 12.4, bold: true, color: i === 2 ? C.white : C.navy });
    addText(slide, d[2], x + 1.12, 5.58, 2.26, 0.3, { fontSize: 10, color: i === 2 ? 'D6E2F7' : C.muted });
    if (i < 2) arrow(slide, x + 3.73, 5.66, x + 4.04, 5.66, C.blue2, 1.8);
  });
  addText(slide, 'Lưu ý: báo cáo KPI hiện còn đang thu thập; không trình bày số accuracy/latency chưa có bằng chứng đo.', 0.72, 6.52, 11.7, 0.28, { fontSize: 9.6, italic: true, color: C.muted, align: 'center' });
  addNotes(slide, 'MVP dùng Next.js, FastAPI, LangGraph và PostgreSQL. Toàn bộ hệ thống có thể chạy qua Docker Compose. Nhóm cũng đã chuẩn bị hướng dẫn xác thực production và smoke test. Các KPI chất lượng chưa có số đo chính thức nên trong deck này chúng em không đưa ra con số chưa được kiểm chứng.');
}

// Slide 11 — Analysis & roadmap
{
  const slide = pptx.addSlide('MEDICHECK');
  title(slide, '10 / Phân tích & định hướng', 'Nền tảng đúng hướng; bước tiếp theo là chứng minh chất lượng ngoài phòng lab', 'Roadmap ưu tiên bằng chứng đo lường, độ tin cậy dữ liệu và khả năng vận hành trước khi mở rộng tính năng.');
  const swot = [
    ['ĐIỂM MẠNH', 'Dữ liệu DDInter thật\nGiải thích tiếng Việt\nHITL dược sĩ', C.green, C.greenPale],
    ['ĐIỂM YẾU', 'KPI chưa đo đủ\nPhụ thuộc dịch vụ LLM\nDữ liệu y tế nhạy cảm', C.red, C.redPale],
    ['CƠ HỘI', 'Nhà thuốc / phòng khám nhỏ\nNgười dùng đa bệnh lý\nOCR đơn thuốc', C.blue, C.pale],
    ['THÁCH THỨC', 'Niềm tin & pháp lý\nDuy trì dữ liệu cập nhật\nTrách nhiệm khi cảnh báo sai', C.amber, C.amberPale],
  ];
  swot.forEach((s, i) => {
    const x = 0.58 + i * 3.05;
    rect(slide, x, 1.88, 2.74, 1.84, s[4], 0.17);
    addText(slide, s[0], x + 0.22, 2.11, 2.3, 0.27, { fontSize: 10.2, bold: true, color: s[3], align: 'center', charSpacing: 0.8 });
    addText(slide, s[1], x + 0.24, 2.57, 2.26, 0.86, { fontSize: 10.5, color: C.text, align: 'center', valign: 'top' });
  });
  addText(slide, 'ROADMAP ĐỀ XUẤT', 0.58, 4.15, 2.4, 0.28, { fontSize: 10, bold: true, color: C.blue, charSpacing: 1.2 });
  const road = [
    ['01', 'ĐO LƯỜNG', 'Bộ test chuẩn; accuracy, latency, citation coverage'],
    ['02', 'KIỂM CHỨNG', 'Pilot với dược sĩ; phân tích cảnh báo sai / bỏ sót'],
    ['03', 'CỨNG HÓA', 'Monitoring, audit log, backup, privacy & security review'],
    ['04', 'MỞ RỘNG', 'OCR tốt hơn, cá nhân hóa bệnh nền, mô hình B2B2C'],
  ];
  road.forEach((r, i) => {
    const x = 0.58 + i * 3.05;
    circle(slide, x, 4.72, 0.47, i === 3 ? C.green : C.blue);
    addText(slide, r[0], x, 4.75, 0.47, 0.34, { fontSize: 9.2, bold: true, color: C.white, align: 'center' });
    if (i < 3) arrow(slide, x + 0.52, 4.96, x + 2.82, 4.96, C.line, 1.4);
    addText(slide, r[1], x, 5.38, 2.72, 0.28, { fontSize: 10.5, bold: true, color: i === 3 ? C.green : C.navy });
    addText(slide, r[2], x, 5.79, 2.72, 0.72, { fontSize: 10.2, color: C.muted, valign: 'top' });
  });
  addNotes(slide, 'Qua phân tích, sản phẩm có ba điểm mạnh: nguồn dữ liệu thật, trải nghiệm tiếng Việt và quy trình dược sĩ. Nhưng để đi tiếp, ưu tiên số một không phải thêm thật nhiều tính năng mà là đo lường, pilot với dược sĩ, hoàn thiện audit và bảo mật. Sau đó mới mở rộng OCR và mô hình kinh doanh.');
}

// Slide 12 — Team & close
{
  const slide = pptx.addSlide('MEDICHECK');
  slide.background = { color: C.dark };
  addText(slide, 'TEAM  /  VMEC-12', 0.58, 0.53, 3.6, 0.28, { fontSize: 10, bold: true, color: '9AB6F4', charSpacing: 1.5 });
  addText(slide, 'MediCheck', 0.58, 1.08, 4.8, 0.7, { fontSize: 33, bold: true, color: C.white });
  addText(slide, 'AI hỗ trợ hiểu đúng rủi ro.\nDược sĩ giúp ra quyết định an toàn.', 0.58, 1.85, 5.6, 1.15, { fontSize: 24, bold: true, color: 'AFC8FF', valign: 'top' });
  const team = [
    ['Hoàng Sỹ Toàn', 'Leader • Data • PM • OCR'],
    ['Đàm Lê Minh Quân', 'Data • Backend • AI Agent'],
    ['Nguyễn Thị Tuyết Mai', 'Data • Design • Frontend'],
    ['Lê Thị Linh', 'Data • Design • Frontend'],
  ];
  team.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.58 + col * 3.08, y = 3.55 + row * 1.13;
    circle(slide, x, y, 0.52, i < 2 ? C.blue : C.green);
    addText(slide, t[0].split(' ').pop().substring(0, 1), x, y + 0.03, 0.52, 0.4, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    addText(slide, t[0], x + 0.68, y - 0.01, 2.17, 0.32, { fontSize: 11.3, bold: true, color: C.white });
    addText(slide, t[1], x + 0.68, y + 0.36, 2.17, 0.32, { fontSize: 9.3, color: 'A8B9D6' });
  });
  rect(slide, 7.30, 0.62, 5.45, 6.2, '10213D', 0.24, '304A75');
  addText(slide, 'THÔNG ĐIỆP KẾT', 7.75, 1.10, 4.55, 0.28, { fontSize: 10, bold: true, color: '9AB6F4', charSpacing: 1.4 });
  addText(slide, '“Cảnh báo tốt không chỉ đúng — mà còn phải dễ hiểu, có nguồn và có người chịu trách nhiệm.”', 7.75, 1.70, 4.55, 1.72, { fontSize: 22, bold: true, color: C.white, valign: 'top' });
  line(slide, 7.75, 3.84, 12.20, 3.84, '304A75', 1.2);
  addText(slide, 'Q & A', 7.75, 4.30, 4.55, 0.84, { fontSize: 36, bold: true, color: 'AFC8FF' });
  addText(slide, 'Cảm ơn thầy cô và các bạn đã lắng nghe.', 7.75, 5.42, 4.55, 0.48, { fontSize: 13, color: 'D6E2F7' });
  addText(slide, 'github.com/AI20K-Build-Phase-Cohort-3/P-005', 7.75, 6.22, 4.55, 0.26, { fontSize: 9, color: '7F97C4' });
  addNotes(slide, 'MediCheck hướng tới một nguyên tắc đơn giản: cảnh báo y tế không chỉ cần đúng, mà còn phải dễ hiểu, có nguồn và có người chịu trách nhiệm. Nhóm xin cảm ơn và sẵn sàng trả lời câu hỏi.');
}

const notes = `# Lời dẫn thuyết trình — MediCheck\n\n` + [
  ['1. Mở đầu', 'Giới thiệu MediCheck là AI Agent hỗ trợ kiểm tra tương tác thuốc, nhấn mạnh đây không phải bác sĩ ảo.'],
  ['2. Bài toán', 'Nêu ba nỗi đau: bệnh nhân dùng nhiều thuốc, thông tin phân mảnh, dược sĩ thiếu thời gian.'],
  ['3. Giải pháp', 'Trình bày pipeline từ nhập thuốc đến guardrail và review; nhấn mạnh dữ liệu trước, AI sau.'],
  ['4. Người dùng', 'So sánh mục tiêu của bệnh nhân và dược sĩ; giải thích vòng phản hồi hai chiều.'],
  ['5. Trải nghiệm', 'Demo landing page: nhập tên, autocomplete, tra cứu nhanh, đăng nhập khi cần lưu lịch sử.'],
  ['6. Kết quả', 'Giải thích đồ thị và màu mức độ; nhắc disclaimer không tự đổi hoặc ngừng thuốc.'],
  ['7. HITL', 'Cho thấy ca rủi ro đi từ bệnh nhân sang hàng đợi dược sĩ và quay lại dưới dạng xác nhận.'],
  ['8. Kiến trúc', 'Đi qua bốn lớp: Next.js, FastAPI, LangGraph, dữ liệu; DeepSeek chỉ sinh giải thích.'],
  ['9. AI Agent', 'Giới thiệu 5 node và các lớp an toàn: DDInter, citation, guardrail, dược sĩ.'],
  ['10. Kỹ thuật', 'Tóm tắt tech stack và đường triển khai Docker → staging → production.'],
  ['11. Phân tích', 'Trình bày SWOT ngắn và roadmap ưu tiên đo lường, pilot, hardening rồi mới mở rộng.'],
  ['12. Kết', 'Giới thiệu team, nhắc lại thông điệp và mời Q&A.'],
].map(([h, b]) => `## ${h}\n\n${b}\n`).join('\n');

async function main() {
  const onlySlide = Number(process.env.ONLY_SLIDE || 0);
  const maxSlides = Number(process.env.MAX_SLIDES || 0);
  if (onlySlide > 0) {
    pptx._slides = [pptx._slides[onlySlide - 1]];
  } else if (maxSlides > 0) {
    pptx._slides = pptx._slides.slice(0, maxSlides);
  }
  const outName = onlySlide > 0 ? `_test_slide_${onlySlide}.pptx` : (maxSlides > 0 ? `_test_prefix_${maxSlides}.pptx` : 'pitch_deck_medicheck_vi.pptx');
  const out = path.join(__dirname, outName);
  const notesOut = path.join(__dirname, 'speaker_notes_vi.md');
  await pptx.writeFile({ fileName: out, compression: true });
  fs.writeFileSync(notesOut, notes, 'utf8');
  console.log(`Created: ${out}`);
  console.log(`Created: ${notesOut}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
