from pathlib import Path

from ai.client import SalesQAAnalyzer
from ai.fallback import RuleBasedSalesQAAnalyzer
from ai.schemas import SalesQAResult
from database.repositories import AnalysisRepository, ManagerRepository
from ocr.service import OCRService


class AnalysisService:
    def __init__(self, ocr: OCRService, analyzer: SalesQAAnalyzer) -> None:
        self.ocr = ocr
        self.analyzer = analyzer
        self.fallback = RuleBasedSalesQAAnalyzer()

    async def analyze_and_save(
        self,
        image_paths: list[Path],
        session_id: str,
        telegram_user_id: int,
        username: str | None,
        full_name: str | None,
        manager_repo: ManagerRepository,
        analysis_repo: AnalysisRepository,
    ) -> SalesQAResult:
        ocr_text = await self.ocr.extract_dialog(image_paths)
        if not self.analyzer.settings.openai_enabled:
            result = self.fallback.analyze(ocr_text)
            manager = await manager_repo.get_or_create(telegram_user_id, username, full_name)
            await analysis_repo.save(manager, session_id, result, ocr_text, len(image_paths))
            return result

        try:
            result = await self.analyzer.analyze(image_paths=image_paths, ocr_text=ocr_text)
        except Exception:
            if not self.analyzer.settings.rule_based_fallback_enabled:
                raise
            result = self.fallback.analyze(ocr_text)
        manager = await manager_repo.get_or_create(telegram_user_id, username, full_name)
        await analysis_repo.save(manager, session_id, result, ocr_text, len(image_paths))
        return result
