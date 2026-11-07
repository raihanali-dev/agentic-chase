"""Crafty Edge — ingestion pipeline: PII redaction, media understanding, temporal chunking, index.

Processes uploaded .txt WhatsApp exports and live WebSocket payloads from the WA bridge.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import chroma_store
from llm import caption_image, generate_json, transcribe_audio
from models import Chat, Message, Persona, Project

# --- PII ---
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_OTP = re.compile(r"\b(?:otp|password|pin)\s*[:=]?\s*\d{4,8}\b", re.I)

WA_LINE = re.compile(
    r"^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\]?\s*[-–]?\s*([^:]+):\s*(.*)$"
)
ISO_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)\s+[|-]\s+([^:]+):\s*(.*)$")


def redact_pii(text: str) -> str:
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _CARD.sub("[REDACTED_CARD]", text)
    text = _OTP.sub("[REDACTED_SECRET]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    return text


def _parse_ts(date_s: str, time_s: str) -> datetime:
    time_s = time_s.strip()
    date_s = date_s.strip().replace("-", "/")
    candidates = [
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%y %I:%M:%S %p",
        "%d/%m/%y %I:%M %p",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%y %H:%M",
    ]
    blob = f"{date_s} {time_s}"
    for fmt in candidates:
        try:
            return datetime.strptime(blob, fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def parse_whatsapp_export(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    for line in raw.splitlines():
        line = line.rstrip("\n")
        m = WA_LINE.match(line)
        iso = ISO_LINE.match(line)
        if m:
            if current:
                rows.append(current)
            current = {
                "ts": _parse_ts(m.group(1), m.group(2)),
                "sender": m.group(3).strip(),
                "body": m.group(4),
            }
        elif iso:
            if current:
                rows.append(current)
            ts_raw = iso.group(1).replace(" ", "T")
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                ts = datetime.utcnow()
            current = {"ts": ts, "sender": iso.group(2).strip(), "body": iso.group(3)}
        elif current:
            current["body"] += "\n" + line
    if current:
        rows.append(current)
    return rows


def temporal_chunks(rows: list[dict[str, Any]], gap_minutes: int = 60) -> list[dict[str, Any]]:
    """Split a linear log whenever silence exceeds `gap_minutes`."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: r["ts"])
    buckets: list[list[dict[str, Any]]] = [[ordered[0]]]
    gap = timedelta(minutes=gap_minutes)
    for row in ordered[1:]:
        prev = buckets[-1][-1]
        if row["ts"] - prev["ts"] >= gap:
            buckets.append([row])
        else:
            buckets[-1].append(row)

    chunks = []
    for bucket in buckets:
        participants = sorted({r["sender"] for r in bucket})
        lines = []
        for r in bucket:
            stamp = r["ts"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{stamp}] {r['sender']}: {r['body']}")
        text = "\n".join(lines)
        chunks.append(
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "start_ts": bucket[0]["ts"].isoformat(),
                "end_ts": bucket[-1]["ts"].isoformat(),
                "participants": ",".join(participants),
            }
        )
    return chunks


async def enrich_media_row(row: dict[str, Any]) -> dict[str, Any]:
    media = row.get("media")
    if not media:
        return row
    kind = media.get("type")
    data: bytes = media.get("bytes") or b""
    mime = media.get("mime") or "application/octet-stream"
    if kind == "image" and data:
        caption = await caption_image(data, mime)
        row["body"] = f"[IMAGE] {caption}"
        row["media_type"] = "image"
        row["media_caption"] = caption
    elif kind == "audio" and data:
        transcript = await transcribe_audio(data, mime)
        row["body"] = f"[AUDIO] {transcript}"
        row["media_type"] = "audio"
        row["media_caption"] = transcript
    return row


def _default_persona(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "vocabulary": [],
        "signature_phrases": [],
        "emojis": [],
        "active_hours": [],
        "tone": "unknown",
        "formality": "mixed",
        "humor": "unknown",
        "summary": "Not enough signal yet.",
    }


async def extract_persona_profile(participant: str, texts: list[str]) -> dict[str, Any]:
    sample = "\n".join(texts[-80:])[:8000]
    data = await generate_json(
        f"""You extract a grounded WhatsApp persona JSON. Use ONLY the chat sample.
Participant: {participant}

Sample:
{sample}

Return JSON with keys:
name, vocabulary (array of distinctive words), signature_phrases (array),
emojis (array of frequently used emojis), active_hours (array of hours 0-23 as ints),
tone, formality (casual|mixed|formal), humor (dry|playful|roast|none|unknown),
summary (2 sentences).
""",
        default=_default_persona(participant),
    )
    data.setdefault("name", participant)
    return data


async def ingest_rows(
    db: AsyncSession,
    *,
    project_id: str,
    chat_id: str,
    rows: list[dict[str, Any]],
    rebuild_personas: bool = True,
) -> dict[str, Any]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        row = dict(row)
        if "media" in row:
            row = await enrich_media_row(row)
        body = redact_pii(str(row.get("body") or ""))
        ts = row.get("ts") or datetime.utcnow()
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", ""))
            except ValueError:
                ts = datetime.utcnow()
        sender = str(row.get("sender") or "unknown")
        cleaned.append(
            {
                "ts": ts,
                "sender": sender,
                "body": body,
                "media_type": row.get("media_type") or "text",
                "media_caption": redact_pii(str(row.get("media_caption") or "")),
            }
        )

    for item in cleaned:
        db.add(
            Message(
                project_id=project_id,
                chat_id=chat_id,
                sender=item["sender"],
                body=item["body"],
                media_type=item["media_type"],
                media_caption=item["media_caption"],
                ts=item["ts"],
            )
        )
    await db.flush()

    chunks = temporal_chunks(cleaned, gap_minutes=60)
    indexed = chroma_store.upsert_chunks(project_id=project_id, chat_id=chat_id, chunks=chunks)

    personas_updated = 0
    if rebuild_personas:
        by_sender: dict[str, list[str]] = {}
        for item in cleaned:
            by_sender.setdefault(item["sender"], []).append(item["body"])
        for sender, texts in by_sender.items():
            profile = await extract_persona_profile(sender, texts)
            existing = await db.scalar(
                select(Persona).where(
                    Persona.chat_id == chat_id,
                    Persona.participant == sender,
                )
            )
            import json as _json

            blob = _json.dumps(profile, ensure_ascii=False)
            if existing:
                existing.profile_json = blob
            else:
                db.add(
                    Persona(
                        project_id=project_id,
                        chat_id=chat_id,
                        participant=sender,
                        profile_json=blob,
                    )
                )
            personas_updated += 1

    await db.commit()
    return {
        "messages": len(cleaned),
        "chunks_indexed": indexed,
        "personas_updated": personas_updated,
        "project_id": project_id,
        "chat_id": chat_id,
    }


async def ingest_txt_export(
    db: AsyncSession,
    *,
    project_id: str,
    chat_id: str,
    raw_text: str,
) -> dict[str, Any]:
    rows = parse_whatsapp_export(raw_text)
    return await ingest_rows(db, project_id=project_id, chat_id=chat_id, rows=rows)


async def ingest_live_event(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """Live WA bridge event: resolve/create project+chat, then index one message."""
    jid = payload.get("wa_jid") or payload.get("chat_jid") or "unknown"
    chat_type = "GROUP" if payload.get("is_group") else "DIRECT"
    title = payload.get("chat_title") or jid

    project_id = payload.get("project_id")
    if not project_id:
        project = await db.scalar(select(Project).order_by(Project.created_at.asc()))
        if not project:
            project = Project(name="Inbox", description="Auto-created from WhatsApp live events")
            db.add(project)
            await db.flush()
        project_id = project.id

    chat = await db.scalar(select(Chat).where(Chat.wa_jid == jid, Chat.project_id == project_id))
    if not chat:
        chat = Chat(project_id=project_id, title=title, chat_type=chat_type, wa_jid=jid)
        db.add(chat)
        await db.flush()

    rows = [
        {
            "ts": payload.get("ts") or datetime.utcnow().isoformat(),
            "sender": payload.get("sender") or "unknown",
            "body": payload.get("body") or "",
            "media": payload.get("media"),
        }
    ]
    return await ingest_rows(
        db,
        project_id=chat.project_id,
        chat_id=chat.id,
        rows=rows,
        rebuild_personas=bool(payload.get("rebuild_personas", False)),
    )
