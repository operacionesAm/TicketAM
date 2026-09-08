# TicketAM

Plataforma de tickets **multi-departamento**: cada "departamento" es un sistema de
tickets completo e independiente (su propio panel, sus propios tipos de solicitud,
su propio PIN de administrador) sobre el mismo backend Flask + Supabase y el mismo
despliegue de Vercel. Hoy corren dos:

| Sistema | Departamento (slug) | Para qué |
|---|---|---|
| **Flota** | `flota` | Solicitudes y reportes de la flotilla vehicular |
| **Talento AM** | `talento-am` | Solicitudes de Capital Humano (administrativas, incidencias, apoyo ocupacional, mobiliario, reclutamiento, capacitación) |

Un **Administrador Global** (`/global`) ve los dos en agregado y puede dar de alta
sistemas nuevos. Ver [Arquitectura multi-departamento](#arquitectura-multi-departamento-sistemas-de-tickets)
para qué tan automático es agregar uno más.

## Arquitectura

Front y back están separados en carpetas independientes, pero se despliegan bajo el
**mismo dominio** de Vercel (`vercel.json` en la raíz rutea `/api/*` al backend y cada
pantalla a su HTML estático). Sin CORS, sin cookies cross-site: el navegador nunca sale
del mismo origen, y todos los sistemas de tickets comparten la misma cookie de sesión
de Flask (ver [Aislamiento de sesión entre sistemas](#aislamiento-de-sesión-entre-sistemas)).

```
vercel.json                       # rutea /api/* -> backend, cada pantalla -> su HTML
schema.sql                         # esquema de Supabase (tablas, RLS, seed de Flota)
vehiculos.json                     # inventario para scripts/import_vehiculos.py
GLOBAL-ADMIN.png                   # QR de acceso -> /global
ADMIN-FLOTA.png                    # QR de acceso -> /admin
ADMIN-TALENTO-AM.png               # QR de acceso -> /talento/admin
USUARIO-FLOTA.png                  # QR de acceso -> / (colaborador común)
USUARIO-OPERADOR.png               # QR de acceso -> /operador
USUARIO-TALENTO-AM.png             # QR de acceso -> /talento

backend/
  run.py                           # entrypoint local y para Vercel (expone `app`)
  requirements.txt
  .env.example
  scripts/
    set_passcode.py                  # fija el PIN de admin de un departamento
    import_vehiculos.py               # importa vehiculos.json al catálogo de Flota
    setup_talento_am.py               # aprovisiona el departamento Talento AM y sus 6 tipos
  app/
    __init__.py                     # create_app(): API pura, registra los blueprints
    extensions.py                   # cliente de Supabase (service role key)
    demo_data.py                     # datos de ejemplo cuando no hay Supabase (solo Flota)
    crypto.py                       # cifrado reversible del NIP (para "Más detalles" en /global)
    mailer.py                       # notificaciones por correo (SMTP y/o Google conectado)
    google_oauth.py                  # "Conectar con Google" — enviar como una cuenta @am.com.mx real
    photos.py                        # comprime y sube/baja fotos de reportes (imagen -> JPEG)
    attachments.py                   # adjuntos genéricos (PDF/Word/Excel/imagen, sin comprimir)
    qr.py                            # genera QR con logo y leyenda (vehículos y QR de acceso)
    assets/logo-am.png                # logo usado en los QR (copia de frontend/tickets/assets)
    routes/
      public.py                      # /api/departments/* — sin autenticación
      admin.py                        # /api/admin/* — protegidas por sesión de departamento
      global_admin.py                  # /api/global/* — protegidas por sesión de admin global

frontend/
  build/                             # compila tickets/assets/app.css — ver "Rendimiento" abajo
    package.json / tailwind.config.js / tailwind-input.css
  tickets/
    usuario/index.html              # colaborador común de Flota (QR / liga pública) -> "/"
    operador/index.html              # operador de unidad de Flota (QR / liga pública) -> "/operador"
    talento/index.html               # solicitante de Talento AM (liga pública) -> "/talento"
    admin/                           # panel de Flota
      admin-shared.js                   # sesión, nav, exportar XLSX, picker de vehículo — COMPARTIDO
      login.html                        # bienvenida + PIN -> "/admin"
      dashboard.html                    # KPIs, alertas, gráficas (Chart.js) -> "/admin/dashboard"
      tickets.html                      # kanban de tickets -> "/admin/tickets"
      inventario.html                   # alta/edición/baja de vehículos y QR -> "/admin/inventario"
      reportes.html                     # tickets + historial por vehículo -> "/admin/reportes"
      piezas.html                       # histórico de refacciones -> "/admin/piezas"
      servicios.html                    # servicios programados de motos -> "/admin/servicios"
      siniestros.html                   # histórico de siniestros -> "/admin/siniestros"
      configuracion.html                # correo de notificaciones, Google -> "/admin/configuracion"
      global-login.html                 # contraseña maestra -> "/global"
      global-panel.html                 # todos los departamentos, Storage, PIN/reset, alta -> "/global/panel"
    admin-talento/                   # panel de Talento AM — copia adaptada de admin/, propia y aislada
      login.html                        # bienvenida + NIP -> "/talento/admin"
      dashboard.html                    # KPIs de SLA/carga de trabajo -> "/talento/admin/dashboard"
      tickets.html                      # kanban de las 6 solicitudes -> "/talento/admin/tickets"
      configuracion.html                # correo de notificaciones, Google -> "/talento/admin/configuracion"
    assets/
      app.css                          # CSS de Tailwind precompilado (commiteado) — ver "Rendimiento"
      logo-am.png                       # logo, ver también backend/app/assets/
```

## Rendimiento en equipos de gama baja

Todas las pantallas cargan un único CSS estático precompilado
(`frontend/tickets/assets/app.css`, ~28 KB) en vez del **Play CDN** de Tailwind
(`cdn.tailwindcss.com`). El Play CDN no es solo un archivo pesado de más — es un
compilador JIT completo que corre en el navegador: escanea el DOM al cargar la página
**y vuelve a compilar estilos con cada mutación del DOM** (un `MutationObserver` activo
todo el tiempo que la pestaña sigue abierta). En un teléfono o laptop de gama baja de
alrededor de 2020, eso se nota como micro-cuelgues cada vez que el panel admin
re-renderiza el Kanban de tickets, la tabla de inventario o el dashboard — no solo al
cargar la página, sino en cada interacción. Cambiarlo por un `<link rel="stylesheet">`
normal elimina ese trabajo por completo: el navegador solo aplica CSS ya calculado, sin
JS de por medio.

`frontend/build/` es el proyecto Node (no se sube a Vercel, es solo una herramienta)
que genera ese archivo. Todas las pantallas comparten la misma paleta de colores
(`brand`, `brand-dark`, `accent` — la personalización de Talento AM se hace con las
clases `rose-*` que ya trae Tailwind por defecto, no requiere configuración aparte), así
que un solo build cubre toda la plataforma. Si agregas una clase de Tailwind nueva a
cualquier HTML, hay que recompilar para que quede incluida en `app.css`:

```powershell
cd frontend/build
npm install   # una sola vez
npm run build
```

Esto vuelve a escanear todos los `.html`/`.js` bajo `frontend/tickets/` y sobreescribe
`../tickets/assets/app.css`. Olvidar este paso no rompe nada visualmente obvio de
inmediato — simplemente la clase nueva no tendrá estilo hasta el siguiente build, así
que conviene correrlo como parte de cualquier cambio de UI antes de hacer commit.

Chart.js, xlsx (exportar a Excel) y jsPDF (imprimir QR) se dejaron en CDN tal cual
estaban: solo se cargan en las pantallas de administrador que realmente los usan (no en
las pantallas públicas de creación de tickets, que son las que más tráfico reciben desde
equipos variados), y a diferencia del Play CDN no vuelven a ejecutar nada en segundo
plano una vez cargados.

## Arquitectura multi-departamento ("sistemas de tickets")

El **backend y el modelo de datos ya son multi-tenant de fábrica**: cada fila de
`departments` es un sistema de tickets aislado (sus propios `ticket_types`, `entities`,
`tickets` — todo filtrado por `department_id` en cada ruta `/api/admin/*`, sin
excepción). El **Administrador Global** puede dar de alta un departamento nuevo desde
`/global/panel` en segundos, con PIN y tipos de ticket por defecto (los de Flota).

Lo que **no** es automático es la interfaz: cada sistema de tickets necesita su propio
formulario público y su propio panel de administrador, porque el HTML/JS de Flota está
escrito pensando en sus tipos de ticket concretos (nombres de tabs, KPIs de vehículos,
Inventario). Por eso Talento AM no es solo una fila nueva en `departments` — es una
carpeta completa (`frontend/tickets/talento/`, `frontend/tickets/admin-talento/`) copiada
y adaptada de la de Flota, más un script de aprovisionamiento
(`backend/scripts/setup_talento_am.py`) para sus 6 tipos de ticket. Agregar un tercer
sistema de tickets algún día implica repetir ese mismo patrón.

Piezas reutilizadas sin duplicar entre sistemas: el backend completo (`app/routes/*`,
`app/mailer.py`, `app/photos.py`, `app/attachments.py`, `app/qr.py`) y
`frontend/tickets/admin/admin-shared.js` (sesión, barra de navegación, exportar a Excel).
`admin-shared.js` acepta un `basePath` y un color de nav opcionales — por defecto el de
Flota, sin cambio de comportamiento — para que un panel nuevo pueda vivir en su propia
URL con su propio color sin bifurcar el archivo.

### Aislamiento de sesión entre sistemas

Todos los sistemas comparten la **misma cookie de sesión de Flask** (un solo dominio,
un solo login activo a la vez) — no hay "sesión de Flota" y "sesión de Talento AM"
simultáneas en el mismo navegador. `POST /api/admin/login` revisa la contraseña contra
**todos** los departamentos y abre sesión del primero cuyo hash coincida.

Para que un usuario nunca vea el panel de un sistema con los tickets de otro (por
ejemplo, entrar a `/talento/admin` sin haber cerrado antes la sesión de Flota),
`requireSession(loginPath, expectedSlug)` en `admin-shared.js` valida el `slug` de la
sesión activa contra el que espera esa pantalla — si no coincide, cierra esa sesión
ajena y manda al login en vez de renderizar con datos del departamento equivocado.
`expectedSlug` es opcional y por defecto `null` (sin chequeo), así que no cambia nada
para quien no lo use. Cada `login.html` hace el mismo chequeo en su verificación de
"¿ya hay sesión?" al cargar.

El botón "Entrar" de cada login se deshabilita mientras la petición está en vuelo — con
cold starts de Vercel la respuesta puede tardar unos segundos, y un doble clic ahí podía
disparar dos logins casi simultáneos que se pisaban entre sí (la cookie que "ganaba"
podía terminar siendo la de otro sistema si había una petición vieja todavía en curso).

## Sistema 1: Flota

### Dos formularios públicos: colaborador común vs. operador

- **`/` — colaborador común.** Dos opciones: "Pedir un vehículo" (nunca elige la unidad
  — el campo `entity_id` siempre va vacío, flota asigna después) y "Levantar ticket"
  (reporta una falla sobre un vehículo puntual, eligiendo la placa o escaneando su QR).
  No hay "Solicitar refacción" aquí — ese pedido es exclusivo del operador.
- **`/operador` — operador de unidad.** Muestra las tres acciones (Pedir un vehículo /
  Levantar ticket / Solicitar refacción), y las tres empiezan eligiendo o escaneando la
  unidad — incluida "Pedir un vehículo": a diferencia del colaborador común, el operador
  sí elige qué unidad toma, y por traer `entity_id` desde la creación el backend la
  autoriza de inmediato (autoasignación), sin esperar revisión de flota — salvo que el
  vehículo esté marcado `Inactivo` o `Dado de baja`, en cuyo caso cae a revisión igual
  que cualquier solicitud normal.

Ambas páginas comparten la misma API pública y el mismo QR físico de cada vehículo (que
sigue apuntando a `/?placa=...`) — el botón "Escanear QR" del operador lee esa misma
calcomanía con su propio lector en pantalla, sin necesidad de reimprimir nada.

### Panel de administrador (`/admin`)

Tras iniciar sesión, el **Dashboard** es la pantalla principal: KPIs (total de tickets,
abiertos, en proceso, resueltos, promedio de días de solución — excluye las
autoasignaciones instantáneas de "Solicitud de vehículo", que hundirían el promedio
artificialmente —, antigüedad del ticket más viejo abierto), alertas de atención urgente
(prioridad Alta abiertos, reportes sin clasificar, tickets abiertos hace más de 5 días,
servicios de moto próximos/vencidos), gráficas (tickets por tipo de incidente, estado del
inventario, vehículos con más reportes, reportes por mes) y tablas de distribución — todo
calculado en vivo sobre los tickets/vehículos del departamento.

- **Tickets** (kanban por tipo, Lista y Archivo — ver abajo). Clasificar un reporte
  (tipo de incidente + prioridad), mover de estado (drag & drop o select — valida contra
  los estados del tipo), asignar vehículo a una "Solicitud de vehículo" (bloquea unidades
  `Inactivo`/`Dado de baja`), asignar responsable (texto libre), dejar observaciones (con
  opción de notificar por correo), ver la foto adjunta.
- **Inventario**: alta, edición y generación/impresión de QR de vehículos — ver
  [Estados de un vehículo](#estados-de-un-vehículo-y-por-qué-no-se-pueden-eliminar) para
  cómo se retira una unidad sin perder su historial.
- **Reportes individuales**: de solo lectura — tickets, estadísticas de tiempo de
  solución e historial de eventos de un vehículo, pensado para detectar unidades con
  desgaste o fallas recurrentes.
- **Histórico de Piezas** y **Histórico de Siniestros**: vistas derivadas de los mismos
  tickets (filtran "Ticket de Mantenimiento" y `incidente_tipo = "Siniestro"`
  respectivamente) — sin tabla ni endpoint nuevo, se arman en el navegador.
- **Servicios Programados**: mantenimiento preventivo/correctivo de motocicletas
  (`atributos.tipo === "Motocicleta"` exacto). Un preventivo calcula y guarda cuándo toca
  el siguiente (fecha + 1 mes, ajustando fin de mes); un correctivo solo queda en la
  bitácora.
- **Configuración**: correo de notificaciones del departamento y "Conectar con Google".

En Tickets, además del toggle Kanban/Lista hay una tercera vista, **Archivo**: un ticket
en un estado final (Resuelto, Cerrado, Asignado o Negado) sale de Kanban/Lista
automáticamente 5 días después de resuelto (`resolved_at`) y pasa a Archivo — nada se
borra, es solo un filtro por fecha calculado en el navegador. Un cuarto tab, **Todos**,
combina Reportes + Asignaciones + Mantenimiento en Lista y Archivo (el Kanban se queda
por tipo, porque sus columnas son los estados de un solo tipo).

### Reportes de falla: vehículo obligatorio y foto opcional

Un "Reporte de falla" o "Ticket de Mantenimiento" **siempre** debe traer `entity_id` —
el backend lo rechaza con 400 si falta. Solo "Pedir un vehículo" (del colaborador común)
puede quedar sin vehículo, porque ahí es flota quien asigna la unidad después.

El formulario de reporte permite adjuntar una foto (`campos.foto_path` en el ticket). Se
reduce en el navegador antes de enviarla (canvas, máx. 1600px) y **otra vez** en el
backend al recibirla (`app/photos.py`, PIL, máx. 1280px, JPEG calidad 70) — esa es la
compresión que de verdad cuenta. Se guarda en **Supabase Storage** (bucket privado
`reportes-fotos`), no en la base de datos — la tabla `tickets` solo guarda el path. Los
admins la ven vía `GET /api/admin/tickets/{id}/foto`.

### Vehículo asignado y licencia de conducir

Al registrar "Pedir un vehículo" (colaborador o autoasignación de operador), se le avisa
al solicitante — en pantalla y por correo (`send_vehicle_request_received_email` si
queda pendiente de revisión, `send_vehicle_assigned_email` si se autoasignó o cuando el
admin la autoriza) — que como último paso obligatorio debe presentar copia de su
licencia de conducir. El panel de asignación en `/admin/tickets` muestra el mismo
recordatorio al admin.

### Estados de un vehículo y por qué no se pueden eliminar

Un vehículo tiene tres estados posibles (`atributos.estado` en `entities`):

| Estado | Significa | Cuenta en el inventario/KPIs | Se puede asignar |
|---|---|---|---|
| `Activo` | En operación normal | Sí | Sí |
| `Inactivo` | Fuera de servicio temporalmente (taller, etc.) | Sí | No |
| `Dado de baja` | Se fue de verdad — vendido, robado, pérdida total | **No** | No |

El panel admin **no tiene forma de borrar un vehículo** — no existe endpoint de borrado
(`DELETE /api/admin/entities/{id}` fue retirado a propósito). La razón es el esquema:
`tickets.entity_id` referencia `entities` con `on delete set null` y `servicios.entity_id`
con `on delete cascade` — un borrado real desvincularía los tickets viejos de su vehículo
y **destruiría por completo** el historial de mantenimiento de esa unidad. En vez de
borrar, un vehículo que se vende, se pierde o sufre una pérdida total se marca como
**`Dado de baja`** (mismo formulario de edición en `/admin/inventario`, sin campo nuevo):
desaparece de los contadores del Dashboard, de la vista normal del Inventario (solo
aparece si filtras explícitamente por ese estado) y de todos los selectores de vehículo
de las pantallas públicas (`/`, `/operador`) y del picker de asignación en
`/admin/tickets` — pero la fila en `entities` sigue existiendo, así que sus tickets,
fotos y servicios pasados se siguen viendo exactamente igual en **Reportes individuales**,
**Histórico de Piezas**, **Histórico de Siniestros** y **Servicios Programados**, que
deliberadamente no filtran por estado porque son las pantallas de historial.

### Imprimir QR en lote (Inventario)

En `/admin/inventario`, el botón **"🖨️ Imprimir PDF"** activa un modo de selección
(checkboxes en la tabla y en la cuadrícula, con "Seleccionar todos" / "Deseleccionar
todos" — persiste al cambiar entre Lista y Cuadrícula) y genera un PDF con los vehículos
marcados: 4 por página (2×2), cada uno con su QR (con logo) y sus datos debajo, con guías
de corte. Se arma en el navegador con `jsPDF` (CDN); descarga las imágenes de QR ya
generadas vía `GET /api/admin/entities/{id}/qr`.

## Sistema 2: Talento AM (Capital Humano)

### Formulario público (`/talento`)

Un solo formulario con **6 tipos de solicitud**, adaptados de la especificación de
Capital Humano al modelo de datos que ya existía (`campos_config` + `estados` por tipo,
igual que Flota — sin tablas nuevas):

| Tipo | Campos propios | Estados |
|---|---|---|
| Solicitud Administrativa | departamento, puesto, tipo de solicitud, descripción, urgencia, adjunto opcional | Abierto → Revisando → Aprobado → Completado → Cerrado (+ En espera de información, Cancelado) |
| Reporte de Incidencia 🔒 | departamento, puesto, tipo de reporte, personas involucradas, descripción, fecha del incidente, testigos, evidencia opcional | Abierto → Investigación → Documentación → Resuelto → Cerrado (+ En espera de información, Cancelado) |
| Solicitud de Apoyo Ocupacional 🔒 | departamento, tipo de apoyo, descripción, ¿contacto telefónico? + teléfono condicional | Abierto → Asignado → En seguimiento → Completado → Cerrado (+ En espera de información, Cancelado) |
| Solicitud de Mobiliario y Espacios | departamento, puesto, tipo, descripción, justificación, adjunto opcional, presupuesto aproximado | Abierto → Evaluación → Aprobado → Adquisición → Entregado → Cerrado (+ Rechazado, En espera de información, Cancelado) |
| Solicitud de Reclutamiento | puesto actual, departamento, tipo, descripción, perfil/justificación, salario propuesto, **adjunto obligatorio** (autorización) | Abierto → Revisión → Aprobado → Reclutamiento → Entrevistas → Contratado → Cerrado (+ Rechazado, En espera de información, Cancelado) |
| Solicitud de Capacitación | departamento, puesto, tipo, nombre del curso, descripción, duración, costo, proveedor, fechas, beneficio | Abierto → Revisión → Aprobado → Programado → En progreso → Completado → Cerrado (+ Rechazado, En espera de información, Cancelado) |

🔒 = nivel de confidencialidad alto en el spec original — ver
[Limitaciones conocidas](#limitaciones-conocidas--decisiones-de-alcance).

El folio de estos tickets usa el prefijo **`TKT-CH-`** en vez del `TKT-` genérico (ver
`FOLIO_PREFIX_BY_SLUG` en `public.py` — solo afecta a `talento-am`, el resto de
departamentos sigue con el default de la tabla).

### Panel de administrador (`/talento/admin`)

Reutiliza el mismo login/sesión/API que Flota, pero con pantallas propias:

- **Dashboard**: KPIs de la sección 3 del spec de Capital Humano — solicitudes de hoy,
  abiertas, vencidas por SLA, % de cumplimiento de SLA, tiempo promedio de resolución,
  antigüedad de la más vieja sin resolver, en espera de información, tasa de
  cancelación/rechazo, distribución y SLA por tipo, carga de trabajo por responsable,
  tiempo promedio de primera respuesta. SLA por tipo hardcodeado en el frontend (48h
  Administrativa/Incidencia/Apoyo — 24h si `campos.urgencia === "Urgente"` —, 120h/5 días
  Mobiliario/Reclutamiento/Capacitación), con semáforo 🟢/🟡/🔴 **calculado en vivo al
  abrir la pantalla** (no hay cron ni cambios de estado automáticos — ver limitaciones).
- **Tickets**: kanban con una pestaña por tipo (+ "Todos" en Lista/Archivo), badge
  "🔒 Confidencial" en Incidencia/Apoyo Ocupacional, adjunto descargable en vez de foto.
- **Configuración**: igual que Flota (correo de notificaciones, Google).

No hay Inventario/Reportes/Piezas/Servicios/Siniestros — son conceptos de vehículos que
no aplican aquí.

### Adjuntos genéricos (no solo fotos)

`app/photos.py` fuerza todo a imagen (compresión JPEG) — no sirve para PDF/Word/Excel.
`app/attachments.py` sube el archivo tal cual (sin procesarlo), validando extensión
(`pdf`, `jpg`, `jpeg`, `png`, `doc`, `docx`, `xls`, `xlsx`) y tamaño (máx. 5 MB), en un
bucket propio de Storage: **`ch-adjuntos`** (privado). El path queda en
`campos.adjunto_path`, mismo patrón que `campos.foto_path` de Flota. Los admins lo
descargan vía `GET /api/admin/tickets/{id}/adjunto`. Cualquier departamento puede usar
este mecanismo si algún día lo necesita — no está atado a Talento AM en el código.

### Aprovisionamiento

`backend/scripts/setup_talento_am.py` crea el departamento `talento-am` (NIP `1234`) y
sus 6 `ticket_types` con `campos_config`/`estados` — idempotente, se corre una sola vez:

```powershell
cd backend
python scripts/setup_talento_am.py
```

Además hay que crear una vez (a mano, en el dashboard de Supabase) el bucket privado
**`ch-adjuntos`**, igual que `reportes-fotos` — ver [Supabase](#supabase).

## Aislamiento entre departamentos

Cada admin de departamento solo ve y toca lo de su propio departamento — todas las rutas
`/api/admin/*` filtran por `session["department_id"]`, sin excepción. Verificado en vivo
contra producción, creando y probando por completo un departamento de prueba desechable:
su sesión mostró 0 tickets mientras Flota seguía con los suyos, sin cruce de datos, y al
borrarlo el conteo de Flota no se movió.

## Administrador global

Por encima de los admins de cada departamento hay un **Administrador Global**, en
`/global` — una sola contraseña maestra (`GLOBAL_ADMIN_PASSCODE`, **no** un PIN corto:
usa algo largo y fuerte) con sesión propia (`session["is_global_admin"]`), separada de
las sesiones de departamento. Desde `/global/panel` puede:

- Ver **uso de Supabase Storage** (fotos de Flota + adjuntos de Talento AM, los 2
  buckets) contra el 1 GB del plan gratis, con barra de progreso y desglose por bucket —
  para verlo venir antes de que una subida falle (`GET /api/global/storage-usage`, suma
  recursiva de ambos buckets ya que los archivos viven como `{department_id}/{archivo}`).
- Ver todos los departamentos, con badge de PIN configurado y Google conectado, y un
  resumen agregado (tickets totales/abiertos de todos juntos).
- **Crear un departamento nuevo** ("+ Nuevo departamento": slug, nombre, PIN) — se crea
  con los mismos tipos de ticket por defecto que Flota (para un sistema con tipos
  distintos, como Talento AM, se aprovisiona por script en vez de este botón — ver
  [Arquitectura multi-departamento](#arquitectura-multi-departamento-sistemas-de-tickets)).
- **Resetear el PIN** de cualquier departamento — sin poder ver el actual (está
  hasheado); "Más detalles" sí puede *mostrar* el NIP vigente gracias a una copia cifrada
  reversible (`admin_passcode_encrypted`, `app/crypto.py`, requiere `PASSCODE_ENCRYPTION_KEY`).

Sin `GLOBAL_ADMIN_PASSCODE` configurado, `/global` responde error al iniciar sesión — el
resto de la app sigue funcionando igual.

## Notificaciones por correo

Cuando llega un ticket nuevo, el backend avisa por correo al departamento
(`backend/app/mailer.py`, SMTP estándar o la cuenta de Google conectada). Sin `SMTP_*`
configurado y sin cuenta de Google conectada, el envío simplemente se omite; el resto de
la app sigue funcionando igual.

1. Define en `backend/.env`: `SMTP_HOST`, `SMTP_PORT` (587 por defecto), `SMTP_USER`,
   `SMTP_PASSWORD` y opcionalmente `SMTP_FROM`.
2. Cada departamento captura su correo de aviso desde su panel, en `.../configuracion`
   (`departments.notification_email`).
3. El aviso se dispara desde `POST /api/departments/{slug}/tickets`.

Además, desde el detalle de un ticket el admin puede dejar **observaciones** con opción
de enviarlas por correo al `solicitante_email` — para dudas o seguimiento puntual.

### Enviar como una cuenta real de Google ("Conectar con Google")

Para dominios de Google Workspace donde Sistemas bloquea las contraseñas de aplicación
(`app/google_oauth.py`), el admin conecta su cuenta real una sola vez desde
**`.../configuracion`** y desde ahí se mandan todos los correos del departamento. Si un
departamento tiene cuenta de Google conectada, `mailer.py` la usa antes que SMTP; si no,
cae a SMTP; si ninguna está configurada, no envía nada.

Alguien con acceso al **Google Cloud Console** de la organización tiene que crear las
credenciales una sola vez:

1. Ve a [console.cloud.google.com](https://console.cloud.google.com) y crea un proyecto
   (o usa uno existente).
2. **APIs y servicios → Biblioteca** → busca "Gmail API" → **Habilitar**.
3. **APIs y servicios → Pantalla de consentimiento OAuth**: Tipo de usuario **Interno**
   (restringe a cuentas @am.com.mx); agrega el scope
   `https://www.googleapis.com/auth/gmail.send`.
4. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   Tipo **Aplicación web**; **URI de redirección autorizados**: agrega exactamente
   `https://tu-dominio.vercel.app/api/admin/google/callback` (producción) y, si vas a
   probar en local, `http://127.0.0.1:5000/api/admin/google/callback`.
5. Copia el **Client ID** y **Client secret** a `backend/.env` y a Vercel:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://tu-dominio.vercel.app/api/admin/google/callback
   ```
6. En cualquier panel, `.../configuracion` → **"Conectar con Google"** → el admin de ese
   departamento inicia sesión con su cuenta @am.com.mx y autoriza el envío. El callback
   respeta desde qué sistema se conectó (`return_to`, ver `admin_google_connect` en
   `admin.py`) y regresa a la pantalla de Configuración correcta — Flota o Talento AM.

Sin estas tres variables, "Conectar con Google" responde con error controlado — SMTP
sigue disponible como alternativa.

## Arranque local

La forma que refleja exactamente el ruteo de producción (un solo origen) es la CLI de
Vercel:

```powershell
npm install -g vercel   # una sola vez
vercel dev
```

Esto sirve `frontend/` y las funciones de `backend/` bajo el mismo `http://localhost:3000`.

Para iterar solo en la API (por ejemplo con `curl`) también puedes correr el backend
suelto:

```powershell
cd backend
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Esto levanta la API en `http://127.0.0.1:5000`. **Sin credenciales de Supabase corre en
modo demo** — pero el modo demo solo simula el departamento Flota (`app/demo_data.py`,
PIN `12345678`); Talento AM necesita Supabase real, porque se aprovisiona por script
directo a la base de datos, no hay datos de ejemplo para ella.

## Supabase

1. Crea un proyecto en Supabase.
2. Ejecuta `schema.sql` en el SQL Editor (crea las tablas, RLS y siembra el departamento
   `flota` con sus 3 tipos de ticket y 3 vehículos de ejemplo).
3. Copia la URL y la **service role key** a `backend/.env` como `SUPABASE_SERVICE_KEY`.
   El backend Flask corre en el servidor (nunca en el navegador), así que es seguro
   usarla ahí — el control de acceso al panel admin lo hace la sesión de Flask, no las
   políticas RLS. Nunca la expongas en el frontend ni la subas a git.
4. Define un `FLASK_SECRET_KEY` propio (ver advertencia en
   [Variables de entorno](#variables-de-entorno) — es más importante de lo que parece).
5. Fija el PIN de Flota: desde `backend/`, `python scripts/set_passcode.py flota 12345678`.
6. Si tienes un inventario de vehículos en `vehiculos.json` (raíz del repo), impórtalo
   con `python scripts/import_vehiculos.py` — idempotente.
7. Si vas a usar Talento AM: corre `python scripts/setup_talento_am.py` (ver
   [Sistema 2](#sistema-2-talento-am-capital-humano)).
8. Crea los 2 buckets privados de Storage (dashboard de Supabase → Storage → New bucket
   → sin marcar "Public") o con el service role key:
   ```python
   supabase.storage.create_bucket("reportes-fotos", options={"public": False})
   supabase.storage.create_bucket("ch-adjuntos", options={"public": False})
   ```

## Variables de entorno

| Variable | Requerida | Para qué |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Para correr contra datos reales (si faltan, cae a modo demo de Flota) | Cliente de Supabase |
| `FLASK_SECRET_KEY` | **Sí, en producción** | Firma la cookie de sesión. **Sin esta variable, cada arranque del proceso usa una llave aleatoria distinta** — en Vercel, cada cold start de la función puede firmar con una llave distinta a la que validó el request anterior, invalidando sesiones de admin sin ningún error visible más que un 401 intermitente. `app/__init__.py` imprime una advertencia en los logs si falta. Usa el mismo valor en local y en Vercel, y en **los 3 ambientes** de Vercel (Production/Preview/Development). |
| `GLOBAL_ADMIN_PASSCODE` | Para usar `/global` | Contraseña maestra del Administrador Global |
| `PASSCODE_ENCRYPTION_KEY` | Opcional | Llave Fernet para que "Más detalles" en `/global/panel` pueda mostrar el NIP vigente de un departamento (`app/crypto.py`) — sin ella, esa función se omite sin romper el resto |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Opcional | Notificaciones por correo vía SMTP |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Opcional | "Conectar con Google" para enviar correo como una cuenta real |
| `PUBLIC_BASE_URL` | Opcional, solo backend suelto en local | Dominio que se codifica en los QR de vehículo — en Vercel no hace falta, se infiere de `request.host_url` |

## Migraciones pendientes (si tu Supabase ya existía antes de estos cambios)

`schema.sql` ya trae estas columnas para instalaciones nuevas. Si tu proyecto de
Supabase ya existía, corre esto una vez en el **SQL Editor**:

```sql
alter table departments add column if not exists notification_email text;
alter table departments add column if not exists google_refresh_token text;
alter table departments add column if not exists google_connected_email text;
alter table departments add column if not exists admin_passcode_encrypted text;
alter table tickets add column if not exists incidente_tipo text;
alter table tickets add column if not exists prioridad text;
alter table tickets add column if not exists responsable_nombre text;
```

Sin estas, "Responsable", el correo de notificaciones, "Conectar con Google" y "Más
detalles" en `/global/panel` fallan con error controlado — no rompen el resto del panel.

## Despliegue en Vercel

Un solo proyecto de Vercel apuntando a la raíz del repo. `vercel.json` ya define los dos
builds (`backend/run.py` como función Python, `frontend/` como sitio estático) y el
ruteo de cada pantalla de cada sistema de tickets. Configura en el proyecto las mismas
variables de `backend/.env` (ver [Variables de entorno](#variables-de-entorno)) — **en
los 3 ambientes** (Production/Preview/Development), y presta especial atención a
`FLASK_SECRET_KEY`.

**Cambiar una variable de entorno en el dashboard de Vercel no actualiza las funciones
ya desplegadas** — hace falta un **Redeploy** explícito (Deployments → los 3 puntos del
deployment más reciente → Redeploy) para que el cambio tome efecto.

## Limitaciones conocidas / decisiones de alcance

Documentadas a propósito para quien retome esto después:

- **Confidencialidad de "Reporte de Incidencia" y "Apoyo Ocupacional" (Talento AM):** el
  spec original pide que solo un psicólogo/gerente vea el detalle — hoy no hay roles
  dentro de un departamento, un solo PIN ve todo. Se implementó solo el badge visual
  "🔒 Confidencial" como aviso; separación de acceso real requeriría un segundo PIN con
  su propia sesión, no construido todavía.
- **SLA y automatización por tiempo (Talento AM):** el semáforo y las alertas de SLA se
  calculan en vivo cada vez que se abre el Dashboard/Kanban (mismo patrón que el filtro
  de Archivo de Flota) — no hay Vercel Cron ni cambios de estado automáticos por
  inactividad, ni correos de alerta por vencimiento. El admin actúa a mano.
- **Duplicados (RN-13 del spec de CH):** no se implementó detección/auto-cancelación de
  solicitudes duplicadas.
- **Responsable como texto libre:** no existe un directorio de usuarios/agentes por
  departamento — `responsable_nombre` es texto libre en ambos sistemas, igual que ya
  era en Flota.
- **Solo Flota tiene modo demo:** `app/demo_data.py` no cubre Talento AM; sin Supabase
  configurado, `/talento` y `/talento/admin` no van a mostrar datos.
- **El formulario público de cada sistema tiene el `slug` de su departamento fijo en el
  JS** (`DEPARTMENT_SLUG` en `usuario/index.html`, `operador/index.html`,
  `talento/index.html`) — no eligen departamento dinámicamente. Un sistema de tickets
  nuevo necesita su propia página, no solo una fila nueva en `departments`.

## API

### Pública (sin sesión)

- `GET /api/departments/{slug}` — tipos de ticket y catálogo de entidades para armar el
  formulario. No incluye tickets.
- `POST /api/departments/{slug}/tickets` — crea un ticket y su evento `creado`. Rechaza
  (400) un "Reporte de falla"/"Ticket de Mantenimiento" sin `entity_id`, o un `entity_id`/
  `ticket_type_id` que no pertenezca a ese departamento. Acepta `foto_base64` (solo
  "Reporte de falla", se comprime y sube a `reportes-fotos`) y/o `adjunto_base64` +
  `adjunto_nombre` (cualquier tipo, sube tal cual a `ch-adjuntos`, valida extensión y
  tamaño ≤5 MB). El folio usa `TKT-CH-` para `talento-am`, `TKT-` (default de la tabla)
  para el resto.

### Admin de departamento (requiere sesión — `session["department_id"]`)

- `POST /api/admin/login` / `POST /api/admin/logout` / `GET /api/admin/me` — sesión por
  PIN, revisa el hash contra todos los departamentos.
- `GET /api/admin/tickets` — tickets del departamento de la sesión activa.
- `PATCH /api/admin/tickets/{id}/classify` — clasifica un "Reporte de falla"
  (`incidente_tipo`, `prioridad`).
- `PATCH /api/admin/tickets/{id}/status` — cambia el estado (valida que pertenezca a
  `ticket_types.estados` de ese ticket) y registra el evento; marca `resolved_at` si el
  nuevo estado es uno de los finales de **cualquier** sistema conocido (`ESTADOS_FINALES`
  en `admin.py` — Flota y Talento AM juntos, un sistema nuevo con nombres de estado
  distintos tendría que sumar los suyos ahí).
- `PATCH /api/admin/tickets/{id}/responsable` — asigna `responsable_nombre` (texto libre).
- `POST /api/admin/tickets/{id}/observaciones` — agrega una observación; `notificar_email`
  la manda también al solicitante.
- `GET /api/admin/tickets/{id}/foto` — foto del reporte (JPEG) desde `reportes-fotos`.
- `GET /api/admin/tickets/{id}/adjunto` — adjunto genérico desde `ch-adjuntos`, con su
  content-type correcto.
- `GET /api/admin/settings` / `PATCH /api/admin/settings` — correo de notificaciones del
  departamento de la sesión.
- `GET /api/admin/google/connect` (acepta `?return_to=` para volver a la pantalla de
  Configuración correcta) / `GET /api/admin/google/callback` / `POST /api/admin/google/disconnect`.
- `GET /api/admin/entities` / `POST /api/admin/entities` / `PATCH /api/admin/entities/{id}`
  / `GET /api/admin/entities/{id}/qr` — catálogo de vehículos (Flota; cualquier
  departamento podría usarlo). Sin `DELETE` a propósito — ver
  [Estados de un vehículo](#estados-de-un-vehículo-y-por-qué-no-se-pueden-eliminar).
- `GET /api/admin/servicios` / `POST /api/admin/servicios` — servicios programados de
  motocicletas (Flota).
- `GET /api/admin/events` — eventos (`ticket_events`), filtrables por `?entity_id=` y/o
  `?ticket_id=`.

### Administrador global (requiere sesión — `session["is_global_admin"]`)

- `POST /api/global/login` / `POST /api/global/logout` / `GET /api/global/me`.
- `GET /api/global/departments` — todos los departamentos con estatus de PIN, Google
  conectado y conteo de tickets.
- `POST /api/global/departments` — crea un departamento nuevo con los tipos de ticket
  por defecto de Flota.
- `PATCH /api/global/departments/{id}/passcode` — resetea el PIN de un departamento.
- `GET /api/global/departments/{id}/detail` — agregados de un departamento (nunca
  contenido de tickets individuales) más el NIP vigente si hay cifrado configurado.
- `GET /api/global/storage-usage` — bytes/archivos usados en `reportes-fotos` y
  `ch-adjuntos` contra el límite del plan gratis de Supabase (1 GB).
