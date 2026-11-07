/**
 * Agentic Chase — WhatsApp bridge
 * Baileys socket + Express dispatch. Directives execute instantly (no LangGraph).
 */
"use strict";

require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });

const express = require("express");
const cors = require("cors");
const axios = require("axios");
const fs = require("fs");
const path = require("path");
const qrcode = require("qrcode");
const qrcodeTerminal = require("qrcode-terminal");
const pino = require("pino");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  Browsers,
} = require("@whiskeysockets/baileys");

const PORT = Number(process.env.WA_BRIDGE_PORT || 3001);
const AI_BACKEND_URL = process.env.AI_BACKEND_URL || "http://localhost:8000";
const AUTH_DIR = path.join(__dirname, "auth_info");

const logger = pino({ level: "silent" });

const state = {
  sock: null,
  status: "disconnected",
  qrDataUrl: null,
  lastError: null,
  directives: [],
  focusMode: false,
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function hourNow() {
  return new Date().getHours();
}

function conditionMatches(condition = {}, extra = {}) {
  const after = condition.after_hour;
  const before = condition.before_hour;
  const h = hourNow();
  if (typeof after === "number" && h < after) return false;
  if (typeof before === "number" && h >= before) return false;
  if (condition.weekdays_only) {
    const d = new Date().getDay();
    if (d === 0 || d === 6) return false;
  }
  if (condition.chat_type && condition.chat_type !== "any") {
    if (extra.chatType && extra.chatType !== condition.chat_type) return false;
  }
  if (condition.contains && extra.text) {
    if (!String(extra.text).toLowerCase().includes(String(condition.contains).toLowerCase())) {
      return false;
    }
  }
  return true;
}

/** Human-like outbound send — composing → 2-4s jitter → paused → send */
async function humanSend(sock, jid, text) {
  if (!sock || !jid || !text) return;
  await sock.sendPresenceUpdate("composing", jid);
  const delay = 2000 + Math.floor(Math.random() * 2000);
  await sleep(delay);
  await sock.sendPresenceUpdate("paused", jid);
  await sock.sendMessage(jid, { text: String(text) });
}

async function refreshDirectives() {
  try {
    const { data } = await axios.get(`${AI_BACKEND_URL}/api/directives/active`, { timeout: 8000 });
    state.directives = Array.isArray(data) ? data : [];
  } catch {
    /* backend may not be up yet */
  }
}

async function refreshFocus() {
  try {
    const { data } = await axios.get(`${AI_BACKEND_URL}/api/focus-mode`, { timeout: 5000 });
    state.focusMode = Boolean(data && data.enabled);
  } catch {
    /* ignore */
  }
}

async function forwardLive(payload) {
  try {
    await axios.post(`${AI_BACKEND_URL}/api/ingest/live`, payload, { timeout: 20000 });
  } catch (err) {
    console.error("[bridge] ingest/live failed:", err.message);
  }
}

async function maybeStandIn(jid, text, isGroup) {
  if (!state.focusMode || isGroup) return;
  try {
    const projects = await axios.get(`${AI_BACKEND_URL}/api/projects`, { timeout: 8000 });
    const list = projects.data || [];
    let projectId = null;
    let chatId = null;
    for (const p of list) {
      const chat = (p.chats || []).find((c) => c.wa_jid === jid);
      if (chat) {
        projectId = p.id;
        chatId = chat.id;
        break;
      }
    }
    if (!projectId && list[0]) {
      projectId = list[0].id;
      const dm = (list[0].chats || []).find((c) => c.chat_type === "DIRECT");
      chatId = dm ? dm.id : (list[0].chats || [])[0]?.id;
    }
    if (!projectId || !chatId) return;
    const { data } = await axios.post(
      `${AI_BACKEND_URL}/api/agents/run`,
      {
        project_id: projectId,
        chat_id: chatId,
        query: text,
        agent: "stand_in",
      },
      { timeout: 45000 }
    );
    if (data && data.requires_hitl) return;
    if (data && data.result && data.result !== "PAUSED_FOR_HUMAN") {
      await humanSend(state.sock, jid, data.result);
    }
  } catch (err) {
    console.error("[bridge] stand-in failed:", err.message);
  }
}

async function handleCallOffer(call) {
  const from = call.from;
  const matched = state.directives.filter((d) => d.trigger === "call" && d.enabled !== false);
  for (const d of matched) {
    if (!conditionMatches(d.condition, { chatType: "DIRECT" })) continue;
    const action = d.action || {};
    try {
      if (typeof state.sock.rejectCall === "function" && call.id && from) {
        await state.sock.rejectCall(call.id, from);
      }
      if (action.type === "reject_and_text" || action.type === "text") {
        const msg = action.message || "I am offline for the day.";
        await humanSend(state.sock, from, msg);
      }
      console.log("[bridge] directive executed on call from", from, d.id);
    } catch (err) {
      console.error("[bridge] call directive failed:", err.message);
    }
  }
}

async function handleIncomingMessage(msg) {
  if (!msg.message || msg.key.fromMe) return;
  const jid = msg.key.remoteJid;
  if (!jid || jid === "status@broadcast") return;
  const isGroup = jid.endsWith("@g.us");
  const body =
    msg.message.conversation ||
    msg.message.extendedTextMessage?.text ||
    msg.message.imageMessage?.caption ||
    msg.message.videoMessage?.caption ||
    (msg.message.audioMessage ? "[voice note]" : "") ||
    "";
  const sender = msg.pushName || msg.key.participant || jid;

  for (const d of state.directives.filter((x) => x.trigger === "message" && x.enabled !== false)) {
    if (!conditionMatches(d.condition, { chatType: isGroup ? "GROUP" : "DIRECT", text: body })) continue;
    const action = d.action || {};
    if (action.type === "text" || action.type === "reject_and_text") {
      await humanSend(state.sock, jid, action.message || "");
    }
  }

  await forwardLive({
    wa_jid: jid,
    chat_title: isGroup ? jid : sender,
    is_group: isGroup,
    sender,
    body,
    ts: new Date().toISOString(),
  });

  await maybeStandIn(jid, body, isGroup);
}

async function connectWhatsApp() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    logger,
    printQRInTerminal: false,
    auth: authState,
    browser: Browsers.ubuntu("Chrome"),
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });
  state.sock = sock;

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      state.status = "qr";
      state.qrDataUrl = await qrcode.toDataURL(qr);
      qrcodeTerminal.generate(qr, { small: true });
      console.log("\n[bridge] Scan the WhatsApp QR code above (or open the dashboard).\n");
    }
    if (connection === "open") {
      state.status = "connected";
      state.qrDataUrl = null;
      state.lastError = null;
      console.log("[bridge] WhatsApp connected");
    }
    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      state.status = "disconnected";
      state.lastError = lastDisconnect?.error?.message || String(code || "closed");
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      console.log("[bridge] connection closed", state.lastError, "reconnect=", shouldReconnect);
      if (shouldReconnect) {
        await sleep(2000);
        connectWhatsApp().catch((err) => console.error(err));
      } else {
        console.log("[bridge] logged out — delete wa-bridge/auth_info and restart to scan again");
      }
    }
  });

  sock.ev.on("call", async (calls) => {
    for (const call of calls || []) {
      if (call.status === "offer" || call.status === "ringing" || !call.status) {
        await handleCallOffer(call);
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages || []) {
      await handleIncomingMessage(msg);
    }
  });
}

const app = express();
app.use(
  cors({
    origin: ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    credentials: true,
  })
);
app.use(express.json({ limit: "8mb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true, status: state.status, focusMode: state.focusMode });
});

app.get("/status", (_req, res) => {
  res.json({
    status: state.status,
    qr: state.qrDataUrl,
    lastError: state.lastError,
    directives: state.directives.length,
    focusMode: state.focusMode,
  });
});

app.post("/send", async (req, res) => {
  try {
    const { jid, wa_jid, message, text } = req.body || {};
    const target = jid || wa_jid;
    const body = message || text;
    if (!state.sock || state.status !== "connected") {
      return res.status(409).json({ ok: false, error: "whatsapp not connected" });
    }
    await humanSend(state.sock, target, body);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.listen(PORT, async () => {
  console.log(`[bridge] listening on http://localhost:${PORT}`);
  await refreshDirectives();
  await refreshFocus();
  setInterval(() => {
    refreshDirectives();
    refreshFocus();
  }, 8000);
  connectWhatsApp().catch((err) => {
    console.error("[bridge] failed to start socket", err);
    state.lastError = err.message;
  });
});
