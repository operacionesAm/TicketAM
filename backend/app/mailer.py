"""Envío de correo: ticket nuevo y observaciones que deja el admin.

Dos formas de enviar, en este orden:
1. Cuenta de Google conectada por el departamento (ver google_oauth.py) —
   manda como esa cuenta real, pensado para dominios donde Sistemas bloquea
   las contraseñas de aplicación de SMTP.
2. SMTP estándar (variables SMTP_* en backend/.env) — sirve cualquier
   proveedor con contraseña de aplicación habilitada.

Si ninguna está configurada, las funciones de este módulo simplemente no
hacen nada: el resto de la app (crear tickets, dejar observaciones) sigue
funcionando igual sin credenciales de correo.
"""
import os
import smtplib
from email.message import EmailMessage

from app import google_oauth

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER


def mail_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_ticket_notification(department: dict, ticket: dict) -> None:
    """Avisa al departamento que llegó un ticket nuevo."""
    to_email = (department or {}).get("notification_email")
    if not to_email:
        return
    department_name = (department or {}).get("name") or ""
    subject = f"[TicketAM] Nuevo ticket en {department_name}: {ticket.get('folio', '')}"
    body = (
        f"Se registró un nuevo ticket en {department_name}.\n\n"
        f"Folio: {ticket.get('folio', '')}\n"
        f"Solicitante: {ticket.get('solicitante_nombre', '')}\n"
        f"Estado: {ticket.get('estado', '')}\n\n"
        "Entra al panel de administrador para ver el detalle y darle seguimiento."
    )
    _dispatch(department, to_email, subject, body)


def send_observation_email(department: dict, ticket: dict, comentario: str) -> None:
    """Le manda al solicitante la observación que el admin dejó en su ticket
    al atenderlo — para dudas o seguimiento sobre el caso."""
    to_email = ticket.get("solicitante_email")
    if not to_email:
        return
    department_name = (department or {}).get("name") or ""
    subject = f"[TicketAM] Actualización de tu ticket {ticket.get('folio', '')} — {department_name}"
    body = (
        f"Hola {ticket.get('solicitante_nombre', '')},\n\n"
        f"El equipo de {department_name} dejó la siguiente observación en tu ticket {ticket.get('folio', '')}:\n\n"
        f"\"{comentario}\"\n\n"
        f"Estado actual: {ticket.get('estado', '')}\n\n"
        "Si tienes dudas, responde directamente a este correo."
    )
    _dispatch(department, to_email, subject, body)


def _dispatch(department: dict, to_email: str, subject: str, body: str) -> None:
    """Intenta con la cuenta de Google conectada; si no hay o falla, cae a SMTP."""
    refresh_token = (department or {}).get("google_refresh_token")
    if refresh_token and google_oauth.is_configured():
        if google_oauth.send_gmail(refresh_token, to_email, subject, body):
            return

    if not mail_configured():
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:
        print(f"[mailer] No se pudo enviar el correo a {to_email}: {exc}")
