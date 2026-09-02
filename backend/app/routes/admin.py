"""Rutas de administrador: login por contraseña de 8 dígitos y panel.

Cada departamento tiene su propia contraseña (hasheada en
departments.admin_passcode_hash, ver scripts/set_passcode.py). Ingresarla
identifica el departamento automáticamente y abre una sesión de Flask
(cookie httponly) que las demás rutas /api/admin/* exigen y usan para
limitar cada operación al departamento de esa sesión.
"""
import base64
import calendar
import os
import secrets
from datetime import datetime, timezone
from functools import wraps
from uuid import uuid4

from flask import Blueprint, Response, jsonify, redirect, request, session
from werkzeug.security import check_password_hash

from app import google_oauth
from app.demo_data import DEMO_ADMIN_PASSCODES, DEMO_DEPARTMENT, DEMO_ENTITIES, DEMO_SERVICIOS, DEMO_TICKET_EVENTS, DEMO_TICKETS, DEMO_TYPE_ASIGNACION, DEMO_TYPE_REPORTE
from app.extensions import supabase
from app.mailer import send_observation_email, send_status_update_email, send_vehicle_assigned_email
from app.photos import download_photo
from app.qr import entity_qr_url, generate_labeled_qr_png

admin_bp = Blueprint("admin", __name__)


def public_base_url() -> str:
    """Dominio publico al que apunta el QR. En produccion front y back
    comparten dominio (ver vercel.json), asi que request.host_url ya es
    correcto sin configurar nada. PUBLIC_BASE_URL solo hace falta para
    pruebas locales del backend sin frontend en el mismo origen.
    """
    return os.environ.get("PUBLIC_BASE_URL") or request.host_url.rstrip("/")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_one_month(dt: datetime) -> datetime:
    """Suma un mes calendario, ajustando el día si el mes destino es más
    corto (31 ene -> 28/29 feb, no 3 mar)."""
    year = dt.year + dt.month // 12
    month = dt.month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def error(message: str, status: int):
    return jsonify({"detail": message}), status


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("department_id"):
            return error("No has iniciado sesión", 401)
        return fn(*args, **kwargs)

    return wrapper


@admin_bp.post("/api/admin/login")
def admin_login():
    payload = request.get_json(silent=True) or {}
    passcode = (payload.get("passcode") or "").strip()
    if not passcode:
        return error("Ingresa tu contraseña", 400)

    if not supabase:
        dept = DEMO_ADMIN_PASSCODES.get(passcode)
        if not dept:
            return error("Contraseña incorrecta", 401)
        session["department_id"] = dept["id"]
        session["department_slug"] = dept["slug"]
        session["department_name"] = dept["name"]
        return jsonify({"department": {"slug": dept["slug"], "name": dept["name"]}})

    rows = supabase.table("departments").select("id, slug, name, admin_passcode_hash").execute().data or []
    for row in rows:
        stored_hash = row.get("admin_passcode_hash")
        if stored_hash and check_password_hash(stored_hash, passcode):
            session["department_id"] = row["id"]
            session["department_slug"] = row["slug"]
            session["department_name"] = row["name"]
            return jsonify({"department": {"slug": row["slug"], "name": row["name"]}})

    return error("Contraseña incorrecta", 401)


@admin_bp.post("/api/admin/logout")
def admin_logout():
    session.clear()
    return jsonify({"ok": True})


@admin_bp.get("/api/admin/me")
@require_admin
def admin_me():
    return jsonify({"department": {"slug": session["department_slug"], "name": session["department_name"]}})


@admin_bp.get("/api/admin/tickets")
@require_admin
def admin_tickets():
    department_id = session["department_id"]

    if not supabase:
        tickets = [t for t in DEMO_TICKETS if t["department_id"] == department_id]
        return jsonify({"tickets": tickets, "ticket_types": [DEMO_TYPE_REPORTE, DEMO_TYPE_ASIGNACION], "demo": True})

    tickets = supabase.table("tickets").select("*").eq("department_id", department_id).order("created_at", desc=True).execute()
    types = supabase.table("ticket_types").select("*").eq("department_id", department_id).execute()
    return jsonify({"tickets": tickets.data or [], "ticket_types": types.data or [], "demo": False})


@admin_bp.patch("/api/admin/tickets/<ticket_id>/classify")
@require_admin
def admin_classify_ticket(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    incidente_tipo = payload.get("incidente_tipo") or None
    prioridad = payload.get("prioridad") or None
    if prioridad and prioridad not in {"Alta", "Media", "Baja"}:
        return error("prioridad debe ser Alta, Media o Baja", 400)
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        ticket["incidente_tipo"] = incidente_tipo
        ticket["prioridad"] = prioridad
        return jsonify({"ticket": ticket})

    current = supabase.table("tickets").select("department_id").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)
    updated = supabase.table("tickets").update({"incidente_tipo": incidente_tipo, "prioridad": prioridad}).eq("id", ticket_id).execute()
    supabase.table("ticket_events").insert({
        "ticket_id": ticket_id,
        "accion": "clasificado",
        "comentario": f"{incidente_tipo or '—'} · prioridad {prioridad or '—'}",
    }).execute()
    return jsonify({"ticket": updated.data[0]})


@admin_bp.patch("/api/admin/tickets/<ticket_id>/status")
@require_admin
def admin_update_status(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    estado = payload.get("estado")
    comentario = payload.get("comentario", "")
    if not estado:
        return error("estado es requerido", 400)
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        previous = ticket["estado"]
        ticket["estado"] = estado
        send_status_update_email(DEMO_DEPARTMENT, ticket, previous)
        return jsonify({"ticket": ticket, "event": {"accion": "cambio_estado", "estado_anterior": previous, "estado_nuevo": estado, "comentario": comentario}})

    current = supabase.table("tickets").select("estado, department_id").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)
    updated = supabase.table("tickets").update({"estado": estado, "resolved_at": now() if estado in {"Resuelto", "Cerrado", "Asignado", "Negado"} else None}).eq("id", ticket_id).execute()
    supabase.table("ticket_events").insert({"ticket_id": ticket_id, "accion": "cambio_estado", "estado_anterior": current.data["estado"], "estado_nuevo": estado, "comentario": comentario}).execute()
    dept = supabase.table("departments").select("name, google_refresh_token").eq("id", department_id).single().execute()
    send_status_update_email(dept.data or {}, updated.data[0], current.data["estado"])
    return jsonify({"ticket": updated.data[0], "event": {"accion": "cambio_estado"}})


@admin_bp.patch("/api/admin/tickets/<ticket_id>/responsable")
@require_admin
def admin_assign_responsable(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    responsable_nombre = (payload.get("responsable_nombre") or "").strip() or None
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        ticket["responsable_nombre"] = responsable_nombre
        return jsonify({"ticket": ticket})

    current = supabase.table("tickets").select("department_id").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)
    updated = supabase.table("tickets").update({"responsable_nombre": responsable_nombre}).eq("id", ticket_id).execute()
    supabase.table("ticket_events").insert({
        "ticket_id": ticket_id,
        "accion": "responsable_asignado",
        "comentario": responsable_nombre or "(sin asignar)",
    }).execute()
    return jsonify({"ticket": updated.data[0]})


@admin_bp.patch("/api/admin/tickets/<ticket_id>/vehiculo")
@require_admin
def admin_assign_vehiculo(ticket_id: str):
    """Autoriza una "Solicitud de vehículo": Carlos elige una unidad activa
    del inventario y, en el mismo paso, el ticket pasa a estado "Asignado" y
    se le avisa al solicitante por correo (incluye el aviso de llevar copia
    de su licencia). Mandar entity_id vacío solo quita la asignación, sin
    tocar el estado."""
    payload = request.get_json(silent=True) or {}
    entity_id = payload.get("entity_id") or None
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        if not entity_id:
            ticket["entity_id"] = None
            return jsonify({"ticket": ticket})
        entity = next((e for e in DEMO_ENTITIES if e["id"] == entity_id and e["department_id"] == department_id), None)
        if not entity:
            return error("Vehículo no encontrado", 404)
        if (entity.get("atributos") or {}).get("estado") == "Inactivo":
            return error("Solo se pueden asignar vehículos activos", 400)
        ticket["entity_id"] = entity_id
        ticket["estado"] = "Asignado"
        send_vehicle_assigned_email(DEMO_DEPARTMENT, ticket, entity)
        return jsonify({"ticket": ticket})

    current = supabase.table("tickets").select("*").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)

    if not entity_id:
        updated = supabase.table("tickets").update({"entity_id": None}).eq("id", ticket_id).execute()
        return jsonify({"ticket": updated.data[0]})

    entity_result = supabase.table("entities").select("*").eq("id", entity_id).single().execute()
    if not entity_result.data or entity_result.data["department_id"] != department_id:
        return error("Vehículo no encontrado", 404)
    if (entity_result.data.get("atributos") or {}).get("estado") == "Inactivo":
        return error("Solo se pueden asignar vehículos activos", 400)

    updated = supabase.table("tickets").update({
        "entity_id": entity_id,
        "estado": "Asignado",
        "resolved_at": now(),
    }).eq("id", ticket_id).execute()
    supabase.table("ticket_events").insert({
        "ticket_id": ticket_id,
        "accion": "vehiculo_asignado",
        "estado_anterior": current.data["estado"],
        "estado_nuevo": "Asignado",
        "comentario": f"Vehículo asignado: {entity_result.data['codigo']}",
    }).execute()
    dept = supabase.table("departments").select("name, google_refresh_token").eq("id", department_id).single().execute()
    send_vehicle_assigned_email(dept.data or {}, updated.data[0], entity_result.data)
    return jsonify({"ticket": updated.data[0]})


@admin_bp.post("/api/admin/tickets/<ticket_id>/observaciones")
@require_admin
def admin_add_observacion(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    comentario = (payload.get("comentario") or "").strip()
    notificar_email = bool(payload.get("notificar_email"))
    if not comentario:
        return error("La observación no puede estar vacía", 400)
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        event = {
            "id": str(uuid4()), "ticket_id": ticket_id, "accion": "observacion",
            "estado_anterior": None, "estado_nuevo": None, "comentario": comentario, "created_at": now(),
        }
        DEMO_TICKET_EVENTS.insert(0, event)
        if notificar_email:
            send_observation_email(DEMO_DEPARTMENT, ticket, comentario)
        return jsonify({"event": event}), 201

    current = supabase.table("tickets").select("*").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)
    result = supabase.table("ticket_events").insert({"ticket_id": ticket_id, "accion": "observacion", "comentario": comentario}).execute()
    if notificar_email:
        dept = supabase.table("departments").select("name, google_refresh_token").eq("id", department_id).single().execute()
        send_observation_email(dept.data or {}, current.data, comentario)
    return jsonify({"event": result.data[0]}), 201


@admin_bp.get("/api/admin/tickets/<ticket_id>/foto")
@require_admin
def admin_ticket_foto(ticket_id: str):
    department_id = session["department_id"]

    if not supabase:
        ticket = next((item for item in DEMO_TICKETS if item["id"] == ticket_id and item["department_id"] == department_id), None)
        if not ticket:
            return error("Ticket no encontrado", 404)
        return error("Sin foto (modo demo)", 404)

    current = supabase.table("tickets").select("campos, department_id").eq("id", ticket_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Ticket no encontrado", 404)
    foto_path = (current.data.get("campos") or {}).get("foto_path")
    if not foto_path:
        return error("Este ticket no tiene foto", 404)

    try:
        image_bytes = download_photo(supabase, foto_path)
    except Exception:
        return error("No se pudo cargar la foto", 404)
    return Response(image_bytes, mimetype="image/jpeg")


@admin_bp.get("/api/admin/entities")
@require_admin
def admin_list_entities():
    department_id = session["department_id"]

    if not supabase:
        entities = [e for e in DEMO_ENTITIES if e["department_id"] == department_id]
        return jsonify({"entities": entities, "demo": True})

    result = supabase.table("entities").select("*").eq("department_id", department_id).order("codigo").execute()
    return jsonify({"entities": result.data or [], "demo": False})


@admin_bp.post("/api/admin/entities")
@require_admin
def admin_create_entity():
    payload = request.get_json(silent=True) or {}
    codigo = (payload.get("codigo") or "").strip().upper()
    if not codigo:
        return error("La placa (codigo) es requerida", 400)
    nombre = (payload.get("nombre") or "").strip()
    atributos = payload.get("atributos") or {}
    department_id = session["department_id"]

    if not supabase:
        if any(e["codigo"] == codigo and e["department_id"] == department_id for e in DEMO_ENTITIES):
            return error("Ya existe un vehículo con esa placa", 400)
        entity = {"id": str(uuid4()), "department_id": department_id, "codigo": codigo, "nombre": nombre, "atributos": atributos}
        DEMO_ENTITIES.append(entity)
        qr_b64 = base64.b64encode(generate_labeled_qr_png(entity_qr_url(public_base_url(), codigo), codigo, nombre)).decode("ascii")
        return jsonify({"entity": entity, "qr_base64": qr_b64}), 201

    record = {"department_id": department_id, "codigo": codigo, "nombre": nombre, "atributos": atributos}
    result = supabase.table("entities").insert(record).execute()
    if not result.data:
        return error("No se pudo crear el vehículo (¿la placa ya existe?)", 400)
    entity = result.data[0]
    qr_b64 = base64.b64encode(generate_labeled_qr_png(entity_qr_url(public_base_url(), codigo), codigo, nombre)).decode("ascii")
    return jsonify({"entity": entity, "qr_base64": qr_b64}), 201


@admin_bp.patch("/api/admin/entities/<entity_id>")
@require_admin
def admin_update_entity(entity_id: str):
    payload = request.get_json(silent=True) or {}
    department_id = session["department_id"]

    nuevo_codigo = payload.get("codigo")
    if nuevo_codigo is not None:
        nuevo_codigo = nuevo_codigo.strip().upper()
        if not nuevo_codigo:
            return error("La placa no puede quedar vacía", 400)
    nuevo_nombre = payload.get("nombre")
    nuevos_atributos = payload.get("atributos")
    if nuevo_codigo is None and nuevo_nombre is None and nuevos_atributos is None:
        return error("Nada que actualizar", 400)

    if not supabase:
        entity = next((e for e in DEMO_ENTITIES if e["id"] == entity_id and e["department_id"] == department_id), None)
        if not entity:
            return error("Vehículo no encontrado", 404)
        if nuevo_codigo is not None and any(e["codigo"] == nuevo_codigo and e["id"] != entity_id and e["department_id"] == department_id for e in DEMO_ENTITIES):
            return error("Ya existe un vehículo con esa placa", 400)
        if nuevo_codigo is not None:
            entity["codigo"] = nuevo_codigo
        if nuevo_nombre is not None:
            entity["nombre"] = nuevo_nombre
        if nuevos_atributos is not None:
            entity["atributos"] = {**entity.get("atributos", {}), **nuevos_atributos}
        return jsonify({"entity": entity})

    current = supabase.table("entities").select("*").eq("id", entity_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Vehículo no encontrado", 404)

    updates = {}
    if nuevo_codigo is not None:
        updates["codigo"] = nuevo_codigo
    if nuevo_nombre is not None:
        updates["nombre"] = nuevo_nombre
    if nuevos_atributos is not None:
        updates["atributos"] = {**(current.data.get("atributos") or {}), **nuevos_atributos}

    result = supabase.table("entities").update(updates).eq("id", entity_id).execute()
    if not result.data:
        return error("No se pudo actualizar el vehículo (¿la placa ya existe?)", 400)
    return jsonify({"entity": result.data[0]})


@admin_bp.delete("/api/admin/entities/<entity_id>")
@require_admin
def admin_delete_entity(entity_id: str):
    department_id = session["department_id"]

    if not supabase:
        before = len(DEMO_ENTITIES)
        DEMO_ENTITIES[:] = [e for e in DEMO_ENTITIES if not (e["id"] == entity_id and e["department_id"] == department_id)]
        if len(DEMO_ENTITIES) == before:
            return error("Vehículo no encontrado", 404)
        return jsonify({"ok": True})

    current = supabase.table("entities").select("department_id").eq("id", entity_id).single().execute()
    if not current.data or current.data["department_id"] != department_id:
        return error("Vehículo no encontrado", 404)
    supabase.table("entities").delete().eq("id", entity_id).execute()
    return jsonify({"ok": True})


@admin_bp.get("/api/admin/entities/<entity_id>/qr")
@require_admin
def admin_entity_qr(entity_id: str):
    department_id = session["department_id"]

    if not supabase:
        entity = next((e for e in DEMO_ENTITIES if e["id"] == entity_id and e["department_id"] == department_id), None)
        if not entity:
            return error("Vehículo no encontrado", 404)
        codigo, nombre = entity["codigo"], entity.get("nombre", "")
    else:
        current = supabase.table("entities").select("codigo, nombre, department_id").eq("id", entity_id).single().execute()
        if not current.data or current.data["department_id"] != department_id:
            return error("Vehículo no encontrado", 404)
        codigo, nombre = current.data["codigo"], current.data.get("nombre", "")

    png_bytes = generate_labeled_qr_png(entity_qr_url(public_base_url(), codigo), codigo, nombre)
    return Response(png_bytes, mimetype="image/png", headers={"Content-Disposition": f'inline; filename="qr-{codigo}.png"'})


@admin_bp.get("/api/admin/servicios")
@require_admin
def admin_list_servicios():
    department_id = session["department_id"]

    if not supabase:
        servicios = [s for s in DEMO_SERVICIOS if s["department_id"] == department_id]
        return jsonify({"servicios": servicios, "demo": True})

    result = supabase.table("servicios").select("*").eq("department_id", department_id).order("fecha", desc=True).execute()
    return jsonify({"servicios": result.data or [], "demo": False})


@admin_bp.post("/api/admin/servicios")
@require_admin
def admin_create_servicio():
    """Registra un servicio de moto (módulo "Servicios Programados"). Un
    preventivo calcula y guarda cuándo toca el siguiente (fecha + 1 mes); un
    correctivo solo queda en la bitácora, sin afectar ese conteo."""
    payload = request.get_json(silent=True) or {}
    entity_id = payload.get("entity_id")
    tipo = payload.get("tipo")
    notas = (payload.get("notas") or "").strip() or None
    fecha_raw = payload.get("fecha")
    department_id = session["department_id"]

    if not entity_id:
        return error("entity_id es requerido", 400)
    if tipo not in {"preventivo", "correctivo"}:
        return error("tipo debe ser 'preventivo' o 'correctivo'", 400)

    try:
        fecha_dt = datetime.fromisoformat(fecha_raw) if fecha_raw else datetime.now(timezone.utc)
    except ValueError:
        return error("fecha inválida", 400)
    if fecha_dt.tzinfo is None:
        fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
    fecha_iso = fecha_dt.isoformat()
    proximo_iso = add_one_month(fecha_dt).isoformat() if tipo == "preventivo" else None

    if not supabase:
        entity = next((e for e in DEMO_ENTITIES if e["id"] == entity_id and e["department_id"] == department_id), None)
        if not entity:
            return error("Vehículo no encontrado", 404)
        if (entity.get("atributos") or {}).get("tipo") != "Motocicleta":
            return error("Los servicios programados solo aplican a motocicletas", 400)
        servicio = {
            "id": str(uuid4()), "department_id": department_id, "entity_id": entity_id,
            "tipo": tipo, "fecha": fecha_iso, "proximo_servicio_fecha": proximo_iso,
            "notas": notas, "created_at": now(),
        }
        DEMO_SERVICIOS.insert(0, servicio)
        return jsonify({"servicio": servicio}), 201

    entity_result = supabase.table("entities").select("id, atributos, department_id").eq("id", entity_id).single().execute()
    if not entity_result.data or entity_result.data["department_id"] != department_id:
        return error("Vehículo no encontrado", 404)
    if (entity_result.data.get("atributos") or {}).get("tipo") != "Motocicleta":
        return error("Los servicios programados solo aplican a motocicletas", 400)

    record = {
        "department_id": department_id, "entity_id": entity_id, "tipo": tipo,
        "fecha": fecha_iso, "proximo_servicio_fecha": proximo_iso, "notas": notas,
    }
    result = supabase.table("servicios").insert(record).execute()
    if not result.data:
        return error("No se pudo registrar el servicio", 400)
    return jsonify({"servicio": result.data[0]}), 201


@admin_bp.get("/api/admin/settings")
@require_admin
def admin_get_settings():
    department_id = session["department_id"]

    if not supabase:
        return jsonify({
            "notification_email": DEMO_DEPARTMENT.get("notification_email"),
            "google_connected_email": DEMO_DEPARTMENT.get("google_connected_email"),
        })

    current = supabase.table("departments").select("notification_email, google_connected_email").eq("id", department_id).single().execute()
    data = current.data or {}
    return jsonify({
        "notification_email": data.get("notification_email"),
        "google_connected_email": data.get("google_connected_email"),
    })


@admin_bp.patch("/api/admin/settings")
@require_admin
def admin_update_settings():
    payload = request.get_json(silent=True) or {}
    notification_email = (payload.get("notification_email") or "").strip() or None
    department_id = session["department_id"]

    if not supabase:
        DEMO_DEPARTMENT["notification_email"] = notification_email
        return jsonify({"notification_email": notification_email})

    supabase.table("departments").update({"notification_email": notification_email}).eq("id", department_id).execute()
    return jsonify({"notification_email": notification_email})


@admin_bp.get("/api/admin/google/connect")
@require_admin
def admin_google_connect():
    if not google_oauth.is_configured():
        return error("La conexión con Google no está configurada en el servidor (faltan GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI).", 400)
    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    return redirect(google_oauth.build_auth_url(state))


@admin_bp.get("/api/admin/google/callback")
def admin_google_callback():
    # Nota: sin @require_admin — Google navega aquí directo, no manda la
    # sesión como fetch (sí manda la cookie porque es GET top-level, pero
    # validamos "state" contra la sesión en vez de asumir el decorador).
    if not session.get("department_id"):
        return redirect("/admin")

    state = request.args.get("state")
    if not state or state != session.get("google_oauth_state"):
        return redirect("/admin/configuracion?google=error")
    session.pop("google_oauth_state", None)

    code = request.args.get("code")
    if not code:
        return redirect("/admin/configuracion?google=error")

    try:
        result = google_oauth.exchange_code(code)
    except Exception:
        return redirect("/admin/configuracion?google=error")

    if not result.get("refresh_token"):
        # Ya estaba conectado y Google no reenvió refresh_token; nada que guardar.
        return redirect("/admin/configuracion?google=error")

    department_id = session["department_id"]
    if not supabase:
        DEMO_DEPARTMENT["google_refresh_token"] = result["refresh_token"]
        DEMO_DEPARTMENT["google_connected_email"] = result.get("email")
    else:
        supabase.table("departments").update({
            "google_refresh_token": result["refresh_token"],
            "google_connected_email": result.get("email"),
        }).eq("id", department_id).execute()

    return redirect("/admin/configuracion?google=connected")


@admin_bp.post("/api/admin/google/disconnect")
@require_admin
def admin_google_disconnect():
    department_id = session["department_id"]
    if not supabase:
        DEMO_DEPARTMENT["google_refresh_token"] = None
        DEMO_DEPARTMENT["google_connected_email"] = None
        return jsonify({"ok": True})
    supabase.table("departments").update({"google_refresh_token": None, "google_connected_email": None}).eq("id", department_id).execute()
    return jsonify({"ok": True})


@admin_bp.get("/api/admin/events")
@require_admin
def admin_list_events():
    department_id = session["department_id"]
    entity_id = request.args.get("entity_id") or None
    ticket_id = request.args.get("ticket_id") or None

    if not supabase:
        ticket_ids = {
            t["id"] for t in DEMO_TICKETS
            if t["department_id"] == department_id
            and (entity_id is None or t.get("entity_id") == entity_id)
            and (ticket_id is None or t["id"] == ticket_id)
        }
        events = [e for e in DEMO_TICKET_EVENTS if e["ticket_id"] in ticket_ids]
        events.sort(key=lambda e: e["created_at"], reverse=True)
        return jsonify({"events": events, "demo": True})

    tickets_query = supabase.table("tickets").select("id").eq("department_id", department_id)
    if entity_id:
        tickets_query = tickets_query.eq("entity_id", entity_id)
    if ticket_id:
        tickets_query = tickets_query.eq("id", ticket_id)
    ticket_ids = [row["id"] for row in (tickets_query.execute().data or [])]
    if not ticket_ids:
        return jsonify({"events": [], "demo": False})

    events = supabase.table("ticket_events").select("*").in_("ticket_id", ticket_ids).order("created_at", desc=True).limit(200).execute()
    return jsonify({"events": events.data or [], "demo": False})
