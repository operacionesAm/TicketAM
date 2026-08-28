"""Fija la contraseña de administrador (8 dígitos) de un departamento.

Uso (desde la carpeta backend/):
    python scripts/set_passcode.py flota 12345678

Requiere SUPABASE_URL y SUPABASE_SERVICE_KEY en el entorno o en .env.
"""
import os
import sys

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from supabase import create_client

load_dotenv()


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python scripts/set_passcode.py <slug> <passcode-8-digitos>")
        raise SystemExit(1)

    slug, passcode = sys.argv[1], sys.argv[2]
    if not (passcode.isdigit() and len(passcode) == 8):
        print("La contraseña debe ser de exactamente 8 dígitos.")
        raise SystemExit(1)

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    client = create_client(url, key)

    result = (
        client.table("departments")
        .update({"admin_passcode_hash": generate_password_hash(passcode)})
        .eq("slug", slug)
        .execute()
    )
    if not result.data:
        print(f"No existe un departamento con slug '{slug}'.")
        raise SystemExit(1)

    print(f"Contraseña actualizada para '{slug}'.")


if __name__ == "__main__":
    main()
