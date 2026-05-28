import logging
import asyncio
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

from config.settings import Settings

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, settings: Settings) -> None:
        self.language = settings.ocr_language
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    async def extract_dialog(self, image_paths: list[Path]) -> str:
        chunks = []
        for index, path in enumerate(image_paths, start=1):
            try:
                text = await asyncio.to_thread(self._extract_one, path)
                chunks.append(f"[SCREENSHOT {index}]\n{clean_ocr_text(text)}")
            except Exception:
                logger.exception("OCR failed for %s", path)
                chunks.append(f"[SCREENSHOT {index}]\n")
        return "\n\n".join(chunks).strip()

    def _extract_one(self, path: Path) -> str:
        with Image.open(path) as image:
            prepared = prepare_image(image)
            return pytesseract.image_to_string(prepared, lang=self.language)


def prepare_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("L")
    width, height = image.size
    if width < 1400:
        ratio = 1400 / width
        image = image.resize((int(width * ratio), int(height * ratio)))
    return ImageOps.autocontrast(image)


def clean_ocr_text(text: str) -> str:
    text = text.replace("\x0c", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"(?<![.!?:])\n(?=[а-яА-Яa-zA-Z0-9])", " ", text)
    return text.strip()
