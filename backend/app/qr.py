"""Generación de códigos QR para vehículos.

Cada QR codifica una liga directa a la página pública con `?placa=...`
(ver frontend/tickets/usuario/index.html: `getPlacaFromURL()` ya sabe leer
ese parámetro y saltar directo al formulario de ese vehículo). Se genera al
vuelo a partir de la placa — no se guarda como imagen en la base de datos.
"""
import base64
import os
from io import BytesIO
from urllib.parse import quote

import qrcode
from PIL import Image, ImageDraw, ImageFont

COLOR_MARCA = "#000000"

# Ancho fijo del QR etiquetado (px). El QR natural que arma `qrcode` sale muy
# chico para dejarle espacio decente al logo y al texto de la leyenda, así
# que se reescala aquí con NEAREST (sin difuminar los módulos, para que siga
# siendo legible al escanear) a un tamaño cómodo para imprimir en tarjetas.
ANCHO_QR_ETIQUETADO = 480

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo-am.png")

# Pillow trae internamente una fuente escalable (Aileron Regular) accesible
# vía ImageFont.load_default(size=...) desde la 10.1 — no hace falta
# empaquetar ni depender de ninguna fuente del sistema operativo.


def entity_qr_url(base_url: str, codigo: str) -> str:
    return f"{base_url.rstrip('/')}/?placa={quote(codigo)}"


def _qr_image(data: str) -> Image.Image:
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color=COLOR_MARCA, back_color="white").convert("RGB")


def generate_qr_png(data: str) -> bytes:
    buffer = BytesIO()
    _qr_image(data).save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_base64(data: str) -> str:
    return base64.b64encode(generate_qr_png(data)).decode("ascii")


def _fitted_font(draw: "ImageDraw.ImageDraw", texto: str, tamaño_inicial: int, ancho_max: int, tamaño_minimo: int = 11) -> "ImageFont.FreeTypeFont":
    """Reduce el tamaño de fuente hasta que `texto` quepa en `ancho_max` px.

    Equivalente en servidor al auto-ajuste que hacía el canvas del cliente
    en el panel legado de QR (font-shrink-to-fit), para que placas largas o
    modelos largos no se desborden de la franja de leyenda del QR impreso.
    """
    tamaño = tamaño_inicial
    while tamaño > tamaño_minimo:
        font = ImageFont.load_default(size=tamaño)
        if not texto or draw.textbbox((0, 0), texto, font=font)[2] <= ancho_max:
            return font
        tamaño -= 1
    return ImageFont.load_default(size=tamaño)


def generate_labeled_qr_png(data: str, placa: str, marca_modelo: str = "") -> bytes:
    """QR con el logo y la placa/modelo impresos debajo, listo para imprimir.

    Usado por el panel de inventario y por la impresión de QRs: así cada
    tarjeta/etiqueta es autocontenida (no depende de recortar a mano dónde
    empieza y termina cada vehículo en la hoja impresa).
    """
    qr_img = _qr_image(data).resize((ANCHO_QR_ETIQUETADO, ANCHO_QR_ETIQUETADO), Image.NEAREST)
    ancho = qr_img.width

    padding = 20
    logo_gap = 14
    alto_linea_placa = 42
    alto_linea_detalle = 30
    espacio_lineas = 8
    alto_leyenda = padding * 2 + alto_linea_placa + espacio_lineas + alto_linea_detalle

    canvas = Image.new("RGB", (ancho, qr_img.height + alto_leyenda), "white")
    canvas.paste(qr_img, (0, 0))
    draw = ImageDraw.Draw(canvas)

    placa_texto = (placa or "").strip()
    detalle_texto = (marca_modelo or "").strip()

    logo = None
    logo_ancho = 0
    alto_logo = alto_linea_placa + espacio_lineas + alto_linea_detalle
    if os.path.isfile(LOGO_PATH):
        logo_original = Image.open(LOGO_PATH).convert("RGBA")
        logo_ancho = round(logo_original.width * (alto_logo / logo_original.height))
        logo = logo_original.resize((logo_ancho, alto_logo))

    gap = logo_gap if logo else 0
    ancho_disponible_texto = ancho - padding * 2 - logo_ancho - gap

    font_placa = _fitted_font(draw, placa_texto, alto_linea_placa - 8, ancho_disponible_texto)
    font_detalle = _fitted_font(draw, detalle_texto, alto_linea_detalle - 6, ancho_disponible_texto)

    ancho_placa = draw.textbbox((0, 0), placa_texto, font=font_placa)[2] if placa_texto else 0
    ancho_detalle = draw.textbbox((0, 0), detalle_texto, font=font_detalle)[2] if detalle_texto else 0
    ancho_texto_max = max(ancho_placa, ancho_detalle)

    ancho_grupo = logo_ancho + gap + ancho_texto_max
    x_grupo = max(padding, round((ancho - ancho_grupo) / 2))
    y_inicio = qr_img.height + padding
    x_texto = x_grupo

    if logo:
        canvas.paste(logo, (x_grupo, y_inicio), logo)
        x_texto = x_grupo + logo_ancho + gap

    if placa_texto:
        draw.text((x_texto, y_inicio), placa_texto, fill=COLOR_MARCA, font=font_placa)
    if detalle_texto:
        draw.text((x_texto, y_inicio + alto_linea_placa + espacio_lineas), detalle_texto, fill=COLOR_MARCA, font=font_detalle)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
