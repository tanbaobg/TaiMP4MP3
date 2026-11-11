import re
import urllib.parse
import urllib.request
import json
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
    if any(k in url_lower for k in ["tiktok.com", "douyin.com", "vt.tiktok", "vm.tiktok"]):
        return "tiktok"
    elif any(k in url_lower for k in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif any(k in url_lower for k in ["facebook.com", "fb.watch", "fb.com", "fb.gg"]):
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


def extract_tiktok_direct(url: str, base_api_url: str = "") -> Optional[MediaInfo]:
    """Bóc tách link video và nhạc TikTok không logo tốc độ cao qua TikWM API."""
    try:
        # Xử lý tự động rút gọn link vt.tiktok.com hoặc vm.tiktok.com
        if any(k in url.lower() for k in ["vt.tiktok", "vm.tiktok", "/t/"]):
            try:
                head_req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
                        ),
                    }
                )
                with urllib.request.urlopen(head_req, timeout=5) as head_resp:
                    resolved = head_resp.geturl()
                    if "tiktok.com" in resolved and "/video/" in resolved:
                        url = resolved.split("?")[0]
            except Exception:
                pass

        api_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("code") == 0:
            d = data.get("data", {})
            title = d.get("title") or "Video TikTok không logo"
            safe_title = clean_title(title)
            author = d.get("author", {}).get("nickname") or d.get("author", {}).get("unique_id") or "TikTok"
            thumbnail = d.get("cover") or d.get("origin_cover") or ""
            duration = d.get("duration")
            duration_val = int(round(float(duration))) if duration is not None else None

            play_url = d.get("play") or ""
            if play_url.startswith("/"):
                play_url = f"https://www.tikwm.com{play_url}"

            music_url = d.get("music") or ""
            if music_url.startswith("/"):
                music_url = f"https://www.tikwm.com{music_url}"

            formats: List[FormatOption] = []
            # 1. Định dạng chuẩn H.264 không logo (Tương thích 100% hình & tiếng trên mọi trình duyệt & thiết bị)
            if play_url:
                formats.append(
                    FormatOption(
                        id="tiktok-nowm",
                        quality="MP4 Không Logo (Có hình & tiếng)",
                        type="video",
                        ext="mp4",
                        filesize_str=format_filesize(d.get("size")) or "Chuẩn H.264 Nét",
                        direct_url=play_url,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(play_url)}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                        watermark=False,
                    )
                )

            # 2. Âm thanh gốc MP3
            if music_url:
                formats.append(
                    FormatOption(
                        id="tiktok-audio",
                        quality="MP3 Âm thanh gốc (320kbps)",
                        type="audio",
                        ext="mp3",
                        filesize_str="320 kbps",
                        direct_url=music_url,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(music_url)}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                        has_audio=True,
                        watermark=False,
                    )
                )

            if formats:
                return MediaInfo(
                    url=url,
                    title=title,
                    platform="tiktok",
                    thumbnail=thumbnail,
                    duration_str=format_duration(duration_val),
                    duration_seconds=duration_val,
                    author=author,
                    formats=formats,
                )
    except Exception:
        pass
    return None


def extract_info(url: str, base_api_url: str = "") -> MediaInfo:
    platform = detect_platform(url)

    # 1. Với TikTok: Ưu tiên bóc tách link direct không watermark qua TikWM API
    if platform == "tiktok":
        tiktok_res = extract_tiktok_direct(url, base_api_url=base_api_url)
        if tiktok_res:
            return tiktok_res

    # 2. Với Facebook, YouTube và các nền tảng khác: Dùng yt-dlp tối ưu có tiếng
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
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

    if platform == "facebook":
        ydl_opts["http_headers"]["Referer"] = "https://www.facebook.com/"
    elif platform == "tiktok":
        ydl_opts["http_headers"]["Referer"] = "https://www.tiktok.com/"
    elif platform == "youtube":
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android"],
                "player_skip": ["webpage", "configs"],
            }
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
            if platform == "youtube":
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["ios", "android"],
                        "player_skip": ["webpage", "configs"],
                    }
                }
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

    # --- TIKTOK FALLBACK ---
    if platform == "tiktok":
        valid_videos = []
        for f in raw_formats:
            f_url = f.get("url")
            vcodec = str(f.get("vcodec", "")).lower()
            acodec = str(f.get("acodec", "")).lower()
            fmt_id = str(f.get("format_id", "")).lower()
            if not f_url or vcodec == "none" or acodec == "none":
                continue
            # Tuyệt đối loại bỏ ByteVC1 / H.265 để đảm bảo video luôn có hình trên mọi trình duyệt & thiết bị
            if "bytevc1" in fmt_id or "bytevc1" in vcodec or "h265" in vcodec or "hevc" in vcodec:
                continue
            valid_videos.append(f)

        best_v = valid_videos[-1]["url"] if valid_videos else None
        if not best_v:
            # Tìm bất kỳ định dạng h264 nào có url
            h264_fmts = [f for f in raw_formats if f.get("url") and "h264" in str(f.get("format_id", "")).lower()]
            if h264_fmts:
                best_v = h264_fmts[-1]["url"]
            elif raw_formats:
                best_v = raw_formats[0].get("url") or info.get("url")
            else:
                best_v = info.get("url")

        if best_v:
            formats.append(
                FormatOption(
                    id="tiktok-nowm",
                    quality="MP4 Không Logo (Có hình & tiếng)",
                    type="video",
                    ext="mp4",
                    filesize_str="Chuẩn H.264 Siêu Nét",
                    direct_url=best_v,
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(best_v)}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                    watermark=False,
                )
            )

        for f in raw_formats:
            f_url = f.get("url", "")
            if f.get("vcodec") == "none" and f.get("acodec") != "none" and f_url:
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

    # --- FACEBOOK (CHỈ LẤY CÁC ĐỊNH DẠNG CÓ ĐẦY ĐỦ TIẾNG & HÌNH) ---
    elif platform == "facebook":
        # Lọc bỏ hoàn toàn các stream DASH video bị câm (acodec == 'none')
        valid_videos = []
        for f in raw_formats:
            f_url = f.get("url")
            if not f_url:
                continue
            v = f.get("vcodec")
            a = f.get("acodec")
            # Phải có hình và KHÔNG ĐƯỢC câm tiếng
            if v == "none" or a == "none":
                continue
            valid_videos.append(f)

        for f in valid_videos:
            f_id = str(f.get("format_id", "")).lower()
            f_note = str(f.get("format_note", "")).upper()
            height = f.get("height") or 0

            is_hd = ("hd" in f_id or "hd" in f_note or height >= 720)
            q_id = "fb-hd" if is_hd else "fb-sd"
            q_label = "MP4 HD (Có tiếng)" if is_hd else "MP4 SD (Có tiếng)"

            if q_id not in seen_qualities:
                seen_qualities.add(q_id)
                size_str = format_filesize(f.get("filesize") or f.get("filesize_approx"))
                formats.append(
                    FormatOption(
                        id=q_id,
                        quality=q_label,
                        type="video",
                        ext="mp4",
                        filesize_str=size_str or ("Chuẩn HD" if is_hd else "Chuẩn SD"),
                        direct_url=f["url"],
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(f['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                    )
                )

        # Sắp xếp để HD đứng trước
        formats.sort(key=lambda x: (0 if "hd" in x.id else 1))

        # Nếu không có định dạng video nào vượt qua bộ lọc nhưng info.get("url") có
        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="fb-best",
                    quality="MP4 Video HD (Có tiếng)",
                    type="video",
                    ext="mp4",
                    filesize_str="Chuẩn HD",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

        # Âm thanh MP3
        direct_audio = next((f["url"] for f in raw_formats if f.get("vcodec") == "none" and f.get("url")), None)
        if not direct_audio and valid_videos:
            direct_audio = valid_videos[0]["url"]
        if direct_audio:
            formats.append(
                FormatOption(
                    id="fb-audio-mp3",
                    quality="MP3 Âm thanh (Nhạc gốc)",
                    type="audio",
                    ext="mp3",
                    filesize_str="Chất lượng cao",
                    direct_url=direct_audio,
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(direct_audio)}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                    has_audio=True,
                )
            )

    # --- YOUTUBE & NỀN TẢNG KHÁC (CHỈ LẤY CÁC ĐỊNH DẠNG CÓ CẢ VIDEO VÀ AUDIO) ---
    else:
        progressive_formats = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
        ]
        progressive_formats.sort(key=lambda x: (x.get("height") or 0), reverse=True)

        for f in progressive_formats:
            height = f.get("height") or 0
            q_key = f"{height}p" if height else "mp4"
            if q_key not in seen_qualities:
                seen_qualities.add(q_key)
                size_str = format_filesize(f.get("filesize") or f.get("filesize_approx"))
                quality_title = f"MP4 {height}p (Có tiếng)" if height else "MP4 Chuẩn (Có tiếng)"
                formats.append(
                    FormatOption(
                        id=f"yt-{height}p" if height else "yt-std",
                        quality=quality_title,
                        type="video",
                        ext="mp4",
                        filesize_str=size_str or "Độ nét cao",
                        direct_url=f["url"],
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(f['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                    )
                )

        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="best-video",
                    quality="MP4 Tốt nhất (Có tiếng)",
                    type="video",
                    ext="mp4",
                    filesize_str="Tối ưu",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

        # Audio formats (Phải có acodec, không lấy storyboard ảnh thumbnail)
        audio_formats = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") == "none" and f.get("acodec") != "none"
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
        elif progressive_formats:
            # Nếu không có stream audio riêng, trích xuất âm thanh từ progressive video stream
            best_prog = progressive_formats[0]
            formats.append(
                FormatOption(
                    id="audio-from-video",
                    quality="MP3 Âm thanh gốc (320kbps)",
                    type="audio",
                    ext="mp3",
                    filesize_str="Chất lượng cao",
                    direct_url=best_prog["url"],
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(best_prog['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp3",
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
