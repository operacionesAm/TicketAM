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
from app.mailer import send_ticket_notification
from app.photos import upload_photo

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
    foto_base64 = payload.get("foto_base64") or None

    if not supabase:
        if slug != "flota":
            return error("Departamento no encontrado", 404)
        if ticket_type_id == DEMO_TYPE_REPORTE["id"] and not entity_id:
            return error("Un reporte de falla debe tener un vehículo asociado", 400)
        # Una "Solicitud de vehículo" que ya trae entity_id vino de escanear el
        # QR directamente (solo circulación tiene acceso físico a los QR sin
        # tener antes un vehículo asignado) — se autoasigna sin pasar por
        # revisión del admin. Ver create_ticket() para el mismo criterio en
        # el branch de Supabase.
        estado_inicial = "Asignado" if (ticket_type_id == DEMO_TYPE_ASIGNACION["id"] and entity_id) else "Abierto"
        ticket = {
            "id": str(uuid4()),
            "folio": f"TKT-{uuid4().hex[:8].upper()}",
            "department_id": DEMO_DEPARTMENT["id"],
            "ticket_type_id": ticket_type_id,
            "entity_id": entity_id,
            "estado": estado_inicial,
            "solicitante_nombre": nombre,
            "solicitante_email": correo,
            "created_at": now(),
            "campos": campos,
        }
        if estado_inicial == "Asignado":
            ticket["resolved_at"] = now()
        DEMO_TICKETS.insert(0, ticket)
        send_ticket_notification(DEMO_DEPARTMENT, ticket)
        return jsonify(ticket), 201

    department_result = supabase.table("departments").select("id, name, notification_email, google_refresh_token").eq("slug", slug).single().execute()
    if not department_result.data:
        return error("Departamento no encontrado", 404)
    department_id = department_result.data["id"]

    type_result = supabase.table("ticket_types").select("name").eq("id", ticket_type_id).single().execute()
    if not type_result.data:
        return error("Tipo de ticket no encontrado", 404)
    if type_result.data["name"] == "Reporte de falla" and not entity_id:
        return error("Un reporte de falla debe tener un vehículo asociado", 400)

    if foto_base64 and type_result.data["name"] == "Reporte de falla":
        try:
            campos["foto_path"] = upload_photo(supabase, department_id, foto_base64)
        except Exception as exc:
            print(f"[photos] No se pudo subir la foto del reporte: {exc}")

    # Una "Solicitud de vehículo" que ya trae entity_id vino de escanear el QR
    # directamente — solo circulación tiene acceso físico a los QR sin tener
    # antes un vehículo asignado, así que se autoasigna sin pasar por revisión
    # de Carlos. La solicitud normal (sin escaneo) nunca manda entity_id.
    estado_inicial = "Asignado" if (type_result.data["name"] == "Solicitud de vehículo" and entity_id) else "Abierto"

    record = {
        "ticket_type_id": ticket_type_id,
        "entity_id": entity_id,
        "solicitante_nombre": nombre,
        "solicitante_email": correo,
        "campos": campos,
        "department_id": department_id,
        "estado": estado_inicial,
    }
    if estado_inicial == "Asignado":
        record["resolved_at"] = now()
    result = supabase.table("tickets").insert(record).execute()
    if not result.data:
        return error("No se pudo crear el ticket", 400)
    ticket = result.data[0]
    supabase.table("ticket_events").insert({"ticket_id": ticket["id"], "accion": "creado", "estado_nuevo": estado_inicial}).execute()
    send_ticket_notification(department_result.data, ticket)
    return jsonify(ticket), 201
