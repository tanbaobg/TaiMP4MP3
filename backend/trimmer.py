import os
import shutil
import asyncio
import re
from typing import Optional, Tuple

def get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    which_exe = shutil.which("ffmpeg")
    return which_exe or "ffmpeg"

def parse_time(val: Optional[str]) -> float:
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str:
        return 0.0
    # Format HH:MM:SS or MM:SS or SS.S
    parts = val_str.split(":")
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return max(0.0, float(val_str))
    except Exception:
        return 0.0

def format_time_code(seconds: float) -> str:
    sec = max(0.0, seconds)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_stream_headers(url: str) -> str:
    headers = [
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    if "tiktok" in url or "byteoversea" in url or "ibytedtos" in url:
        headers.append("Referer: https://www.tiktok.com/")
    elif "facebook" in url or "fbcdn" in url:
        headers.append("Referer: https://www.facebook.com/")
    return "\r\n".join(headers) + "\r\n"
