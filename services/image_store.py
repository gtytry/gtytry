from pathlib import Path
from uuid import uuid4

from PIL import Image

from config.settings import Settings


class ImageStore:
    def __init__(self, settings: Settings, root: Path = Path("data/uploads")) -> None:
        self.root = root
        self.max_bytes = settings.max_image_mb * 1024 * 1024
        self.root.mkdir(parents=True, exist_ok=True)

    def new_path(self, original_name: str | None = None) -> Path:
        suffix = Path(original_name or "image.jpg").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            suffix = ".jpg"
        return self.root / f"{uuid4().hex}{suffix}"

    def validate(self, path: Path) -> None:
        if path.stat().st_size > self.max_bytes:
            raise ValueError("Image is too large")
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise ValueError("Unsupported image format")
            image.verify()
