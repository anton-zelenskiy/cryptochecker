from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from project.core.db_session import sessionmanager
from project.models.screener import ScreenerSnapshot


class ScreenerSnapshotRepository:
    async def upsert_snapshot(self, row: dict) -> None:
        stmt = pg_insert(ScreenerSnapshot).values(row)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_screener_snapshot_identity",
            set_={
                "feature_version": stmt.excluded.feature_version,
                "features": stmt.excluded.features,
                "decision": stmt.excluded.decision,
                "confidence": stmt.excluded.confidence,
                "long_score": stmt.excluded.long_score,
                "short_score": stmt.excluded.short_score,
                "risk_score": stmt.excluded.risk_score,
                "reasons": stmt.excluded.reasons,
                "llm_verdict": stmt.excluded.llm_verdict,
                "llm_confidence_adjust": stmt.excluded.llm_confidence_adjust,
                "llm_rationale": stmt.excluded.llm_rationale,
                "final_decision": stmt.excluded.final_decision,
                "final_confidence": stmt.excluded.final_confidence,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": func.now(),
            },
        )
        async with sessionmanager.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_latest_for_market(
        self,
        *,
        base_asset: str,
        quote_asset: str,
    ) -> ScreenerSnapshot | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(ScreenerSnapshot)
                .where(ScreenerSnapshot.base_asset == base_asset)
                .where(ScreenerSnapshot.quote_asset == quote_asset)
                .order_by(ScreenerSnapshot.computed_at.desc())
                .limit(1)
            )
            return res.scalar_one_or_none()
