# 🕵️‍♂️ Agentic Chase

**A Local-First, Multi-Agent WhatsApp Conversational Intelligence & Automation Platform.**

Agentic Chase bridges the live WhatsApp network with an advanced AI ecosystem. It acts as a secure, autonomous proxy and analytical engine for digital communications, prioritizing strict data privacy, contextual memory, and human-in-the-loop execution safety. Built for stability and zero cloud-compute costs using a fully free-tier local stack.

---

## ✨ Core Features

*   **Prompt-to-Action Automation:** Set natural language background rules (e.g., *"If I get a call after 8 PM, reject it and text them I'm offline"*). The Node.js bridge listens and executes instantly without heavy LLM overhead.
*   **Zero-Leakage Context Isolation:** Strict relational (SQLite) and semantic vector (ChromaDB) data fencing. Group chats and 1-to-1 direct messages are rigorously isolated—an agent summarizing a private chat cannot access group memory.
*   **Crafty Edge Workflow Engine:** Processes chat exports and live WebSocket data. Transcribes audio notes via Gemini Audio, analyzes images via Gemini Vision, redacts PII, and chunks data by temporal gaps before vectorizing.
*   **Dynamic Persona Profiling:** Analyzes historical messages to extract vocabulary quirks, emoji preferences, active hours, and humor styles, automatically mapping group dynamics and roles.
*   **Human-in-the-Loop Safety Gate:** High-risk actions (mass broadcasts, destructive commands) pause the LangGraph state and push a synchronous alert to the Next.js dashboard, requiring explicit human confirmation before the Node bridge dispatches.

## 🧠 The Multi-Agent Ecosystem (LangGraph)

Instead of a single generic AI, Agentic Chase routes intents to specialized AI personalities:
1.  **The Autonomous Stand-In:** Reads Google Calendar availability and proxies for the user when "Focus Mode" is toggled ON.
2.  **The Deep Analyzer:** Computes project/chat-level analytics, sentiment trends, and relationship health.
3.  **The Persona Roaster:** Generates playful, highly specific roasts grounded in verifiable chat history citations.
4.  **The Reply Giver:** Drafts suggested responses that perfectly mimic the user's historical tone and slang.

---

## 🏗️ Architecture & Tech Stack

The system is distributed across three isolated local environments to guarantee that heavy AI processing never causes the live WhatsApp WebSocket connection to drop.

*   **Frontend UI (`/frontend`):** Next.js 14+ (React, Tailwind CSS). Provides the control dashboard, persona viewer, and live interception modals.
*   **Middle Bridge (`/wa-bridge`):** Node.js (v20+), `@whiskeysockets/baileys`, Express. Maintains the WhatsApp WebSocket connection, captures payloads, and executes delayed, human-simulated outbound dispatch (anti-ban routing).
*   **AI Backend Brain (`/ai-backend`):** Python 3.11+, FastAPI, LangGraph. Houses the Crafty Edge ingestion pipeline, manages the agents, and orchestrates the databases.
*   **Databases:** SQLite (SQLAlchemy) for relational schemas & ChromaDB for local vector embeddings.
*   **Intelligence:** Google Gemini 1.5 Flash (Text, JSON, Vision, Audio).

---

## 🚀 Local Setup & Installation

### 1. Prerequisites
*   Node.js v20+
*   Python 3.11+
*   A Gemini API Key from Google AI Studio

### 2. WhatsApp Bridge Setup
```bash
cd wa-bridge
npm install
node index.js
