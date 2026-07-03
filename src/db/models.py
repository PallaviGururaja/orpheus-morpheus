from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text, TIMESTAMP, Integer, BigInteger, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Session(Base):
    """A persistent workbench; owns datasets and query history."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    queries: Mapped[list["Query"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Dataset(Base):
    """A loaded data source bound to a session, with its cached profile."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="csv")
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )

    session: Mapped["Session"] = relationship(back_populates="datasets")


class Query(Base):
    """One row per analysis run — the full audit trail."""

    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    dataset_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_table: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_rerun: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    session: Mapped["Session"] = relationship(back_populates="queries")


class Dashboard(Base):
    """A named, saveable set of aggregated-chart widgets (Phase 3). No LLM."""

    __tablename__ = "dashboards"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    widgets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
