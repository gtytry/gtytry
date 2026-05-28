import base64
import json
from pathlib import Path

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.schemas import SalesQAResult
from config.settings import Settings


class SalesQAAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "sales_qa_system.md"
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    async def analyze(self, image_paths: list[Path], ocr_text: str) -> SalesQAResult:
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

        raw = response.choices[0].message.content or "{}"
        return SalesQAResult.model_validate(json.loads(raw))


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "image/jpeg"
