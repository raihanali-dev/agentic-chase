"""Risk Classifier — high-risk actions pause LangGraph for human confirmation."""

from __future__ import annotations

import re
from typing import Any

HIGH_PATTERNS = [
    r"\bbroadcast\b",
    r"\bmass\s+(text|message|send)\b",
    r"\bdelete\s+(all|chat|history|group)\b",
    r"\bblock\s+everyone\b",
    r"\bspam\b",
    r"\btransfer\s+money\b",
    r"\bsend\s+to\s+all\b",
    r"\bleave\s+(the\s+)?group\b",
    r"\bforward\s+to\s+everyone\b",
    r"\bwipe\b",
    r"\bdrop\s+table\b",
]

MEDIUM_PATTERNS = [
    r"\breject\s+all\s+calls\b",
    r"\bauto-?reply\s+everyone\b",
    r"\bstand[- ]?in\b",
]


def classify_risk(query: str, intended_action: str = "") -> dict[str, Any]:
    blob = f"{query}\n{intended_action}".lower()
    for pat in HIGH_PATTERNS:
        if re.search(pat, blob):
            return {
                "level": "high",
                "reason": f"Matched high-risk pattern: {pat}",
                "requires_hitl": True,
            }
    for pat in MEDIUM_PATTERNS:
        if re.search(pat, blob):
            return {
                "level": "medium",
                "reason": f"Matched medium-risk pattern: {pat}",
                "requires_hitl": False,
            }
    return {"level": "low", "reason": "No destructive or broadcast intent detected", "requires_hitl": False}
