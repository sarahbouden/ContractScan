import pdfplumber
from docx import Document
from pathlib import Path


def extract_text_from_pdf(file_path: str) -> str:
    """Extrait le texte brut d'un PDF page par page."""
    with pdfplumber.open(file_path) as pdf:
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


def extract_text_from_docx(file_path: str) -> str:
    """Extrait le texte brut d'un DOCX paragraphe par paragraphe."""
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text(file_path: str) -> str:
    """
    Router : détecte le format et appelle le bon extracteur.
    Supporte PDF et DOCX.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Format non supporté : {suffix}. Acceptés : PDF, DOCX")


def extract_text_from_bytes(file_bytes: bytes, file_name: str) -> str:
    """
    Variante pour Streamlit file_uploader qui retourne des bytes.
    Sauvegarde temporairement le fichier et extrait le texte.
    """
    import tempfile, os
    suffix = Path(file_name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return extract_text(tmp_path)
    finally:
        os.unlink(tmp_path)
