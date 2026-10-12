"""On-demand desktop screenshots and local OCR. No webcam or OpenCV dependency."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from io import BytesIO

import mss
from PIL import Image, ImageEnhance, ImageOps


@dataclass(frozen=True)
class VisualContext:
    """Screenshot context retained for an optional cloud vision fallback only."""

    screen_jpeg: bytes
    screen_size: tuple[int, int]


class VisionModule:
    """Capture the desktop only after an explicit screen-related voice command."""

    def __init__(self, _settings: object | None = None) -> None:
        self.log = logging.getLogger(self.__class__.__name__)
        self._tesseract_path = self._find_tesseract()

    @staticmethod
    def _find_tesseract() -> str | None:
        candidates = (
            shutil.which("tesseract"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        )
        return next((path for path in candidates if path and os.path.exists(path)), None)

    @staticmethod
    def _to_jpeg(image: Image.Image, quality: int = 82) -> bytes:
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=quality, optimize=True)
        return stream.getvalue()

    def capture_screen_image(self) -> Image.Image:
        """Capture the primary monitor. The camera is never opened."""
        with mss.mss() as capture:
            monitor = capture.monitors[1]
            raw = capture.grab(monitor)
            return Image.frombytes("RGB", raw.size, raw.rgb)

    def capture_context(self) -> VisualContext:
        image = self.capture_screen_image()
        return VisualContext(screen_jpeg=self._to_jpeg(image), screen_size=image.size)

    @staticmethod
    def _ocr_ready(image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        contrast = ImageEnhance.Contrast(grayscale).enhance(2.0)
        return contrast.resize((contrast.width * 2, contrast.height * 2))

    def read_screen_text(self) -> str:
        """OCR the primary monitor locally; return a safe status on failure."""
        if not self._tesseract_path:
            return "Local screen OCR is not installed yet."
        try:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
            image = self._ocr_ready(self.capture_screen_image())
            text = pytesseract.image_to_string(image, lang="eng", config="--oem 3 --psm 6")
            text = " ".join(text.split())
            return text[:8_000] if text else "I could not read clear text from the current screen."
        except Exception as exc:
            self.log.warning("Screen OCR failed: %s", exc)
            return "I could not read clear text from the current screen."

    def close(self) -> None:
        """Kept for lifecycle compatibility; no camera resource exists to release."""

