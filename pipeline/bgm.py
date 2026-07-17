"""음악쇼츠봇 Google Drive에서 동물 테마에 어울리는 BGM 1개 read-only 다운로드.

전략:
- 음악쇼츠봇이 운영하는 /MusicShorts/queue/<music_theme>/ 폴더에서 mp3 1개 랜덤 픽
- read-only: used로 옮기지 않음 → 음악쇼츠봇 발행에 영향 없음
- 동물별로 어울리는 음악 테마 (comfort/study/sleep/dawn 등) 매핑 유지
  (여행봇처럼 전체 풀 랜덤으로 바꾸지 않는다 — 동물 영상 무드 맞춤 유지)
- 중복 방지 (2026-07-17 여행봇 동기화): used_bgm.json에 사용 file id를 쌓고 픽에서 제외.
  그 테마 폴더가 전부 사용됐으면 직전 5곡만 제외하고 재사용 허용.
- 사용 "기록"은 호출 측(main.py)이 발행 성공 시에만 mark_bgm_used()로 남긴다
  (--no-upload/dry-run 상태 오염 방지 원칙과 동일).
"""
import io
import json
import logging
import os
import pickle
import random
from typing import Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import CREDENTIALS_DIR

log = logging.getLogger("animalbot.bgm")

# 음악쇼츠봇 토큰 재활용 (같은 Google 계정의 Drive)
_OAUTH_TOKEN = os.path.join(CREDENTIALS_DIR, "gdrive_oauth_token.json")

GDRIVE_ROOT = "MusicShorts"
GDRIVE_QUEUE = "queue"

# 사용 이력 — repo 루트(used_animals.json과 나란히), 워크플로 persist 대상.
USED_BGM_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "used_bgm.json")
USED_BGM_KEEP = 500      # 테마 폴더 여러 개 합산 여유 포함 전체 기억
RESET_RECENT_KEEP = 5    # 테마 소진 시에도 직전 N곡은 계속 제외 (연속 반복 방지)


def _load_used_bgm() -> list:
    if not os.path.exists(USED_BGM_PATH):
        return []
    try:
        return [str(i) for i in json.load(open(USED_BGM_PATH, encoding="utf-8"))]
    except Exception:
        return []


def mark_bgm_used(file_id: str):
    """발행 성공 시 호출 — 사용한 BGM 파일 id를 이력에 기록."""
    if not file_id:
        return
    used = _load_used_bgm()
    used.append(str(file_id))
    json.dump(used[-USED_BGM_KEEP:], open(USED_BGM_PATH, "w", encoding="utf-8"))

# 카테고리 → 음악 테마 매핑 (모든 동물 자동 적용)
CATEGORY_TO_MUSIC = {
    "mammal": ["comfort", "study", "morning"],
    "bird": ["dawn", "morning", "comfort"],
    "marine": ["sleep", "comfort", "rainy_day"],
    "fish": ["sleep", "comfort"],
    "reptile": ["dawn", "comfort"],
    "amphibian": ["sleep", "rainy_day", "comfort"],
    "insect": ["morning", "study"],
    "cephalopod": ["sleep", "comfort"],
    "arachnid": ["dawn", "study"],
    "crustacean": ["sleep", "comfort"],
}
DEFAULT_MUSIC_THEMES = ["comfort", "study"]


def _get_service():
    """음악쇼츠봇과 동일한 OAuth 토큰으로 Drive API 인증."""
    if not os.path.exists(_OAUTH_TOKEN):
        log.warning(f"GDrive OAuth 토큰 없음: {_OAUTH_TOKEN} → BGM 스킵")
        return None
    with open(_OAUTH_TOKEN, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        with open(_OAUTH_TOKEN, "wb") as f:
            pickle.dump(creds, f)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_folder(svc, name: str, parent_id: Optional[str] = None) -> Optional[str]:
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    r = svc.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    files = r.get("files", [])
    return files[0]["id"] if files else None


def _list_mp3(svc, folder_id: str) -> list:
    q = (f"'{folder_id}' in parents and trashed=false "
         f"and (mimeType='audio/mpeg' or name contains '.mp3')")
    r = svc.files().list(q=q, fields="files(id,name)", pageSize=200).execute()
    return r.get("files", [])


def fetch_bgm_by_category(category: str, output_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """동물 카테고리에 어울리는 음악 테마에서 미사용 mp3 1개 read-only 다운로드.

    반환: (local_path, file_id). 실패 시 (None, None) — composer가 BGM 없이 진행.
    사용 기록은 여기서 하지 않는다 — 발행 성공 시 main.py가 mark_bgm_used(file_id).
    """
    music_themes = CATEGORY_TO_MUSIC.get((category or "").lower(), DEFAULT_MUSIC_THEMES)
    chosen_theme = random.choice(music_themes)
    log.info(f"bgm theme: category={category} → {chosen_theme}")

    try:
        # _get_service()는 만료/폐지/포맷 불일치 토큰에서 예외(RefreshError/UnpicklingError)를
        # 던질 수 있다 — BGM은 부가요소이므로 반드시 try 안에서 호출해 런 전체 크래시를 막는다.
        svc = _get_service()
        if svc is None:
            return None, None

        root_id = _find_folder(svc, GDRIVE_ROOT)
        if not root_id:
            log.warning(f"Drive '{GDRIVE_ROOT}' 폴더 없음")
            return None, None
        queue_id = _find_folder(svc, GDRIVE_QUEUE, root_id)
        if not queue_id:
            log.warning("queue 서브폴더 없음")
            return None, None

        used = _load_used_bgm()
        used_set = set(used)

        # 첫 매핑 테마에서 못 찾으면 다른 후보로 fallback
        for theme_try in [chosen_theme] + [t for t in music_themes if t != chosen_theme] + DEFAULT_MUSIC_THEMES:
            tid = _find_folder(svc, theme_try, queue_id)
            if not tid:
                continue
            files = _list_mp3(svc, tid)
            if not files:
                continue
            # 중복 방지: 사용 이력 제외 → 이 테마가 전부 사용됐으면 직전 N곡만 제외하고 재사용
            fresh = [f for f in files if f["id"] not in used_set]
            if not fresh:
                recent = set(used[-RESET_RECENT_KEEP:])
                fresh = [f for f in files if f["id"] not in recent] or files
                log.info(f"BGM 테마 '{theme_try}' 소진({len(files)}곡) → 이력 해제 재사용 (직전 {RESET_RECENT_KEEP}곡 제외)")
            pick = random.choice(fresh)
            os.makedirs(output_dir, exist_ok=True)
            local_path = os.path.join(output_dir, f"bgm_{theme_try}_{pick['name']}")
            req = svc.files().get_media(fileId=pick["id"])
            with io.FileIO(local_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            log.info(f"bgm downloaded: theme={theme_try} name={pick['name']} "
                     f"({len(files)}곡 중 미사용 {len(fresh)}곡에서 픽)")
            return local_path, pick["id"]
        log.warning("모든 음악 테마 큐 비어있음 → BGM 없이")
        return None, None
    except Exception as e:
        log.warning(f"BGM 다운로드 실패 → BGM 없이: {e}")
        return None, None
