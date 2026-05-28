import base64
import json
import logging
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

from ai.schemas import SalesQAResult
from config.settings import Settings

logger = logging.getLogger(__name__)


class SalesQAAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "sales_qa_system.md"
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

    async def analyze(self, image_paths: list[Path], ocr_text: str) -> SalesQAResult:
        if self.settings.openai_api_key == "sk-replace-me":
            raise RuntimeError("OpenAI API key is not configured")

        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "Проанализируй скриншоты переписки. "
                    "OCR-текст ниже может быть неточным, проверь выводы по изображениям.\n\n"
                    f"OCR_TEXT:\n{ocr_text or 'OCR text is empty.'}"
                ),
            }
        ]

        for path in image_paths:
            mime = _guess_mime(path)
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "high"},
                }
            )

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0.1,
                max_tokens=self.settings.openai_max_output_tokens,
                response_format={"type": "json_object"},
            )
        except (APITimeoutError, APIConnectionError):
            logger.exception("OpenAI connection failed")
            raise

        raw = response.choices[0].message.content or "{}"
        return SalesQAResult.model_validate(json.loads(raw))


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "image/jpeg"
