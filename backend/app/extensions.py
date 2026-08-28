"""Cliente de Supabase compartido por toda la app.

El backend Flask corre en el servidor, nunca en el navegador, así que usa la
service role key: el control de acceso real lo hacen las rutas de admin (ver
app/routes/admin.py) a través de la sesión de Flask, no las políticas RLS por
auth.uid(). Si SUPABASE_URL o la key no están configuradas, `supabase` queda
en None y las rutas caen a los datos demo (ver app/demo_data.py).
"""
import os

from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import Client, create_client
except ImportError:  # Permite correr la UI mientras se instalan dependencias.
    Client = None
    create_client = None


def _build_client() -> "Client | None":
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if url and key and create_client:
        return create_client(url, key)
    return None


supabase: "Client | None" = _build_client()
