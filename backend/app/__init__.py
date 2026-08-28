import os
import secrets

from flask import Flask


def create_app() -> Flask:
    # API pura: el frontend (carpeta ../frontend) se sirve por separado, no
    # hay HTML ni /static que registrar aquí. En producción ambos quedan
    # bajo el mismo dominio de Vercel (ver vercel.json en la raíz), así que
    # el navegador nunca hace una petición cross-origin y las cookies de
    # sesión del admin funcionan igual que si todo fuera un solo servidor.
    app = Flask(__name__, static_folder=None)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    from app.routes.admin import admin_bp
    from app.routes.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    return app
