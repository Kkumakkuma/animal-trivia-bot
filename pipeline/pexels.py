"""Pexels에서 동물 영상 다운로드 (세로/portrait 우선).

2026-05-06 fix (우주봇 Saturn 케이크 사고 동기화): Pexels 검색에 wedding/jewelry/
fashion 류 garbage 영상이 섞여서 vision 검증 비용/시간만 소모하는 문제. URL slug
기반 사전 필터로 vision 호출 전에 garbage 후보를 일찍 거름.
"""
import logging
import os
import random

import requests

from config import PEXELS_API_KEY, VIDEO_DURATION_SEC

log = logging.getLogger("animalbot.pexels")
PEXELS_API = "https://api.pexels.com/videos/search"

# Pexels video.url slug에 이 단어가 있고 동물명이 없으면 사전 reject.
_BLOCK_SLUG_WORDS = {
    "wedding", "weddings", "bride", "groom", "engagement",
    "jewelry", "necklace", "diamond", "earring", "earrings",
    "cake", "cupcake", "muffin", "pastry", "donut", "icecream", "dessert",
    "manicure", "fashion", "selfie", "makeup", "lipstick", "mascara",
}


def _slug_tokens(url: str) -> set:
    """Pexels url slug → 단어 토큰 집합 (소문자)."""
    if not url:
        return set()
    try:
        slug = url.lower().split("/video/", 1)[1].rstrip("/")
        parts = slug.split("-")
        if parts and parts[-1].isdigit():
            parts = parts[:-1]
        return {p for p in parts if p}
    except Exception:
        return set()


# 동물 종 혼동 pair (2026-05-07 카피바라/비버 사고 fix).
# {topic: {topic의 풋티지로 잘못 들어오는 다른 종 token들}}.
# 토픽 검색에 잘못된 종이 섞여 들어올 때 slug에서 사전 reject.
# vision API는 niche 동물 식별 못 해서 over-reject 사고 (sloth 발행 0편) 발생 → slug에서 처리.
_SPECIES_CONFUSION = {
    "capybara": {"beaver", "beavers", "nutria", "muskrat", "groundhog", "marmot"},
    "beaver": {"capybara", "capybaras", "nutria", "muskrat"},
    "leopard": {"cheetah", "cheetahs", "jaguar", "jaguars"},
    "cheetah": {"leopard", "leopards", "jaguar", "jaguars"},
    "jaguar": {"leopard", "leopards", "cheetah", "cheetahs"},
    "alligator": {"crocodile", "crocodiles"},
    "crocodile": {"alligator", "alligators"},
    "frog": {"toad", "toads", "salamander"},
    "toad": {"frog", "frogs", "salamander"},
    "dolphin": {"porpoise", "porpoises", "whale", "whales", "orca"},
    "whale": {"dolphin", "dolphins", "porpoise"},
    "orca": {"dolphin", "dolphins", "whale", "whales"},
    "seal": {"sealion", "sealions", "walrus", "otter"},
    "sealion": {"seal", "seals", "walrus"},
    "rabbit": {"hare", "hares"},
    "hare": {"rabbit", "rabbits"},
    "tortoise": {"turtle", "turtles"},
    "turtle": {"tortoise", "tortoises"},
    "donkey": {"mule", "mules", "horse", "horses"},
    "mule": {"donkey", "donkeys"},
    "lion": {"tiger", "tigers", "puma", "cougar"},
    "tiger": {"lion", "lions", "puma", "cougar"},
    "gorilla": {"chimpanzee", "chimp", "chimps", "orangutan", "monkey"},
    "chimpanzee": {"gorilla", "gorillas", "orangutan", "monkey"},
    "wolf": {"coyote", "coyotes", "fox", "foxes", "jackal", "dog"},
    "coyote": {"wolf", "wolves", "jackal"},
    "fox": {"coyote", "coyotes", "wolf"},
    "elephant": {"mammoth", "rhinoceros", "rhino", "hippo", "hippopotamus"},
    "rhinoceros": {"elephant", "hippo", "hippopotamus"},
    "rhino": {"elephant", "hippo", "hippopotamus"},
    "hippopotamus": {"elephant", "rhino", "rhinoceros"},
    "hippo": {"elephant", "rhino", "rhinoceros"},
    "octopus": {"squid", "cuttlefish"},
    "squid": {"octopus", "cuttlefish"},
    "raven": {"crow", "crows"},
    "crow": {"raven", "ravens"},
    "eagle": {"hawk", "hawks", "falcon", "falcons", "vulture"},
    "hawk": {"eagle", "eagles", "falcon", "falcons"},
    "falcon": {"eagle", "eagles", "hawk", "hawks"},
}


def _has_confused_species(slug_tokens: set, animal_single: str) -> bool:
    """slug 토큰에 토픽과 혼동되는 다른 종 단어가 들어 있는지."""
    if not animal_single:
        return False
    key = animal_single.lower().strip()
    # plural 정규화
    for suf in ("es", "s"):
        if key.endswith(suf) and len(key) > len(suf) + 2:
            key_singular = key[:-len(suf)]
            if key_singular in _SPECIES_CONFUSION:
                key = key_singular
                break
    confused = _SPECIES_CONFUSION.get(key)
    if not confused:
        return False
    return bool(slug_tokens & confused)


def _passes_slug_filter(video: dict, single_lower: str) -> bool:
    """Pexels url slug 토큰 기반 사전 필터.

    True: vision 검증으로 넘김
    False: 사전 reject (garbage 후보 일찍 거름)

    2026-05-07 v3: species 혼동 pair 추가. 카피바라 검색에 비버 영상 섞이면 사전 reject.
    vision API가 niche 동물 식별 못해서 over-reject로 발행 0편 사고 → slug에서 처리.
    """
    tokens = _slug_tokens(video.get("url", ""))
    if not tokens:
        return True

    # species 혼동 pair: 토픽이랑 다른 종 단어가 slug에 있으면 reject
    # (단, 토픽 단어도 같이 있으면 통과 — 사진가가 둘 다 태깅한 경우)
    if single_lower and _has_confused_species(tokens, single_lower):
        single_words = {w for w in single_lower.split() if len(w) >= 3}
        if not (tokens & single_words):
            return False

    blocked = tokens & _BLOCK_SLUG_WORDS
    if not blocked:
        return True
    # 차단어 있어도 동물명이 같이 들어있으면 진짜 동물 사진일 가능성 → 통과
    if single_lower:
        single_words = {w for w in single_lower.split() if len(w) >= 3}
        if tokens & single_words:
            return True
    return False


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


def fetch_backgrounds(keywords: list, output_dir: str, n: int = 3,
                       animal_single: str = "",
                       exclude_pexels_ids: list = None) -> list:
    """동영상 N개를 다운로드 (각 fact 구간별로 다른 영상).

    animal_single: 안전 보장 — 모든 키워드가 동물명을 포함하지 않으면
    fallback으로 동물명 단독 검색. generic 키워드("wild mammal" 등)로
    엉뚱한 동물 매칭되는 문제 방지.

    exclude_pexels_ids: 최근 N개 영상에서 사용된 Pexels video_id 리스트.
    같은 풋티지 반복으로 채널 영상이 비슷해 보이는 문제 방지 (2026-05-07
    우주봇 사용자 지적 동기화). 풀이 부족할 때만 일부 허용.
    """
    paths = []
    used_ids = set()
    blocked_recent = set(int(i) for i in (exclude_pexels_ids or []) if str(i).isdigit() or isinstance(i, int))
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY 없음")
    os.makedirs(output_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}

    # 동물명 검증 안전망 — 키워드에 동물명이 없으면 generic으로 매칭 위험
    single_lower = ""
    if animal_single:
        single_lower = animal_single.lower()
        verified = [kw for kw in keywords if single_lower in kw.lower()]
        if not verified:
            verified = [animal_single, f"{animal_single} close up",
                        f"{animal_single} in wild"]
        keywords = verified
        log.info(f"pexels keywords (animal-locked): {keywords}")

    candidates = list(keywords) * 3  # 키워드 풀 늘림
    random.shuffle(candidates)

    skipped_slug = 0
    skipped_recent = 0
    # 1차: 최근 사용 video_id 차단하면서 매칭
    # 2차: 풀이 부족하면 차단 풀고 재시도 (안전 폴백)
    for pass_idx in (0, 1):
        block_set = blocked_recent if pass_idx == 0 else set()
        if pass_idx == 1 and len(paths) >= n:
            break
        if pass_idx == 1:
            log.warning(f"pexels: 1차 후 {len(paths)}/{n} 부족 — 최근 사용 차단 풀고 재시도")
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
                    if v.get("id") in block_set:
                        skipped_recent += 1
                        continue
                    if v.get("duration", 0) < 6:
                        continue
                    # URL slug 사전 필터 (vision 비용/TPM 절약 + garbage 사전 차단)
                    if not _passes_slug_filter(v, single_lower):
                        skipped_slug += 1
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

    if skipped_slug:
        log.info(f"pexels slug filter: {skipped_slug}개 garbage 후보 사전 차단")
    if skipped_recent:
        log.info(f"pexels dedup: {skipped_recent}개 최근 사용 풋티지 차단 (used_pexels.json)")
    if not paths:
        raise RuntimeError("Pexels 영상 하나도 못 찾음")
    return paths
