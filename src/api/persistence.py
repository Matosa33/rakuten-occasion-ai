"""Cycle 9.5 — Persistence SQLAlchemy + SQLite.

Historise les identifications et annonces générées pour :
- traçabilité (audit des suggestions faites au vendeur)
- feedback loop futur (Cycle 12 closed-loop : le vendeur corrige → ré-entraînement)
- métriques produit (taux d'identification, distribution des statuts)

Schéma minimal MVP : une table `identification_log`. SQLite local
(DATABASE_URL paramétrable via env, défaut `sqlite:///./rakuten.db`).
"""

from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./rakuten.db")


class Base(DeclarativeBase):
    pass


class IdentificationLog(Base):
    """Trace d'une requête /identify (+ pricing éventuel)."""

    __tablename__ = "identification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.UTC)
    )
    query_text: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20))  # identified | ambiguous | ood
    top1_parent_asin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    top1_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    top1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_price_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_confidence_level: Mapped[str | None] = mapped_column(String(4), nullable=True)


_engine = None


def get_engine():
    """Singleton engine (créé à la première demande)."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def log_identification(
    query_text: str,
    status: str,
    top1_parent_asin: str | None = None,
    top1_category: str | None = None,
    top1_score: float | None = None,
    suggested_price_eur: float | None = None,
    price_confidence_level: str | None = None,
) -> int:
    """Insère une ligne de log et retourne son id."""
    with Session(get_engine()) as session:
        row = IdentificationLog(
            query_text=query_text[:2000],
            status=status,
            top1_parent_asin=top1_parent_asin,
            top1_category=top1_category,
            top1_score=top1_score,
            suggested_price_eur=suggested_price_eur,
            price_confidence_level=price_confidence_level,
        )
        session.add(row)
        session.commit()
        return row.id


def recent_logs(limit: int = 20) -> list[dict]:
    """Retourne les N dernières identifications (pour /history)."""
    from sqlalchemy import select

    with Session(get_engine()) as session:
        stmt = select(IdentificationLog).order_by(IdentificationLog.id.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "query_text": r.query_text,
                "status": r.status,
                "top1_parent_asin": r.top1_parent_asin,
                "top1_category": r.top1_category,
                "top1_score": r.top1_score,
                "suggested_price_eur": r.suggested_price_eur,
                "price_confidence_level": r.price_confidence_level,
            }
            for r in rows
        ]
