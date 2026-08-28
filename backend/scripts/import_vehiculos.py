"""Importa el inventario real de vehículos (vehiculos.json, en la raíz del
repo) al catálogo de entidades de Supabase, bajo el departamento 'flota'.

Uso (desde la carpeta backend/):
    python scripts/import_vehiculos.py

Es idempotente: si una placa ya existe se actualiza (upsert por
department_id+codigo), no se duplica. También elimina los 3 vehículos de
ejemplo sembrados por schema.sql (ABC-123, XYZ-789, DEF-456) si siguen ahí.

Requiere SUPABASE_URL y SUPABASE_SERVICE_KEY en el entorno o en .env.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VEHICULOS_JSON = REPO_ROOT / "vehiculos.json"
DEMO_PLACAS = {"ABC-123", "XYZ-789", "DEF-456"}


def main() -> None:
    if not VEHICULOS_JSON.exists():
        print(f"No se encontró {VEHICULOS_JSON}")
        raise SystemExit(1)

    vehiculos = json.loads(VEHICULOS_JSON.read_text(encoding="utf-8"))

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    client = create_client(url, key)

    dept = client.table("departments").select("id").eq("slug", "flota").single().execute()
    if not dept.data:
        print("No existe el departamento 'flota'. Corre schema.sql primero.")
        raise SystemExit(1)
    department_id = dept.data["id"]

    client.table("entities").delete().eq("department_id", department_id).in_("codigo", list(DEMO_PLACAS)).execute()

    records = []
    for v in vehiculos:
        placa = str(v["placa"]).strip().upper()
        marca = str(v.get("marca", "")).strip()
        modelo = str(v.get("modelo", "")).strip()
        records.append({
            "department_id": department_id,
            "codigo": placa,
            "nombre": f"{marca} {modelo}".strip(),
            "atributos": {
                "tipo": v.get("tipo", ""),
                "marca": marca,
                "modelo": modelo,
                "año": v.get("año", ""),
                "estado": v.get("estado", ""),
                "departamento": v.get("departamento", ""),
                "combustible": v.get("combustible", ""),
            },
        })

    result = client.table("entities").upsert(records, on_conflict="department_id,codigo").execute()
    print(f"Importados/actualizados {len(result.data or [])} de {len(records)} vehículos.")


if __name__ == "__main__":
    main()
