"""Fotos adjuntas a un reporte de falla.

Se guardan en Supabase Storage (no en la tabla `tickets`) — solo el path del
archivo queda en `campos.foto_path`, así que no le pega a la base de datos.
Sin importar la calidad/tamaño con que el personal suba la foto desde su
celular, aquí se comprime antes de subirla: limita el lado más largo y baja
la calidad JPEG, para no gastar cuota de Storage ni hacer lento el panel.
"""
import base64
import io
from uuid import uuid4

from PIL import Image

BUCKET = "reportes-fotos"
MAX_DIMENSION = 1280
JPEG_QUALITY = 70


def compress_photo(base64_data: str) -> bytes:
    if "," in base64_data and base64_data.strip().lower().startswith("data:"):
        base64_data = base64_data.split(",", 1)[1]
    raw = base64.b64decode(base64_data)
    image = Image.open(io.BytesIO(raw))
    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def upload_photo(supabase, department_id: str, base64_data: str) -> str:
    """Comprime y sube la foto; regresa el path dentro del bucket (lo que se
    guarda en campos.foto_path). Puede lanzar excepción — quien la llame
    decide si eso debe tumbar la creación del ticket o solo omitir la foto."""
    jpeg_bytes = compress_photo(base64_data)
    path = f"{department_id}/{uuid4().hex}.jpg"
    supabase.storage.from_(BUCKET).upload(path, jpeg_bytes, {"content-type": "image/jpeg"})
    return path


def download_photo(supabase, path: str) -> bytes:
    return supabase.storage.from_(BUCKET).download(path)
