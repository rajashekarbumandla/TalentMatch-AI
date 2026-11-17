"""
Optional OCR fallback for scanned PDFs (Tesseract via pytesseract).

OCR is an *optional* dependency: the app works without it. If Tesseract is not
installed, the PDF parser reports "OCR required" instead of returning an empty
profile. To enable it:
    1. Install Tesseract (Windows: https://github.com/UB-Mannheim/tesseract/wiki)
    2. pip install pytesseract
    3. Optionally set TESSERACT_CMD to the tesseract.exe path in backend/.env
"""
import io
import os
import shutil
from functools import lru_cache

from app.config import settings

OCR_DPI = 300  # resolution used when rendering PDF pages to images


@lru_cache(maxsize=1)
def is_ocr_available() -> bool:
    """True when both pytesseract and the tesseract executable can be found."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    if settings.TESSERACT_CMD:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        return os.path.exists(settings.TESSERACT_CMD) or shutil.which(settings.TESSERACT_CMD) is not None
    return shutil.which("tesseract") is not None


def ocr_pdf(doc) -> str:
    """Render every page of an open PyMuPDF document and OCR it."""
    import pytesseract
    from PIL import Image

    texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=OCR_DPI)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        texts.append(pytesseract.image_to_string(image))
    return "\n".join(texts)
