"""Aprovisiona el departamento "Talento AM" (Capital Humano) con sus 6 tipos
de ticket, adaptados de CH_Especificacion_Tecnica.md a lo que el modelo de
datos de TicketAM ya sabe representar (campos_config + estados por tipo,
igual que Flota).

Uso (desde la carpeta backend/):
    python scripts/setup_talento_am.py

Idempotente: se puede correr varias veces sin duplicar nada (usa el mismo
unique constraint (department_id, name) que ya trae schema.sql). Requiere
SUPABASE_URL y SUPABASE_SERVICE_KEY en el entorno o en .env.
"""
import os

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from supabase import create_client

load_dotenv()

SLUG = "talento-am"
NAME = "Talento AM"
PASSCODE = "1234"

DEPARTAMENTOS = [
    "AM Digital", "Sistemas", "Xpress DM", "Redacción AM", "Operaciones",
    "Suscripciones", "Capital Humano", "Mercadotecnia", "Publicidad",
    "Cobranza", "Contabilidad", "Imprenta", "Producción", "Circulación",
]

# Estados universales que se agregan a la cadena principal de cada tipo
# (sección 6 del spec): RN-04 (info faltante) y RN-12 (cancelación) aplican
# a los 6 tipos por igual.
EXTRA_ESTADOS = ["En espera de información", "Cancelado"]


def campo(key, label, tipo, required, options=None):
    field = {"key": key, "label": label, "type": tipo, "required": required}
    if options:
        field["options"] = options
    return field


def departamento_field():
    return campo("departamento_solicitante", "Departamento", "select", True, DEPARTAMENTOS)


TICKET_TYPES = [
    {
        "name": "Solicitud Administrativa",
        "campos_config": [
            departamento_field(),
            campo("puesto", "Puesto", "text", True),
            campo("tipo_solicitud", "Tipo de solicitud", "select", True, [
                "Constancia laboral", "Constancia para embajada", "Constancia para guardería",
                "Actualizar expediente", "Cambio de domicilio", "Cambio de estado civil", "Otra",
            ]),
            campo("descripcion", "Descripción", "textarea", True),
            campo("urgencia", "Urgencia", "select", True, ["Normal", "Urgente"]),
            campo("adjunto_path", "Archivo adjunto", "file", False),
        ],
        "estados": ["Abierto", "Revisando", "Aprobado", "Completado", "Cerrado"] + EXTRA_ESTADOS,
    },
    {
        "name": "Reporte de Incidencia",
        "campos_config": [
            departamento_field(),
            campo("puesto", "Puesto", "text", True),
            campo("tipo_reporte", "Tipo de reporte", "select", True, [
                "Conflicto entre colaboradores", "Falta al reglamento", "Ausencia injustificada",
                "Conducta inapropiada", "Incidente de seguridad", "Otro",
            ]),
            campo("personas_involucradas", "Personas involucradas", "textarea", True),
            campo("descripcion", "Descripción detallada de hechos", "textarea", True),
            campo("fecha_incidente", "Fecha del incidente", "date", True),
            campo("testigos", "Testigos", "textarea", False),
            campo("adjunto_path", "Evidencia / Documentación", "file", False),
        ],
        "estados": ["Abierto", "Investigación", "Documentación", "Resuelto", "Cerrado"] + EXTRA_ESTADOS,
    },
    {
        "name": "Solicitud de Apoyo Ocupacional",
        "campos_config": [
            departamento_field(),
            campo("tipo_apoyo", "Tipo de apoyo requerido", "select", True, [
                "Apoyo psicológico", "Contención emocional", "Asesoramiento personal", "Crisis emocional",
            ]),
            campo("descripcion", "Descripción breve", "textarea", True),
            campo("desea_contacto_telefonico", "¿Deseas ser contactado por teléfono?", "radio", True, ["Sí", "No"]),
            campo("telefono", "Teléfono", "text", False),
        ],
        "estados": ["Abierto", "Asignado", "En seguimiento", "Completado", "Cerrado"] + EXTRA_ESTADOS,
    },
    {
        "name": "Solicitud de Mobiliario y Espacios",
        "campos_config": [
            departamento_field(),
            campo("puesto", "Puesto", "text", True),
            campo("tipo_solicitud", "Tipo de solicitud", "select", True, [
                "Silla ergonómica", "Escritorio", "Monitor/Equipo", "Adecuación de espacio", "Otro mobiliario",
            ]),
            campo("descripcion", "Descripción de necesidad", "textarea", True),
            campo("justificacion", "Justificación", "textarea", True),
            campo("adjunto_path", "Foto/Documento de referencia", "file", False),
            campo("presupuesto", "Presupuesto aproximado", "select", False, ["<$500", "$500-$1,000", "$1,000-$2,000", ">$2,000"]),
        ],
        "estados": ["Abierto", "Evaluación", "Aprobado", "Adquisición", "Entregado", "Cerrado", "Rechazado"] + EXTRA_ESTADOS,
    },
    {
        "name": "Solicitud de Reclutamiento",
        "campos_config": [
            campo("puesto_actual", "Puesto actual", "text", True),
            departamento_field(),
            campo("tipo_solicitud", "Tipo de solicitud", "select", True, [
                "Reclutamiento para nueva vacante", "Reclutamiento por reemplazo",
                "Solicitud de promoción", "Cambio de puesto", "Transferencia a otra área",
            ]),
            campo("descripcion", "Descripción de puesto/cambio", "textarea", True),
            campo("perfil_justificacion", "Perfil buscado o justificación", "textarea", True),
            campo("salario_propuesto", "Salario propuesto", "number", False),
            campo("adjunto_path", "Documento de autorización (firma de jefe)", "file", True),
        ],
        "estados": ["Abierto", "Revisión", "Aprobado", "Reclutamiento", "Entrevistas", "Contratado", "Cerrado", "Rechazado"] + EXTRA_ESTADOS,
    },
    {
        "name": "Solicitud de Capacitación",
        "campos_config": [
            departamento_field(),
            campo("puesto", "Puesto", "text", True),
            campo("tipo_capacitacion", "Tipo de capacitación", "select", True, [
                "Curso externo", "Certificación profesional", "Taller interno", "Conferencia/Seminario", "Otra",
            ]),
            campo("nombre_curso", "Nombre del curso/certificación", "text", True),
            campo("descripcion", "Descripción y objetivo", "textarea", True),
            campo("duracion", "Duración", "text", True),
            campo("costo_estimado", "Costo estimado", "number", True),
            campo("proveedor", "Proveedor/Institución", "text", True),
            campo("fechas_propuestas", "Fechas propuestas", "text", True),
            campo("beneficio_area", "Beneficio para el área", "textarea", True),
        ],
        "estados": ["Abierto", "Revisión", "Aprobado", "Programado", "En progreso", "Completado", "Cerrado", "Rechazado"] + EXTRA_ESTADOS,
    },
]

# Tipos con nivel de confidencialidad alto (RN-09) — el frontend admin usa
# esta misma lista (duplicada en tickets.html) para pintarles el badge
# "🔒 Confidencial". No hay separación de acceso real en v1 (ver plan).
TIPOS_CONFIDENCIALES = ["Reporte de Incidencia", "Solicitud de Apoyo Ocupacional"]


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    client = create_client(url, key)

    existing = client.table("departments").select("id").eq("slug", SLUG).execute().data
    if existing:
        department_id = existing[0]["id"]
        print(f"Departamento '{SLUG}' ya existe (id={department_id}), no se vuelve a crear.")
    else:
        dept_result = client.table("departments").insert({
            "slug": SLUG,
            "name": NAME,
            "admin_passcode_hash": generate_password_hash(PASSCODE),
        }).execute()
        department_id = dept_result.data[0]["id"]
        print(f"Departamento '{NAME}' creado (id={department_id}), NIP {PASSCODE}.")

    existing_types = {
        row["name"]
        for row in (client.table("ticket_types").select("name").eq("department_id", department_id).execute().data or [])
    }
    for ticket_type in TICKET_TYPES:
        if ticket_type["name"] in existing_types:
            print(f"  = tipo '{ticket_type['name']}' ya existía, sin cambios.")
            continue
        result = client.table("ticket_types").insert({
            "department_id": department_id,
            "name": ticket_type["name"],
            "campos_config": ticket_type["campos_config"],
            "estados": ticket_type["estados"],
        }).execute()
        if result.data:
            print(f"  + tipo '{ticket_type['name']}' creado.")
        else:
            print(f"  ! no se pudo crear el tipo '{ticket_type['name']}'.")

    print("\nListo. Recuerda crear a mano (una sola vez) el bucket privado")
    print("'ch-adjuntos' en Supabase Storage si todavía no existe.")


if __name__ == "__main__":
    main()
