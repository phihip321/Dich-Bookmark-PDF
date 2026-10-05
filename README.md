# PDF TOC Translator

Dịch mục lục (bookmark/outline) trong file PDF sang tiếng Việt bằng Gemini API.

## Tính năng

- Đọc mục lục có sẵn trong PDF (nhiều cấp)
- Xuất ra Markdown có cấu trúc để chỉnh sửa
- Dịch tự động sang tiếng Việt bằng Gemini (1 request / file)
- Ghi lại mục lục tiếng Việt vào PDF mới (giữ nguyên nội dung)

## Yêu cầu

- Python 3.12 – 3.14
- API key Gemini (lấy miễn phí tại https://aistudio.google.com/apikey)

## Cài đặt

```powershell
pip install -r requirements.txt
```

## Chạy

```powershell
python app.py
```

## Sử dụng

1. Nhập **API key** Gemini → bấm **💾 Lưu**
2. Bấm **📂 Chọn…** → chọn file PDF có mục lục tiếng Anh
3. Bấm **🤖 Dịch bằng Gemini** → chờ vài giây
4. (Tùy chọn) Mở file `*_vi.md` chỉnh sửa → bấm **🔄 Nạp lại file**
5. Bấm **📥 Ghi PDF mới** → chọn nơi lưu PDF tiếng Việt

## File sinh ra

Với `mybook.pdf`, chương trình tạo:

| File | Nội dung |
|------|----------|
| `mybook.md` | Mục lục có cấu trúc (level, page, title) |
| `mybook_titles.json` | Chỉ tiêu đề, gửi Gemini |
| `mybook_translated.json` | Kết quả Gemini |
| `mybook_vi.md` | Markdown tiếng Việt |
| `mybook_vi.pdf` | PDF thành phẩm |

## Build exe

```powershell
build.bat
```

File `dist\PDF-TOC-Translator.exe` chạy độc lập, không cần Python.

## Bảo mật

API key lưu tại `.pdf-toc.json` cạnh app/exe dạng plaintext.
**Xóa file này trước khi chia sẻ tool cho người khác.**

## Lưu ý

- PDF phải có **outline thật** (bookmark), không phải trang "Table of Contents" dạng chữ.
- PDF scan hoặc có mật khẩu có thể không đọc được outline.