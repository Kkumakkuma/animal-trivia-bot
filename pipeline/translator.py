"""title/description을 7개국 언어로 번역 → YouTube localizations."""
import json
import logging

from config import META_MODEL, OPENAI_API_KEY

log = logging.getLogger("animalbot.translator")

LOCALIZATION_LANGS = [
    ("ko", "Korean"),
    ("ja", "Japanese"),
    ("es", "Spanish"),
    ("pt", "Portuguese (Brazilian)"),
    ("de", "German"),
    ("fr", "French"),
    ("hi", "Hindi"),
]


def translate_for_youtube(title_en: str, description_en: str) -> dict:
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY 없음 — localizations 스킵")
        return {}

    lang_list = "\n".join(f"- {c}: {n}" for c, n in LOCALIZATION_LANGS)
    prompt = f"""You are a YouTube localization expert for animal trivia shorts. Translate the title and description below into the following languages, optimized for native click-through. Use natural, viral phrasing — NOT literal translation.

Languages:
{lang_list}

ENGLISH TITLE:
{title_en}

ENGLISH DESCRIPTION:
{description_en}

Output STRICT JSON only (no markdown):
{{
  "ko": {{"title":"...", "description":"..."}},
  "ja": {{"title":"...", "description":"..."}},
  "es": {{...}},
  "pt": {{...}},
  "de": {{...}},
  "fr": {{...}},
  "hi": {{...}}
}}"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=2500,
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning(f"번역 실패 — locales 스킵: {e}")
        return {}

    out = {}
    for code, _ in LOCALIZATION_LANGS:
        e = data.get(code) or {}
        title = (e.get("title") or "").strip()
        desc = (e.get("description") or "").strip()
        if title:
            out[code] = {"title": title[:95], "description": desc[:4900]}
    log.info(f"localizations 완료: {','.join(out.keys())}")
    return out
