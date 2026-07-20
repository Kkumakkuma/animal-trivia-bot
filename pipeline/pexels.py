"""Pexels에서 동물 영상 다운로드 (세로/portrait 우선).

2026-05-06 fix (우주봇 Saturn 케이크 사고 동기화): Pexels 검색에 wedding/jewelry/
fashion 류 garbage 영상이 섞여서 vision 검증 비용/시간만 소모하는 문제. URL slug
기반 사전 필터로 vision 호출 전에 garbage 후보를 일찍 거름.
"""
import logging
import os
import shutil
import subprocess
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


def _media_ok(path: str, min_bytes: int = 30_000) -> bool:
    """다운로드 클립 무결성 검증 — 잘린/손상 파일이 MoviePy/ffmpeg 인코딩을 깨뜨리는 것 방지.
    ffmpeg로 전체 디코드(-xerror)해 스트림 중간 truncation('0 bytes read at frame N')을 잡는다.
    도구(ffmpeg)가 없으면 크기만 검사해 통과 — 인프라 fault로 발행을 막지 않는다(fail-open on tooling).
    (여행봇 pexels.py 원본 이식 — 3봇 동기, 2026-07-20)"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) < min_bytes:
            return False
    except OSError:
        return False
    ff = shutil.which("ffmpeg")
    if not ff:
        return True
    try:
        r = subprocess.run(
            [ff, "-v", "error", "-xerror", "-i", path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=90,
        )
        return r.returncode == 0 and not (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return True


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


# 광범위 동물 단어 사전 — slug에 토픽이 아닌 다른 동물명이 있으면 reject용.
# 2026-05-07 사용자 신고 (Pangolin 토픽에 기린/멧돼지/새 풋티지) fix.
# Pexels는 niche 동물 검색 시 관련 없는 wildlife 영상을 무차별 매칭 → slug로 사전 차단.
_KNOWN_ANIMAL_TOKENS = {
    # mammals - large
    "giraffe", "giraffes", "elephant", "elephants", "rhino", "rhinos", "rhinoceros",
    "hippo", "hippos", "hippopotamus", "buffalo", "bison", "ox", "bull", "cow", "cattle",
    "horse", "horses", "donkey", "donkeys", "zebra", "zebras", "camel", "camels",
    "moose", "elk", "deer", "antelope", "gazelle", "wildebeest", "kangaroo", "kangaroos",
    # mammals - mid (rodents/etc)
    "capybara", "capybaras", "beaver", "beavers", "otter", "otters", "muskrat", "nutria",
    "rabbit", "rabbits", "hare", "hares", "squirrel", "squirrels", "raccoon", "raccoons",
    "mouse", "mice", "rat", "rats", "hamster", "hamsters", "gerbil", "guinea",
    "groundhog", "marmot", "porcupine", "hedgehog", "hedgehogs", "shrew", "mole", "moles",
    # mammals - cats/dogs/wild
    "cat", "cats", "kitten", "kittens", "lion", "lions", "tiger", "tigers", "leopard", "leopards",
    "cheetah", "cheetahs", "jaguar", "jaguars", "puma", "cougar", "lynx", "bobcat",
    "dog", "dogs", "puppy", "puppies", "wolf", "wolves", "fox", "foxes", "coyote", "coyotes",
    "jackal", "jackals", "hyena", "hyenas",
    # mammals - other
    "bear", "bears", "panda", "pandas", "koala", "koalas", "sloth", "sloths",
    "pangolin", "pangolins", "armadillo", "armadillos", "anteater", "anteaters",
    "monkey", "monkeys", "ape", "apes", "chimpanzee", "chimp", "chimps", "gorilla", "gorillas",
    "orangutan", "orangutans", "lemur", "lemurs", "baboon", "macaque",
    "pig", "pigs", "boar", "boars", "wartog", "warthog", "warthogs",
    "sheep", "lamb", "lambs", "goat", "goats", "yak", "alpaca", "llama", "llamas",
    "platypus", "echidna", "opossum", "possum", "wombat", "tasmanian",
    "bat", "bats", "skunk", "skunks", "weasel", "weasels", "ferret", "ferrets",
    "mongoose", "meerkat", "meerkats", "badger", "badgers", "wolverine",
    # marine
    "whale", "whales", "dolphin", "dolphins", "porpoise", "orca", "shark", "sharks",
    "seal", "seals", "sealion", "walrus", "octopus", "squid", "jellyfish", "stingray",
    "ray", "rays", "fish", "fishes", "salmon", "tuna", "trout", "cod", "eel", "lobster",
    "crab", "crabs", "shrimp", "starfish", "seahorse", "manatee", "narwhal",
    # reptiles/amphibians
    "snake", "snakes", "python", "cobra", "viper", "boa", "anaconda",
    "lizard", "lizards", "iguana", "iguanas", "gecko", "geckos", "chameleon", "chameleons",
    "alligator", "alligators", "crocodile", "crocodiles", "turtle", "turtles", "tortoise", "tortoises",
    "frog", "frogs", "toad", "toads", "salamander", "newt", "axolotl",
    # birds (광범위 — 새는 너무 많이 매칭되니 기본 동물 단어 reject)
    "bird", "birds", "eagle", "eagles", "hawk", "hawks", "falcon", "falcons",
    "owl", "owls", "vulture", "vultures", "crow", "crows", "raven", "ravens",
    "parrot", "parrots", "macaw", "cockatoo", "duck", "ducks", "goose", "geese",
    "swan", "swans", "chicken", "chickens", "rooster", "hen", "turkey", "turkeys",
    "peacock", "ostrich", "emu", "flamingo", "flamingos", "stork", "heron",
    "penguin", "penguins", "puffin", "albatross", "seagull", "pigeon", "pigeons",
    "sparrow", "robin", "cardinal", "hummingbird",
    # insects/spiders
    "ant", "ants", "bee", "bees", "wasp", "wasps", "butterfly", "butterflies",
    "moth", "moths", "spider", "spiders", "tarantula", "scorpion", "scorpions",
    "ladybug", "beetle", "beetles", "dragonfly", "mosquito",
}


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

    2026-05-07 v4: 광범위 동물 vocab. 토픽이 아닌 다른 동물명이 slug에 있으면 reject.
    Pangolin 토픽에 giraffe/boar/bird 영상 섞이는 사고 fix. Pexels는 niche 동물
    검색 시 무차별 wildlife 매칭하므로 slug에서 1차 차단 필수.
    """
    tokens = _slug_tokens(video.get("url", ""))
    if not tokens:
        return True

    single_words = set()
    if single_lower:
        single_words = {w for w in single_lower.split() if len(w) >= 3}

    # === 1차: 광범위 동물명 검사 ===
    # slug에 다른 동물 vocab이 있고 토픽 단어가 없으면 → 다른 동물 영상 → reject
    # 단, 토픽 단어가 같이 있으면 (사진가가 둘 다 태깅) → 통과
    other_animals_in_slug = (tokens & _KNOWN_ANIMAL_TOKENS) - single_words
    if other_animals_in_slug:
        # 토픽 단어가 같이 있는지 확인
        if not (tokens & single_words):
            # 토픽이 _KNOWN_ANIMAL_TOKENS에 있는데 (= 정상 동물 토픽) slug에 토픽 단어 없음 + 다른 동물 단어만
            return False

    # === 2차: 종 혼동 pair (정확한 매칭, _KNOWN_ANIMAL에 없는 케이스 보강) ===
    if single_lower and _has_confused_species(tokens, single_lower):
        if not (tokens & single_words):
            return False

    # === 3차: garbage 단어 (결혼/케이크/사람) ===
    blocked = tokens & _BLOCK_SLUG_WORDS
    if not blocked:
        return True
    # 차단어 있어도 동물명이 같이 들어있으면 진짜 동물 사진일 가능성 → 통과
    if single_words and (tokens & single_words):
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
                       exclude_pexels_ids: list = None,
                       ordered: bool = False,
                       hard_exclude_ids: list = None) -> list:
    """동영상 N개를 다운로드 (각 fact 구간별로 다른 영상).

    animal_single: 안전 보장 — 모든 키워드가 동물명을 포함하지 않으면
    fallback으로 동물명 단독 검색. generic 키워드("wild mammal" 등)로
    엉뚱한 동물 매칭되는 문제 방지.

    exclude_pexels_ids: 최근 N개 영상 풋티지 dedup(**soft** — 풀 부족 시 2차 패스에서 완화).
    hard_exclude_ids: content_history 30일 클립 dedup(**hard** — 2차 패스에서도 절대 완화 안 함).

    ordered: True면 키워드를 셔플하지 않고 주어진 순서대로 각 키워드당 1클립씩
    수집 → fact_keywords를 fact 순서대로 넘기면 배경도 fact 순서로 매칭됨.
    (2026-07-05 per-fact 배경 매칭)
    """
    paths = []
    used_ids = set()
    blocked_soft = set(int(i) for i in (exclude_pexels_ids or []) if str(i).isdigit() or isinstance(i, int))
    blocked_hard = set(int(i) for i in (hard_exclude_ids or []) if str(i).isdigit() or isinstance(i, int))
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

    if ordered:
        candidates = list(keywords)  # fact 순서 유지 (셔플/증식 안 함)
    else:
        candidates = list(keywords) * 3  # 키워드 풀 늘림
        random.shuffle(candidates)

    skipped_slug = 0
    skipped_recent = 0
    # 1차: soft+hard 모두 차단. 2차: 풀 부족 시 soft만 완화, **hard는 유지**.
    for pass_idx in (0, 1):
        block_set = (blocked_soft | blocked_hard) if pass_idx == 0 else blocked_hard
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
                    if not _media_ok(out):
                        log.warning(f"pexels 손상/잘린 클립 폐기: id={v['id']}")
                        try:
                            os.remove(out)
                        except OSError:
                            pass
                        continue
                    paths.append(out)
                    used_ids.add(v["id"])
                    log.info(f"pexels bg[{len(paths)}]: kw={kw} id={v['id']} dur={v.get('duration')}s")
                    if len(paths) >= n:
                        break
                    if ordered:
                        break  # 키워드당 1클립 → 다음 키워드로 (fact 순서 유지)
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
