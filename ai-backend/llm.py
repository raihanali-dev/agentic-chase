"""Gemini 1.5 Flash wrapper with async offload and crash-proof fallbacks."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FALLBACK = "🤖 [AI Stand-in]: Currently unavailable."
MODEL_NAME = "gemini-1.5-flash"

_api_key = os.getenv("GEMINI_API_KEY", "")
if _api_key and _api_key != "your_gemini_api_key_here":
    genai.configure(api_key=_api_key)


def _model(json_mode: bool = False):
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["generation_config"] = {"response_mime_type": "application/json"}
    return genai.GenerativeModel(MODEL_NAME, **kwargs)


def _sync_generate(prompt: str, json_mode: bool = False) -> str:
    model = _model(json_mode=json_mode)
    resp = model.generate_content(prompt)
    text = (resp.text or "").strip()
    return text or ( "{}" if json_mode else FALLBACK)


async def generate_text(prompt: str, json_mode: bool = False) -> str:
    if not _api_key or _api_key == "your_gemini_api_key_here":
        return "{}" if json_mode else FALLBACK
    try:
        return await asyncio.to_thread(_sync_generate, prompt, json_mode)
    except Exception:
        return "{}" if json_mode else FALLBACK


async def generate_json(prompt: str, default: Optional[dict] = None) -> dict:
    raw = await generate_text(prompt, json_mode=True)
    parsed = _parse_json(raw)
    if parsed is None:
        return default if default is not None else {}
    return parsed


def _parse_json(raw: str) -> Optional[dict]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {"value": data}
        except Exception:
            return None


def _sync_multimodal(parts: list) -> str:
    model = _model()
    resp = model.generate_content(parts)
    return (resp.text or "").strip() or FALLBACK


async def caption_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    if not _api_key or _api_key == "your_gemini_api_key_here":
        return "[image: caption unavailable]"
    try:
        parts = [
            {"mime_type": mime, "data": image_bytes},
            "Describe this WhatsApp image in one concise factual caption. Note any visible text.",
        ]
        return await asyncio.to_thread(_sync_multimodal, parts)
    except Exception:
        return "[image: caption unavailable]"


async def transcribe_audio(audio_bytes: bytes, mime: str = "audio/ogg") -> str:
    if not _api_key or _api_key == "your_gemini_api_key_here":
        return "[audio: transcription unavailable]"
    try:
        parts = [
            {"mime_type": mime, "data": audio_bytes},
            "Transcribe this WhatsApp voice note verbatim. If unclear, note [inaudible].",
        ]
        return await asyncio.to_thread(_sync_multimodal, parts)
    except Exception:
        return "[audio: transcription unavailable]"
