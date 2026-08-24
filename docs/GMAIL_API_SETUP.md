# Hướng dẫn lấy Gmail OAuth credentials

## Tóm tắt (đọc phần này trước)

Mình cần bạn làm 3 việc trên Google Cloud Console + máy của bạn, để lấy ra
**3 đoạn mã (credentials)**. Sau khi có 3 đoạn mã đó, gửi lại cho mình là
xong — mình sẽ tự lo phần còn lại (deploy, cấu hình server).

Không cần biết code, không cần đụng vào Render hay repo. Chỉ cần 1 trình
duyệt web và 1 terminal để chạy 1 lệnh.

**Thời gian: khoảng 10–15 phút.**

**Bạn cần đăng nhập đúng tài khoản `medichecksupport@gmail.com`** ở 1 bước
quan trọng (Bước 3) — nhớ kỹ, sẽ nhắc lại lúc đó.

---

## Chuẩn bị

- [ ] File `gmail_oauth_setup.py` (mình gửi kèm cùng file hướng dẫn này) —
      để cùng 1 thư mục cho dễ tìm.
- [ ] Máy đã cài Python (gõ `python --version` trong terminal, nếu ra số
      phiên bản như `Python 3.11.x` là có rồi).
- [ ] Biết mật khẩu đăng nhập tài khoản `medichecksupport@gmail.com`.

---

## Bước 1 — Mở Gmail API cho project

1. Mở https://console.cloud.google.com/
2. Ở thanh trên cùng, chọn đúng **project** đang dùng cho MediCheck.
   (Nếu thấy nhiều project và không chắc cái nào — hỏi mình trước khi làm
   tiếp, chọn nhầm project sẽ phải làm lại từ đầu.)
3. Ở ô tìm kiếm trên cùng, gõ `Gmail API` → bấm vào kết quả đầu tiên.
4. Bấm nút xanh **Enable**.

✅ **Xong Bước 1 khi:** trang chuyển sang hiện chữ "API enabled" hoặc nút
Enable biến mất/đổi thành "Manage".

---

## Bước 2 — Tạo bộ khóa OAuth (Client ID + Client secret)

1. Ở menu bên trái, vào **APIs & Services → Credentials**.
2. Bấm **+ Create Credentials** (trên cùng) → chọn **OAuth client ID**.
3. **Nếu Google bắt cấu hình "OAuth consent screen" trước** (thường chỉ hỏi
   lần đầu tiên của project) thì làm nhanh theo thứ tự:
   - **User Type**: chọn **External** → Create.
   - **App name**: gõ gì cũng được, ví dụ `MediCheck`.
   - **User support email**: chọn email của bạn trong danh sách.
   - **Developer contact information**: gõ email của bạn.
   - Bấm **Save and Continue** liên tục qua các màn "Scopes" (bỏ trống,
     không cần thêm gì) cho tới màn **Test users**.
   - Ở màn **Test users**: bấm **+ Add users**, gõ chính xác
     `medichecksupport@gmail.com`, bấm **Add**.
     ⚠️ **Bước này rất quan trọng — đừng bỏ qua.** Nếu thiếu, Bước 3 sẽ báo
     lỗi "access_denied" khi đăng nhập.
   - Bấm **Save and Continue** tới hết, rồi quay lại **Credentials**
     (menu bên trái) để tiếp tục bước tạo OAuth client ID.
4. **Application type**: chọn **Desktop app**.
5. **Name**: gõ gì cũng được, ví dụ `MediCheck mail sender`.
6. Bấm **Create**.

✅ **Xong Bước 2 khi:** 1 popup hiện ra 2 dòng **Your Client ID** và **Your
Client Secret** — đây chính là 2 trong 3 giá trị cần gửi lại cho mình. Bấm
nút copy cạnh mỗi dòng, dán tạm vào Notepad để không bị mất (sau này vẫn có
thể xem lại trong danh sách Credentials nếu quên copy).

---

## Bước 3 — Chạy script để lấy giá trị thứ 3 (refresh token)

1. Mở terminal (Windows: gõ `cmd` hoặc `powershell` trong Start Menu; Mac:
   mở app **Terminal**).
2. Di chuyển tới thư mục chứa file `gmail_oauth_setup.py` — ví dụ nếu file
   nằm trong `Downloads`:
   ```bash
   cd Downloads
   ```
3. Chạy lệnh sau, **thay `DÁN_CLIENT_ID` và `DÁN_CLIENT_SECRET` bằng 2 giá
   trị đã copy ở Bước 2** (giữ nguyên dấu ngoặc kép nếu giá trị có ký tự
   đặc biệt):
   ```bash
   python gmail_oauth_setup.py --client-id DÁN_CLIENT_ID --client-secret DÁN_CLIENT_SECRET
   ```
4. Trình duyệt sẽ tự mở ra trang đăng nhập Google.
   **Đăng nhập đúng tài khoản `medichecksupport@gmail.com`** — không dùng
   tài khoản Gmail cá nhân của bạn.
5. Google sẽ hiện cảnh báo màu vàng/đỏ **"Google hasn't verified this
   app"** — đây là bình thường, không phải lỗi (vì app đang ở chế độ thử
   nghiệm nội bộ). Bấm chữ **Advanced** (hoặc "Nâng cao") → bấm dòng
   **"Go to MediCheck (unsafe)"** → bấm **Continue/Allow** ở màn tiếp theo
   để cấp quyền gửi mail.
6. Trình duyệt hiện dòng "Đã xác thực xong..." → quay lại cửa sổ terminal.

✅ **Xong Bước 3 khi:** terminal in ra dòng bắt đầu bằng
`GMAIL_OAUTH_REFRESH_TOKEN = 1//0g...` — đây là giá trị thứ 3.

**Nếu terminal báo lỗi "KHONG co refresh_token":** khả năng cao tài khoản
này đã từng bấm "Allow" cho app này 1 lần trước đó rồi. Vào
https://myaccount.google.com/permissions (nhớ đăng nhập bằng
`medichecksupport@gmail.com`), tìm app vừa tạo trong danh sách, bấm gỡ
quyền truy cập, rồi quay lại chạy lại lệnh ở bước 3.

---

## Bước 4 — Gửi lại cho mình

Bạn giờ có đủ 3 giá trị:

| Tên | Lấy từ đâu |
|---|---|
| `GMAIL_OAUTH_CLIENT_ID` | Bước 2 |
| `GMAIL_OAUTH_CLIENT_SECRET` | Bước 2 |
| `GMAIL_OAUTH_REFRESH_TOKEN` | Bước 3 |

Gửi cả 3 giá trị này lại cho mình qua **kênh nhắn tin riêng** (chat riêng,
không post lên group chung) — vì đây gần như là "chìa khóa" cho phép gửi
email từ `medichecksupport@gmail.com`, không nên để lộ công khai.

**Xong — cảm ơn bạn đã hỗ trợ! 🙏** Phần deploy server và test lại mình sẽ
tự làm tiếp.
