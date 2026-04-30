"""GPT가 동물 + Pexels 키워드 + 영문 hook/intro/facts/outro 일괄 생성.

ANIMALS 사전은 fallback용 (legacy). 기본은 GPT 동적 픽 (희귀종 포함).
"""
import json
import logging
import random

from config import ANIMALS, META_MODEL, OPENAI_API_KEY

log = logging.getLogger("animalbot.animals")


def pick_animal(rng: random.Random = None, exclude: list = None) -> str:
    """legacy fallback (사전에서 픽). pick_random_animal() 우선."""
    rng = rng or random.Random()
    pool = [k for k in ANIMALS.keys() if not exclude or k not in exclude]
    return rng.choice(pool)


# 컴필레이션 단어 차단 (단일 영상이므로)
_BAD_TITLE_EN = ["compilation", "best of", "top 10", "top 20", " mix", " list"]
_VALID_CATEGORIES = {"mammal", "bird", "marine", "fish", "reptile", "amphibian",
                     "insect", "cephalopod", "arachnid", "crustacean"}


def _has_bad(text: str, words) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def pick_random_animal(exclude_keys: list = None) -> dict:
    """GPT가 동적으로 동물 1마리 + 메타데이터 일괄 생성.

    풀: well-known 50% + 희귀종 50%.
    실패 시 사전에서 fallback.

    반환: {animal_key, display, single, category, pexels_keywords, title_en,
           description_en, hook, intro, facts, outro, tags}
    """
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY 없음 — fallback 사전 사용")
        key = pick_animal(exclude=exclude_keys or [])
        return _legacy_meta(key)

    exclude_str = ", ".join(exclude_keys[-10:]) if exclude_keys else "none"

    prompt = f"""You are a viral wildlife scriptwriter for YouTube Shorts channel "Animal Trivia 60s".
Pick ONE surprising animal RIGHT NOW and write a 30-second script.

ANIMAL POOL (mix of well-known and lesser-known):
- Well-known: otter, fox, owl, octopus, dolphin, elephant, penguin, capybara, sloth, raven, shark, squirrel, bee, hedgehog, koala, panda, kangaroo, cheetah, wolf, eagle, hummingbird, seahorse, jellyfish, starfish, butterfly, ladybug...
- Lesser-known/rare (people don't usually know these): pangolin, axolotl, glass frog, mantis shrimp, naked mole rat, fennec fox, peacock spider, immortal jellyfish, blobfish, leafy seadragon, tardigrade, aye-aye, okapi, tarsier, narwhal, dumbo octopus, vampire squid, anglerfish, frilled shark, snub-nosed monkey, saiga antelope, fossa, binturong, pink fairy armadillo, kakapo, hoatzin, shoebill, sun bear, Japanese spider crab, bombardier beetle, peacock mantis shrimp, walking shark, giant isopod, yeti crab, leaf-tailed gecko, sunfish, chevrotain, dik-dik, gerenuk, secretary bird, Honduran white bat, Philippine eagle, axolotl, archerfish, cassowary, harpy eagle...

Aim for about 50% of picks to be the lesser-known group — viewers love surprising animals they've never heard of.

AVOID picking these animals (recently used): {exclude_str}

REQUIREMENTS:
- The fact MUST be SURPRISING / counter-intuitive / shocking with a specific number when possible.
- Each fact ≤ 14 words. ONE sentence each.
- Hook line MUST start with "Did you know" / "Wait until you see" / "This is why" / "Watch this".
- Outro CTA MUST be one of: "Follow for more animal facts." / "Follow for daily wild facts." / "Comment your favorite animal."
- pexels_keywords: 5 keywords likely to find PORTRAIT video on Pexels (mix specific name + visual descriptors). For very rare animals, include broad fallback like "[category] close up" or "wild [category]".
- category: one of {sorted(_VALID_CATEGORIES)}.
- Title: max 90 chars, includes the animal name. NEVER use "compilation", "best of", "top 10".
- Description: 2 sentences + 5 hashtags (no emoji).
- Hook (on-screen overlay text): 2-4 words like "Pangolins • Trivia".

Output STRICT JSON only:
{{
  "animal_key": "snake_case_id",
  "display": "Pangolins",
  "single": "pangolin",
  "category": "mammal",
  "pexels_keywords": ["pangolin close up", "pangolin walking", "wild pangolin", "scaly mammal", "pangolin tongue"],
  "title_en": "...",
  "description_en": "... #shorts #animalfacts #wildlife #didyouknow #pangolin",
  "hook": "Pangolins • Trivia",
  "intro": "Did you know pangolins do this?",
  "facts": ["fact1 (≤14 words)", "fact2", "fact3"],
  "outro": "Follow for more animal facts.",
  "tags": ["shorts","animals","animal facts","wildlife","trivia","did you know","pangolin","scales"]
}}"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=1.0,  # 다양성 확보
            max_tokens=1200,
        )
        d = json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning(f"GPT 동물 픽 실패 → legacy fallback: {e}")
        key = pick_animal(exclude=exclude_keys or [])
        return _legacy_meta(key)

    # 검증 + 정제
    animal_key = (d.get("animal_key") or "").strip().lower().replace(" ", "_") or "wild_animal"
    display = (d.get("display") or "Animals").strip()
    single = (d.get("single") or "animal").strip()
    category = (d.get("category") or "mammal").strip().lower()
    if category not in _VALID_CATEGORIES:
        category = "mammal"

    pexels_kw = d.get("pexels_keywords") or [f"{single} close up", f"{single} wild", f"wild {category}"]
    if not isinstance(pexels_kw, list) or len(pexels_kw) < 3:
        pexels_kw = [f"{single} close up", f"{single} wild", f"wild {category}"]
    # 항상 fallback 키워드 추가
    pexels_kw = list(pexels_kw) + [f"wild {category}", f"{category} close up"]

    title_en = (d.get("title_en") or f"{display} Facts").strip()[:95]
    if _has_bad(title_en, _BAD_TITLE_EN):
        title_en = f"{display}: 3 Wild Facts"

    facts = d.get("facts") or []
    if not isinstance(facts, list) or len(facts) < 3:
        facts = [f"{display} are way more interesting than people think."] * 3
    facts = [str(f).strip() for f in facts[:3]]

    return {
        "animal_key": animal_key,
        "display": display,
        "single": single,
        "category": category,
        "pexels_keywords": pexels_kw,
        "title_en": title_en,
        "description_en": (d.get("description_en") or f"3 wild facts about {single}s.")[:4900],
        "hook": (d.get("hook") or f"{display} • Trivia")[:40],
        "intro": (d.get("intro") or f"Did you know {single}s do this?").strip(),
        "facts": facts,
        "outro": (d.get("outro") or "Follow for more animal facts.").strip(),
        "tags": d.get("tags") or ["shorts", "animals", "animal facts", "wildlife", "trivia",
                                  "did you know", animal_key.replace("_", " "), single, display],
    }


def _legacy_meta(animal_key: str) -> dict:
    """fallback: ANIMALS 사전 + 기본 fact."""
    cfg = ANIMALS.get(animal_key) or list(ANIMALS.values())[0]
    display = cfg["display"]
    single = cfg["single"]
    return {
        "animal_key": animal_key,
        "display": display,
        "single": single,
        "category": cfg.get("category", "mammal"),
        "pexels_keywords": cfg["pexels_keywords"],
        "title_en": f"3 Wild Facts About {display}",
        "description_en": f"3 surprising facts about {single}s. \n\n#shorts #animals #wildlife #didyouknow #animalfacts",
        "hook": f"{display} • Trivia",
        "intro": f"Did you know {single}s do this?",
        "facts": [
            f"{display} are way more interesting than most people think.",
            f"This one habit of {single}s might surprise you.",
            f"Most folks have no idea what {single}s really do.",
        ],
        "outro": "Follow for more animal facts.",
        "tags": ["shorts", "animals", "animal facts", "wildlife", "trivia",
                 "did you know", animal_key.replace("_", " "), single, display],
    }


def make_meta(animal_key: str) -> dict:
    """반환: {title_en, description_en, intro, facts[3], outro, hook, tags}

    intro: 0~3s에 깔리는 한 줄 (예: "Did you know about otters?")
    facts: 3개 fact (각 20~30 단어, 자막+TTS)
    outro: 마지막 5~9s 한 줄 (예: "Follow for daily animal trivia.")
    hook: 영상 상단에 박는 짧은 한 줄 (예: "Otter Trivia")
    """
    cfg = ANIMALS[animal_key]
    display = cfg["display"]
    single = cfg["single"]

    fallback = {
        "title_en": f"3 Wild Facts About {display} You Didn't Know",
        "description_en": (
            f"3 surprising facts about {single}s in 30 seconds. "
            f"\n\n#shorts #{animal_key.replace('_', '')} #animals #wildlife #didyouknow"
        ),
        "intro": f"Did you know {single}s do this?",
        "facts": [
            f"{display} are way more interesting than people think.",
            f"Most folks have no idea what {single}s actually do.",
            f"This one fact about {single}s might blow your mind.",
        ],
        "outro": "Follow for more animal facts.",
        "hook": f"{display} • Trivia",
        "tags": [
            "shorts", "animals", "animal facts", "wildlife", "trivia",
            "did you know", animal_key.replace("_", " "), single, display,
        ],
    }

    if not OPENAI_API_KEY:
        return fallback

    prompt = f"""You are a viral YouTube Shorts scriptwriter for an animal trivia channel called "Animal Trivia 60s".
Benchmark: NatGeo Wild, BBC Earth, Bright Side, Animals Around The Globe — punchy hook, surprising fact, CTA.

Generate a ~30-second script about {display} ({single}). Structure:
- 0~3s: hook line (must START with "Did you know" or "Wait until you see" or "This is why" — proven viral templates)
- 3~28s: three SHORT punchy facts, each ~7 seconds spoken
- 28~32s: outro CTA

HARD RULES:
- Each fact MUST be EXACTLY ONE SENTENCE, 10~14 words. NOT MORE THAN 14. Subtitles split into 3-4 word phrases on screen, so each fact must be tight.
- Facts must be SURPRISING / counter-intuitive / shocking — not generic ("they live in groups" is BAD; "they hold hands while sleeping" is GOOD). Include a specific number/measurement when possible (e.g. "270 degrees", "5 minutes", "40 yards").
- Plain spoken English, no jargon, no emoji.
- Title: catchy, max 90 chars, includes "{display}" or "{single}". NEVER use "compilation", "best of", "top 10".
- Description: 2 sentences hook + 5 hashtags (no emoji).
- Hook (on-screen overlay text): 2-4 words, e.g. "{display} • Trivia" or "Wild {display} Facts".
- Intro: 5~9 words, MUST start with "Did you know" / "Wait until you see" / "This is why" / "Watch this".
- Outro: 4~7 words CTA, MUST be one of: "Follow for more animal facts." / "Follow for daily wild facts." / "Comment your favorite animal."

Output STRICT JSON only:
{{
  "title_en": "...",
  "description_en": "...",
  "hook": "...",
  "intro": "...",
  "facts": ["fact1", "fact2", "fact3"],
  "outro": "..."
}}"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=900,
        )
        d = json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning(f"GPT 메타 실패 fallback: {e}")
        return fallback

    title_en = (d.get("title_en") or fallback["title_en"])[:95]
    if _has_bad(title_en, _BAD_TITLE_EN):
        log.warning(f"bad word in title fallback: {title_en}")
        title_en = fallback["title_en"]

    facts = d.get("facts") or []
    if not isinstance(facts, list) or len(facts) < 3:
        log.warning(f"facts 부족 fallback: {facts}")
        facts = fallback["facts"]
    facts = [str(f).strip() for f in facts[:3]]

    return {
        "title_en": title_en,
        "description_en": (d.get("description_en") or fallback["description_en"])[:4900],
        "intro": (d.get("intro") or fallback["intro"]).strip(),
        "facts": facts,
        "outro": (d.get("outro") or fallback["outro"]).strip(),
        "hook": (d.get("hook") or fallback["hook"]).strip()[:40],
        "tags": fallback["tags"],
    }
