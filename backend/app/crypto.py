"""Cifrado simétrico reversible del NIP de cada departamento, solo para que
el Administrador Global lo pueda mostrar en "Más detalles".

El login de cada departamento (app/routes/admin.py) sigue verificando
siempre contra el hash de siempre (departments.admin_passcode_hash) — este
cifrado es una copia aparte que existe únicamente para poder desplegar el
valor, nunca se usa para validar el login. Un departamento cuyo PIN se
configuró antes de esta función no tendrá copia cifrada hasta que se
resetee una vez.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

_KEY = os.environ.get("PASSCODE_ENCRYPTION_KEY")


def is_configured() -> bool:
    return bool(_KEY)


def encrypt_passcode(passcode: str) -> str:
    return Fernet(_KEY).encrypt(passcode.encode()).decode()


def decrypt_passcode(token):
    if not token or not _KEY:
        return None
    try:
        return Fernet(_KEY).decrypt(token.encode()).decode()
    except InvalidToken:
        return None
