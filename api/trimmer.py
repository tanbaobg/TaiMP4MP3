import os
import shutil
import asyncio
import re
from typing import Optional, List, Tuple

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

def parse_time(val) -> float:
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str:
        return 0.0
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
    sec = max(0.0, float(seconds or 0))
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_stream_headers(url: str) -> str:
    headers = [
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    if any(k in url for k in ["tiktok", "byteoversea", "ibytedtos", "tikwm", "musical.ly"]):
        headers.append("Referer: https://www.tiktok.com/")
    elif any(k in url for k in ["facebook", "fbcdn", "fbsbx"]):
        headers.append("Referer: https://www.facebook.com/")
    return "\r\n".join(headers) + "\r\n"

def calculate_kept_intervals(segments: List[Tuple[float, float]], mode: str, total_duration: float) -> List[Tuple[float, float]]:
    cleaned = []
    for s, e in segments:
        s_val = max(0.0, float(s))
        e_val = max(s_val + 0.1, float(e))
        cleaned.append((s_val, e_val))
    cleaned.sort(key=lambda x: x[0])

    # Merge overlapping intervals
    merged = []
    for s, e in cleaned:
        if not merged:
            merged.append([s, e])
        elif s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    if mode == "keep":
        return [(round(m[0], 2), round(m[1], 2)) for m in merged]
    else:
        # Complement of merged
        kept = []
        cur = 0.0
        dur = max(total_duration, merged[-1][1] if merged else 60.0)
        for s, e in merged:
            if s > cur + 0.1:
                kept.append((round(cur, 2), round(s, 2)))
            cur = max(cur, e)
        if dur > cur + 0.1:
            kept.append((round(cur, 2), round(dur, 2)))
        return kept
