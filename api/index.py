import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import httpx
import yt_dlp

try:
    from extractor import extract_info, MediaInfo, clean_title
except ImportError:
    from .extractor import extract_info, MediaInfo, clean_title

app = FastAPI(
    title="TaiMP4MP3 Serverless API",
    description="Vercel Serverless Function trích xuất video từ TikTok, Facebook, YouTube",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.get("/")
@app.get("/api")
def root():
    return {
        "app": "TaiMP4MP3 Serverless API",
        "platform": "Vercel",
        "status": "online",
        "yt_dlp": yt_dlp.version.__version__,
    }

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "yt_dlp": yt_dlp.version.__version__,
    }

@app.post("/analyze", response_model=MediaInfo)
@app.post("/api/analyze", response_model=MediaInfo)
async def analyze_url(req: AnalyzeRequest, request: Request):
    target_url = req.url.strip()
    if not target_url:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp đường dẫn URL hợp lệ")

    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    base_url = str(request.base_url).rstrip("/")

    try:
        media_info = extract_info(target_url, base_api_url=base_url)
        return media_info
    except Exception as e:
        error_msg = str(e)
        if "Unsupported URL" in error_msg:
            detail = "Đường dẫn không được hỗ trợ hoặc không tồn tại."
        elif "Private video" in error_msg or "Sign in" in error_msg:
            detail = "Video này đang ở chế độ riêng tư hoặc yêu cầu đăng nhập."
        else:
            detail = f"Không thể lấy thông tin video: {error_msg}"
        raise HTTPException(status_code=400, detail=detail)

@app.get("/download")
@app.get("/api/download")
async def download_proxy(
    url: str = Query(..., description="Đường dẫn file media trực tiếp"),
    title: str = Query("video", description="Tên file tải về"),
    ext: str = Query("mp4", description="Đuôi định dạng file (mp4, mp3)"),
):
    decoded_url = urllib.parse.unquote(url)
    safe_name = clean_title(urllib.parse.unquote(title))
    filename = f"{safe_name}.{ext}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    if "tiktok" in decoded_url or "byteoversea" in decoded_url:
        headers["Referer"] = "https://www.tiktok.com/"
    elif "facebook" in decoded_url or "fbcdn" in decoded_url:
        headers["Referer"] = "https://www.facebook.com/"

    client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    try:
        req = client.build_request("GET", decoded_url, headers=headers)
        res = await client.send(req, stream=True)

        media_type = "video/mp4" if ext == "mp4" else "audio/mpeg"

        async def stream_generator():
            try:
                async for chunk in res.aiter_bytes(chunk_size=1024 * 64):
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

        encoded_filename = urllib.parse.quote(filename)
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

        return StreamingResponse(
            stream_generator(),
            media_type=media_type,
            headers={
                "Content-Disposition": content_disposition,
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Lỗi khi tải stream: {str(e)}")
