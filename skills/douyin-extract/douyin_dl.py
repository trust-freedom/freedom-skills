#!/usr/bin/env python3
"""Download Douyin video without watermark via share page."""

import json
import re
import sys
import time
from datetime import datetime
import requests


def extract_video_id(url: str) -> str:
    """Resolve short URL and extract video ID."""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/17.0 Mobile/15E148 Safari/604.1",
    }
    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
    resolved = resp.url

    for pattern in [r"/video/(\d{15,})", r"modal_id=(\d{15,})", r"/(\d{15,})/"]:
        m = re.search(pattern, resolved)
        if m:
            return m.group(1)

    raise ValueError(f"Cannot extract video ID from: {resolved}")


def fetch_video_info(video_id: str) -> dict:
    """Fetch video metadata from iesdouyin share page."""
    url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.douyin.com/",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    m = re.search(r"window\._ROUTER_DATA\s*=\s*({.*?})\s*;?\s*</script>", resp.text, re.DOTALL)
    if not m:
        raise ValueError("Cannot find _ROUTER_DATA in page")

    raw = m.group(1).replace("\\u002F", "/").replace("\\u0026", "&")
    data = json.loads(raw)

    loader = data.get("loaderData", {})
    item = None
    for key, val in loader.items():
        if not isinstance(val, dict):
            continue
        info_res = val.get("videoInfoRes") or val.get("videoInfo")
        if isinstance(info_res, dict):
            items = info_res.get("item_list") or info_res.get("items") or []
            if items:
                item = items[0]
                break

    if not item:
        raise ValueError("Cannot locate video data in _ROUTER_DATA")

    # Extract play URL (playwm -> play for no watermark)
    play_url = ""
    video_obj = item.get("video", {})
    play_addr = video_obj.get("play_addr", {})
    urls = play_addr.get("url_list", [])
    if urls:
        play_url = urls[0].replace("playwm", "play")

    if not play_url:
        raise ValueError("Cannot find play URL in video data")

    desc = item.get("desc", "")
    author = item.get("author", {}).get("nickname", "")
    duration_ms = video_obj.get("duration", 0) or item.get("duration", 0)

    return {
        "video_id": video_id,
        "title": desc,
        "author": author,
        "duration_ms": duration_ms,
        "play_url": play_url,
    }


def download_video(play_url: str, save_path: str) -> str:
    """Download video file."""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        "Referer": "https://www.douyin.com/",
    }
    resp = requests.get(play_url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

    return save_path


def sanitize_title(title: str) -> str:
    """Clean title for use as filename: remove hashtags, special chars, collapse spaces."""
    # Remove hashtags (#xxx)
    title = re.sub(r"#[^\s#]+", "", title)
    # Replace newlines with spaces
    title = title.replace("\n", " ")
    # Remove characters unsafe for filenames
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    # Collapse whitespace and strip
    title = re.sub(r"\s+", " ", title).strip()
    # Truncate to 60 chars
    return title[:60].rstrip()


def main():
    if len(sys.argv) < 2:
        print("Usage: douyin_dl.py <douyin_url> [save_dir]", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    save_dir = sys.argv[2] if len(sys.argv) > 2 else "/Users/sunli/Downloads"

    video_id = extract_video_id(url)
    info = fetch_video_info(video_id)

    duration_s = info["duration_ms"] // 1000 if info["duration_ms"] else 0
    date_prefix = datetime.now().strftime("%Y%m%d")
    clean_title = sanitize_title(info["title"])
    base_name = f"{date_prefix}-{clean_title}"
    save_path = f"{save_dir.rstrip('/')}/{base_name}.mp4"

    download_video(info["play_url"], save_path)

    meta = {
        "title": info["title"],
        "author": info["author"],
        "duration": f"{duration_s // 60}分{duration_s % 60}秒",
        "base_name": base_name,
        "file": save_path,
    }
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
