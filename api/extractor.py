import re
import urllib.parse
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
import yt_dlp

class FormatOption(BaseModel):
    id: str
    quality: str
    type: str  # "video" or "audio"
    ext: str   # "mp4", "mp3", "m4a"
    filesize_str: Optional[str] = None
    filesize_bytes: Optional[int] = None
    direct_url: Optional[str] = None
    proxy_url: Optional[str] = None
    has_audio: bool = True
    watermark: bool = False

class MediaInfo(BaseModel):
    url: str
    title: str
    platform: str  # "tiktok", "youtube", "facebook", "other"
    thumbnail: Optional[str] = None
    duration_str: Optional[str] = None
    duration_seconds: Optional[Union[int, float]] = None
    author: Optional[str] = None
    formats: List[FormatOption] = []


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if any(k in url_lower for k in ["tiktok.com", "douyin.com"]):
        return "tiktok"
    elif any(k in url_lower for k in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif any(k in url_lower for k in ["facebook.com", "fb.watch", "fb.com"]):
        return "facebook"
    elif "instagram.com" in url_lower:
        return "instagram"
    elif any(k in url_lower for k in ["x.com", "twitter.com"]):
        return "twitter"
    return "other"


def format_duration(seconds: Any) -> str:
    if not seconds:
        return ""
    try:
        sec_int = int(round(float(seconds)))
        m, s = divmod(sec_int, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except Exception:
        return ""


def format_filesize(bytes_val: Any) -> str:
    if not bytes_val:
        return ""
    try:
        val = float(bytes_val)
        if val <= 0:
            return ""
        mb = val / (1024 * 1024)
        if mb >= 1024:
            return f"{mb / 1024:.1f} GB"
        return f"{mb:.1f} MB"
    except Exception:
        return ""


def clean_title(title: str) -> str:
    cleaned = title.replace("\n", " ").replace("\r", " ")
    cleaned = re.sub(r'[\\/*?:"<>|]', "", cleaned)
    cleaned = re.sub(r'\s+', " ", cleaned).strip()
    return cleaned[:80] or "video"


def extract_info(url: str, base_api_url: str = "") -> MediaInfo:
    platform = detect_platform(url)

    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "format": "best",
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }

    if platform == "tiktok":
        ydl_opts["http_headers"]["Referer"] = "https://www.tiktok.com/"
    elif platform == "facebook":
        ydl_opts["http_headers"]["Referer"] = "https://www.facebook.com/"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
            ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
            with yt_dlp.YoutubeDL(ydl_opts) as fallback_ydl:
                info = fallback_ydl.extract_info(url, download=False)

    title = info.get("title") or info.get("description") or "Video không tiêu đề"
    safe_title = clean_title(title)
    thumbnail = info.get("thumbnail") or ""
    duration = info.get("duration")
    duration_val = None
    if duration is not None:
        try:
            duration_val = int(round(float(duration)))
        except Exception:
            duration_val = None

    author = info.get("uploader") or info.get("channel") or info.get("creator") or platform.capitalize()

    raw_formats = info.get("formats", [])
    formats: List[FormatOption] = []
    seen_qualities = set()

    # --- 1. TIKTOK ---
    if platform == "tiktok":
        best_video_url = info.get("url")
        for f in raw_formats:
            f_url = f.get("url", "")
            if not f_url:
                continue
            is_audio = f.get("vcodec") == "none"
            if not is_audio:
                best_video_url = f_url
                break

        if best_video_url:
            formats.append(
                FormatOption(
                    id="tiktok-hd-nowatermark",
                    quality="MP4 Không Logo (HD)",
                    type="video",
                    ext="mp4",
                    filesize_str="HD Siêu Nét",
                    direct_url=best_video_url,
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(best_video_url)}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                    watermark=False,
                )
            )

        for f in raw_formats:
            f_url = f.get("url", "")
            if f.get("vcodec") == "none" and f_url:
                formats.append(
                    FormatOption(
                        id="tiktok-audio",
                        quality="MP3 Âm thanh gốc",
                        type="audio",
                        ext="mp3",
                        filesize_str=format_filesize(f.get("filesize") or f.get("filesize_approx")),
                        direct_url=f_url,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(f_url)}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                        has_audio=True,
                        watermark=False,
                    )
                )
                break

    # --- 2. FACEBOOK ---
    elif platform == "facebook":
        for f in reversed(raw_formats):
            f_url = f.get("url", "")
            if not f_url:
                continue
            f_id = str(f.get("format_id", ""))
            f_note = str(f.get("format_note", "")).upper()
            height = f.get("height") or 0

            quality_label = "HD" if ("HD" in f_id or "HD" in f_note or height >= 720) else "SD"
            if quality_label not in seen_qualities:
                seen_qualities.add(quality_label)
                size_str = format_filesize(f.get("filesize") or f.get("filesize_approx"))
                formats.append(
                    FormatOption(
                        id=f"fb-{quality_label.lower()}",
                        quality=f"MP4 {quality_label} ({height}p)" if height else f"MP4 {quality_label}",
                        type="video",
                        ext="mp4",
                        filesize_str=size_str or "Chuẩn HD",
                        direct_url=f_url,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(f_url)}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                    )
                )

        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="fb-best",
                    quality="MP4 Video HD",
                    type="video",
                    ext="mp4",
                    filesize_str="Chuẩn HD",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

        direct_audio = next((f["url"] for f in raw_formats if f.get("vcodec") == "none" and f.get("url")), None)
        if direct_audio:
            formats.append(
                FormatOption(
                    id="fb-audio-mp3",
                    quality="MP3 Âm thanh",
                    type="audio",
                    ext="mp3",
                    filesize_str="Chất lượng tốt",
                    direct_url=direct_audio,
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(direct_audio)}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                )
            )

    # --- 3. YOUTUBE & OTHERS ---
    else:
        progressive_formats = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
        ]
        progressive_formats.sort(key=lambda x: (x.get("height") or 0), reverse=True)

        for f in progressive_formats:
            height = f.get("height") or 0
            if not height:
                continue
            q_key = f"{height}p"
            if q_key not in seen_qualities and height in [1080, 720, 480, 360, 240]:
                seen_qualities.add(q_key)
                size_str = format_filesize(f.get("filesize") or f.get("filesize_approx"))
                formats.append(
                    FormatOption(
                        id=f"yt-{height}p",
                        quality=f"MP4 {height}p {'(Full HD)' if height >= 1080 else '(HD)' if height >= 720 else '(SD)'}",
                        type="video",
                        ext="mp4",
                        filesize_str=size_str,
                        direct_url=f["url"],
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(f['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                    )
                )

        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="best-video",
                    quality="MP4 Tốt nhất (Mặc định)",
                    type="video",
                    ext="mp4",
                    filesize_str="Tối ưu",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

        audio_formats = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") == "none"
        ]
        audio_formats.sort(key=lambda x: (x.get("abr") or 0), reverse=True)

        if audio_formats:
            best_audio = audio_formats[0]
            abr = best_audio.get("abr")
            abr_str = f"{int(abr)} kbps" if abr else "320 kbps"
            formats.append(
                FormatOption(
                    id="audio-high",
                    quality=f"MP3 Chất lượng cao ({abr_str})",
                    type="audio",
                    ext="mp3",
                    filesize_str=format_filesize(best_audio.get("filesize") or best_audio.get("filesize_approx")),
                    direct_url=best_audio["url"],
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(best_audio['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                    has_audio=True,
                )
            )

    return MediaInfo(
        url=url,
        title=title,
        platform=platform,
        thumbnail=thumbnail,
        duration_str=format_duration(duration_val),
        duration_seconds=duration_val,
        author=author,
        formats=formats,
    )
