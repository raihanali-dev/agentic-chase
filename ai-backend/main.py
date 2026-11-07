"""Agentic Chase AI backend — FastAPI, CORS, agents, HITL, Crafty Edge."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agents.graph import run_agent
from calendar_mock import get_schedule
from crafty_edge_service import ingest_live_event, ingest_txt_export
from database import AsyncSessionLocal, get_db, init_db
from llm import generate_json
from models import Chat, Directive, Message, PendingAction, Persona, Project, Setting


def heuristic_directive(nl: str) -> dict:
    """Safe parser when Gemini is missing — covers the hackathon call-after-hours example."""
    lower = nl.lower()
    trigger = "call" if "call" in lower else "message"
    after = None
    if "after 8" in lower or "after 8pm" in lower or "after 8 pm" in lower:
        after = 20
    elif "after 10" in lower or "after 10pm" in lower:
        after = 22
    action_type = "reject_and_text" if "reject" in lower else "text"
    msg = "I am offline for the day."
    quoted = None
    if "'" in nl:
        quoted = nl.split("'")[1] if nl.count("'") >= 2 else None
    if '"' in nl:
        quoted = nl.split('"')[1] if nl.count('"') >= 2 else quoted
    if quoted:
        msg = quoted
    return {
        "trigger": trigger,
        "condition": {
            "after_hour": after,
            "before_hour": None,
            "weekdays_only": False,
            "contains": None,
            "chat_type": "any",
        },
        "action": {"type": action_type if trigger == "call" else "text", "message": msg},
    }

DIRECTIVE_SCHEMA_HINT = """
Return JSON:
{
  "trigger": "call" | "message" | "mention" | "media",
  "condition": {
    "after_hour": 0-23 or null,
    "before_hour": 0-23 or null,
    "weekdays_only": boolean,
    "contains": string or null,
    "chat_type": "any" | "DIRECT" | "GROUP"
  },
  "action": {
    "type": "reject_and_text" | "text" | "ignore" | "notify_dashboard",
    "message": string
  }
}
Example: If anyone WhatsApp calls me after 8 PM, reject it and text them 'I am offline for the day.'
→ trigger=call, condition.after_hour=20, action.type=reject_and_text
"""


class ConnectionHub:
    def __init__(self) -> None:
        self.clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.clients:
            self.clients.remove(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = ConnectionHub()


async def _get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    row = await db.get(Setting, key)
    return row.value if row else default


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    await db.commit()


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count(Project.id)))
        if count:
            return
        project = Project(
            name="Hackathon Demo",
            description="Isolated workspace for Agentic Chase — group vs DMs never mix.",
        )
        db.add(project)
        await db.flush()
        dm = Chat(project_id=project.id, title="Aanya (DM)", chat_type="DIRECT", wa_jid="demo-aanya")
        grp = Chat(project_id=project.id, title="Squad Group", chat_type="GROUP", wa_jid="demo-squad")
        db.add_all([dm, grp])
        await db.flush()
        sample = """12/11/2024, 9:12 PM - Aanya: yo are you coming to the cafe?? 😭
12/11/2024, 9:14 PM - You: stuck in a meeting, 20 mins
12/11/2024, 9:15 PM - Aanya: okok bring the charger 🔌
12/11/2024, 11:40 PM - Aanya: also please don't pick calls after 10 I panic lol
13/11/2024, 10:02 AM - Aanya: morninggg ☕ we still on for the deck?
13/11/2024, 10:05 AM - You: yes, dropping comments by noon
"""
        group_sample = """12/11/2024, 8:01 PM - Ravi: WHO ate the last samosa
12/11/2024, 8:02 PM - Meera: not me 😇
12/11/2024, 8:03 PM - You: it was ravi we all saw
12/11/2024, 8:04 PM - Ravi: betrayal. broadcast this to the whole college
"""
        await ingest_txt_export(db, project_id=project.id, chat_id=dm.id, raw_text=sample)
        await ingest_txt_export(db, project_id=project.id, chat_id=grp.id, raw_text=group_sample)
        db.add(Setting(key="focus_mode", value="off"))
        db.add(
            Directive(
                project_id=project.id,
                natural_language="If anyone WhatsApp calls me after 8 PM, reject it and text them 'I am offline for the day.'",
                trigger="call",
                condition_json=json.dumps(
                    {
                        "after_hour": 20,
                        "before_hour": None,
                        "weekdays_only": False,
                        "contains": None,
                        "chat_type": "any",
                    }
                ),
                action_json=json.dumps({"type": "reject_and_text", "message": "I am offline for the day."}),
                enabled=True,
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_if_empty()
    yield


app = FastAPI(title="Agentic Chase AI Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- schemas ----------
class ProjectIn(BaseModel):
    name: str
    description: str = ""


class ChatIn(BaseModel):
    title: str
    chat_type: str = "DIRECT"
    wa_jid: Optional[str] = None


class DirectiveParseIn(BaseModel):
    natural_language: str
    project_id: Optional[str] = None


class AgentRunIn(BaseModel):
    project_id: str
    chat_id: str
    query: str
    agent: str = "analyze"
    participant: Optional[str] = None


class LiveEventIn(BaseModel):
    wa_jid: str
    chat_title: Optional[str] = None
    is_group: bool = False
    sender: str
    body: str = ""
    ts: Optional[str] = None
    project_id: Optional[str] = None
    rebuild_personas: bool = False


class FocusIn(BaseModel):
    enabled: bool


class DispatchIn(BaseModel):
    wa_jid: Optional[str] = None
    message: Optional[str] = None


# ---------- health ----------
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "ai-backend", "time": datetime.utcnow().isoformat()}


# ---------- projects / chats ----------
@app.get("/api/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Project).options(selectinload(Project.chats)))).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
            "chats": [
                {"id": c.id, "title": c.title, "chat_type": c.chat_type, "wa_jid": c.wa_jid}
                for c in p.chats
            ],
        }
        for p in rows
    ]


@app.post("/api/projects")
async def create_project(body: ProjectIn, db: AsyncSession = Depends(get_db)):
    p = Project(name=body.name, description=body.description)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "name": p.name, "description": p.description}


@app.post("/api/projects/{project_id}/chats")
async def create_chat(project_id: str, body: ChatIn, db: AsyncSession = Depends(get_db)):
    p = await db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    chat_type = body.chat_type.upper()
    if chat_type not in ("GROUP", "DIRECT"):
        raise HTTPException(400, "chat_type must be GROUP or DIRECT")
    c = Chat(project_id=project_id, title=body.title, chat_type=chat_type, wa_jid=body.wa_jid)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return {"id": c.id, "title": c.title, "chat_type": c.chat_type, "project_id": c.project_id}


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str, db: AsyncSession = Depends(get_db)):
    c = await db.get(Chat, chat_id)
    if not c:
        raise HTTPException(404, "chat not found")
    msgs = (
        await db.scalars(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.ts.asc()).limit(400)
        )
    ).all()
    return {
        "id": c.id,
        "project_id": c.project_id,
        "title": c.title,
        "chat_type": c.chat_type,
        "wa_jid": c.wa_jid,
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "body": m.body,
                "media_type": m.media_type,
                "ts": m.ts.isoformat(),
            }
            for m in msgs
        ],
    }


# ---------- directives (prompt-to-action) ----------
@app.post("/api/directives/parse")
async def parse_directive(body: DirectiveParseIn, db: AsyncSession = Depends(get_db)):
    fallback = heuristic_directive(body.natural_language)
    parsed = await generate_json(
        f"Convert this WhatsApp automation rule into JSON.\n{DIRECTIVE_SCHEMA_HINT}\nRule: {body.natural_language}",
        default=fallback,
    )
    if not parsed.get("trigger"):
        parsed = fallback
    if parsed.get("trigger") == "call" and not (parsed.get("action") or {}).get("type"):
        parsed = fallback
    trigger = str(parsed.get("trigger") or "message")
    condition = parsed.get("condition") or {}
    action = parsed.get("action") or {}
    d = Directive(
        project_id=body.project_id,
        natural_language=body.natural_language,
        trigger=trigger,
        condition_json=json.dumps(condition),
        action_json=json.dumps(action),
        enabled=True,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return _directive_out(d)


@app.get("/api/directives")
async def list_directives(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Directive).order_by(Directive.created_at.desc()))).all()
    return [_directive_out(d) for d in rows]


@app.get("/api/directives/active")
async def active_directives(db: AsyncSession = Depends(get_db)):
    """Polled by the Node bridge — execute instantly, no LangGraph."""
    rows = (await db.scalars(select(Directive).where(Directive.enabled.is_(True)))).all()
    return [_directive_out(d) for d in rows]


@app.post("/api/directives/{directive_id}/toggle")
async def toggle_directive(directive_id: str, db: AsyncSession = Depends(get_db)):
    d = await db.get(Directive, directive_id)
    if not d:
        raise HTTPException(404, "directive not found")
    d.enabled = not d.enabled
    await db.commit()
    return _directive_out(d)


def _directive_out(d: Directive) -> dict[str, Any]:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "natural_language": d.natural_language,
        "trigger": d.trigger,
        "condition": json.loads(d.condition_json or "{}"),
        "action": json.loads(d.action_json or "{}"),
        "enabled": d.enabled,
        "created_at": d.created_at.isoformat(),
    }


# ---------- ingest ----------
@app.post("/api/ingest/upload")
async def ingest_upload(
    project_id: str = Form(...),
    chat_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    chat = await db.get(Chat, chat_id)
    if not chat or chat.project_id != project_id:
        raise HTTPException(400, "chat does not belong to project")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    result = await ingest_txt_export(db, project_id=project_id, chat_id=chat_id, raw_text=raw)
    return result


@app.post("/api/ingest/live")
async def ingest_live(body: LiveEventIn, db: AsyncSession = Depends(get_db)):
    return await ingest_live_event(db, body.model_dump())


# ---------- personas ----------
@app.get("/api/personas")
async def list_personas(chat_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(Persona)
    if chat_id:
        q = q.where(Persona.chat_id == chat_id)
    rows = (await db.scalars(q)).all()
    out = []
    for p in rows:
        try:
            profile = json.loads(p.profile_json or "{}")
        except json.JSONDecodeError:
            profile = {}
        out.append(
            {
                "id": p.id,
                "project_id": p.project_id,
                "chat_id": p.chat_id,
                "participant": p.participant,
                "profile": profile,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
        )
    return out


# ---------- agents ----------
@app.post("/api/agents/run")
async def agents_run(body: AgentRunIn, db: AsyncSession = Depends(get_db)):
    chat = await db.get(Chat, body.chat_id)
    if not chat or chat.project_id != body.project_id:
        raise HTTPException(400, "chat/project mismatch — refusing unscoped memory")
    persona_json = "{}"
    if body.participant:
        persona = await db.scalar(
            select(Persona).where(Persona.chat_id == body.chat_id, Persona.participant == body.participant)
        )
        if persona:
            persona_json = persona.profile_json
    else:
        persona = await db.scalar(select(Persona).where(Persona.chat_id == body.chat_id))
        if persona:
            persona_json = persona.profile_json

    result = await run_agent(
        project_id=body.project_id,
        chat_id=body.chat_id,
        query=body.query,
        agent=body.agent,
        persona_json=persona_json,
    )

    if result.get("requires_hitl"):
        pending = PendingAction(
            project_id=body.project_id,
            chat_id=body.chat_id,
            risk_level=result.get("risk_level") or "high",
            summary=result.get("pending_summary") or body.query,
            payload_json=json.dumps(
                {
                    "agent": body.agent,
                    "query": body.query,
                    "wa_jid": chat.wa_jid,
                    "draft": result.get("result"),
                }
            ),
            status="pending",
        )
        db.add(pending)
        await db.commit()
        await db.refresh(pending)
        await hub.broadcast(
            {
                "type": "hitl_alert",
                "id": pending.id,
                "summary": pending.summary,
                "risk_level": pending.risk_level,
                "payload": json.loads(pending.payload_json),
            }
        )
        result["pending_action_id"] = pending.id
        result["status"] = "paused"
    return result


# ---------- HITL ----------
@app.get("/api/alerts/pending")
async def pending_alerts(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(PendingAction).where(PendingAction.status == "pending").order_by(PendingAction.created_at.desc())
        )
    ).all()
    return [
        {
            "id": a.id,
            "summary": a.summary,
            "risk_level": a.risk_level,
            "payload": json.loads(a.payload_json or "{}"),
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


@app.post("/api/alerts/{alert_id}/confirm")
async def confirm_alert(alert_id: str, body: DispatchIn | None = None, db: AsyncSession = Depends(get_db)):
    a = await db.get(PendingAction, alert_id)
    if not a or a.status != "pending":
        raise HTTPException(404, "pending action not found")
    a.status = "confirmed"
    payload = json.loads(a.payload_json or "{}")
    await db.commit()
    dispatch = {
        "confirmed": True,
        "wa_jid": (body.wa_jid if body else None) or payload.get("wa_jid"),
        "message": (body.message if body else None) or payload.get("query") or payload.get("draft"),
        "alert_id": a.id,
    }
    await hub.broadcast({"type": "hitl_confirmed", **dispatch})
    return {"ok": True, "dispatch": dispatch, "note": "Node bridge should POST /send with this payload"}


@app.post("/api/alerts/{alert_id}/reject")
async def reject_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    a = await db.get(PendingAction, alert_id)
    if not a or a.status != "pending":
        raise HTTPException(404, "pending action not found")
    a.status = "rejected"
    await db.commit()
    await hub.broadcast({"type": "hitl_rejected", "id": a.id})
    return {"ok": True, "status": "rejected"}


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)


# ---------- focus / calendar / stats ----------
@app.get("/api/focus-mode")
async def get_focus(db: AsyncSession = Depends(get_db)):
    val = await _get_setting(db, "focus_mode", "off")
    return {"enabled": val == "on"}


@app.post("/api/focus-mode")
async def set_focus(body: FocusIn, db: AsyncSession = Depends(get_db)):
    await _set_setting(db, "focus_mode", "on" if body.enabled else "off")
    return {"enabled": body.enabled}


@app.get("/api/calendar")
async def calendar():
    return get_schedule()


@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    projects = await db.scalar(select(func.count(Project.id)))
    chats = await db.scalar(select(func.count(Chat.id)))
    messages = await db.scalar(select(func.count(Message.id)))
    directives = await db.scalar(select(func.count(Directive.id)))
    pending = await db.scalar(select(func.count(PendingAction.id)).where(PendingAction.status == "pending"))
    focus = await _get_setting(db, "focus_mode", "off")
    return {
        "projects": projects or 0,
        "chats": chats or 0,
        "messages": messages or 0,
        "directives": directives or 0,
        "pending_alerts": pending or 0,
        "focus_mode": focus == "on",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("AI_BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("AI_BACKEND_PORT", "8000")),
        reload=True,
    )
