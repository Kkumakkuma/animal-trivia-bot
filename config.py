"""Animal Trivia 60s — 통합 설정.

매 cron마다 ANIMALS에서 랜덤 동물 1마리 선택 → GPT가 흥미 사실 3개 생성 →
edge-tts 영문 내레이션 + Pexels 동물 영상 + 시간차 자막으로 1분 영상 합성 →
YouTube Shorts (영문 메인 + 7개국 localizations) 자동 발행.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")

# .env
_env = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env):
    for line in open(_env, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# YouTube
YOUTUBE_CLIENT_SECRET = os.path.join(CREDENTIALS_DIR, "youtube_client_secret.json")
YOUTUBE_TOKEN = os.path.join(CREDENTIALS_DIR, "youtube_token.json")
YOUTUBE_CATEGORY_ID = "15"  # Pets & Animals
CONTAINS_SYNTHETIC_MEDIA = True  # TTS는 AI 합성 음성

# Video — Shorts (1080x1920)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_DURATION_SEC = 60
MIN_VIDEO_DURATION_SEC = 40  # 적응형 길이 하한 (composer v4: min(59.7, max(내레이션+7s, 이 값)))
VIDEO_BITRATE = "4500k"
VIDEO_PRESET = "veryfast"
VIDEO_THREADS = 8

# 영문 채널이라 영문 sans-serif 굵은 폰트 우선
FONT_PATH = os.path.join(ASSETS_DIR, "fonts", "Roboto-Bold.ttf")

# OpenAI
# 2026-07-10: 사실 오류(토성 고리 소멸 100M vs 300M년 모순) 재발 방지로 모델 3분할.
# 생성과 검증을 다른 계열로 두어 자기합치(self-agreement) 편향을 줄인다.
META_MODEL = "gpt-4o-mini"      # 경량 호출(번역·키워드 등)
SCRIPT_MODEL = "gpt-4o"         # 토픽 픽 + 스크립트 생성 (사실 정확도 우선)
FACTCHECK_MODEL = "gpt-4.1"     # 적대적 검증 — 생성 모델과 다른 계열

# edge-tts voice (영문)
TTS_VOICE = "en-US-AriaNeural"  # 자연스러운 여성 보이스
TTS_RATE = "+12%"  # 인기 트리비아 채널 페이스에 맞춤
TTS_PITCH = "+0Hz"

# 자막 스타일
CAPTION_BASE_SIZE = 80
CAPTION_Y_RATIO = 0.60  # 하단 1/3 (피사체 얼굴 가림 해소 + 인스타 UI 버튼 회피, 쇼츠 가독성)
CAPTION_PHRASE_SIZE = 4  # 한 자막에 3-4 단어 묶음 (TikTok 스타일)
CAPTION_HIGHLIGHT_NUMBERS = True  # 숫자는 옐로우 강조

# 썸네일 — 완성 영상 프레임 + 대형 후크 텍스트 (pipeline/thumbnail.py, fail-soft: 실패해도 발행 진행)
ENABLE_THUMBNAIL = True
THUMBNAIL_FONT_SIZE = 190  # 시작 크기 — 폭 초과 시 14씩 자동 축소 (하한 80)

# BGM (선택) — assets/bgm/*.mp3 풀에서 랜덤. 없으면 BGM 없이 진행
BGM_VOLUME_DB = -22  # TTS 가리지 않게 작게

# 콘텐츠 이력 (시간 기반 중복 방지 + 클립 dedup + angle/format 로테이션) — 2026-07-05
CONTENT_HISTORY = os.path.join(BASE_DIR, "content_history.json")
CONTENT_WINDOW_DAYS = 60        # 동물: 60일 내 같은 topic 재등장 차단
HISTORY_MIN_CANDIDATES = 8      # 제외 후 후보 8개 미만이면 창 0.75배씩 완화
HISTORY_MIN_WINDOW_DAYS = 7     # 완화 하한 (한 번에 전체 리셋 금지)
CLIP_DEDUP_DAYS = 30            # 30일 내 사용한 클립(Pexels/NASA id) 재사용 금지
RECENT_FORMAT_KEEP = 2          # 전역 직전 N편 format 연속 금지
USE_NASA_MEDIA = False          # 동물봇은 NASA 소스 미사용 (우주봇만 True)
CONTENT_DOMAIN = "animal"       # grounding 도메인 맥락(동음이의 위키 오매칭 방지)

# 동물 사전 — Pexels에서 잘 뽑히는 동물 위주
ANIMALS = {
    "otter": {
        "display": "Otters",
        "single": "otter",
        "pexels_keywords": [
            "otter swimming", "sea otter water", "otter floating",
            "river otter close up", "otter playing",
        ],
        "category": "mammal",
    },
    "octopus": {
        "display": "Octopus",
        "single": "octopus",
        "pexels_keywords": [
            "octopus swimming", "octopus tentacles", "octopus underwater",
            "octopus reef", "octopus close up",
        ],
        "category": "cephalopod",
    },
    "dolphin": {
        "display": "Dolphins",
        "single": "dolphin",
        "pexels_keywords": [
            "dolphin swimming", "dolphin jumping ocean", "dolphin pod",
            "dolphin underwater", "dolphin slow motion",
        ],
        "category": "mammal",
    },
    "fox": {
        "display": "Foxes",
        "single": "fox",
        "pexels_keywords": [
            "red fox forest", "fox snow", "fox close up",
            "fox running", "fox cubs",
        ],
        "category": "mammal",
    },
    "red_panda": {
        "display": "Red Pandas",
        "single": "red panda",
        "pexels_keywords": [
            "red panda eating", "red panda tree", "red panda close up",
            "red panda zoo", "red panda bamboo",
        ],
        "category": "mammal",
    },
    "owl": {
        "display": "Owls",
        "single": "owl",
        "pexels_keywords": [
            "owl close up", "owl flying", "owl eyes",
            "barn owl", "snowy owl forest",
        ],
        "category": "bird",
    },
    "elephant": {
        "display": "Elephants",
        "single": "elephant",
        "pexels_keywords": [
            "elephant herd savanna", "elephant trunk close up",
            "baby elephant", "elephant water", "elephant africa",
        ],
        "category": "mammal",
    },
    "penguin": {
        "display": "Penguins",
        "single": "penguin",
        "pexels_keywords": [
            "penguin antarctica", "penguin colony", "penguin walking",
            "penguin swimming underwater", "emperor penguin chick",
        ],
        "category": "bird",
    },
    "raven": {
        "display": "Ravens",
        "single": "raven",
        "pexels_keywords": [
            "raven black", "crow flying", "raven close up",
            "crow tree", "black bird intelligent",
        ],
        "category": "bird",
    },
    "axolotl": {
        "display": "Axolotls",
        "single": "axolotl",
        "pexels_keywords": [
            "axolotl aquarium", "axolotl close up", "axolotl pink",
            "axolotl swimming", "salamander water",
        ],
        "category": "amphibian",
    },
    "capybara": {
        "display": "Capybaras",
        "single": "capybara",
        "pexels_keywords": [
            "capybara water", "capybara group", "capybara close up",
            "capybara south america", "capybara relaxing",
        ],
        "category": "mammal",
    },
    "sloth": {
        "display": "Sloths",
        "single": "sloth",
        "pexels_keywords": [
            "sloth tree", "sloth slow", "sloth close up",
            "three toed sloth", "sloth hanging",
        ],
        "category": "mammal",
    },
    "squirrel": {
        "display": "Squirrels",
        "single": "squirrel",
        "pexels_keywords": [
            "squirrel tree", "squirrel eating nuts", "red squirrel",
            "squirrel close up", "squirrel jumping",
        ],
        "category": "mammal",
    },
    "honeybee": {
        "display": "Honeybees",
        "single": "honeybee",
        "pexels_keywords": [
            "bee flower close up", "honeybee macro", "bees hive",
            "bee pollinating", "bee slow motion",
        ],
        "category": "insect",
    },
    "shark": {
        "display": "Sharks",
        "single": "shark",
        "pexels_keywords": [
            "shark swimming", "great white shark", "shark underwater",
            "hammerhead shark", "shark slow motion",
        ],
        "category": "fish",
    },
    "raccoon": {
        "display": "Raccoons",
        "single": "raccoon",
        "pexels_keywords": [
            "raccoon close up", "raccoon night", "raccoon eating",
            "raccoon forest", "raccoon hands",
        ],
        "category": "mammal",
    },
    "meerkat": {
        "display": "Meerkats",
        "single": "meerkat",
        "pexels_keywords": [
            "meerkat standing", "meerkat group", "meerkat close up",
            "meerkat desert", "meerkat lookout",
        ],
        "category": "mammal",
    },
    "chameleon": {
        "display": "Chameleons",
        "single": "chameleon",
        "pexels_keywords": [
            "chameleon color", "chameleon close up", "chameleon tongue",
            "chameleon branch", "chameleon eyes",
        ],
        "category": "reptile",
    },
    "orca": {
        "display": "Orcas",
        "single": "orca",
        "pexels_keywords": [
            "orca swimming", "killer whale ocean", "orca jumping",
            "orca pod", "orca underwater",
        ],
        "category": "marine",
    },
    "lynx": {
        "display": "Lynxes",
        "single": "lynx",
        "pexels_keywords": [
            "lynx snow", "lynx close up", "lynx forest",
            "wild lynx", "lynx eyes",
        ],
        "category": "mammal",
    },
    "beaver": {
        "display": "Beavers",
        "single": "beaver",
        "pexels_keywords": [
            "beaver swimming", "beaver dam", "beaver close up",
            "beaver river", "beaver wood",
        ],
        "category": "mammal",
    },
    "bat": {
        "display": "Bats",
        "single": "bat",
        "pexels_keywords": [
            "bat flying", "bat cave", "bat close up",
            "fruit bat", "bats night",
        ],
        "category": "mammal",
    },
    "moose": {
        "display": "Moose",
        "single": "moose",
        "pexels_keywords": [
            "moose forest", "moose antlers", "moose close up",
            "moose snow", "moose wild",
        ],
        "category": "mammal",
    },
    "toucan": {
        "display": "Toucans",
        "single": "toucan",
        "pexels_keywords": [
            "toucan close up", "toucan beak", "toucan tree",
            "toucan rainforest", "toucan colorful",
        ],
        "category": "bird",
    },
    "starfish": {
        "display": "Starfish",
        "single": "starfish",
        "pexels_keywords": [
            "starfish ocean", "starfish underwater", "starfish reef",
            "starfish close up", "sea star tide pool",
        ],
        "category": "marine",
    },
    "seahorse": {
        "display": "Seahorses",
        "single": "seahorse",
        "pexels_keywords": [
            "seahorse swimming", "seahorse close up", "seahorse reef",
            "seahorse underwater", "seahorse ocean",
        ],
        "category": "fish",
    },
    "crab": {
        "display": "Crabs",
        "single": "crab",
        "pexels_keywords": [
            "crab beach", "crab close up", "hermit crab",
            "crab claws", "crab sand",
        ],
        "category": "crustacean",
    },
}
