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
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash

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
]

ESTADOS_FINALES = {"Resuelto", "Cerrado", "Asignado", "Negado"}


def error(message: str, status: int):
    return jsonify({"detail": message}), status


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
    if not (passcode.isdigit() and len(passcode) == 8):
        return error("La contraseña debe ser de exactamente 8 dígitos", 400)

    existing = supabase.table("departments").select("id").eq("slug", slug).execute().data
    if existing:
        return error("Ya existe un departamento con ese slug", 400)

    dept_result = supabase.table("departments").insert({
        "slug": slug,
        "name": name,
        "admin_passcode_hash": generate_password_hash(passcode),
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
    if not (passcode.isdigit() and len(passcode) == 8):
        return error("La contraseña debe ser de exactamente 8 dígitos", 400)

    result = supabase.table("departments").update({
        "admin_passcode_hash": generate_password_hash(passcode)
    }).eq("id", department_id).execute()
    if not result.data:
        return error("Departamento no encontrado", 404)
    return jsonify({"ok": True})
