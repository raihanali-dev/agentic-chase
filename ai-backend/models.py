"""SQLAlchemy schemas: Project, Chat, Persona, Directive, Messages, HITL, settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chats: Mapped[list["Chat"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    chat_type: Mapped[str] = mapped_column(String(16), nullable=False, default="DIRECT")  # GROUP | DIRECT
    wa_jid: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")
    personas: Mapped[list["Persona"]] = relationship(back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id"), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[str] = mapped_column(String(32), default="text")  # text | image | audio | system
    media_caption: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    chat: Mapped["Chat"] = relationship(back_populates="messages")


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id"), nullable=False, index=True)
    participant: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat: Mapped["Chat"] = relationship(back_populates="personas")


class Directive(Base):
    __tablename__ = "directives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    natural_language: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)  # call | message | mention | media
    condition_json: Mapped[str] = mapped_column(Text, default="{}")
    action_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    chat_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="high")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | confirmed | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
