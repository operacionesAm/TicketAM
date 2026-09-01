"""Datos de demostración usados cuando no hay credenciales de Supabase.

Permiten correr y revisar toda la interfaz (pública y admin) sin depender de
una base de datos real. DEMO_TICKETS se muta en memoria durante la sesión del
proceso (se pierde al reiniciar el servidor) para simular creación y cambios
de estatus.
"""

DEMO_DEPARTMENT = {
    "id": "demo-flota", "slug": "flota", "name": "Flota",
    "notification_email": None, "google_refresh_token": None, "google_connected_email": None,
}

DEMO_TYPE_REPORTE = {
    "id": "demo-reporte",
    "department_id": "demo-flota",
    "name": "Reporte de falla",
    "campos_config": [
        {"key": "departamento_solicitante", "label": "Departamento", "type": "text", "required": True},
        {"key": "numero_nomina", "label": "Número de nómina", "type": "text", "required": False},
        {"key": "descripcion", "label": "Describe la falla", "type": "textarea", "required": True},
    ],
    "estados": ["Abierto", "Pendiente", "En progreso", "Resuelto", "Cerrado"],
}

DEMO_TYPE_ASIGNACION = {
    "id": "demo-asignacion",
    "department_id": "demo-flota",
    "name": "Solicitud de vehículo",
    "campos_config": [
        {"key": "departamento_solicitante", "label": "Departamento", "type": "text", "required": True},
        {"key": "numero_nomina", "label": "Número de nómina", "type": "text", "required": True},
        {"key": "proposito", "label": "Propósito / Destino", "type": "text", "required": True},
    ],
    "estados": ["Abierto", "Pendiente", "Asignado", "Negado"],
}

DEMO_ENTITIES = [
    {"id": "demo-veh-1", "department_id": "demo-flota", "codigo": "ABC-123", "nombre": "Nissan NP300", "atributos": {"año": "2022", "estado": "Disponible", "departamento": "Flota"}},
    {"id": "demo-veh-2", "department_id": "demo-flota", "codigo": "XYZ-789", "nombre": "Toyota Hilux", "atributos": {"año": "2021", "estado": "Disponible", "departamento": "Flota"}},
    {"id": "demo-veh-3", "department_id": "demo-flota", "codigo": "DEF-456", "nombre": "Chevrolet Silverado", "atributos": {"año": "2023", "estado": "En taller", "departamento": "Flota"}},
]

DEMO_TICKETS = [
    {"id": "demo-1", "folio": "TKT-8F42A1C0", "department_id": "demo-flota", "ticket_type_id": "demo-reporte", "entity_id": "demo-veh-1", "estado": "En progreso", "solicitante_nombre": "Mariana López", "solicitante_email": "mariana@grupoam.com", "created_at": "2026-08-28T08:40:00Z", "resolved_at": None, "campos": {"descripcion": "La unidad presenta ruido en el eje delantero.", "numero_nomina": "10432"}, "incidente_tipo": "Falla / Problema", "prioridad": "Media", "responsable_nombre": None},
    {"id": "demo-2", "folio": "TKT-29D77B13", "department_id": "demo-flota", "ticket_type_id": "demo-reporte", "entity_id": "demo-veh-2", "estado": "Abierto", "solicitante_nombre": "Luis Hernández", "solicitante_email": "luis@grupoam.com", "created_at": "2026-08-28T07:15:00Z", "resolved_at": None, "campos": {"descripcion": "No enciende el tablero.", "numero_nomina": "10218"}, "incidente_tipo": None, "prioridad": None, "responsable_nombre": None},
    {"id": "demo-3", "folio": "TKT-0BC912E4", "department_id": "demo-flota", "ticket_type_id": "demo-reporte", "entity_id": "demo-veh-3", "estado": "Resuelto", "solicitante_nombre": "Ana Torres", "solicitante_email": "ana@grupoam.com", "created_at": "2026-08-27T16:20:00Z", "resolved_at": "2026-08-27T18:45:00Z", "campos": {"descripcion": "Fuga de aceite detectada.", "numero_nomina": "10087"}, "incidente_tipo": "Mantenimiento Correctivo", "prioridad": "Alta", "responsable_nombre": "Jorge Peña"},
    {"id": "demo-4", "folio": "TKT-5A19E6D2", "department_id": "demo-flota", "ticket_type_id": "demo-asignacion", "entity_id": "demo-veh-1", "estado": "Asignado", "solicitante_nombre": "Carlos Ruiz", "solicitante_email": "carlos@grupoam.com", "created_at": "2026-08-20T09:05:00Z", "resolved_at": "2026-08-20T09:30:00Z", "campos": {"proposito": "Distribución Centro", "numero_nomina": "10510"}, "incidente_tipo": None, "prioridad": None, "responsable_nombre": "Jorge Peña"},
]

# Un evento "creado" por cada ticket demo (igual que inserta public.py al
# crear uno real), más un par de "cambio_estado" para que la línea de
# tiempo de ejemplo no se vea vacía en modo demo.
DEMO_TICKET_EVENTS = [
    {"id": "demo-evt-1", "ticket_id": "demo-1", "accion": "creado", "estado_anterior": None, "estado_nuevo": "Abierto", "comentario": None, "created_at": "2026-08-28T08:40:00Z"},
    {"id": "demo-evt-2", "ticket_id": "demo-1", "accion": "cambio_estado", "estado_anterior": "Abierto", "estado_nuevo": "En progreso", "comentario": "Se agendó revisión en taller.", "created_at": "2026-08-28T09:10:00Z"},
    {"id": "demo-evt-3", "ticket_id": "demo-2", "accion": "creado", "estado_anterior": None, "estado_nuevo": "Abierto", "comentario": None, "created_at": "2026-08-28T07:15:00Z"},
    {"id": "demo-evt-4", "ticket_id": "demo-3", "accion": "creado", "estado_anterior": None, "estado_nuevo": "Abierto", "comentario": None, "created_at": "2026-08-27T16:20:00Z"},
    {"id": "demo-evt-5", "ticket_id": "demo-3", "accion": "cambio_estado", "estado_anterior": "En progreso", "estado_nuevo": "Resuelto", "comentario": "Se reemplazó el empaque del cárter.", "created_at": "2026-08-27T18:45:00Z"},
    {"id": "demo-evt-6", "ticket_id": "demo-4", "accion": "creado", "estado_anterior": None, "estado_nuevo": "Abierto", "comentario": None, "created_at": "2026-08-20T09:05:00Z"},
    {"id": "demo-evt-7", "ticket_id": "demo-4", "accion": "cambio_estado", "estado_anterior": "Abierto", "estado_nuevo": "Asignado", "comentario": None, "created_at": "2026-08-20T09:30:00Z"},
]

# Solo para desarrollo local sin Supabase. En producción la contraseña vive
# hasheada en departments.admin_passcode_hash (ver scripts/set_passcode.py).
DEMO_ADMIN_PASSCODES = {"12345678": DEMO_DEPARTMENT}
