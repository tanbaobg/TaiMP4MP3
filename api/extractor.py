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
    type: str  # "video", "audio", "image"
    ext: str   # "mp4", "mp3", "m4a", "jpg"
    filesize_str: Optional[str] = None
    filesize_bytes: Optional[int] = None
    direct_url: Optional[str] = None
    proxy_url: Optional[str] = None
    audio_url: Optional[str] = None  # Secondary audio stream for muxing
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
    images: List[str] = []


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


_cached_youtube_cookiejar = None

def get_youtube_cookiejar():
    """Tạo hoặc tái sử dụng CookieJar với visitor session cookies từ YouTube để vượt qua kiểm tra Bot trên cloud serverless."""
    global _cached_youtube_cookiejar
    if _cached_youtube_cookiejar is not None:
        return _cached_youtube_cookiejar
    try:
        from yt_dlp.cookies import YoutubeDLCookieJar
        jar = YoutubeDLCookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        req = urllib.request.Request(
            "https://www.youtube.com/",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        opener.open(req, timeout=5)
        _cached_youtube_cookiejar = jar
        return jar
    except Exception:
        return None


def extract_tiktok_direct(url: str, base_api_url: str = "") -> Optional[MediaInfo]:
    """Bóc tách link video, ảnh và nhạc TikTok không logo tốc độ cao qua TikWM API."""
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
                    if "tiktok.com" in resolved and ("/video/" in resolved or "/photo/" in resolved):
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
            title = d.get("title") or "TikTok"
            safe_title = clean_title(title)
            author = d.get("author", {}).get("nickname") or d.get("author", {}).get("unique_id") or "TikTok"
            thumbnail = d.get("cover") or d.get("origin_cover") or ""
            duration = d.get("duration")
            duration_val = int(round(float(duration))) if duration is not None else None

            images = d.get("images") or []
            music_url = d.get("music") or ""
            if music_url.startswith("/"):
                music_url = f"https://www.tikwm.com{music_url}"

            play_url = d.get("play") or ""
            if play_url.startswith("/"):
                play_url = f"https://www.tikwm.com{play_url}"

            wmplay_url = d.get("wmplay") or ""
            if wmplay_url.startswith("/"):
                wmplay_url = f"https://www.tikwm.com{wmplay_url}"

            formats: List[FormatOption] = []

            # KIỂM TRA: Dạng Album Ảnh (Photo Mode) hay Video thực sự
            is_photo_mode = bool(images) or ("/photo/" in url.lower()) or ("audio_mp4" in play_url)

            if is_photo_mode and images:
                # 1. Video MP4 (Ghép ảnh và nhạc nền gốc có cả hình và tiếng)
                first_img = images[0]
                audio_src = music_url or play_url
                slideshow_proxy = (
                    f"{base_api_url}/api/download?url={urllib.parse.quote(first_img)}"
                    f"&audio_url={urllib.parse.quote(audio_src)}"
                    f"&title={urllib.parse.quote(safe_title)}"
                    f"&ext=mp4&is_slideshow=1"
                )
                formats.append(
                    FormatOption(
                        id="tiktok-video",
                        quality="MP4 Video (Có cả hình & tiếng)",
                        type="video",
                        ext="mp4",
                        filesize_str="Chuẩn H.264 HD",
                        direct_url=slideshow_proxy,
                        proxy_url=slideshow_proxy,
                        audio_url=audio_src,
                        has_audio=True,
                        watermark=False,
                    )
                )

            elif play_url and not ("audio_mp4" in play_url):
                # Video MP4 bình thường không logo
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
            elif wmplay_url:
                # Dự phòng nếu bản không logo không có sẵn
                formats.append(
                    FormatOption(
                        id="tiktok-nowm",
                        quality="MP4 Video (Có hình & tiếng)",
                        type="video",
                        ext="mp4",
                        filesize_str=format_filesize(d.get("wm_size")) or "Chuẩn H.264 Nét",
                        direct_url=wmplay_url,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(wmplay_url)}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                        watermark=True,
                    )
                )

            # Âm thanh gốc MP3
            audio_track = music_url or (play_url if "audio_mp4" in play_url else "")
            if audio_track:
                formats.append(
                    FormatOption(
                        id="tiktok-audio",
                        quality="MP3 Âm thanh gốc (Nhạc nền)",
                        type="audio",
                        ext="mp3",
                        filesize_str="320 kbps",
                        direct_url=audio_track,
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(audio_track)}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                        has_audio=True,
                        watermark=False,
                    )
                )

            if formats:
                return MediaInfo(
                    url=url,
                    title=title,
                    platform="tiktok",
                    thumbnail=thumbnail or (images[0] if images else ""),
                    duration_str=format_duration(duration_val),
                    duration_seconds=duration_val,
                    author=author,
                    formats=formats,
                    images=images,
                )
    except Exception:
        pass
    return None


def extract_info(url: str, base_api_url: str = "") -> MediaInfo:
    platform = detect_platform(url)

    # 1. Với TikTok: Ưu tiên bóc tách direct qua TikWM API
    if platform == "tiktok":
        tiktok_res = extract_tiktok_direct(url, base_api_url=base_api_url)
        if tiktok_res:
            return tiktok_res

    # 2. Cấu hình cơ bản yt-dlp
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "socket_timeout": 12,
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

    info = None
    last_err = None

    if platform == "youtube":
        jar = get_youtube_cookiejar()
        # Tự động xoay vòng chiến lược client cho YouTube để vượt qua mọi rào cản
        strategies = [
            {"name": "android", "args": {"player_client": ["android"]}},
            {"name": "default", "args": None},
            {"name": "tv_combo", "args": {"player_client": ["tv_embedded", "android_music", "ios_music"]}},
            {"name": "ios_mweb", "args": {"player_client": ["ios", "mweb"]}},
            {"name": "web", "args": {"player_client": ["web"]}},
        ]
        for st in strategies:
            opts = dict(ydl_opts)
            if st["args"]:
                opts["extractor_args"] = {"youtube": st["args"]}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    if jar:
                        ydl.cookiejar = jar
                    candidate = ydl.extract_info(url, download=False)
                    if candidate and candidate.get("formats"):
                        info = candidate
                        break
            except Exception as e:
                last_err = e
                continue
    else:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            last_err = e

    if not info:
        raise Exception(f"Không thể bóc tách link: {last_err}")

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
        valid_videos = [f for f in raw_formats if f.get("url") and f.get("vcodec") != "none"]
        audio_streams = [f for f in raw_formats if f.get("url") and f.get("vcodec") == "none" and f.get("acodec") != "none"]
        best_audio = audio_streams[-1] if audio_streams else None

        best_v = None
        h264_candidates = [v for v in valid_videos if "h264" in str(v.get("format_id", "")).lower() or "avc" in str(v.get("vcodec", "")).lower()]
        if h264_candidates:
            best_v = h264_candidates[-1]
        elif valid_videos:
            best_v = valid_videos[-1]

        if best_v:
            v_url = best_v.get("url")
            has_sound = (best_v.get("acodec") != "none")
            audio_param = f"&audio_url={urllib.parse.quote(best_audio['url'])}" if (not has_sound and best_audio) else ""
            formats.append(
                FormatOption(
                    id="tiktok-nowm",
                    quality="MP4 Không Logo (Có hình & tiếng)",
                    type="video",
                    ext="mp4",
                    filesize_str="Chuẩn Nét H.264",
                    direct_url=v_url,
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(v_url)}{audio_param}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    audio_url=best_audio.get("url") if (not has_sound and best_audio) else None,
                    has_audio=True,
                    watermark=False,
                )
            )

        if best_audio:
            formats.append(
                FormatOption(
                    id="tiktok-audio",
                    quality="MP3 Âm thanh gốc",
                    type="audio",
                    ext="mp3",
                    filesize_str=format_filesize(best_audio.get("filesize") or best_audio.get("filesize_approx")),
                    direct_url=best_audio["url"],
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(best_audio['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp3",
                    has_audio=True,
                    watermark=False,
                )
            )

    # --- FACEBOOK ---
    elif platform == "facebook":
        valid_videos = [f for f in raw_formats if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"]

        for f in valid_videos:
            f_id = str(f.get("format_id", "")).lower()
            f_note = str(f.get("format_note", "")).upper()
            height = f.get("height") or 0

            is_hd = ("hd" in f_id or "hd" in f_note or height >= 720)
            q_id = "fb-hd" if is_hd else "fb-sd"
            q_label = "MP4 HD (Có hình & tiếng)" if is_hd else "MP4 SD (Có hình & tiếng)"

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

        formats.sort(key=lambda x: (0 if "hd" in x.id else 1))

        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="fb-best",
                    quality="MP4 Video (Có hình & tiếng)",
                    type="video",
                    ext="mp4",
                    filesize_str="Chuẩn HD",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

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

    # --- YOUTUBE & NỀN TẢNG KHÁC ---
    else:
        # 1. Progressive streams (vừa có video vừa có audio)
        progressive_streams = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
        ]
        progressive_streams.sort(key=lambda x: (x.get("height") or 0), reverse=True)

        # 2. Tìm audio stream chất lượng tốt nhất
        audio_streams = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") == "none" and f.get("acodec") != "none"
        ]
        m4a_streams = [f for f in audio_streams if f.get("ext") == "m4a"]
        best_audio = m4a_streams[-1] if m4a_streams else (audio_streams[-1] if audio_streams else None)
        if not best_audio and progressive_streams:
            best_audio = progressive_streams[0]

        for pf in progressive_streams:
            height = pf.get("height") or 0
            if height < 144:
                continue
            q_key = f"{height}p"
            if q_key not in seen_qualities:
                seen_qualities.add(q_key)
                size_str = format_filesize(pf.get("filesize") or pf.get("filesize_approx"))
                formats.append(
                    FormatOption(
                        id=f"yt-{height}p",
                        quality=f"MP4 {height}p (Có tiếng & hình)",
                        type="video",
                        ext="mp4",
                        filesize_str=size_str or "Độ nét cao",
                        direct_url=pf["url"],
                        proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(pf['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                        has_audio=True,
                    )
                )

        # 2. Adaptive video streams (Cần ghép với best_audio)
        adaptive_video_streams = [
            f for f in raw_formats
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") == "none"
        ]
        adaptive_video_streams.sort(
            key=lambda x: (
                1 if (x.get("ext") == "mp4" or "avc1" in str(x.get("vcodec", "")).lower()) else 0,
                x.get("height") or 0,
            ),
            reverse=True,
        )

        for vf in adaptive_video_streams:
            height = vf.get("height") or 0
            if height < 144:
                continue
            q_key = f"{height}p"
            if q_key not in seen_qualities:
                seen_qualities.add(q_key)
                size_str = format_filesize(vf.get("filesize") or vf.get("filesize_approx"))
                audio_target = best_audio.get("url") if best_audio else None
                a_param = f"&audio_url={urllib.parse.quote(audio_target)}" if audio_target else ""
                p_url = f"{base_api_url}/api/download?url={urllib.parse.quote(vf['url'])}{a_param}&title={urllib.parse.quote(safe_title)}&ext=mp4"

                formats.append(
                    FormatOption(
                        id=f"yt-{height}p",
                        quality=f"MP4 {height}p (Có tiếng & hình)",
                        type="video",
                        ext="mp4",
                        filesize_str=size_str or "Độ nét cao",
                        direct_url=vf["url"],
                        proxy_url=p_url,
                        audio_url=audio_target,
                        has_audio=True,
                    )
                )

        if not formats and info.get("url"):
            formats.append(
                FormatOption(
                    id="best-video",
                    quality="MP4 Tốt nhất (Có tiếng & hình)",
                    type="video",
                    ext="mp4",
                    filesize_str="Tối ưu",
                    direct_url=info.get("url"),
                    proxy_url=f"{base_api_url}/api/download?url={urllib.parse.quote(info['url'])}&title={urllib.parse.quote(safe_title)}&ext=mp4",
                    has_audio=True,
                )
            )

        # 3. Audio format MP3
        if best_audio:
            abr = best_audio.get("abr")
            abr_str = f"{int(abr)} kbps" if abr else "320 kbps"
            formats.append(
                FormatOption(
                    id="audio-high",
                    quality=f"MP3 Âm thanh chất lượng cao ({abr_str})",
                    type="audio",
                    ext="mp3",
                    filesize_str=format_filesize(best_audio.get("filesize") or best_audio.get("filesize_approx")) or "320 kbps",
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
