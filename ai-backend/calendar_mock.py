"""Mock / optional ICS Google Calendar reader for Autonomous Stand-In."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Kolkata")


def _demo_events(now: datetime) -> list[dict[str, Any]]:
    start_focus = now.replace(hour=14, minute=0, second=0, microsecond=0)
    end_focus = now.replace(hour=16, minute=0, second=0, microsecond=0)
    start_gym = now.replace(hour=19, minute=0, second=0, microsecond=0)
    end_gym = now.replace(hour=20, minute=0, second=0, microsecond=0)
    return [
        {
            "title": "Deep Work — Agentic Chase",
            "start": start_focus.isoformat(),
            "end": end_focus.isoformat(),
            "busy": True,
        },
        {
            "title": "Gym",
            "start": start_gym.isoformat(),
            "end": end_gym.isoformat(),
            "busy": True,
        },
        {
            "title": "Open office hours",
            "start": now.replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
            "end": now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
            "busy": False,
        },
    ]


def _parse_ics(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    events: list[dict[str, Any]] = []
    blocks = re.split(r"BEGIN:VEVENT", text)
    for block in blocks[1:]:
        summary = re.search(r"SUMMARY:(.+)", block)
        dtstart = re.search(r"DTSTART(?:;[^:]*)?:(\d{8}T\d{6})", block)
        dtend = re.search(r"DTEND(?:;[^:]*)?:(\d{8}T\d{6})", block)
        if not dtstart:
            continue
        def _p(raw: str) -> str:
            return datetime.strptime(raw, "%Y%m%dT%H%M%S").isoformat()
        start = _p(dtstart.group(1))
        end = _p(dtend.group(1)) if dtend else start
        events.append(
            {
                "title": (summary.group(1).strip() if summary else "Busy"),
                "start": start,
                "end": end,
                "busy": True,
            }
        )
    return events


def get_schedule() -> dict[str, Any]:
    now = datetime.now(tz=LOCAL_TZ).replace(tzinfo=None)
    ics = os.getenv("GOOGLE_CALENDAR_ICS_PATH", "").strip()
    events = _parse_ics(Path(ics)) if ics and Path(ics).exists() else _demo_events(now)
    current = None
    for ev in events:
        try:
            s = datetime.fromisoformat(ev["start"])
            e = datetime.fromisoformat(ev["end"])
        except Exception:
            continue
        if s <= now <= e:
            current = ev
            break
    return {
        "now": now.isoformat(),
        "timezone": "Asia/Kolkata",
        "source": "ics" if ics and Path(ics).exists() else "mock",
        "current_event": current,
        "is_busy": bool(current and current.get("busy")),
        "events": events,
    }


def next_free_hint() -> str:
    sched = get_schedule()
    now = datetime.fromisoformat(sched["now"])
    if not sched["is_busy"]:
        return "available now"
    current = sched["current_event"]
    try:
        end = datetime.fromisoformat(current["end"])
        return f"free after {end.strftime('%I:%M %p')}"
    except Exception:
        return "busy until later"
