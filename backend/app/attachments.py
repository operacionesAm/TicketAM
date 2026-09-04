"""Adjuntos genéricos de un ticket (PDF/Word/Excel/imagen) — a diferencia de
app/photos.py, aquí no se procesa nada: se valida tipo y tamaño y se sube
el archivo tal cual. Pensado para los "Archivo adjunto"/"Evidencia"/
"Documento de autorización" de Talento AM (Capital Humano), pero cualquier
departamento puede usarlo si en algún momento lo necesita.
"""
import base64
from uuid import uuid4

BUCKET = "ch-adjuntos"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

MIME_BY_EXT = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class AdjuntoInvalido(Exception):
    """Extensión no permitida o archivo demasiado grande — quien llame
    decide si eso debe tumbar la creación del ticket (a diferencia de una
    foto opcional, varios adjuntos de Talento AM son obligatorios)."""


def upload_attachment(supabase, department_id: str, filename: str, base64_data: str) -> str:
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if extension not in MIME_BY_EXT:
        raise AdjuntoInvalido(f"Tipo de archivo no permitido: .{extension or '?'} (permitidos: {', '.join(sorted(MIME_BY_EXT))})")

    if "," in base64_data and base64_data.strip().lower().startswith("data:"):
        base64_data = base64_data.split(",", 1)[1]
    raw = base64.b64decode(base64_data)
    if len(raw) > MAX_BYTES:
        raise AdjuntoInvalido("El archivo supera el máximo de 5 MB")

    path = f"{department_id}/{uuid4().hex}.{extension}"
    supabase.storage.from_(BUCKET).upload(path, raw, {"content-type": MIME_BY_EXT[extension]})
    return path


def download_attachment(supabase, path: str) -> bytes:
    return supabase.storage.from_(BUCKET).download(path)
