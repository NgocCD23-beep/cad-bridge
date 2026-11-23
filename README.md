# Cầu nối AutoCAD — Muse ↔ AutoCAD trên máy tính của bạn

Chương trình nhỏ chạy trên máy Windows của bạn, nói chuyện trực tiếp với
AutoCAD đang mở trên máy đó, và trả lời các câu hỏi của Muse qua mạng riêng
Tailscale (chỉ máy bạn với máy Muse thấy nhau, không đưa dữ liệu lên cloud).

Nhờ đó Muse có thể, ngay trong lúc bạn đang mở bản vẽ:
- Đọc tên bản vẽ đang mở, liệt kê đối tượng, layer
- Tính diện tích + chu vi đường bao kín (như lệnh DIENTICH, nhưng trực tiếp)
- Chạy mã LISP, gửi lệnh cho AutoCAD
- Vẽ thêm đối tượng (đường thẳng, polyline, tròn, chữ) vào bản vẽ đang mở

## Cách 1 — Tải file .exe (khuyên dùng, không cần cài Python)

1. Vào mục **Releases** của repo này, tải file `cad-bridge.exe` mới nhất.
2. Mở AutoCAD 2022 và mở 1 bản vẽ bất kỳ.
3. Chạy `cad-bridge.exe` (bấm đúp). Lần đầu Windows Firewall hỏi thì bấm
   **Allow access**. Cửa sổ đen hiện lên, trong đó có 1 dòng Token.
4. Nhắn cho Muse 2 thứ: Token đó và tên máy Tailscale của bạn
   (ví dụ `DESKTOP-ABC123`).
5. Cứ để cửa sổ đó mở trong lúc dùng. Đóng cửa sổ là cầu nối dừng.

## Cách 2 — Chạy từ source (cần Python)

1. Cài Python (https://www.python.org/downloads/), nhớ tick
   **Add python.exe to PATH** khi cài.
2. Chạy `run.bat` — lần đầu nó tự cài thêm `pyautocad` và `comtypes`.
3. Các bước còn lại giống cách 1 từ bước 2.

## Chuẩn bị mạng (chỉ làm 1 lần)

Cài Tailscale trên máy này: https://tailscale.com/download — tải bản
Windows, cài đặt, đăng nhập bằng tài khoản của bạn. Sau khi đăng nhập,
Tailscale hiện tên máy, ví dụ `DESKTOP-ABC123` (ghi lại tên này để gửi
cho Muse).

## Bảo mật

- Cầu nối chỉ nhận lệnh khi có đúng Token (header `X-Bridge-Token`).
  Đừng gửi Token cho ai khác ngoài Muse.
- Muốn đổi Token: xóa file `token.txt` cạnh file .exe (hoặc cạnh `bridge.py`
  khi chạy từ source) rồi chạy lại, Token mới sẽ sinh ra.
- Cầu nối chỉ nghe trong mạng Tailscale và mạng LAN nhà bạn,
  không mở ra internet.
- Cầu nối có thể vẽ/sửa bản vẽ đang mở theo lệnh của Muse — chỉ chạy khi
  bạn đang làm việc với Muse.

## Các lệnh (JSON qua HTTP, cổng 8765)

| Lệnh | Mô tả |
| --- | --- |
| `GET /ping` | Kiểm tra cầu nối còn sống (không cần Token) |
| `GET /status` | Version AutoCAD, tên bản vẽ đang mở |
| `GET /layers` | Danh sách layer |
| `GET /entities?type=line&limit=200` | Đối tượng trong ModelSpace |
| `GET /areas` | Đường bao kín: diện tích + chu vi + tổng |
| `POST /lisp {"expr": "(+ 1 2)"}` | Đánh giá biểu thức LISP |
| `POST /draw {"items": [...]}` | Vẽ line / polyline / circle / text |
| `POST /command {"cmd": "ZOOM E"}` | Gửi lệnh cho AutoCAD |

## Khắc phục nhanh

- "Khong ket noi duoc AutoCAD dang chay": mở AutoCAD 2022 trước, mở 1 bản
  vẽ, rồi thử lại (cầu nối không tự mở AutoCAD).
- "Cai pyautocad that bai" (cách 2): kiểm tra mạng, chạy lại `run.bat`.
- Lệnh vẽ / tính diện tích báo lỗi: kiểm tra AutoCAD có đang mở hộp thoại
  nào không — đóng hộp thoại rồi thử lại.
- Chu vi ellipse chưa lấy được qua COM (AutoCAD không cho sẵn) — diện tích
  ellipse vẫn có, chu vi để trống.

## Giới hạn bản 1.0

- Tầng HTTP đã kiểm thử bằng bản giả lập (15/15 PASS); phần nối vào
  AutoCAD thật cần thử cùng người dùng lần đầu để sửa nếu lệch.
- LISP chạy qua VisualLISP ActiveX (`VL.Application`); nếu máy thiếu thành
  phần này, cầu nối tự chuyển sang cách dự phòng (gửi lệnh + file tạm),
  chậm hơn một chút.
- Cầu nối chỉ làm việc khi AutoCAD đang mở và không bị hộp thoại chặn.

## File trong repo

- `bridge.py` — máy chủ HTTP (chạy bằng Python hoặc đóng gói thành .exe)
- `cadapi.py` — lớp nối AutoCAD qua COM (pyautocad) + bản giả lập để kiểm thử
- `run.bat` — chạy cầu nối từ source trên Windows
- `HUONG-DAN.txt` — hướng dẫn tiếng Việt chi tiết
- `test_bridge.py` — kiểm thử tầng HTTP bằng bản giả lập
- `.github/workflows/build.yml` — tự động đóng gói `cad-bridge.exe` trên
  Windows mỗi khi đẩy code lên nhánh main, đăng lên mục Releases.
