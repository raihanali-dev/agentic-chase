"""LangGraph multi-agent workflows: Analyzer, Roaster, Reply Giver, Stand-In + HITL pause."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

import calendar_mock
import chroma_store
from agents.risk import classify_risk
from llm import FALLBACK, generate_text


class AgentState(TypedDict, total=False):
    project_id: str
    chat_id: str
    query: str
    agent: str
    persona_json: str
    context: str
    citations: list
    risk_level: str
    risk_reason: str
    requires_hitl: bool
    result: str
    structured: dict
    pending_summary: str


def _format_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "(no isolated memory for this chat)"
    parts = []
    for i, hit in enumerate(hits, 1):
        meta = hit.get("metadata") or {}
        parts.append(
            f"[cite:{i} chat_id={meta.get('chat_id')} {meta.get('start_ts')}→{meta.get('end_ts')}]\n{hit.get('text','')}"
        )
    return "\n\n".join(parts)


async def retrieve_node(state: AgentState) -> AgentState:
    hits = chroma_store.query_isolated(
        project_id=state["project_id"],
        chat_id=state["chat_id"],
        query=state.get("query") or "conversation summary",
        n_results=8,
    )
    return {
        **state,
        "context": _format_context(hits),
        "citations": [
            {
                "id": h.get("id"),
                "start_ts": (h.get("metadata") or {}).get("start_ts"),
                "end_ts": (h.get("metadata") or {}).get("end_ts"),
                "excerpt": (h.get("text") or "")[:280],
            }
            for h in hits
        ],
    }


async def risk_node(state: AgentState) -> AgentState:
    verdict = classify_risk(state.get("query") or "", state.get("agent") or "")
    return {
        **state,
        "risk_level": verdict["level"],
        "risk_reason": verdict["reason"],
        "requires_hitl": bool(verdict["requires_hitl"]),
        "pending_summary": f"{state.get('agent')} wants to run: {state.get('query')}",
    }


def route_after_risk(state: AgentState) -> str:
    if state.get("requires_hitl"):
        return "hitl"
    agent = (state.get("agent") or "analyze").lower()
    if agent in ("roast", "roaster"):
        return "roast"
    if agent in ("reply", "reply_giver"):
        return "reply"
    if agent in ("stand_in", "stand-in", "standin"):
        return "stand_in"
    return "analyze"


async def hitl_node(state: AgentState) -> AgentState:
    return {
        **state,
        "result": "PAUSED_FOR_HUMAN",
        "structured": {
            "status": "paused",
            "message": "High-risk action intercepted. Confirm in the dashboard to dispatch.",
        },
    }


async def analyze_node(state: AgentState) -> AgentState:
    prompt = f"""You are Deep Analyzer for Agentic Chase. Use ONLY the isolated chat context.
Never mix in other chats. Cite [cite:N] when making claims.

User question: {state.get('query')}

Isolated context:
{state.get('context')}

Return a markdown briefing with:
1) Sentiment timeline
2) Key topics
3) Relationship dynamics
4) Risks / unresolved threads
5) Citations
"""
    text = await generate_text(prompt)
    return {**state, "result": text or FALLBACK}


async def roast_node(state: AgentState) -> AgentState:
    prompt = f"""You are Persona Roaster. Roast using ONLY cited lines from this isolated chat.
Rules:
- Every roast beat must include a [cite:N] reference.
- If evidence is missing, say you cannot roast that claim.
- Keep it witty, not hateful. No slurs.

Persona JSON:
{state.get('persona_json') or '{}'}

Isolated context:
{state.get('context')}

Roast request: {state.get('query')}
"""
    text = await generate_text(prompt)
    return {**state, "result": text or FALLBACK}


async def reply_node(state: AgentState) -> AgentState:
    prompt = f"""You are Reply Giver. Draft 3 tone-matched WhatsApp replies.
Match vocabulary, emoji density, and formality from the persona + isolated context.
Label them Casual / Mirror / Diplomatic.

Persona JSON:
{state.get('persona_json') or '{}'}

Isolated context:
{state.get('context')}

Draft a reply to: {state.get('query')}
"""
    text = await generate_text(prompt)
    return {**state, "result": text or FALLBACK}


async def stand_in_node(state: AgentState) -> AgentState:
    schedule = calendar_mock.get_schedule()
    hint = calendar_mock.next_free_hint()
    prompt = f"""You are Autonomous Stand-In. Focus Mode is ON.
Write ONE short WhatsApp proxy reply (max 2 sentences) as the user.
If busy, decline politely and mention when they are free ({hint}).
Do not invent commitments. Do not leak private calendar titles unless needed.

Calendar JSON:
{json.dumps(schedule, default=str)}

Persona JSON:
{state.get('persona_json') or '{}'}

Isolated context:
{state.get('context')}

Incoming message: {state.get('query')}
"""
    text = await generate_text(prompt)
    if text == FALLBACK:
        text = f"Hey — I am in focus mode and {hint}. I will reply properly later."
    return {**state, "result": text, "structured": {"schedule": schedule, "free_hint": hint}}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("risk", risk_node)
    g.add_node("hitl", hitl_node)
    g.add_node("analyze", analyze_node)
    g.add_node("roast", roast_node)
    g.add_node("reply", reply_node)
    g.add_node("stand_in", stand_in_node)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "risk")
    g.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "hitl": "hitl",
            "analyze": "analyze",
            "roast": "roast",
            "reply": "reply",
            "stand_in": "stand_in",
        },
    )
    g.add_edge("hitl", END)
    g.add_edge("analyze", END)
    g.add_edge("roast", END)
    g.add_edge("reply", END)
    g.add_edge("stand_in", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_agent(
    *,
    project_id: str,
    chat_id: str,
    query: str,
    agent: str = "analyze",
    persona_json: str = "{}",
) -> dict[str, Any]:
    graph = get_graph()
    initial: AgentState = {
        "project_id": project_id,
        "chat_id": chat_id,
        "query": query,
        "agent": agent,
        "persona_json": persona_json,
    }
    try:
        final = await graph.ainvoke(initial)
    except Exception:
        return {
            "result": FALLBACK,
            "risk_level": "low",
            "requires_hitl": False,
            "citations": [],
            "structured": {},
        }
    return {
        "result": final.get("result") or FALLBACK,
        "risk_level": final.get("risk_level") or "low",
        "risk_reason": final.get("risk_reason") or "",
        "requires_hitl": bool(final.get("requires_hitl")),
        "pending_summary": final.get("pending_summary") or "",
        "citations": final.get("citations") or [],
        "context_preview": (final.get("context") or "")[:500],
        "structured": final.get("structured") or {},
        "project_id": project_id,
        "chat_id": chat_id,
        "agent": agent,
    }
