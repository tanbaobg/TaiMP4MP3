import os
import urllib.parse
import json
import asyncio
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel
import httpx
import yt_dlp

try:
    from extractor import extract_info, MediaInfo, clean_title
    from trimmer import get_ffmpeg_path, parse_time, format_time_code, get_stream_headers, calculate_kept_intervals
except ImportError:
    from .extractor import extract_info, MediaInfo, clean_title
    from .trimmer import get_ffmpeg_path, parse_time, format_time_code, get_stream_headers, calculate_kept_intervals

app = FastAPI(
    title="TaiMP4MP3 Serverless",
    description="Web, API & Multi-Segment Video Trimmer Serverless chạy trên Vercel",
    version="1.3.0",
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

def find_file(filename: str):
    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(base_dir, "static", filename),
        os.path.join(base_dir, "..", "public", filename),
        os.path.join(base_dir, filename),
        os.path.join("public", filename),
        os.path.join("web", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

# --- WEB UI ROUTES ---
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def serve_index():
    path = find_file("index.html")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(
                content=f.read(),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
            )
    return HTMLResponse("<h1>TaiMP4MP3</h1><p>Vui lòng thử lại sau giây lát...</p>")

@app.get("/style.css")
def serve_style():
    path = find_file("style.css")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="text/css")
    return Response(content="", media_type="text/css")

@app.get("/app.js")
def serve_app_js():
    path = find_file("app.js")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/manifest.json")
def serve_manifest():
    path = find_file("manifest.json")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="application/manifest+json")
    raise HTTPException(status_code=404)

@app.get("/sw.js")
def serve_sw():
    path = find_file("sw.js")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    raise HTTPException(status_code=404)

@app.get("/assets/{file_path:path}")
def serve_assets(file_path: str):
    path = find_file(os.path.join("assets", file_path))
    if path and os.path.exists(path):
        media_type = "image/png"
        if file_path.endswith(".svg"):
            media_type = "image/svg+xml"
        elif file_path.endswith(".json"):
            media_type = "application/json"
        return FileResponse(path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Asset not found")

@app.get("/apple-touch-icon.png")
def serve_apple_touch():
    path = find_file(os.path.join("assets", "apple-touch-icon.png"))
    if path and os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404)

@app.get("/taimp4mp3-latest.apk")
@app.get("/taimp4mp3.apk")
def download_apk():
    path = find_file("taimp4mp3-latest.apk") or find_file("taimp4mp3.apk")
    if path and os.path.exists(path):
        return FileResponse(
            path,
            media_type="application/vnd.android.package-archive",
            filename="taimp4mp3-latest.apk"
        )
    return RedirectResponse(
        url="https://github.com/tanbaobg/TaiMP4MP3/raw/main/web/taimp4mp3-latest.apk",
        status_code=302
    )

# --- API ROUTES ---
@app.get("/api")
def api_status():
    return {
        "app": "TaiMP4MP3 Serverless API",
        "platform": "Vercel",
        "status": "online",
        "version": "1.3.0",
        "features": ["video_download", "audio_extract", "multi_segment_trim", "keep_remove_modes"],
        "yt_dlp": yt_dlp.version.__version__,
    }

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.3.0",
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
        raise HTTPException(status_code=400, detail=f"Lỗi: {error_msg}")

@app.get("/download")
@app.get("/api/download")
async def download_proxy(
    url: str = Query(..., description="Đường dẫn file media trực tiếp"),
    title: str = Query("video", description="Tên file tải về"),
    ext: str = Query("mp4", description="Đuôi định dạng file (mp4, mp3, jpg)"),
    audio_url: Optional[str] = Query(None, description="Đường dẫn âm thanh nếu cần ghép video + audio"),
    is_slideshow: Optional[int] = Query(0, description="1 nếu là tạo video slideshow từ ảnh và nhạc"),
):
    decoded_url = urllib.parse.unquote(url)
    safe_name = clean_title(urllib.parse.unquote(title))
    filename = f"{safe_name}.{ext}"

    import re
    encoded_filename = urllib.parse.quote(filename)
    ascii_fallback = re.sub(r'[^\x20-\x7E]', '_', filename)
    content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_filename}'

    # 1. Trường hợp tạo Slideshow từ ảnh + nhạc nền (cho Album ảnh TikTok)
    if is_slideshow and audio_url:
        decoded_audio = urllib.parse.unquote(audio_url)
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            ffmpeg_bin, "-y",
            "-headers", "User-Agent: Mozilla/5.0\r\nReferer: https://www.tiktok.com/\r\n",
            "-loop", "1", "-i", decoded_url,
            "-headers", "User-Agent: Mozilla/5.0\r\nReferer: https://www.tiktok.com/\r\n",
            "-i", decoded_audio,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async def slideshow_stream():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        return StreamingResponse(
            slideshow_stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": content_disposition,
                "Accept-Ranges": "bytes",
            }
        )

    # 2. Trường hợp ghép Video + Audio (YouTube DASH)
    if audio_url and ext == "mp4":
        decoded_audio = urllib.parse.unquote(audio_url)
        ffmpeg_bin = get_ffmpeg_path()
        v_headers = get_stream_headers(decoded_url)
        a_headers = get_stream_headers(decoded_audio)
        cmd = [
            ffmpeg_bin, "-y",
            "-headers", v_headers,
            "-i", decoded_url,
            "-headers", a_headers,
            "-i", decoded_audio,
            "-c", "copy",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async def mux_stream():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        return StreamingResponse(
            mux_stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": content_disposition,
                "Accept-Ranges": "bytes",
            }
        )

    # 3. Trường hợp tải MP3 tách từ video có sẵn
    if ext == "mp3" and not any(k in decoded_url for k in [".mp3", "audio", "sound", "music"]):
        ffmpeg_bin = get_ffmpeg_path()
        v_headers = get_stream_headers(decoded_url)
        cmd = [
            ffmpeg_bin, "-y",
            "-headers", v_headers,
            "-i", decoded_url,
            "-vn",
            "-c:a", "libmp3lame", "-q:a", "2",
            "-f", "mp3",
            "pipe:1"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async def mp3_stream():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        return StreamingResponse(
            mp3_stream(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": content_disposition,
                "Accept-Ranges": "bytes",
            }
        )

    # 4. Stream trực tiếp (Facebook, TikTok Video gốc, Ảnh JPG, MP3 direct)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    if any(k in decoded_url for k in ["tiktok", "byteoversea", "ibytedtos", "tikwm", "musical.ly"]):
        headers["Referer"] = "https://www.tiktok.com/"
    elif any(k in decoded_url for k in ["facebook", "fbcdn", "fbsbx"]):
        headers["Referer"] = "https://www.facebook.com/"

    client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    try:
        req = client.build_request("GET", decoded_url, headers=headers)
        res = await client.send(req, stream=True)

        media_type = "video/mp4" if ext == "mp4" else ("image/jpeg" if ext in ["jpg", "jpeg"] else "audio/mpeg")

        async def stream_generator():
            try:
                async for chunk in res.aiter_bytes(chunk_size=1024 * 64):
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

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

@app.get("/stream")
@app.get("/api/stream")
async def stream_proxy(
    request: Request,
    url: str = Query(..., description="Đường dẫn file media trực tiếp để phát trong player"),
    audio_url: Optional[str] = Query(None, description="Đường dẫn âm thanh nếu cần ghép phát"),
    is_slideshow: Optional[int] = Query(0, description="1 nếu là slideshow từ ảnh và nhạc"),
):
    """Proxy media trực tiếp vào thẻ <video> của trình duyệt với Range Header và hỗ trợ ghép audio on-the-fly."""
    decoded_url = urllib.parse.unquote(url)

    if is_slideshow and audio_url:
        decoded_audio = urllib.parse.unquote(audio_url)
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            ffmpeg_bin, "-y",
            "-headers", "User-Agent: Mozilla/5.0\r\nReferer: https://www.tiktok.com/\r\n",
            "-loop", "1", "-i", decoded_url,
            "-headers", "User-Agent: Mozilla/5.0\r\nReferer: https://www.tiktok.com/\r\n",
            "-i", decoded_audio,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async def slideshow_stream_gen():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        return StreamingResponse(
            slideshow_stream_gen(),
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}
        )

    if audio_url:
        decoded_audio = urllib.parse.unquote(audio_url)
        ffmpeg_bin = get_ffmpeg_path()
        v_headers = get_stream_headers(decoded_url)
        a_headers = get_stream_headers(decoded_audio)
        cmd = [
            ffmpeg_bin, "-y",
            "-headers", v_headers,
            "-i", decoded_url,
            "-headers", a_headers,
            "-i", decoded_audio,
            "-c", "copy",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
            "pipe:1"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        async def stream_mux_gen():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

        return StreamingResponse(
            stream_mux_gen(),
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    if any(k in decoded_url for k in ["tiktok", "byteoversea", "ibytedtos", "tikwm", "musical.ly"]):
        headers["Referer"] = "https://www.tiktok.com/"
    elif any(k in decoded_url for k in ["facebook", "fbcdn", "fbsbx"]):
        headers["Referer"] = "https://www.facebook.com/"

    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    try:
        req = client.build_request("GET", decoded_url, headers=headers)
        res = await client.send(req, stream=True)

        async def stream_gen():
            try:
                async for chunk in res.aiter_bytes(chunk_size=1024 * 64):
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

        resp_headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": res.headers.get("Content-Type", "video/mp4"),
        }
        if "Content-Range" in res.headers:
            resp_headers["Content-Range"] = res.headers["Content-Range"]
        if "Content-Length" in res.headers:
            resp_headers["Content-Length"] = res.headers["Content-Length"]

        return StreamingResponse(
            stream_gen(),
            status_code=res.status_code,
            headers=resp_headers
        )
    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Lỗi khi stream video: {str(e)}")

# --- MULTI-SEGMENT VIDEO & AUDIO TRIMMER ---
@app.get("/trim")
@app.get("/api/trim")
async def trim_media(
    url: str = Query(..., description="Đường dẫn file media trực tiếp"),
    start: Optional[str] = Query(None, description="Thời điểm bắt đầu"),
    end: Optional[str] = Query(None, description="Thời điểm kết thúc"),
    segments: Optional[str] = Query(None, description="Mảng các đoạn JSON [{'start':..., 'end':...}]"),
    mode: str = Query("keep", description="'keep' để lấy các đoạn, 'remove' để cắt bỏ các đoạn"),
    type: str = Query("video", description="'video' hoặc 'audio'"),
    duration: float = Query(0.0, description="Tổng thời lượng"),
    title: str = Query("trimmed", description="Tên file tải về"),
):
    decoded_url = urllib.parse.unquote(url)
    safe_title = clean_title(urllib.parse.unquote(title))
    ext = "mp4" if type == "video" else "mp3"
    media_type = "video/mp4" if type == "video" else "audio/mpeg"

    ffmpeg_bin = get_ffmpeg_path()
    headers_str = get_stream_headers(decoded_url)

    # Parse segments
    raw_segments = []
    if segments:
        try:
            parsed = json.loads(urllib.parse.unquote(segments))
            if isinstance(parsed, list):
                for item in parsed:
                    s = parse_time(item.get("start"))
                    e = parse_time(item.get("end"))
                    if e > s:
                        raw_segments.append((s, e))
        except Exception:
            pass

    if not raw_segments:
        s_val = parse_time(start) if start else 0.0
        e_val = parse_time(end) if end else (s_val + 30.0)
        raw_segments = [(s_val, e_val)]

    kept_intervals = calculate_kept_intervals(raw_segments, mode=mode, total_duration=duration)
    if not kept_intervals:
        kept_intervals = [(0.0, max(duration, 30.0))]

    # Build filename
    action_label = "lay" if mode == "keep" else "bo"
    filename = f"{safe_title}_{action_label}_{len(raw_segments)}doan.{ext}"

    # Single segment optimization (Lossless stream copy)
    if len(kept_intervals) == 1:
        k_start, k_end = kept_intervals[0]
        if type == "video":
            cmd = [
                ffmpeg_bin, "-y",
                "-ss", str(k_start),
                "-to", str(k_end),
                "-headers", headers_str,
                "-i", decoded_url,
                "-c", "copy",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "pipe:1"
            ]
        else:
            cmd = [
                ffmpeg_bin, "-y",
                "-ss", str(k_start),
                "-to", str(k_end),
                "-headers", headers_str,
                "-i", decoded_url,
                "-vn",
                "-c:a", "libmp3lame", "-q:a", "2",
                "-f", "mp3",
                "pipe:1"
            ]
    else:
        # Multi-segment concat filtering
        filter_parts = []
        concat_inputs = []
        for i, (k_start, k_end) in enumerate(kept_intervals):
            if type == "video":
                filter_parts.append(f"[0:v]trim={k_start}:{k_end},setpts=PTS-STARTPTS[v{i}]")
                concat_inputs.append(f"[v{i}]")
            filter_parts.append(f"[0:a]atrim={k_start}:{k_end},asetpts=PTS-STARTPTS[a{i}]")
            concat_inputs.append(f"[a{i}]")

        if type == "video":
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(kept_intervals)}:v=1:a=1[outv][outa]")
            cmd = [
                ffmpeg_bin, "-y",
                "-headers", headers_str,
                "-i", decoded_url,
                "-filter_complex", ";".join(filter_parts),
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "pipe:1"
            ]
        else:
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(kept_intervals)}:v=0:a=1[outa]")
            cmd = [
                ffmpeg_bin, "-y",
                "-headers", headers_str,
                "-i", decoded_url,
                "-filter_complex", ";".join(filter_parts),
                "-map", "[outa]",
                "-c:a", "libmp3lame", "-q:a", "2",
                "-f", "mp3",
                "pipe:1"
            ]

    encoded_filename = urllib.parse.quote(filename)
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def stream_ffmpeg():
            try:
                while True:
                    chunk = await proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        return StreamingResponse(
            stream_ffmpeg(),
            media_type=media_type,
            headers={
                "Content-Disposition": content_disposition,
                "Accept-Ranges": "bytes",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cắt ghép video/audio: {str(e)}")
