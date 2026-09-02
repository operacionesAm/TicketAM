"""Administrador global: por encima de los admins de cada departamento
("sistema de tickets"). Ve todos los departamentos, verifica que cada uno
tenga su PIN configurado, puede crear departamentos nuevos y resetear el PIN
de cualquiera. Login separado (contraseña maestra en `GLOBAL_ADMIN_PASSCODE`,
no una fila en `departments`) y sesión propia (`session["is_global_admin"]`)
— completamente aparte de la sesión de admin de departamento, para no mezclar
el alcance de una con el de la otra.
"""
import os
import secrets
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash

from app import crypto
from app.extensions import supabase

global_admin_bp = Blueprint("global_admin", __name__)

DEFAULT_TICKET_TYPES = [
    {
        "name": "Reporte de falla",
        "campos_config": [
            {"key": "departamento_solicitante", "label": "Departamento", "type": "text", "required": True},
            {"key": "numero_nomina", "label": "Número de nómina", "type": "text", "required": False},
            {"key": "descripcion", "label": "Describe la falla", "type": "textarea", "required": True},
        ],
        "estados": ["Abierto", "Pendiente", "En progreso", "Resuelto", "Cerrado"],
    },
    {
        "name": "Solicitud de vehículo",
        "campos_config": [
            {"key": "departamento_solicitante", "label": "Departamento", "type": "text", "required": True},
            {"key": "numero_nomina", "label": "Número de nómina", "type": "text", "required": True},
            {"key": "proposito", "label": "Propósito / Destino", "type": "text", "required": True},
        ],
        "estados": ["Abierto", "Pendiente", "Asignado", "Negado"],
    },
    {
        "name": "Ticket de Mantenimiento",
        "campos_config": [
            {"key": "pieza_refaccion", "label": "Pieza o refacción", "type": "text", "required": True},
            {"key": "departamento_solicitante", "label": "Departamento", "type": "text", "required": True},
            {"key": "observaciones", "label": "Observaciones", "type": "textarea", "required": False},
        ],
        "estados": ["Abierto", "Pendiente", "En progreso", "Resuelto", "Cerrado"],
    },
]

ESTADOS_FINALES = {"Resuelto", "Cerrado", "Asignado", "Negado"}


def error(message: str, status: int):
    return jsonify({"detail": message}), status


def valid_passcode(passcode: str) -> bool:
    return passcode.isdigit() and 4 <= len(passcode) <= 8


def passcode_updates(passcode: str) -> dict:
    """admin_passcode_hash es lo único que usa el login (app/routes/admin.py,
    no cambia); admin_passcode_encrypted es la copia reversible que solo
    existe para poder mostrar el NIP en "Más detalles" — si no hay llave de
    cifrado configurada, simplemente se omite esa columna."""
    updates = {"admin_passcode_hash": generate_password_hash(passcode)}
    if crypto.is_configured():
        updates["admin_passcode_encrypted"] = crypto.encrypt_passcode(passcode)
    return updates


def require_global_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_global_admin"):
            return error("No has iniciado sesión", 401)
        return fn(*args, **kwargs)

    return wrapper


@global_admin_bp.post("/api/global/login")
def global_login():
    if not supabase:
        return error("El administrador global requiere Supabase configurado", 400)
    master_passcode = os.environ.get("GLOBAL_ADMIN_PASSCODE")
    if not master_passcode:
        return error("GLOBAL_ADMIN_PASSCODE no está configurado en el servidor", 400)

    payload = request.get_json(silent=True) or {}
    passcode = (payload.get("passcode") or "").strip()
    if not passcode or not secrets.compare_digest(passcode, master_passcode):
        return error("Contraseña incorrecta", 401)

    session["is_global_admin"] = True
    return jsonify({"ok": True})


@global_admin_bp.post("/api/global/logout")
def global_logout():
    session.pop("is_global_admin", None)
    return jsonify({"ok": True})


@global_admin_bp.get("/api/global/me")
@require_global_admin
def global_me():
    return jsonify({"ok": True})


@global_admin_bp.get("/api/global/departments")
@require_global_admin
def global_list_departments():
    departments = supabase.table("departments").select(
        "id, slug, name, admin_passcode_hash, notification_email, google_connected_email, created_at"
    ).order("created_at").execute().data or []

    result = []
    for dept in departments:
        tickets = supabase.table("tickets").select("estado").eq("department_id", dept["id"]).execute().data or []
        abiertos = sum(1 for t in tickets if t["estado"] not in ESTADOS_FINALES)
        result.append({
            "id": dept["id"],
            "slug": dept["slug"],
            "name": dept["name"],
            "passcode_configurado": bool(dept.get("admin_passcode_hash")),
            "notification_email": dept.get("notification_email"),
            "google_connected_email": dept.get("google_connected_email"),
            "created_at": dept.get("created_at"),
            "total_tickets": len(tickets),
            "tickets_abiertos": abiertos,
        })
    return jsonify({"departments": result})


@global_admin_bp.post("/api/global/departments")
@require_global_admin
def global_create_department():
    payload = request.get_json(silent=True) or {}
    slug = (payload.get("slug") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    passcode = (payload.get("passcode") or "").strip()

    if not slug or not name:
        return error("slug y name son requeridos", 400)
    if not valid_passcode(passcode):
        return error("El NIP debe ser numérico, de 4 a 8 dígitos", 400)

    existing = supabase.table("departments").select("id").eq("slug", slug).execute().data
    if existing:
        return error("Ya existe un departamento con ese slug", 400)

    dept_result = supabase.table("departments").insert({
        "slug": slug,
        "name": name,
        **passcode_updates(passcode),
    }).execute()
    if not dept_result.data:
        return error("No se pudo crear el departamento", 400)
    department_id = dept_result.data[0]["id"]

    for ticket_type in DEFAULT_TICKET_TYPES:
        supabase.table("ticket_types").insert({
            "department_id": department_id,
            "name": ticket_type["name"],
            "campos_config": ticket_type["campos_config"],
            "estados": ticket_type["estados"],
        }).execute()

    return jsonify({"department": dept_result.data[0]}), 201


@global_admin_bp.patch("/api/global/departments/<department_id>/passcode")
@require_global_admin
def global_reset_passcode(department_id: str):
    payload = request.get_json(silent=True) or {}
    passcode = (payload.get("passcode") or "").strip()
    if not valid_passcode(passcode):
        return error("El NIP debe ser numérico, de 4 a 8 dígitos", 400)

    result = supabase.table("departments").update(passcode_updates(passcode)).eq("id", department_id).execute()
    if not result.data:
        return error("Departamento no encontrado", 404)
    return jsonify({"ok": True})


@global_admin_bp.get("/api/global/departments/<department_id>/detail")
@require_global_admin
def global_department_detail(department_id: str):
    """Todo lo que el Administrador Global puede ver de un sistema de
    tickets: nunca el contenido de un ticket individual (folio, solicitante,
    descripción), solo agregados — conteos, promedios, distribución por
    tipo — más el NIP actual (si hay copia cifrada) y los datos de
    configuración del departamento."""
    dept = supabase.table("departments").select(
        "id, slug, name, admin_passcode_encrypted, notification_email, google_connected_email, created_at"
    ).eq("id", department_id).single().execute()
    if not dept.data:
        return error("Departamento no encontrado", 404)

    tickets = supabase.table("tickets").select("estado, ticket_type_id, created_at, resolved_at").eq("department_id", department_id).execute().data or []
    types = supabase.table("ticket_types").select("id, name").eq("department_id", department_id).execute().data or []
    entities = supabase.table("entities").select("atributos").eq("department_id", department_id).execute().data or []

    type_names = {t["id"]: t["name"] for t in types}
    por_tipo = {}
    for t in tickets:
        name = type_names.get(t["ticket_type_id"], "Otro")
        por_tipo[name] = por_tipo.get(name, 0) + 1

    def parse_ts(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    resueltos_con_tiempo = [t for t in tickets if t.get("resolved_at")]
    promedio_dias = None
    if resueltos_con_tiempo:
        total_dias = sum((parse_ts(t["resolved_at"]) - parse_ts(t["created_at"])).total_seconds() / 86400 for t in resueltos_con_tiempo)
        promedio_dias = round(total_dias / len(resueltos_con_tiempo), 1)

    vehiculos_activos = sum(1 for e in entities if (e.get("atributos") or {}).get("estado") != "Inactivo")

    return jsonify({
        "id": dept.data["id"],
        "slug": dept.data["slug"],
        "name": dept.data["name"],
        "nip_actual": crypto.decrypt_passcode(dept.data.get("admin_passcode_encrypted")),
        "notification_email": dept.data.get("notification_email"),
        "google_connected_email": dept.data.get("google_connected_email"),
        "created_at": dept.data.get("created_at"),
        "total_tickets": len(tickets),
        "abiertos": sum(1 for t in tickets if t["estado"] not in ESTADOS_FINALES),
        "resueltos": sum(1 for t in tickets if t["estado"] in ESTADOS_FINALES),
        "por_tipo": por_tipo,
        "promedio_dias_solucion": promedio_dias,
        "vehiculos_total": len(entities),
        "vehiculos_activos": vehiculos_activos,
    })
