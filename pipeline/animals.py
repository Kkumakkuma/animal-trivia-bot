"""오늘의 동물 선택 + GPT가 흥미 사실 3개 + 영문 제목/설명 생성.

각 fact는 짧게 (20~30 단어). 60초에 인트로(3s) + fact x3 (16s씩) + outro(9s).
"""
import json
import logging
import random

from config import ANIMALS, META_MODEL, OPENAI_API_KEY

log = logging.getLogger("animalbot.animals")


def pick_animal(rng: random.Random = None, exclude: list = None) -> str:
    rng = rng or random.Random()
    pool = [k for k in ANIMALS.keys() if not exclude or k not in exclude]
    return rng.choice(pool)


# 컴필레이션 단어 차단 (단일 영상이므로)
_BAD_TITLE_EN = ["compilation", "best of", "top 10", "top 20", " mix", " list"]


def _has_bad(text: str, words) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


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
