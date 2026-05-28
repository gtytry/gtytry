import json
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.schemas import SalesQAResult
from database.models import Analysis, Manager


@dataclass(slots=True)
class StatsSnapshot:
    total_analyses: int
    average_score: float
    top_mistakes: list[tuple[str, int]]
    best_manager: tuple[str, float] | None
    worst_manager: tuple[str, float] | None


class ManagerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, telegram_user_id: int, username: str | None, full_name: str | None) -> Manager:
        result = await self.session.execute(select(Manager).where(Manager.telegram_user_id == telegram_user_id))
        manager = result.scalar_one_or_none()
        if manager:
            manager.username = username
            manager.full_name = full_name
            return manager

        manager = Manager(telegram_user_id=telegram_user_id, username=username, full_name=full_name)
        self.session.add(manager)
        await self.session.flush()
        return manager


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(
        self,
        manager: Manager,
        session_id: str,
        result: SalesQAResult,
        ocr_text: str,
        image_count: int,
    ) -> Analysis:
        analysis = Analysis(
            manager_id=manager.id,
            session_id=session_id,
            score=result.score,
            sale_probability=result.sale_probability,
            summary=result.summary,
            strengths=json.dumps(result.strengths, ensure_ascii=False),
            mistakes=json.dumps(result.mistakes, ensure_ascii=False),
            missed_opportunities=json.dumps(result.missed_opportunities, ensure_ascii=False),
            recommendations=json.dumps(result.recommendations, ensure_ascii=False),
            criteria_scores=result.criteria_scores.model_dump_json(),
            raw_response=result.model_dump_json(),
            ocr_text=ocr_text,
            image_count=image_count,
        )
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def stats(self) -> StatsSnapshot:
        total = await self.session.scalar(select(func.count(Analysis.id))) or 0
        avg = await self.session.scalar(select(func.avg(Analysis.score))) or 0.0

        rows = (await self.session.execute(select(Analysis.mistakes))).scalars().all()
        counter: Counter[str] = Counter()
        for raw in rows:
            try:
                counter.update(json.loads(raw))
            except json.JSONDecodeError:
                continue

        manager_avg = (
            select(
                Manager.full_name,
                Manager.username,
                func.avg(Analysis.score).label("avg_score"),
            )
            .join(Analysis, Analysis.manager_id == Manager.id)
            .group_by(Manager.id)
        )

        best = (await self.session.execute(manager_avg.order_by(desc("avg_score")).limit(1))).first()
        worst = (await self.session.execute(manager_avg.order_by(asc("avg_score")).limit(1))).first()

        return StatsSnapshot(
            total_analyses=total,
            average_score=float(avg),
            top_mistakes=counter.most_common(5),
            best_manager=self._manager_tuple(best),
            worst_manager=self._manager_tuple(worst),
        )

    @staticmethod
    def _manager_tuple(row: object) -> tuple[str, float] | None:
        if not row:
            return None
        full_name, username, avg_score = row
        name = full_name or (f"@{username}" if username else "unknown")
        return name, float(avg_score)
