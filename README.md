# PDF TOC Translator

Dịch mục lục (bookmark) trong file PDF sang tiếng Việt bằng Gemini API.

---

## Tính năng

- Đọc mục lục có sẵn trong PDF (nhiều cấp)
- Dịch tự động sang tiếng Việt bằng Gemini (1 request cho mỗi file)
- Ghi lại mục lục tiếng Việt vào PDF mới, giữ nguyên toàn bộ nội dung gốc
- Hỗ trợ chỉnh sửa bản dịch trước khi ghi vào PDF

---

## Yêu cầu

- Windows 10 / 11 (64-bit)
- Kết nối Internet khi dịch
- API key Gemini (miễn phí)

---

## Lấy API key Gemini

1. Mở https://aistudio.google.com/apikey
2. Đăng nhập tài khoản Google
3. Bấm **Create API key**
4. Copy key (dạng `AIzaSy...`)

---

## Sử dụng

### Bước 1: Mở phần mềm

Nhấp đôi file `PDF-TOC-Translator.exe`.

### Bước 2: Nhập API key

- Dán API key vào ô **API Key**
- Chọn (hoặc gõ) tên model, mặc định: `gemini-2.5-flash`
- Bấm **💾 Lưu**

### Bước 3: Chọn PDF

- Bấm **📂 Chọn…** → chọn file PDF có mục lục
- Mục lục sẽ hiện ra trong bảng bên dưới

### Bước 4: Dịch

- Bấm **🤖 Dịch bằng Gemini** → chờ vài giây

### Bước 5: Ghi PDF mới

- Bấm **📥 Ghi PDF mới** → chọn nơi lưu
- Mở file PDF mới bằng Adobe Reader → panel trái có mục lục tiếng Việt

---

## Các nút chức năng

| Nút | Chức năng |
|-----|-----------|
| 👁 | Hiện / ẩn API key |
| 💾 Lưu | Lưu API key và model |
| 🗑️ | Xóa API key khỏi máy |
| 📂 Chọn… | Chọn file PDF có mục lục |
| 📤 Xuất Markdown | Xuất mục lục ra file `.md` để sửa tay |
| 🤖 Dịch bằng Gemini | Dịch mục lục sang tiếng Việt |
| 🔄 Nạp lại file | Nạp file `.md` đã sửa để xem trước |
| 📥 Ghi PDF mới | Tạo PDF mới với mục lục tiếng Việt |

---

## File sinh ra

Với file gốc `mybook.pdf`, phần mềm tạo:

| File | Nội dung |
|------|----------|
| `mybook.md` | Mục lục có cấu trúc (level, page, title) |
| `mybook_titles.json` | Tiêu đề gửi Gemini |
| `mybook_translated.json` | Kết quả Gemini trả về |
| `mybook_vi.md` | Markdown tiếng Việt |
| `mybook_vi.pdf` | **PDF thành phẩm** |

Các file `.md` và `.json` là file tạm, có thể xóa sau khi hoàn tất.

---

## Lưu ý

- PDF phải có **mục lục thật** (bookmark). Kiểm tra bằng Adobe Reader — panel bên trái phải có danh sách bookmarks.
- PDF chỉ có trang "Table of Contents" dạng chữ **không** dùng được.
- PDF scan ảnh hoặc có mật khẩu có thể không đọc được mục lục.
- Không ghi đè lên PDF gốc — phần mềm luôn tạo file mới.

---

## Gỡ cài đặt

Xóa file `.exe` và mọi file `*_vi.pdf`, `*_vi.md`, `*_titles.json`, `*_translated.json` do phần mềm tạo ra (nằm cạnh file PDF gốc).

---

## Giấy phép

Sử dụng cá nhân, phi thương mại.