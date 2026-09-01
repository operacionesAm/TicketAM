"""Enviar correo como una cuenta real de Google Workspace (@am.com.mx) vía
"Iniciar sesión con Google", para departamentos donde Sistemas bloquea las
contraseñas de aplicación.

El admin conecta su cuenta una sola vez desde /admin/configuracion (botón
"Conectar con Google" -> GET /api/admin/google/connect). Guardamos solo el
refresh_token (departments.google_refresh_token) — con eso, mailer.py puede
pedir un access_token nuevo cada vez que hay que mandar un correo, sin volver
a pedirle login a nadie.

Requiere GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REDIRECT_URI en
backend/.env (ver README — hay que crearlos en Google Cloud Console). Sin
esas variables, is_configured() es False y las rutas de conexión devuelven
error en vez de fallar a medias.
"""
import base64
import os
from email.message import EmailMessage

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and REDIRECT_URI)


def _client_config() -> dict:
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def build_auth_url(state: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # fuerza a que Google regrese refresh_token siempre, no solo la primera vez
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> dict:
    """Cambia el code por tokens y regresa {refresh_token, email}."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(code=code)
    creds = flow.credentials

    profile = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10,
    )
    profile.raise_for_status()
    email = profile.json().get("email")

    return {"refresh_token": creds.refresh_token, "email": email}


def send_gmail(refresh_token: str, to_email: str, subject: str, body: str) -> bool:
    """Manda un correo con la cuenta de Google conectada. True si se envió."""
    if not is_configured() or not refresh_token or not to_email:
        return False

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )
        creds.refresh(Request())

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = to_email
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        service = build("gmail", "v1", credentials=creds)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as exc:
        print(f"[google_oauth] No se pudo enviar el correo a {to_email}: {exc}")
        return False
