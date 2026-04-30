"""edge-tts로 영문 내레이션 생성.

각 라인별 mp3 파일 + duration 측정해서 자막 시간차 계산에 사용.
"""
import asyncio
import logging
import os
import wave

from config import TTS_PITCH, TTS_RATE, TTS_VOICE

log = logging.getLogger("animalbot.tts")


async def _synth_one(text: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await communicate.save(output_path)


def synth(text: str, output_path: str) -> str:
    """텍스트 → mp3 파일 저장. 경로 반환."""
    asyncio.run(_synth_one(text, output_path))
    return output_path


def get_duration(audio_path: str) -> float:
    """mp3/wav 길이(초) 측정. moviepy AudioFileClip 사용."""
    from moviepy.editor import AudioFileClip
    with AudioFileClip(audio_path) as a:
        return float(a.duration)


def synth_lines(lines: list, output_dir: str, prefix: str = "tts") -> list:
    """리스트의 각 라인을 별도 mp3로 저장.

    반환: [{"text": ..., "path": ..., "duration": ...}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    out = []
    for i, text in enumerate(lines):
        path = os.path.join(output_dir, f"{prefix}_{i:02d}.mp3")
        synth(text, path)
        dur = get_duration(path)
        out.append({"text": text, "path": path, "duration": dur})
        log.info(f"tts[{i}] {dur:.2f}s — {text[:60]}")
    return out
