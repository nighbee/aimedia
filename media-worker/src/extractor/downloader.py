import os
import shutil
import time
import requests
import yt_dlp
from src.config import Config


class VideoDownloader:
    """
    Layered video download strategy:
      Layer 1: yt-dlp with browser cookies (if cookies file provided)
      Layer 2: yt-dlp without cookies (default)
      Layer 3: Cobalt API (self-hosted, multi-platform)
      Layer 4: Mock placeholder (last resort)
    """

    @staticmethod
    def download(url: str, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if Config.IS_MOCK_MODE:
            print(f"[MOCK] Simulating video download from: {url}")
            with open(output_path, 'wb') as f:
                f.write(b"MOCK VIDEO CONTENT")
            return os.path.abspath(output_path)

        # Layer 1: yt-dlp with cookies
        if Config.YTDLP_COOKIES_FILE and os.path.isfile(Config.YTDLP_COOKIES_FILE):
            print(f"[Download] Trying yt-dlp with cookies ({Config.YTDLP_COOKIES_FILE})")
            result = _try_ytdlp(url, output_path, cookies_file=Config.YTDLP_COOKIES_FILE)
            if result:
                return result
            print("[Download] yt-dlp with cookies failed, trying next layer...")

        # Layer 2: yt-dlp without cookies
        print("[Download] Trying yt-dlp (no cookies)")
        result = _try_ytdlp(url, output_path)
        if result:
            return result
        print("[Download] yt-dlp failed, trying next layer...")

        # Layer 3: Cobalt API
        if Config.COBALT_API_URL:
            print(f"[Download] Trying Cobalt API ({Config.COBALT_API_URL})")
            result = _try_cobalt(url, output_path)
            if result:
                return result
            print("[Download] Cobalt API failed, trying next layer...")

        # Layer 4: Mock fallback (last resort)
        print("[Download] All download methods failed. Writing mock placeholder.")
        with open(output_path, 'wb') as f:
            f.write(b"MOCK VIDEO CONTENT")
        return os.path.abspath(output_path)


def _try_ytdlp(url: str, output_path: str, cookies_file: str = None) -> str | None:
    """Attempt download via yt-dlp. Returns path on success, None on failure."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Referer': 'https://www.google.com/',
        },
    }
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"[Download] yt-dlp error: {e}")
        return None

    # Handle yt-dlp appending extension
    if not os.path.exists(output_path):
        for ext in ['.mp4', '.mkv', '.webm']:
            candidate = output_path + ext
            if os.path.exists(candidate):
                shutil.move(candidate, output_path)
                return os.path.abspath(output_path)
        return None

    return os.path.abspath(output_path)


def _try_cobalt(url: str, output_path: str) -> str | None:
    """Attempt download via self-hosted Cobalt API. Returns path on success, None on failure."""
    cobalt_url = Config.COBALT_API_URL.rstrip('/')

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if Config.COBALT_API_KEY:
        headers['Authorization'] = f'Api-Key {Config.COBALT_API_KEY}'

    payload = {
        'url': url,
        'videoQuality': '1080',
        'filenameStyle': 'basic',
    }

    try:
        # Step 1: Request the download URL from Cobalt
        resp = requests.post(cobalt_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get('status')

        if status == 'error':
            error_code = data.get('error', {}).get('code', 'unknown')
            print(f"[Download] Cobalt error: {error_code}")
            return None

        if status == 'picker':
            # Multiple items — take the first video
            picker = data.get('picker', [])
            video_items = [p for p in picker if p.get('type') == 'video']
            if not video_items:
                print("[Download] Cobalt picker had no video items")
                return None
            download_url = video_items[0]['url']
        elif status in ('tunnel', 'redirect'):
            download_url = data.get('url')
        else:
            print(f"[Download] Cobalt unexpected status: {status}")
            return None

        if not download_url:
            print("[Download] Cobalt returned no download URL")
            return None

        # Step 2: Download the actual file
        file_resp = requests.get(download_url, stream=True, timeout=120)
        file_resp.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in file_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(output_path)
        if file_size < 1024:
            print(f"[Download] Cobalt file too small ({file_size} bytes), likely invalid")
            os.remove(output_path)
            return None

        print(f"[Download] Cobalt download complete ({file_size} bytes)")
        return os.path.abspath(output_path)

    except Exception as e:
        print(f"[Download] Cobalt error: {e}")
        return None
