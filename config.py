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
VIDEO_BITRATE = "4500k"
VIDEO_PRESET = "veryfast"
VIDEO_THREADS = 8

# 영문 채널이라 영문 sans-serif 굵은 폰트 우선
FONT_PATH = os.path.join(ASSETS_DIR, "fonts", "Roboto-Bold.ttf")

# OpenAI
META_MODEL = "gpt-4o-mini"

# edge-tts voice (영문)
TTS_VOICE = "en-US-AriaNeural"  # 자연스러운 여성 보이스
TTS_RATE = "+12%"  # 인기 트리비아 채널 페이스에 맞춤
TTS_PITCH = "+0Hz"

# 자막 스타일
CAPTION_BASE_SIZE = 80
CAPTION_Y_RATIO = 0.50  # 화면 정중앙 (인스타 UI 버튼 회피)
CAPTION_PHRASE_SIZE = 4  # 한 자막에 3-4 단어 묶음 (TikTok 스타일)
CAPTION_HIGHLIGHT_NUMBERS = True  # 숫자는 옐로우 강조

# BGM (선택) — assets/bgm/*.mp3 풀에서 랜덤. 없으면 BGM 없이 진행
BGM_VOLUME_DB = -22  # TTS 가리지 않게 작게

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
}
