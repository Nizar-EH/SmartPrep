"""
Extraction de texte à partir de fichiers importés ou scannés (txt, pdf, images).
Utilisé par la sandbox d'exercices et l'import de scans d'évaluations.
"""


def extract_text_from_file(path: str) -> str:
    """Extrait le texte d'un fichier : txt, pdf (texte ou scanné via OCR si
    tesseract est installé), image (OCR)."""
    lower = path.lower()
    if lower.endswith(".txt") or lower.endswith(".md"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
        # PDF scanné sans texte -> tentative OCR
        return _ocr_pdf(path)

    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return _ocr_image(path)

    raise ValueError("Format de fichier non supporté (utilise .txt, .pdf, .png ou .jpg).")


def _ocr_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path), lang="fra+eng")
    except Exception as e:
        raise RuntimeError(
            "OCR indisponible : installe 'pytesseract', 'pillow' et le binaire "
            f"Tesseract sur ta machine. Détail : {e}"
        )


def _ocr_pdf(path: str) -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pages = convert_from_path(path)
        return "\n".join(pytesseract.image_to_string(p, lang="fra+eng") for p in pages)
    except Exception as e:
        raise RuntimeError(
            "OCR indisponible pour ce PDF scanné : installe 'pdf2image', "
            f"'pytesseract' et poppler/tesseract. Détail : {e}"
        )
