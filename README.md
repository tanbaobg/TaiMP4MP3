# 🎬 TaiMP4MP3 — Trình Tải Video & Âm Thanh Đa Nền Tảng (Android & Web)

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Android%20%7C%20Web-blue?style=for-the-badge&logo=android" alt="Platforms">
  <img src="https://img.shields.io/badge/TikTok-No%20Watermark-pink?style=for-the-badge&logo=tiktok" alt="TikTok">
  <img src="https://img.shields.io/badge/Facebook-Full%20HD-blue?style=for-the-badge&logo=facebook" alt="Facebook">
  <img src="https://img.shields.io/badge/YouTube-MP4%20%2F%20MP3-red?style=for-the-badge&logo=youtube" alt="YouTube">
  <img src="https://img.shields.io/badge/Backend-FastAPI%20%2B%20yt--dlp-emerald?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License">
</p>

**TaiMP4MP3** là giải pháp toàn diện cho phép tải video và âm thanh (MP4/MP3) chất lượng cao từ **TikTok (không logo)**, **Facebook (HD)**, và **YouTube (MP4 1080p, MP3 320kbps)**, hoạt động đồng thời trên cả **Trình duyệt Web** và **Ứng dụng Android**.

---

## 🌟 Tính Năng Nổi Bật

- 🎯 **TikTok Không Logo (No Watermark):** Bóc tách và tải trực tiếp video TikTok HD sạch không dính ID và watermark.
- 📱 **Facebook Full HD:** Tự động lấy các luồng video chất lượng cao nhất (1080p, 720p HD, SD).
- 🎵 **YouTube MP4 & MP3:** Tải video độ phân giải cao hoặc bóc tách riêng luồng âm thanh MP3 320kbps chất lượng studio.
- 📲 **Ứng Dụng Android Native:**
  - Tích hợp **Android DownloadManager**: Tải ngầm, có thanh thông báo tiến trình, lưu trực tiếp vào thư mục `/Download/TaiMP4MP3/`.
  - Hỗ trợ **Menu Chia Sẻ (Share Intent)**: Khi xem video trên app TikTok hoặc YouTube, chỉ cần bấm *Chia sẻ* ➔ Chọn *TaiMP4MP3*, app sẽ tự động nhận link và phân tích ngay lập tức.
- 🌐 **Web App & PWA Hiện Đại:** Giao diện Dark Mode Glassmorphism, tự động nhận diện liên kết từ clipboard, xem trước video/nhạc trước khi tải.
- 🚀 **CI/CD Tự Động Hóa:** GitHub Actions tự động build file APK Release mới nhất ngay khi bạn push code lên GitHub.

---

## 🏗️ Cấu Trúc Dự Án

```
TaiMP4MP3/
├── .github/
│   └── workflows/
│       └── build-apk.yml          # GitHub Actions tự động build file Android APK
├── app/                           # Mã nguồn Ứng dụng Android (Kotlin, Gradle)
│   ├── src/main/
│   │   ├── java/com/tanbao/taimp4mp3/MainActivity.kt  # WebView + DownloadManager
│   │   ├── assets/web/            # Bundle web offline chạy ngay trong APK
│   │   ├── res/                   # Giao diện, icon, cấu hình mạng
│   │   └── AndroidManifest.xml    # Khai báo quyền tải & Share Intent
│   └── build.gradle.kts
├── backend/                       # Máy chủ Backend API (Python FastAPI + yt-dlp)
│   ├── main.py                    # REST API: /api/analyze, /api/download, /api/health
│   ├── extractor.py               # Thuật toán bóc tách TikTok, FB, YouTube
│   ├── requirements.txt           # Thư viện phụ thuộc
│   ├── Dockerfile                 # Đóng gói Docker để deploy Render/Railway/VPS
│   ├── render.yaml                # Cấu hình 1-click deploy Render.com
│   └── railway.json               # Cấu hình 1-click deploy Railway
├── web/                           # Giao diện Web Client & PWA
│   ├── index.html                 # Giao diện người dùng Tailwind CSS & Lucide Icons
│   ├── app.js                     # Xử lý logic tải, dán clipboard, lưu lịch sử
│   ├── style.css                  # Hiệu ứng Glassmorphism & Animations
│   ├── manifest.json              # Khai báo PWA (Installable Web App)
│   └── sw.js                      # Service Worker lưu cache offline
├── build.gradle.kts               # Cấu hình Gradle Root
├── settings.gradle.kts
├── vercel.json                    # Cấu hình deploy Web lên Vercel
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Thử

### 1. Khởi động Backend (Python FastAPI)

Backend chịu trách nhiệm bóc tách link từ các nền tảng và cung cấp luồng tải trực tiếp:

```bash
# Di chuyển vào thư mục backend
cd backend

# Tạo môi trường ảo (khuyến nghị)
python -m venv venv
# Kích hoạt trên Windows:
venv\Scripts\activate
# Hoặc trên Linux/macOS:
# source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt

# Khởi chạy server API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

* API Swagger UI sẽ có tại: `http://localhost:8000/docs`
* Kiểm tra trạng thái: `http://localhost:8000/api/health`

### 2. Chạy Frontend trên Trình Duyệt Web

Bạn có thể mở trực tiếp file `web/index.html` trên trình duyệt, hoặc chạy qua máy chủ tĩnh:

```bash
# Dùng npx serve hoặc python http.server
cd web
python -m http.server 3000
```
Truy cập: `http://localhost:3000`

> **Mẹo:** Vào biểu tượng **Cài đặt (bánh răng)** trên góc phải màn hình để kiểm tra hoặc đổi URL máy chủ Backend của bạn.

---

## 📱 Build Ứng Dụng Android APK

### Cách 1: Tải trực tiếp từ GitHub Actions (Tự động)
Mỗi khi bạn commit/push code lên nhánh `main`, **GitHub Actions** sẽ tự động biên dịch và tạo sẵn file APK tại mục **Actions / Releases** của kho lưu trữ này.

### Cách 2: Tự build bằng dòng lệnh (Gradle)
```bash
# Windows
.\gradlew.bat assembleRelease

# Linux / macOS
./gradlew assembleRelease
```
File APK hoàn thiện sẽ nằm tại: `app/build/outputs/apk/release/app-release.apk`.

---

## ☁️ Triển Khai Lên Vercel & Cloud Miễn Phí

### ⚡ 1. Chạy hoàn toàn trên Vercel (Khuyên dùng)
Dự án đã được cấu hình sẵn **Vercel Serverless Functions (Python)** tại thư mục `/api` và giao diện Web tại `/web`:
1. Truy cập [Vercel Dashboard](https://vercel.com/new).
2. Chọn **Import** kho lưu trữ: `https://github.com/tanbaobg/TaiMP4MP3`.
3. Bấm **Deploy** (không cần cấu hình thêm gì).
4. Vercel sẽ tự động:
   - Triển khai giao diện Web tốc độ cao (PWA) với liên kết tải APK trực tiếp.
   - Kích hoạt Python Serverless Function tại `/api/analyze` và `/api/download` để bóc tách video.

### 🌐 2. Triển khai Backend riêng trên Render / Railway / VPS:
- **Render.com:** Kết nối repo, chọn file cấu hình `backend/render.yaml`.
- **Railway.app:** Tạo Project mới, chọn `backend/Dockerfile`.
- **Docker / VPS:**
  ```bash
  docker build -t taimp4mp3-api backend/
  docker run -d -p 8000:8000 --name taimp4mp3 taimp4mp3-api
  ```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)

Dự án này được tạo ra cho mục đích học tập, nghiên cứu kỹ thuật và sao lưu dữ liệu cá nhân hợp pháp. Vui lòng tôn trọng quyền sở hữu trí tuệ, bản quyền tác giả và điều khoản dịch vụ (ToS) của từng nền tảng khi sử dụng.

---

## 👨‍💻 Tác giả & Đóng góp

- **Tác giả:** [tanbaobg](https://github.com/tanbaobg)
- **Kho lưu trữ:** [TaiMP4MP3](https://github.com/tanbaobg/TaiMP4MP3)
- Đóng góp (Pull Requests) và báo lỗi (Issues) luôn được chào đón!
