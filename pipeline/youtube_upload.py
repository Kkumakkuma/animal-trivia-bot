"""YouTube 업로드 — defaultLanguage=en + localizations + AI 라벨 자동."""
import logging
import os
import pickle

from config import (
    CONTAINS_SYNTHETIC_MEDIA,
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_TOKEN,
)

log = logging.getLogger("animalbot.youtube")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_service():
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(YOUTUBE_TOKEN):
        with open(YOUTUBE_TOKEN, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(YOUTUBE_TOKEN), exist_ok=True)
        with open(YOUTUBE_TOKEN, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def upload(video_path: str, title: str, description: str, tags: list,
           thumbnail_path: str = None, localizations: dict = None,
           default_language: str = "en") -> str:
    from googleapiclient.http import MediaFileUpload

    svc = get_service()
    snippet = {
        "title": title[:95],
        "description": description[:4900],
        "tags": (tags or [])[:30],
        "categoryId": YOUTUBE_CATEGORY_ID,
    }
    if localizations:
        snippet["defaultLanguage"] = default_language
        snippet["defaultAudioLanguage"] = default_language

    body = {
        "snippet": snippet,
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": CONTAINS_SYNTHETIC_MEDIA,
        },
    }
    parts = "snippet,status"
    if localizations:
        body["localizations"] = localizations
        parts = "snippet,status,localizations"

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    log.info(f"upload start: {os.path.basename(video_path)} locales={len(localizations or {})}")
    try:
        response = svc.videos().insert(part=parts, body=body, media_body=media).execute()
    except Exception as e:
        if localizations and ("insufficientPermissions" in str(e) or "forbidden" in str(e).lower()):
            log.warning(f"locales 권한 부족 → 영어 단일로 재업로드: {e}")
            body.pop("localizations", None)
            snippet.pop("defaultLanguage", None)
            snippet.pop("defaultAudioLanguage", None)
            media2 = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            response = svc.videos().insert(part="snippet,status", body=body, media_body=media2).execute()
        else:
            raise

    video_id = response["id"]
    url = f"https://youtube.com/shorts/{video_id}"
    log.info(f"upload done: {url}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            tn = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            svc.thumbnails().set(videoId=video_id, media_body=tn).execute()
        except Exception as e:
            log.warning(f"thumbnail 실패: {e}")

    if localizations:
        applied = response.get("localizations") or {}
        if len(applied) < len(localizations):
            try:
                svc.videos().update(
                    part="localizations",
                    body={"id": video_id, "localizations": localizations},
                ).execute()
                log.info(f"localizations update: {len(localizations)}")
            except Exception as e:
                log.warning(f"localizations update 실패 (영상은 정상): {e}")

    return url
