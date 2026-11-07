"""ChromaDB with mandatory project_id + chat_id isolation (zero-leakage memory)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
if not Path(_CHROMA_PATH).is_absolute():
    _CHROMA_PATH = str(Path(__file__).resolve().parent / _CHROMA_PATH)

Path(_CHROMA_PATH).mkdir(parents=True, exist_ok=True)

_client = chromadb.PersistentClient(path=_CHROMA_PATH, settings=Settings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(
    name="agentic_chase_chunks",
    metadata={"hnsw:space": "cosine"},
)


def isolation_where(project_id: str, chat_id: str) -> dict[str, Any]:
    """Strict metadata filter — never query without both IDs."""
    return {"$and": [{"project_id": str(project_id)}, {"chat_id": str(chat_id)}]}


def upsert_chunks(
    *,
    project_id: str,
    chat_id: str,
    chunks: list[dict[str, Any]],
) -> int:
    if not chunks:
        return 0
    ids, docs, metas = [], [], []
    for chunk in chunks:
        ids.append(str(chunk["id"]))
        docs.append(str(chunk["text"]))
        metas.append(
            {
                "project_id": str(project_id),
                "chat_id": str(chat_id),
                "start_ts": str(chunk.get("start_ts", "")),
                "end_ts": str(chunk.get("end_ts", "")),
                "participants": str(chunk.get("participants", "")),
            }
        )
    _collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def query_isolated(
    *,
    project_id: str,
    chat_id: str,
    query: str,
    n_results: int = 8,
) -> list[dict[str, Any]]:
    if not project_id or not chat_id:
        return []
    try:
        result = _collection.query(
            query_texts=[query],
            n_results=n_results,
            where=isolation_where(project_id, chat_id),
        )
    except Exception:
        return []
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    out = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        if str(meta.get("project_id")) != str(project_id) or str(meta.get("chat_id")) != str(chat_id):
            continue
        out.append({"id": ids[i] if i < len(ids) else "", "text": doc, "metadata": meta})
    return out


def count_for_chat(project_id: str, chat_id: str) -> int:
    try:
        got = _collection.get(where=isolation_where(project_id, chat_id), include=[])
        return len(got.get("ids") or [])
    except Exception:
        return 0
