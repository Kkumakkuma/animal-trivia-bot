#!/usr/bin/env python3
"""Animal Trivia 60s — 1분 동물 트리비아 영상 자동 발행.

흐름:
1. 최근 사용 회피하면서 동물 1마리 랜덤 선택
2. GPT가 hook + intro + fact x3 + outro + 영문 title/description 생성
3. edge-tts로 영문 내레이션 5개 생성 (intro/fact x3/outro)
4. Pexels에서 동물 영상 3개 다운로드
5. MoviePy로 1분 영상 합성 (배경 concat + 비네트 + hook 상단 + 자막 시간차 + brand 하단)
6. 영문 메인 + 7개국 localizations 번역
7. YouTube Shorts 업로드 (privacy=public, defaultLanguage=en)
8. 사용 동물 기록 (used_animals.json) — 같은 cron에서 연속 회피
"""
import argparse
import io
import json
import logging
import os
import random
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ANIMALS, BASE_DIR, OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("animalbot")

USED_PATH = os.path.join(BASE_DIR, "used_animals.json")
USED_KEEP = 5  # 직전 5번 사용한 동물 회피


def _load_used():
    if not os.path.exists(USED_PATH):
        return []
    try:
        return json.load(open(USED_PATH, encoding="utf-8"))
    except Exception:
        return []


def _save_used(used):
    json.dump(used[-USED_KEEP:], open(USED_PATH, "w", encoding="utf-8"))


def run_once(forced_animal: str = None, dry_run: bool = False, no_upload: bool = False) -> dict:
    from pipeline import animals, pexels, tts, composer, translator

    rng = random.Random()
    used = _load_used()

    if forced_animal:
        animal_key = forced_animal
    else:
        animal_key = animals.pick_animal(rng, exclude=used)
    log.info(f"=== 동물: {animal_key} ({ANIMALS[animal_key]['display']}) ===")

    work_dir = os.path.join(OUTPUT_DIR, datetime.now().strftime("%Y%m%d"), animal_key)
    os.makedirs(work_dir, exist_ok=True)

    # 1) 메타 (hook/intro/facts/outro/title/description)
    meta = animals.make_meta(animal_key)
    log.info(f"title_en: {meta['title_en']}")
    log.info(f"hook: {meta['hook']}")
    for i, f in enumerate(meta["facts"]):
        log.info(f"fact[{i}]: {f}")

    # 2) TTS (intro + fact x3 + outro)
    tts_texts = [meta["intro"]] + list(meta["facts"]) + [meta["outro"]]
    tts_lines = tts.synth_lines(tts_texts, work_dir, prefix="tts")

    # 3) 배경 영상 3개
    bg_paths = pexels.fetch_backgrounds(ANIMALS[animal_key]["pexels_keywords"], work_dir, n=3)

    # 4) 영상 합성
    out_video = os.path.join(
        work_dir, f"{animal_key}_{datetime.now().strftime('%H%M%S')}.mp4"
    )
    composer.compose(bg_paths, tts_lines, meta["hook"], out_video)
    log.info(f"video: {out_video} ({os.path.getsize(out_video) / 1024 / 1024:.1f}MB)")

    # 5) 7개국 localizations
    locs = translator.translate_for_youtube(meta["title_en"], meta["description_en"])

    if dry_run:
        log.info("--dry-run → 업로드 스킵")
        return {
            "animal": animal_key,
            "video": out_video,
            "url": None,
            "locales": list(locs.keys()),
        }

    # 6) 업로드
    url = None
    if not no_upload:
        from pipeline import youtube_upload
        url = youtube_upload.upload(
            out_video,
            title=meta["title_en"],
            description=meta["description_en"],
            tags=meta["tags"],
            localizations=locs,
            default_language="en",
        )

    # 7) 사용 기록
    used.append(animal_key)
    _save_used(used)

    return {
        "animal": animal_key,
        "video": out_video,
        "url": url,
        "locales": list(locs.keys()),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--animal", help="강제 동물 키 (예: otter)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-upload", action="store_true")
    args = p.parse_args()

    try:
        result = run_once(
            forced_animal=args.animal,
            dry_run=args.dry_run,
            no_upload=args.no_upload,
        )
        print(result)
    except Exception as e:
        log.exception(f"실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
