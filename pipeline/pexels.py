"""Pexels에서 동물 영상 다운로드 (세로/portrait 우선)."""
import logging
import os
import random

import requests

from config import PEXELS_API_KEY, VIDEO_DURATION_SEC

log = logging.getLogger("animalbot.pexels")
PEXELS_API = "https://api.pexels.com/videos/search"


def fetch_background(keywords: list, output_dir: str) -> str:
    """키워드 후보 → portrait 영상 → 로컬 mp4 경로."""
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY 없음")

    os.makedirs(output_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}

    last_err = None
    candidates = list(keywords)
    random.shuffle(candidates)

    for kw in candidates:
        try:
            r = requests.get(
                PEXELS_API,
                headers=headers,
                params={"query": kw, "per_page": 20, "orientation": "portrait"},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            videos = data.get("videos", [])
            if not videos:
                continue
            random.shuffle(videos)
            for v in videos:
                if v.get("duration", 0) < 8:
                    continue
                files = v.get("video_files", [])
                portrait_files = [f for f in files
                                  if f.get("width", 0) <= f.get("height", 0)
                                  and (f.get("file_type") == "video/mp4" or "mp4" in (f.get("link", "")))]
                if not portrait_files:
                    portrait_files = [f for f in files if f.get("file_type") == "video/mp4"]
                portrait_files.sort(key=lambda f: abs((f.get("width") or 0) - 1080))
                if not portrait_files:
                    continue
                pick = portrait_files[0]
                url = pick["link"]
                fname = f"pexels_{v['id']}.mp4"
                out = os.path.join(output_dir, fname)
                with requests.get(url, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    with open(out, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=1 << 20):
                            fh.write(chunk)
                log.info(f"pexels bg: kw={kw} id={v['id']} dur={v.get('duration')}s")
                return out
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Pexels 배경 못 찾음: {last_err}")


def fetch_backgrounds(keywords: list, output_dir: str, n: int = 3) -> list:
    """동영상 N개를 다운로드 (각 fact 구간별로 다른 영상 사용)."""
    paths = []
    used_ids = set()
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY 없음")
    os.makedirs(output_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}

    candidates = list(keywords) * 3  # 키워드 풀 늘림
    random.shuffle(candidates)

    for kw in candidates:
        if len(paths) >= n:
            break
        try:
            r = requests.get(
                PEXELS_API,
                headers=headers,
                params={"query": kw, "per_page": 20, "orientation": "portrait"},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            videos = data.get("videos", [])
            random.shuffle(videos)
            for v in videos:
                if v.get("id") in used_ids:
                    continue
                if v.get("duration", 0) < 6:
                    continue
                files = v.get("video_files", [])
                portrait_files = [f for f in files
                                  if f.get("width", 0) <= f.get("height", 0)
                                  and (f.get("file_type") == "video/mp4" or "mp4" in (f.get("link", "")))]
                if not portrait_files:
                    portrait_files = [f for f in files if f.get("file_type") == "video/mp4"]
                portrait_files.sort(key=lambda f: abs((f.get("width") or 0) - 1080))
                if not portrait_files:
                    continue
                pick = portrait_files[0]
                url = pick["link"]
                fname = f"pexels_{v['id']}.mp4"
                out = os.path.join(output_dir, fname)
                with requests.get(url, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    with open(out, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=1 << 20):
                            fh.write(chunk)
                paths.append(out)
                used_ids.add(v["id"])
                log.info(f"pexels bg[{len(paths)}]: kw={kw} id={v['id']} dur={v.get('duration')}s")
                if len(paths) >= n:
                    break
        except Exception as e:
            log.warning(f"pexels kw={kw} 실패: {e}")
            continue

    if not paths:
        raise RuntimeError("Pexels 영상 하나도 못 찾음")
    return paths
