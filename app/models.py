import enum
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): pass

class QueueStatus(str, enum.Enum):
    pending = "pending"; sent = "sent"; cancelled = "cancelled"; failed = "failed"; paused = "paused"

class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16))
    category: Mapped[str | None] = mapped_column(String(64))
    business_connection_id: Mapped[str] = mapped_column(String(255), index=True)
    last_incoming_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outgoing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"))
    sends_count: Mapped[int] = mapped_column(Integer, default=0)
    replied_after_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BusinessConnection(Base):
    __tablename__ = "business_connections"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    business_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Script(Base):
    __tablename__ = "scripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="ru")
    category: Mapped[str] = mapped_column(String(64), default="general")
    stage: Mapped[str] = mapped_column(String(64), default="followup")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class FollowupQueue(Base):
    __tablename__ = "followup_queue"
    __table_args__ = (UniqueConstraint("client_id", "run_date", name="uq_queue_client_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"))
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus), default=QueueStatus.pending)
    error: Mapped[str | None] = mapped_column(Text)

class SendLog(Base):
    __tablename__ = "send_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"))
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    business_connection_id: Mapped[str] = mapped_column(String(255))
