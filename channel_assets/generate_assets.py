"""Animal Trivia 60s 채널 브랜딩 — 사파리 그린/골드 + 발자국 모티프.

벤치마크:
- NatGeo Wild: 시그니처 노란 박스 + 자연 다큐
- BBC Earth: 시네마틱 + 다크 그린
- The Dodo: 깔끔한 텍스트 + 컬러 액센트

3가지 아트:
- banner_2048x1152.png : 채널 상단 배너 (안전영역 1235x338 안에 균형 배치)
- profile_1080x1080.png : 원형 outline + 발자국 + 채널명 (DRS 스타일)
- watermark_150x150.png : 작은 발자국 + WILD FACTS 라벨
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

CHANNEL_NAME = "Animal Trivia 60s"
TAGLINE_EN = "wild facts in 60 seconds"
WATERMARK_LABEL = "WILD FACTS"

# 사파리 / 자연 다큐 팔레트
PALETTE = {
    "bg_dark": (22, 42, 30),       # 어두운 숲 그린
    "bg_mid": (52, 90, 60),        # 중간 정글 그린
    "bg_light": (175, 145, 95),    # 사파리 모래
    "accent": (240, 200, 70),      # 황금 골드 (NatGeo 노란 시그니처)
    "text_white": (248, 245, 232), # 따뜻한 크림
    "text_dim": (185, 175, 140),   # 흙 베이지
    "dark": (12, 22, 16),          # 거의 검정
}


def find_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for f in candidates:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def safari_gradient(w, h):
    """대각 그라데이션: 어두운 숲 → 정글 → 사파리 모래."""
    img = Image.new("RGB", (w, h), 0)
    pixels = img.load()
    c1 = PALETTE["bg_dark"]
    c2 = PALETTE["bg_mid"]
    c3 = PALETTE["bg_light"]
    diag = w + h
    for y in range(h):
        for x in range(w):
            t = (x + y) / diag
            if t < 0.55:
                u = t / 0.55
                r = int(c1[0] + (c2[0] - c1[0]) * u)
                g = int(c1[1] + (c2[1] - c1[1]) * u)
                b = int(c1[2] + (c2[2] - c1[2]) * u)
            else:
                u = (t - 0.55) / 0.45
                r = int(c2[0] + (c3[0] - c2[0]) * u)
                g = int(c2[1] + (c3[1] - c2[1]) * u)
                b = int(c2[2] + (c3[2] - c2[2]) * u)
            pixels[x, y] = (r, g, b)
    return img


def add_film_grain(img, opacity=18):
    import random
    random.seed(42)
    w, h = img.size
    grain = Image.new("L", (w, h))
    pix = grain.load()
    for y in range(h):
        for x in range(w):
            pix[x, y] = random.randint(80, 175)
    grain_rgba = Image.new("RGBA", (w, h))
    gpix = grain_rgba.load()
    gp = grain.load()
    for y in range(h):
        for x in range(w):
            v = gp[x, y]
            gpix[x, y] = (v, v, v, opacity)
    base = img.convert("RGBA")
    out = Image.alpha_composite(base, grain_rgba)
    return out.convert("RGB")


def draw_pawprint(draw, cx, cy, scale=1.0, color=None, alpha=255):
    """발자국 (paw print) 단순 형태 — 4개 발가락 + 큰 패드."""
    if color is None:
        color = PALETTE["text_white"]
    fill = (*color[:3], alpha) if len(color) == 3 else color

    pad_w = int(80 * scale)
    pad_h = int(70 * scale)
    # 큰 패드 (하단)
    draw.ellipse([cx - pad_w // 2, cy - pad_h // 4,
                  cx + pad_w // 2, cy + int(pad_h * 0.75)], fill=fill)

    # 4개 발가락 (상단)
    toe_r = int(22 * scale)
    toe_offsets = [
        (int(-50 * scale), int(-50 * scale)),
        (int(-18 * scale), int(-65 * scale)),
        (int(18 * scale), int(-65 * scale)),
        (int(50 * scale), int(-50 * scale)),
    ]
    for dx, dy in toe_offsets:
        draw.ellipse([cx + dx - toe_r, cy + dy - toe_r,
                      cx + dx + toe_r, cy + dy + toe_r], fill=fill)


def make_banner():
    W, H = 2048, 1152
    img = safari_gradient(W, H)
    img = add_film_grain(img, opacity=20)
    draw = ImageDraw.Draw(img)

    # 안전영역 1235x338 가운데
    safe_w, safe_h = 1235, 338
    safe_cx = W // 2
    safe_cy = H // 2

    # 폰트 결정 — Animal Trivia 60s
    title_font_size = 130
    title_font = find_font(title_font_size, bold=True)
    title_w = draw.textlength(CHANNEL_NAME, font=title_font)
    while title_w > safe_w * 0.78 and title_font_size > 80:
        title_font_size -= 4
        title_font = find_font(title_font_size, bold=True)
        title_w = draw.textlength(CHANNEL_NAME, font=title_font)

    tag_font_size = 50
    tag_font = find_font(tag_font_size, bold=False)

    # 발자국 그룹 (좌측 + 우측)
    paw_scale = 0.7
    paw_h = int(140 * paw_scale)
    gap_paw_title = 14
    gap_title_tag = 10

    group_h = paw_h + gap_paw_title + title_font_size + gap_title_tag + tag_font_size
    group_top = safe_cy - group_h // 2

    # 발자국 (정중앙 위쪽) — 골드
    paw_cy = group_top + paw_h // 2
    draw_pawprint(draw, cx=safe_cx, cy=paw_cy, scale=paw_scale,
                  color=PALETTE["accent"], alpha=240)

    # 사파리 그라스 모티프 — 좌하단 / 우하단 (안전영역 밖)
    grass_y = H - 50
    for gx in range(50, 280, 30):
        draw.polygon([(gx, grass_y), (gx + 8, grass_y - 80), (gx + 16, grass_y)],
                     fill=(*PALETTE["bg_dark"], 200))
    for gx in range(W - 280, W - 30, 30):
        draw.polygon([(gx, grass_y), (gx + 8, grass_y - 80), (gx + 16, grass_y)],
                     fill=(*PALETTE["bg_dark"], 200))

    # 타이틀 — Animal Trivia 60s
    title_y = group_top + paw_h + gap_paw_title
    title_x = (W - title_w) // 2
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((title_x + 6, title_y + 6), CHANNEL_NAME, font=title_font, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=8))
    img = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    draw = ImageDraw.Draw(img)
    # 굵은 외곽선 + 흰 텍스트
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx == 0 and dy == 0:
                continue
            draw.text((title_x + dx, title_y + dy), CHANNEL_NAME, font=title_font, fill=(0, 0, 0, 230))
    draw.text((title_x, title_y), CHANNEL_NAME, font=title_font, fill=PALETTE["text_white"])

    # 태그라인 (골드)
    tag_w = draw.textlength(TAGLINE_EN, font=tag_font)
    tag_y = title_y + title_font_size + gap_title_tag
    draw.text(((W - tag_w) // 2, tag_y), TAGLINE_EN, font=tag_font, fill=PALETTE["accent"])

    img.save(os.path.join(OUT_DIR, "banner_2048x1152.png"), "PNG", optimize=True)
    print(f"saved: banner_2048x1152.png (사파리 그린/골드 + 발자국, group {group_h}px)")


def make_profile():
    S = 1080
    img = safari_gradient(S, S)
    img = add_film_grain(img, opacity=22)
    draw = ImageDraw.Draw(img)

    # 원형 outline (DRS 스타일)
    margin = 50
    draw.ellipse([margin, margin, S - margin, S - margin],
                 outline=PALETTE["accent"], width=10)

    # 큰 발자국 (가운데 위쪽)
    draw_pawprint(draw, cx=S // 2, cy=int(S * 0.40), scale=3.6,
                  color=PALETTE["text_white"], alpha=255)

    # 채널명 (원 안 하단, 흰 텍스트 + 검정 테두리)
    name_font_size = 78
    name_font = find_font(name_font_size, bold=True)
    name_w = draw.textlength(CHANNEL_NAME, font=name_font)
    safe_w = int(S * 0.70)
    while name_w + 16 > safe_w and name_font_size > 50:
        name_font_size -= 2
        name_font = find_font(name_font_size, bold=True)
        name_w = draw.textlength(CHANNEL_NAME, font=name_font)
    name_y = int(S * 0.72)
    name_x = (S - name_w) // 2
    # shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((name_x + 4, name_y + 4), CHANNEL_NAME, font=name_font, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=6))
    img = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    draw = ImageDraw.Draw(img)
    # 굵은 검정 테두리 + 흰 텍스트
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            if dx == 0 and dy == 0:
                continue
            draw.text((name_x + dx, name_y + dy), CHANNEL_NAME, font=name_font, fill=(0, 0, 0, 255))
    draw.text((name_x, name_y), CHANNEL_NAME, font=name_font, fill=(255, 255, 255, 255))

    img.save(os.path.join(OUT_DIR, "profile_1080x1080.png"), "PNG", optimize=True)
    print(f"saved: profile_1080x1080.png (사파리 + 발자국 + 흰 채널명)")


def make_watermark():
    S = 150
    grad = safari_gradient(S, S)
    grad_rgba = grad.convert("RGBA")

    mask = Image.new("L", (S, S), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([2, 2, S - 2, S - 2], radius=22, fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(grad_rgba, (0, 0), mask)

    odraw = ImageDraw.Draw(out)
    odraw.rounded_rectangle([2, 2, S - 2, S - 2], radius=22,
                            outline=(*PALETTE["accent"], 230), width=2)

    # 발자국 + 라벨 그룹 정 가운데 정렬
    paw_h = 56
    gap = 8
    label_h = 16
    group_h = paw_h + gap + label_h
    group_top = (S - group_h) // 2

    # 발자국 (위)
    paw_cy = group_top + paw_h // 2
    draw_pawprint(odraw, cx=S // 2, cy=paw_cy, scale=0.32,
                  color=PALETTE["text_white"], alpha=240)

    # 라벨 — 흰 글씨 + 검정 테두리
    label_font = find_font(16, bold=True)
    label_w = odraw.textlength(WATERMARK_LABEL, font=label_font)
    label_y = group_top + paw_h + gap
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            odraw.text(((S - label_w) // 2 + dx, label_y + dy), WATERMARK_LABEL,
                       font=label_font, fill=(0, 0, 0, 240))
    odraw.text(((S - label_w) // 2, label_y), WATERMARK_LABEL,
               font=label_font, fill=(255, 255, 255, 255))

    out.save(os.path.join(OUT_DIR, "watermark_150x150.png"), "PNG", optimize=True)
    print(f"saved: watermark_150x150.png (발자국 + WILD FACTS)")


if __name__ == "__main__":
    make_banner()
    make_profile()
    make_watermark()
    print("\nAnimal Trivia 60s — 사파리 그린/골드 톤 done.")
