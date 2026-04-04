import io

SUPPORTED_EXTENSIONS = {"pdf", "docx", "md", "txt"}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_file(filename: str) -> None:
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Tipo de arquivo nao suportado: .{ext}. Use: {supported}")


async def extract_text(data: bytes, filename: str) -> str:
    ext = _extension(filename)

    if ext == "pdf":
        return _extract_pdf(data)

    if ext == "docx":
        return _extract_docx(data)

    if ext in ("md", "txt"):
        return data.decode("utf-8")

    raise ValueError(f"Tipo de arquivo nao suportado: .{ext}")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p for p in pages if p.strip())


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
