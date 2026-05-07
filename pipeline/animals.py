"""GPT가 동물 + Pexels 키워드 + 영문 hook/intro/facts/outro 일괄 생성.

ANIMALS 사전은 fallback용 (legacy). 기본은 GPT 동적 픽 (희귀종 포함).
"""
import json
import logging
import random

from config import ANIMALS, META_MODEL, OPENAI_API_KEY

log = logging.getLogger("animalbot.animals")


def pick_animal(rng: random.Random = None, exclude: list = None) -> str:
    """legacy fallback (사전에서 픽). pick_random_animal() 우선.

    2026-05-07 fix: exclude가 ANIMALS dict 전체를 덮으면 pool이 빈 리스트가 되어
    random.choice([]) IndexError 발생. used_animals.json이 누적되어 일어남 →
    빈 pool일 때 exclude 무시하고 전체에서 픽 (cycle reset).
    """
    rng = rng or random.Random()
    pool = [k for k in ANIMALS.keys() if not exclude or k not in exclude]
    if not pool:
        pool = list(ANIMALS.keys())
    return rng.choice(pool)


# 컴필레이션 단어 차단 (단일 영상이므로)
_BAD_TITLE_EN = ["compilation", "best of", "top 10", "top 20", " mix", " list"]
_VALID_CATEGORIES = {"mammal", "bird", "marine", "fish", "reptile", "amphibian",
                     "insect", "cephalopod", "arachnid", "crustacean"}

# 다른 동물 단어 — comment에서 본 토픽 외 다른 동물이 등장하면 off-topic 의심.
# 우주봇의 Saturn→Jupiter 사고와 같은 패턴 차단 (양 채널 동기 적용).
_OTHER_TOPIC_WORDS = {
    "octopus", "octopuses", "capybara", "otter", "otters", "fox", "foxes",
    "owl", "owls", "dolphin", "dolphins", "elephant", "elephants",
    "penguin", "penguins", "sloth", "sloths", "bear", "bears",
    "lion", "lions", "tiger", "tigers", "panda", "pandas",
    "cheetah", "leopard", "kangaroo", "koala", "eagle",
    "parrot", "parrots", "hummingbird", "butterfly", "bee", "bees",
    "spider", "spiders", "crab", "lobster", "jellyfish",
    "starfish", "frog", "frogs", "snake", "snakes", "hedgehog",
    "squirrel", "deer", "raccoon", "wolf", "wolves",
    "monkey", "gorilla", "chimpanzee", "zebra", "giraffe",
    "hippo", "rhino", "horse", "donkey", "goat", "sheep",
    "alpaca", "llama", "cow", "pig", "duck", "swan", "flamingo",
    "shark", "sharks", "whale", "whales", "seal", "walrus",
    "axolotl", "fennec", "pangolin", "ocelot", "anteater", "tapir",
    "lemur", "narwhal", "platypus", "echidna", "wombat", "quokka",
}


def _has_bad(text: str, words) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _topic_tokens(text: str) -> set:
    """소문자 단어 토큰 집합 (영문만)."""
    import re as _re
    return {w for w in _re.findall(r"[a-z]+", text.lower()) if len(w) >= 3}


def verify_consistency(meta: dict) -> dict:
    """GPT 1회로 facts/comment 내부 일관성 검증/수정 (우주봇과 동기 fix).

    Catches:
    - facts 내 숫자 모순
    - comment가 다른 토픽
    실패 시 원본 meta 유지.
    """
    if not OPENAI_API_KEY:
        return meta

    display = meta.get("display", "").strip()
    single = meta.get("single", "").strip()
    facts = list(meta.get("facts", []) or [])
    comment = meta.get("comment", "").strip()
    title = meta.get("title_en", "").strip()

    if not facts or not display:
        return meta

    own_tokens = _topic_tokens(f"{display} {single}")
    comment_tokens = _topic_tokens(comment)
    other_in_comment = (comment_tokens & _OTHER_TOPIC_WORDS) - own_tokens
    has_own_in_comment = bool(comment_tokens & own_tokens) or display.lower() in comment.lower() or single.lower() in comment.lower()
    suspect_offtopic_comment = bool(other_in_comment) or not has_own_in_comment

    review_prompt = f"""You are a script consistency editor for YouTube Shorts about {display} ({single}).

Review this script for two CRITICAL issues:
1. NUMERIC CONTRADICTIONS between facts (e.g. fact 1 says "82 millions of years" + fact 2 says "79" for the same metric)
2. COMMENT OFF-TOPIC (comment mentions an animal that is NOT {display} / {single})

Title: {title}
Facts:
{chr(10).join(f"{i+1}. {f}" for i, f in enumerate(facts))}
Comment: {comment}

INSTRUCTIONS:
- If 2+ facts cite different numbers for the SAME metric, pick ONE accurate value (latest 2024 consensus)
  and rewrite ALL contradicting facts to use that value. Keep facts at 28-36 words.
- If comment mentions any animal other than {display}/{single}, rewrite the comment to be about
  {display} ONLY, in 8-20 words, using one of: hot take / forced choice within {single} / what-if /
  personal challenge / confession bait / fill-in-the-blank.
- If everything is fine, return original facts and comment unchanged.

Output STRICT JSON: {{"facts": ["...", "...", "...", "..."], "comment": "...", "fixed": ["short list of issues fixed, empty if none"]}}"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "user", "content": review_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=900,
        )
        d = json.loads(resp.choices[0].message.content)
        new_facts = d.get("facts") or []
        new_comment = (d.get("comment") or "").strip()
        fixed = d.get("fixed") or []
        if isinstance(new_facts, list) and len(new_facts) == len(facts):
            new_facts = [str(f).strip() for f in new_facts if str(f).strip()]
            if len(new_facts) == len(facts):
                meta["facts"] = new_facts
        if new_comment and 5 < len(new_comment) <= 280:
            meta["comment"] = new_comment
        if fixed:
            log.info(f"consistency check fixed {len(fixed)}건: {fixed}")
        elif suspect_offtopic_comment:
            log.warning(f"comment 사전 의심됐지만 GPT는 수정 없다고 판단 (other_in_comment={other_in_comment}, has_own={has_own_in_comment})")
    except Exception as e:
        log.warning(f"consistency check 실패 — 원본 유지: {e}")

    return meta


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

    exclude_str = ", ".join(exclude_keys[-30:]) if exclude_keys else "none"

    prompt = f"""You are a viral wildlife scriptwriter for YouTube Shorts channel "Animal Trivia 60s".
Pick ONE surprising animal RIGHT NOW and write a 55-second script (1-minute Shorts).

CRITICAL CONSTRAINT: pexels_keywords MUST find PORTRAIT video on Pexels. So you must pick animals that are
WELL-PHOTOGRAPHED on stock footage sites. Avoid extremely rare creatures with no video footage.

GOOD ANIMAL POOL (these have abundant Pexels portrait video):
- Common: otter, fox, owl, dolphin, octopus, elephant, penguin, sloth, bear, lion, tiger, panda, cheetah, leopard, kangaroo, koala, eagle, hawk, falcon, parrot, hummingbird, butterfly, bee, dragonfly, spider, crab, lobster, jellyfish, starfish, sea turtle, frog, gecko, chameleon, snake, hedgehog, squirrel, deer, raccoon, wolf, husky, monkey, orangutan, gorilla, chimpanzee, zebra, giraffe, hippo, rhino, buffalo, antelope, horse, donkey, goat, sheep, alpaca, llama, cow, pig, duck, goose, swan, flamingo, peacock, parakeet, cardinal, macaw, ostrich, pelican, heron, seagull, shark, manta ray, fish (clownfish, lionfish, pufferfish, eel), seahorse, dolphin, whale, seal, walrus, sea lion
- Surprising-but-photographed: capybara, axolotl, fennec fox, red panda, sugar glider, pangolin, ocelot, anteater, tapir, lemur, mantis shrimp, narwhal (rare), nudibranch, sea slug, glass frog (rare on pexels), poison dart frog, leaf insect, stick insect, peacock spider (very rare), shoebill stork, secretary bird, harpy eagle, cassowary, kiwi, tasmanian devil, quokka, numbat, echidna, platypus, wombat, bilby, marsupial mole

AVOID (poor Pexels coverage): naked mole rat, blobfish, immortal jellyfish, tardigrade, pink fairy armadillo, aye-aye, kakapo, hoatzin, snub-nosed monkey, walking shark, yeti crab, vampire squid, leafy seadragon (mostly aquariums), bombardier beetle, dumbo octopus, frilled shark.

Aim for about 60% common + 40% surprising-but-photographed. Prioritize coverage over rarity — viewer engagement requires actual visual.

AVOID picking these animals (recently used): {exclude_str}

REQUIREMENTS:
- The fact MUST be SURPRISING / counter-intuitive / shocking with a specific number when possible.
- **Each fact MUST be 28-36 words. NOT LESS THAN 28. NOT MORE THAN 36.** Count the words. Three short facts = REJECT and rewrite.
- Each fact = ONE rich sentence packed with a specific number + comparison/context + surprising consequence. Spoken at TTS rate +12% this gives ~12s per fact.
- Provide EXACTLY 4 facts (not 3). Total spoken length target: intro ~3s + 4 facts × ~10s + outro ~3s ≈ 46s (실TTS +5~10s 마진).
- **INTERNAL CONSISTENCY (CRITICAL — viewers WILL catch contradictions and call you out)**:
  - All numeric claims across the 4 facts MUST agree. If fact 1 says "an octopus has 9 brains", fact 2/3/4 must NOT cite a different number for the same metric. Pick ONE number per metric and use it consistently.
  - If you cite "X% of [thing]" or "Y times [thing]", any other fact about the SAME metric MUST use the SAME value.
  - Use latest 2024 scientific consensus values. Do not mix old and new numbers.
  - title and description MUST be about the same animal as the facts.
- Hook line (intro narration) MUST start with "Did you know" / "Wait until you see" / "This is why" / "Watch this".
- Outro CTA MUST be one of: "Follow for more animal facts." / "Follow for daily wild facts." / "Comment your favorite animal."
- Each fact MUST start differently (vary openers — never repeat "X are way more interesting" or any generic opener).
- pexels_keywords: 5 keywords. **EVERY keyword MUST contain the animal name** (e.g., for octopus: "octopus close up", "octopus swimming", "octopus reef", "octopus tentacles", "octopus camouflage"). NEVER use generic terms like "wild mammal" or "scaly mammal" — those bring up wrong animal videos. The animal name must be the LITERAL species (pangolin/otter/octopus), not a category.
- category: one of {sorted(_VALID_CATEGORIES)}.
- **Title (CRITICAL — single most important CTR factor)**: max 70 chars, MUST include the animal name + a CURIOSITY GAP hook. NEVER use "compilation", "best of", "top 10", "Amazing Facts About X" (too generic, kills CTR).
  Use ONE of these viral patterns (vary across animals):
  (a) Shocking number: "Octopuses Have 9 Brains?! Here's Why"
  (b) Wait what: "Wait, Pangolins Eat 70 Million Ants A Year"
  (c) You'd never guess: "You Won't Believe What Sloths Do at 2AM"
  (d) Conditional twist: "If Capybaras Could Vote, We'd Be in Trouble"
  (e) The truth: "The Truth About Why Foxes Hide From Humans"
  (f) Stop scrolling: "Stop Scrolling — A Cuttlefish Just Hypnotized You"
  (g) Question hook: "How Do Hummingbirds Survive On 0% Sleep?"
  Keep it punchy. Lowercase or Title Case both fine. NO emoji in title.
- Description: 2 sentences + 5 hashtags (no emoji).
- Hook (on-screen overlay text): 2-4 words like "Pangolins • Trivia".
- **comment** (auto-pinned reply-magnet comment under the video): ONE line, 8-20 words.
  GOAL: provoke viewers to actually reply, not just scroll past. Statement-of-fact comments get IGNORED.
  **CRITICAL — TOPIC LOCK**: The comment MUST be about THE EXACT ANIMAL YOU JUST PICKED. If you picked
  pangolin → comment is about pangolin ONLY. Do NOT mention any OTHER animal (no "Capybara or otter"
  type cross-topic forced choices when the video is about pangolin). Below are STYLE patterns —
  replace the example animal with your picked animal.
  (a) Hot take / fight me — STYLE: "Hot take: [animal] is [provocative claim]. Fight me 🔥"
  (b) Forced choice WITHIN the same animal — STYLE: "Would you rather [scenario A with the animal] or [scenario B with the animal]?"
  (c) Reincarnation / what-if — STYLE: "If reincarnation is real I'm coming back as [animal]. Who's with me?"
  (d) Personal challenge — STYLE: "Bet you can't watch a [animal] for 30 seconds without [reaction]. Try it."
  (e) Confession bait — STYLE: "Confession: I would absolutely [action] for a [animal]. Anyone else?"
  (f) Fill-in-the-blank — STYLE: "If [animal] were a coworker, they'd be the one who ___"
  Use 0-1 emoji max. **NEVER** these dead patterns: "Which fact surprised you most?", "Tag a friend who...", "Did you know any of these?", "Like if you learned something" — those get zero replies.

Output STRICT JSON only (the example below uses {{animal_name}} — REPLACE with the animal you actually picked, do NOT copy the example animal verbatim):
{{
  "animal_key": "snake_case_id_of_picked_animal",
  "display": "{{Animal Plural}}",
  "single": "{{animal singular}}",
  "category": "mammal",
  "pexels_keywords": ["{{animal}} close up", "{{animal}} walking", "{{animal}} in wild", "{{animal}} feature_a", "{{animal}} feature_b"],
  "title_en": "viral title with the picked animal name + curiosity gap",
  "description_en": "2 sentences + 5 hashtags ending with #{{animal}}",
  "hook": "{{Animal Plural}} • Trivia",
  "intro": "Did you know {{animals}} do something surprising?",
  "facts": ["fact1 (28-36 words)", "fact2 (28-36 words)", "fact3 (28-36 words)", "fact4 (28-36 words)"],
  "outro": "Follow for more animal facts.",
  "comment": "reply-magnet line about {{animal}} only",
  "tags": ["shorts","animals","animal facts","wildlife","trivia","did you know","{{animal}}","specific_feature"]
}}"""

    # 2026-05-07 fix: GPT가 prompt example의 pangolin에 강하게 bias되어 9연속 pangolin 발행 사고.
    # AVOID 텍스트만으로는 GPT가 무시하는 케이스 → 코드 reject + retry로 강제.
    exclude_set = {k.lower().strip() for k in (exclude_keys or [])}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    d = None
    last_pick = None
    for attempt in range(4):
        try_prompt = prompt
        if attempt > 0 and last_pick:
            try_prompt = (
                f"REJECTED previous pick: '{last_pick}' is in exclude list. Pick a COMPLETELY DIFFERENT animal.\n\n"
                + try_prompt
            )
        try:
            resp = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "user", "content": try_prompt}],
                response_format={"type": "json_object"},
                temperature=1.0,  # 다양성 확보
                max_tokens=1200,
            )
            cand = json.loads(resp.choices[0].message.content)
        except Exception as e:
            log.warning(f"GPT 동물 픽 실패 → legacy fallback: {e}")
            key = pick_animal(exclude=exclude_keys or [])
            return _legacy_meta(key)

        cand_key = (cand.get("animal_key") or "").strip().lower().replace(" ", "_")
        cand_single = (cand.get("single") or "").strip().lower()
        cand_display = (cand.get("display") or "").strip().lower()
        # exclude_set과 매칭: animal_key, single, display 셋 다 검사
        is_excluded = (
            cand_key in exclude_set
            or cand_single in exclude_set
            or cand_display in exclude_set
            or any(e and (e in cand_key or e in cand_single) for e in exclude_set if e)
        )
        if is_excluded:
            last_pick = cand_key or cand_single
            log.warning(f"[picker try {attempt+1}] GPT가 exclude된 '{last_pick}' 픽 → 재요청")
            continue
        d = cand
        break

    if d is None:
        log.warning(f"GPT가 4회 모두 exclude된 토픽만 픽 → legacy fallback")
        key = pick_animal(exclude=exclude_keys or [])
        return _legacy_meta(key)

    # 검증 + 정제
    animal_key = (d.get("animal_key") or "").strip().lower().replace(" ", "_") or "wild_animal"
    display = (d.get("display") or "Animals").strip()
    single = (d.get("single") or "animal").strip()
    category = (d.get("category") or "mammal").strip().lower()
    if category not in _VALID_CATEGORIES:
        category = "mammal"

    # === 매칭 안전선: 모든 검색 키워드에 동물명(single) 반드시 포함 ===
    # 이전 버그: "wild mammal", "mammal close up" 같은 generic fallback이 들어가
    # capybara 검색 시 hedgehog/rabbit 영상까지 매칭됨 (애드센스/시청자 신뢰 직격).
    raw_kw = d.get("pexels_keywords") or []
    if not isinstance(raw_kw, list):
        raw_kw = []
    sanitized_kw = []
    single_lower = single.lower()
    for kw in raw_kw:
        if not isinstance(kw, str):
            continue
        kw = kw.strip()
        if not kw:
            continue
        if single_lower in kw.lower():
            sanitized_kw.append(kw)
        else:
            # 동물명 없는 키워드는 prepend (generic 매칭 방지)
            sanitized_kw.append(f"{single} {kw}")
    if not sanitized_kw:
        sanitized_kw = [single, f"{single} close up", f"{single} in the wild", f"{single} wildlife"]
    # generic category fallback 제거 — 동물명 포함 키워드만
    pexels_kw = sanitized_kw[:8]

    title_en = (d.get("title_en") or f"{display} Facts").strip()[:95]
    if _has_bad(title_en, _BAD_TITLE_EN):
        title_en = f"{display}: 3 Wild Facts"
    # generic "Amazing Facts About X" / "Wild Facts About X" 패턴 reject — CTR 죽음
    _generic = ["amazing facts about", "wild facts about", "interesting facts about",
                "fascinating facts about", "facts you didn't know"]
    if any(g in title_en.lower() for g in _generic):
        log.warning(f"generic title pattern → CTR-friendly fallback: {title_en}")
        # 동물별 hook fallback (number + question)
        title_en = f"Wait — {display} Do This?!"

    facts = d.get("facts") or []
    if not isinstance(facts, list) or len(facts) < 3:
        facts = [f"{display} are way more interesting than people think."] * 4
    # 4개 우선, 부족하면 3개라도 수용
    facts = [str(f).strip() for f in facts[:5] if str(f).strip()]
    if len(facts) < 3:
        facts = facts + [f"{display} have surprising habits most people never notice."] * (3 - len(facts))
    # 한 fact라도 32단어 미만이면 GPT로 확장 (60초 길이 보장 핵심)
    if any(len(f.split()) < 26 for f in facts):
        log.warning(f"facts too short ({[len(f.split()) for f in facts]}), expanding to 28-36 words each...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            n = len(facts)
            joined = "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))
            expand_prompt = f"""Rewrite each fact to EXACTLY 28-36 words. Add a specific number, a comparison or context, and a surprising consequence. Keep them TRUE. Vary the sentence openers (never repeat patterns).

Original {n} facts about {display}:
{joined}

Output STRICT JSON: {{"facts": [{', '.join(['"fact (28-36 words)"'] * n)}]}}"""
            r2 = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "user", "content": expand_prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=900,
            )
            d2 = json.loads(r2.choices[0].message.content)
            new_facts = d2.get("facts") or []
            if isinstance(new_facts, list) and len(new_facts) >= len(facts):
                facts = [str(f).strip() for f in new_facts[:len(facts)]]
                log.info(f"facts expanded to {[len(f.split()) for f in facts]}")
        except Exception as e:
            log.warning(f"expand 실패 — 원본 유지: {e}")

    # 댓글 — 동물별 맞춤 (GPT 생성). 누락 또는 빈 문자열이면 fallback.
    comment = (d.get("comment") or "").strip()
    if not comment or len(comment) < 10:
        comment = f"What's the wildest thing you knew about {single}s?"
    comment = comment[:280]  # YouTube 댓글 길이 안전선

    meta = {
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
        "comment": comment,
        "tags": d.get("tags") or ["shorts", "animals", "animal facts", "wildlife", "trivia",
                                  "did you know", animal_key.replace("_", " "), single, display],
    }
    return verify_consistency(meta)


def expand_legacy_to_rich(meta: dict) -> dict:
    """legacy fallback에서 만든 generic meta를 GPT로 풀어 진짜 facts 생성.

    legacy_meta는 'are way more interesting than people think' 같은 generic 템플릿.
    워크플로 매번 같은 말 반복 방지 위해 GPT로 진짜 facts 4개를 만든다.

    실패 시 호출 측에서 원본 meta 그대로 사용 (안전).
    반환: facts/intro/outro/title_en/description_en/comment 일부 갱신된 dict.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 없음 — expand 불가")

    display = meta.get("display", "Animals")
    single = meta.get("single", "animal")

    prompt = f"""Write a 55-second YouTube Shorts script about {display} ({single}).

REQUIREMENTS:
- 4 facts, each EXACTLY 28-36 words. Specific numbers + comparison + surprising consequence per fact.
- Each fact opens DIFFERENTLY (no repeated openers like "X are way more interesting").
- **INTERNAL CONSISTENCY (CRITICAL)**: All numeric claims across the 4 facts MUST agree. If fact 1 says "{display} have N [thing]", fact 2/3/4 must NOT cite a different number. Use latest 2024 scientific consensus values.
- Intro: 5-9 words, MUST start with "Did you know" / "Wait until you see" / "This is why" / "Watch this".
- Outro: 4-7 words CTA, one of: "Follow for more animal facts." / "Follow for daily wild facts." / "Comment your favorite animal."
- Hook (overlay text): 2-4 words like "{display} • Trivia".
- **Title (CRITICAL CTR — pick ONE viral pattern, max 70 chars, must include "{single}" or "{display}", NO emoji)**:
  (a) Shocking number: "{display} Have ___ ?! Here's Why"
  (b) Wait what: "Wait, {display} Eat ___ A Year"
  (c) You won't believe: "You Won't Believe What {display} Do at Night"
  (d) Conditional twist: "If {display} Could ___, We'd Be in Trouble"
  (e) Stop scrolling: "Stop Scrolling — A {single} Just ___"
  (f) Question hook: "How Do {display} Survive ___?"
  NEVER use "Amazing Facts About", "Wild Facts About", "Facts You Didn't Know" — generic patterns kill CTR.
- Description: 2 sentences + 5 hashtags (no emoji).
- **comment** (reply-magnet, 8-20 words): hot take / forced choice WITHIN {single} only / what-if / personal challenge / confession bait / fill-in-the-blank.
  **TOPIC LOCK**: comment MUST be about {display}/{single} ONLY. NEVER mention any OTHER animal. 0-1 emoji max. NEVER "Which fact surprised you most?" or "Tag a friend".

Output STRICT JSON: {{
  "title_en": "...",
  "description_en": "... #shorts #animalfacts #wildlife #didyouknow #{single}",
  "hook": "{display} • Trivia",
  "intro": "Did you know {single}s do this?",
  "facts": ["fact1 (28-36 words)", "fact2", "fact3", "fact4"],
  "outro": "Follow for more animal facts.",
  "comment": "..."
}}"""

    # Rate limit 429 회피: 최대 3회 retry + exponential backoff
    import time as _time
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    last_err = None
    d = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.9,
                max_tokens=1100,
            )
            d = json.loads(resp.choices[0].message.content)
            break
        except Exception as e:
            last_err = e
            es = str(e).lower()
            if "rate_limit" in es or "429" in es or "tpm" in es:
                wait = [5, 15, 30][attempt]
                log.warning(f"expand_legacy_to_rich rate limit → {wait}s 후 재시도 (attempt {attempt+1}/3)")
                _time.sleep(wait)
            else:
                raise
    if d is None:
        raise last_err or RuntimeError("expand_legacy_to_rich GPT 호출 3회 모두 실패")

    facts = d.get("facts") or []
    if not isinstance(facts, list) or len(facts) < 3:
        raise RuntimeError(f"GPT facts 부족: {facts}")
    facts = [str(f).strip() for f in facts[:5] if str(f).strip()]

    title_en = (d.get("title_en") or f"Wait — {display} Do This?!").strip()[:95]
    if _has_bad(title_en, _BAD_TITLE_EN):
        title_en = f"Wait — {display} Do This?!"
    _generic = ["amazing facts about", "wild facts about", "interesting facts about",
                "fascinating facts about", "facts you didn't know"]
    if any(g in title_en.lower() for g in _generic):
        log.warning(f"legacy expand: generic title → CTR-friendly fallback: {title_en}")
        title_en = f"Wait — {display} Do This?!"

    comment = (d.get("comment") or "").strip()
    if not comment or len(comment) < 10:
        comment = f"What's the wildest thing you knew about {single}s?"
    comment = comment[:280]

    rich = {
        "title_en": title_en,
        "description_en": (d.get("description_en") or f"4 wild facts about {single}s.")[:4900],
        "intro": (d.get("intro") or f"Did you know {single}s do this?").strip(),
        "facts": facts,
        "outro": (d.get("outro") or "Follow for more animal facts.").strip(),
        "hook": (d.get("hook") or f"{display} • Trivia").strip()[:40],
        "comment": comment,
    }
    review_input = {**rich, "display": display, "single": single}
    review_input = verify_consistency(review_input)
    rich["facts"] = review_input.get("facts", rich["facts"])
    rich["comment"] = review_input.get("comment", rich["comment"])
    return rich


def _legacy_meta(animal_key: str) -> dict:
    """fallback: ANIMALS 사전 + 기본 fact (호출 측에서 expand_legacy_to_rich 권장)."""
    cfg = ANIMALS.get(animal_key) or list(ANIMALS.values())[0]
    display = cfg["display"]
    single = cfg["single"]
    return {
        "animal_key": animal_key,
        "display": display,
        "single": single,
        "category": cfg.get("category", "mammal"),
        "pexels_keywords": cfg["pexels_keywords"],
        "title_en": f"4 Wild Facts About {display}",
        "description_en": f"4 surprising facts about {single}s. \n\n#shorts #animals #wildlife #didyouknow #animalfacts",
        "hook": f"{display} • Trivia",
        "intro": f"Did you know {single}s do this?",
        "facts": [
            f"{display} surprise scientists with their unique behaviors and senses.",
            f"Most {single}s have an unusual skill that took millions of years to evolve.",
            f"There is a fascinating thing about {single}s that few people ever get to witness in person.",
            f"Researchers have only recently begun documenting how clever {single}s really are.",
        ],
        "outro": "Follow for more animal facts.",
        "comment": f"What's the wildest thing you knew about {single}s?",
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

Generate a ~35-second script about {display} ({single}). Structure:
- 0~3s: hook line (must START with "Did you know" or "Wait until you see" or "This is why" — proven viral templates)
- 3~30s: three RICH facts, each ~8-9 seconds spoken (about 22 words each)
- 30~35s: outro CTA

HARD RULES:
- Each fact MUST be exactly 20~26 words. NOT LESS THAN 20. NOT MORE THAN 26. Count the words. Three facts under 18 words each = REJECT and rewrite.
- Each fact = ONE long sentence. Pack a specific number + a concrete comparison/extra detail.
- BAD example (8 words): "Crocodiles can hold their breath for an hour."
- GOOD example (22 words): "Crocodiles can hold their breath for over an hour underwater, slowing their heart rate to just 2 or 3 beats per minute."
- BAD example (10 words): "Owls can rotate their heads almost 270 degrees around."
- GOOD example (24 words): "Owls can rotate their heads almost 270 degrees around because they have 14 neck vertebrae — twice as many as humans, who only have 7."
- Always include a specific number/measurement. Always add a comparison or surprising consequence.
- Target spoken length per fact: ~8 seconds. So 22 words is the sweet spot.
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
