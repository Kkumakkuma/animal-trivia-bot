"""동물봇 YouTube OAuth 토큰 재발급 + 채널 검증.

사용법:
  cd 동물쇼츠봇
  python auth.py

작동:
1. credentials/youtube_client_secret.json 읽기
2. 브라우저 자동 열림 → 구글 계정 로그인 → ⚠️ "Animal Trivia 60s" 채널 선택!
3. 토큰을 credentials/youtube_token.json에 저장
4. 토큰으로 실제 채널 이름 조회 → 콘솔에 출력 (잘못된 채널이면 다시 돌려야 함)

⚠️ 중요: OAuth 화면에서 "lofi" 또는 음악 채널 선택 X. 반드시 동물 채널 선택!
"""
import os
import pickle
import sys

# Windows cp949 콘솔에서 이모지 print 시 UnicodeEncodeError 크래시 방지
# (인코딩은 유지 → 한글 정상, 인코딩 불가한 이모지만 ? 로 대체)
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(ROOT, "credentials")
CLIENT = os.path.join(CREDS, "youtube_client_secret.json")
TOKEN = os.path.join(CREDS, "youtube_token.json")

if not os.path.exists(CLIENT):
    print(f"[ERROR] {CLIENT} 없음")
    sys.exit(1)

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

print("=" * 60)
print("⚠️  브라우저가 열리면 반드시 'Animal Trivia 60s' 채널 선택!")
print("⚠️  lofi/음악 채널 고르면 안 됨.")
print("=" * 60)

flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

# pickle 형식 — youtube_upload.py가 pickle.load로 읽음 (.json 확장자지만 binary)
with open(TOKEN, "wb") as f:
    pickle.dump(creds, f)

print(f"\n[OK] 토큰 저장됨: {TOKEN}")
print(f"[OK] refresh_token 포함: {bool(creds.refresh_token)}")

# 토큰으로 실제 채널 정보 조회
print("\n[검증] 발급된 토큰의 채널 확인 중...")
yt = build("youtube", "v3", credentials=creds)
resp = yt.channels().list(part="snippet", mine=True).execute()
items = resp.get("items", [])
if not items:
    print("[ERROR] 채널 정보 조회 실패")
    sys.exit(1)

ch = items[0]
title = ch["snippet"]["title"]
ch_id = ch["id"]
print(f"\n채널 이름: {title}")
print(f"채널 ID:  {ch_id}")

if "animal" in title.lower() or "trivia" in title.lower():
    print("\n✅ 동물 채널로 정상 발급됨!")
else:
    print(f"\n❌ 잘못된 채널 ({title})! 동물 채널 아님!")
    print("❌ 이 토큰 쓰지 말고 auth.py 다시 돌려서 동물 채널 선택!")
    sys.exit(2)
