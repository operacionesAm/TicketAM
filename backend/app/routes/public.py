"""Rutas públicas: la página de registro de tickets y su API.

Sin autenticación. Un solicitante llega por QR o por liga directa, ve los
tipos de ticket y el catálogo de entidades (p. ej. vehículos) de su
departamento, y crea un ticket. Nunca ve la lista de tickets de nadie más —
eso vive solo detrás del login de app/routes/admin.py.
"""
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, jsonify, request

from app.demo_data import DEMO_DEPARTMENT, DEMO_ENTITIES, DEMO_TICKETS, DEMO_TYPE_ASIGNACION, DEMO_TYPE_REPORTE
from app.extensions import supabase

public_bp = Blueprint("public", __name__)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def error(message: str, status: int):
    return jsonify({"detail": message}), status


@public_bp.get("/api/departments/<slug>")
def department(slug: str):
    if not supabase:
        if slug != "flota":
            return error("Departamento no encontrado", 404)
        return jsonify({
            "department": DEMO_DEPARTMENT,
            "ticket_types": [DEMO_TYPE_REPORTE, DEMO_TYPE_ASIGNACION],
            "entities": DEMO_ENTITIES,
            "demo": True,
        })

    dept = supabase.table("departments").select("id, slug, name").eq("slug", slug).single().execute()
    if not dept.data:
        return error("Departamento no encontrado", 404)
    types = supabase.table("ticket_types").select("*").eq("department_id", dept.data["id"]).execute()
    entities = supabase.table("entities").select("*").eq("department_id", dept.data["id"]).execute()
    return jsonify({
        "department": dept.data,
        "ticket_types": types.data or [],
        "entities": entities.data or [],
        "demo": False,
    })


@public_bp.post("/api/departments/<slug>/tickets")
def create_ticket(slug: str):
    payload = request.get_json(silent=True) or {}
    nombre = (payload.get("solicitante_nombre") or "").strip()
    correo = (payload.get("solicitante_email") or "").strip()
    ticket_type_id = payload.get("ticket_type_id")
    if not ticket_type_id:
        return error("ticket_type_id es requerido", 400)
    if len(nombre) < 2:
        return error("solicitante_nombre es requerido", 400)
    if len(correo) < 5:
        return error("solicitante_email es requerido", 400)
    campos = payload.get("campos") or {}
    entity_id = payload.get("entity_id") or None

    if not supabase:
        if slug != "flota":
            return error("Departamento no encontrado", 404)
        ticket = {
            "id": str(uuid4()),
            "folio": f"TKT-{uuid4().hex[:8].upper()}",
            "department_id": DEMO_DEPARTMENT["id"],
            "ticket_type_id": ticket_type_id,
            "estado": "Abierto",
            "solicitante_nombre": nombre,
            "solicitante_email": correo,
            "created_at": now(),
            "campos": campos,
        }
        DEMO_TICKETS.insert(0, ticket)
        return jsonify(ticket), 201

    department_result = supabase.table("departments").select("id").eq("slug", slug).single().execute()
    if not department_result.data:
        return error("Departamento no encontrado", 404)
    record = {
        "ticket_type_id": ticket_type_id,
        "entity_id": entity_id,
        "solicitante_nombre": nombre,
        "solicitante_email": correo,
        "campos": campos,
        "department_id": department_result.data["id"],
        "estado": "Abierto",
    }
    result = supabase.table("tickets").insert(record).execute()
    if not result.data:
        return error("No se pudo crear el ticket", 400)
    ticket = result.data[0]
    supabase.table("ticket_events").insert({"ticket_id": ticket["id"], "accion": "creado", "estado_nuevo": "Abierto"}).execute()
    return jsonify(ticket), 201
