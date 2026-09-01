# TicketAM

MVP de plataforma de tickets multi-departamento con Flask, Supabase y HTML + Tailwind.

## Estructura

Front y back están separados en carpetas independientes, pero se despliegan bajo el **mismo dominio** de Vercel (`vercel.json` en la raíz rutea `/api/*` al backend y todo lo demás al frontend estático). Sin CORS, sin cookies cross-site: cada uno se desarrolla y prueba por separado, pero el navegador nunca sale del mismo origen.

```
vercel.json                    # rutea /api/* -> backend, resto -> frontend
schema.sql                      # esquema de Supabase (tablas, RLS, seed de Flota)

backend/
  run.py                         # entrypoint local y para Vercel (expone `app`)
  requirements.txt
  .env.example
  scripts/set_passcode.py          # fija la contraseña de admin de un departamento
  scripts/import_vehiculos.py       # importa vehiculos.json al catálogo de entidades
  app/
    __init__.py                    # create_app(): API pura, registra los blueprints
    extensions.py                  # cliente de Supabase (service role key)
    demo_data.py                    # datos de ejemplo cuando no hay Supabase configurado
    mailer.py                       # notificaciones por correo (SMTP y/o Google conectado)
    google_oauth.py                  # "Conectar con Google" — enviar como una cuenta @am.com.mx real
    photos.py                        # comprime y sube/baja las fotos de reportes (Supabase Storage)
    qr.py                           # genera el QR de cada vehículo (con logo y leyenda)
    assets/logo-am.png               # logo usado en el QR impreso (copia de frontend/tickets/assets)
    routes/
      public.py                      # /api/departments/* — sin autenticación
      admin.py                        # /api/admin/* — protegidas por sesión de departamento
      global_admin.py                  # /api/global/* — protegidas por sesión de admin global

frontend/
  tickets/
    usuario/index.html             # página del solicitante (QR / liga pública) -> "/"
    admin/                         # panel de administrador, dividido en varias pantallas
      admin-shared.js                 # sesión, barra de navegación, utilidades y picker de vehículo compartidos
      login.html                      # bienvenida + contraseña -> "/admin"
      dashboard.html                  # pantalla principal: alertas, gráficas (Chart.js) y accesos -> "/admin/dashboard"
      tickets.html                    # kanban de tickets (arrastrar entre estados) -> "/admin/tickets"
      inventario.html                 # alta/edición/baja de vehículos y QR -> "/admin/inventario"
      reportes.html                   # tickets + historial por vehículo -> "/admin/reportes"
      configuracion.html              # ajustes del departamento (correo de notificaciones) -> "/admin/configuracion"
      global-login.html               # contraseña maestra -> "/global"
      global-panel.html               # todos los departamentos, PIN/reset, alta -> "/global/panel"
    assets/logo-am.png             # logo, ver también backend/app/assets/
```

Tras iniciar sesión en `/admin`, el Dashboard es la pantalla principal: KPIs (total de
tickets, abiertos, en proceso, resueltos, promedio de días de solución, antigüedad del
ticket más viejo abierto), alertas de atención urgente (prioridad Alta abiertos, reportes
sin clasificar, tickets abiertos hace más de 5 días), gráficas (tickets por tipo de
incidente, estado del inventario) y tablas de distribución (por tipo de ticket, por
estado) — todo calculado en vivo sobre los tickets/vehículos del departamento. Debajo,
accesos a Inventario de unidades y Reportes individuales. Toda alta, edición o baja de
vehículos vive en Inventario — Reportes individuales es de solo lectura (tickets,
estadísticas de tiempo de solución e historial de eventos de un vehículo, pensado para
detectar unidades con desgaste o fallas recurrentes). El Kanban de Tickets y Configuración
viven como secciones hermanas en la barra de navegación superior.

En Tickets, además del toggle Kanban/Lista hay una tercera vista, **Archivo**: un ticket en
un estado final (Resuelto, Cerrado, Asignado o Negado) sale de Kanban/Lista automáticamente
5 días después de resuelto (`resolved_at`) y pasa a Archivo — mantiene el panel principal
enfocado en lo activo sin perder el historial (nada se borra; es solo un filtro por fecha,
calculado en el navegador, sin columna ni job nuevo). Un cuarto tab, **Todos**, combina
Reportes + Asignaciones en Lista y Archivo (el Kanban se queda por tipo, porque sus columnas
son los estados de un solo tipo).

## Reportes de falla: vehículo obligatorio y foto opcional

Un reporte de falla (`POST /api/departments/{slug}/tickets` con el tipo "Reporte de falla")
**siempre** debe traer `entity_id` — el backend lo rechaza con 400 si falta. Tiene sentido con
el flujo del formulario público: para "Levantar ticket" siempre se elige o escanea un vehículo
primero; solo "Pedir un vehículo" (Asignación) puede quedar sin vehículo, porque ahí es
flota quien asigna la unidad después (a menos que sea alguien de Circulación que ya escaneó
el QR de una unidad específica).

El formulario de reporte también permite adjuntar una foto (`campos.foto_path` en el
ticket). No importa el tamaño/calidad que suba el personal desde su celular: se reduce en
el navegador antes de enviarla (canvas, máx. 1600px) y **otra vez** en el backend al
recibirla (`app/photos.py`, PIL, máx. 1280px, JPEG calidad 70) — esa es la compresión que
de verdad cuenta, la del navegador es solo para que la subida no sea pesada. Se guarda en
**Supabase Storage** (bucket privado `reportes-fotos`), no en la base de datos — la tabla
`tickets` solo guarda el path. Los admins la ven vía `GET /api/admin/tickets/{id}/foto`
(requiere sesión, valida que el ticket sea de su departamento).

El bucket `reportes-fotos` ya se creó (privado) en el Supabase de este proyecto. Si se
monta un Supabase nuevo desde cero, hay que crearlo una vez — vía el dashboard
(Storage → New bucket → "reportes-fotos", privado) o con
`supabase.storage.create_bucket("reportes-fotos", options={"public": False})` usando el
service role key.

## Arranque local

La forma que refleja exactamente el ruteo de producción (un solo origen) es la CLI de Vercel:

```powershell
npm install -g vercel   # una sola vez
vercel dev
```

Esto sirve `frontend/` y las funciones de `backend/` bajo el mismo `http://localhost:3000`, igual que en producción — sin configurar nada de CORS.

Para iterar solo en la API (por ejemplo con `curl`) también puedes correr el backend suelto:

```powershell
cd backend
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Esto levanta la API en `http://127.0.0.1:5000`. Sin credenciales de Supabase corre con datos demo (la contraseña de admin demo es `12345678`).

## Supabase

1. Crea un proyecto en Supabase.
2. Ejecuta `schema.sql` en el SQL Editor.
3. Copia la URL y la **service role key** a `backend/.env` como `SUPABASE_SERVICE_KEY`. El backend Flask corre en el servidor (nunca en el navegador), así que es seguro usarla ahí — el control de acceso al panel admin lo hace la sesión de Flask, no las políticas RLS. Nunca la expongas en el frontend ni la subas a git.
4. Define un `FLASK_SECRET_KEY` propio en `backend/.env` (una cadena aleatoria larga) para que las sesiones de admin sobrevivan a un reinicio del servidor.
5. Fija la contraseña de administrador de cada departamento (8 dígitos): desde `backend/`, `python scripts/set_passcode.py flota 12345678`.
6. Si tienes un inventario de vehículos en `vehiculos.json` (raíz del repo, con `placa`, `marca`, `modelo`, `tipo`, `año`, `estado`, `departamento`, `combustible`), impórtalo con `python scripts/import_vehiculos.py` — es idempotente, seguro de correr varias veces.

## Notificaciones por correo

Cuando llega un ticket nuevo, el backend puede avisar por correo al departamento
(`backend/app/mailer.py`, SMTP estándar — sirve cualquier proveedor: Gmail con
contraseña de aplicación, Outlook, Zoho, un SMTP corporativo). Sin las variables
`SMTP_*` configuradas en `backend/.env`, el envío simplemente se omite; el resto de
la app sigue funcionando igual.

1. Define en `backend/.env`: `SMTP_HOST`, `SMTP_PORT` (587 por defecto), `SMTP_USER`,
   `SMTP_PASSWORD` y opcionalmente `SMTP_FROM` (si no se define, usa `SMTP_USER`).
2. Cada departamento captura su correo de aviso desde el panel, en
   `/admin/configuracion` (se guarda en `departments.notification_email`, columna
   que ya trae `schema.sql`).
3. El aviso se dispara desde `POST /api/departments/{slug}/tickets` — el mismo punto
   donde ya se crea el ticket y su evento `creado`.

Además, desde el detalle de un ticket (botón "Ver detalle" en Tickets, Kanban o Lista)
el admin puede dejar **observaciones** con la opción de enviarlas por correo al
`solicitante_email` del ticket — pensado para dudas o seguimiento puntual sobre un
caso ya en curso, separado del aviso de "ticket nuevo".

### Enviar como una cuenta real de Google ("Conectar con Google")

Para dominios de Google Workspace donde Sistemas bloquea las contraseñas de
aplicación (`app/google_oauth.py`), el admin conecta su cuenta real
(`admin@am.com.mx`, por ejemplo) una sola vez desde **`/admin/configuracion`** y
desde ahí se mandan todos los correos del departamento — sin volver a pedir
login. Si un departamento tiene cuenta de Google conectada, `mailer.py` la usa
antes que SMTP; si no, cae a SMTP; si ninguna está configurada, no envía nada.

Alguien con acceso al **Google Cloud Console** de la organización (normalmente
Sistemas) tiene que crear las credenciales una sola vez:

1. Ve a [console.cloud.google.com](https://console.cloud.google.com) y crea un
   proyecto (o usa uno existente).
2. **APIs y servicios → Biblioteca** → busca "Gmail API" → **Habilitar**.
3. **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo de usuario: **Interno** (restringe el login a cuentas @am.com.mx y
     evita el proceso de verificación pública de Google).
   - Agrega el scope `https://www.googleapis.com/auth/gmail.send` (y
     `userinfo.email`/`openid`, que ya vienen por defecto).
4. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: **Aplicación web**.
   - **URI de redirección autorizados**: agrega exactamente
     `https://tu-dominio.vercel.app/api/admin/google/callback` (producción) y,
     si vas a probar en local, `http://127.0.0.1:5000/api/admin/google/callback`.
5. Copia el **Client ID** y **Client secret** a `backend/.env` (y a las variables
   de entorno del proyecto en Vercel):
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://tu-dominio.vercel.app/api/admin/google/callback
   ```
6. En el panel, `/admin/configuracion` → botón **"Conectar con Google"** → el
   admin de flota inicia sesión con su cuenta @am.com.mx y autoriza el envío.
   Puede desconectarla en cualquier momento desde la misma pantalla.

Sin estas tres variables, el botón "Conectar con Google" responde con un error
controlado (no rompe el resto del panel) — mientras tanto, SMTP sigue
disponible como alternativa.

## Migraciones pendientes (si tu Supabase ya existía antes de este cambio)

`schema.sql` ya trae estas columnas para instalaciones nuevas. Si tu proyecto de
Supabase ya existía, corre esto una vez en el **SQL Editor**:

```sql
alter table departments add column if not exists notification_email text;
alter table departments add column if not exists google_refresh_token text;
alter table departments add column if not exists google_connected_email text;
alter table tickets add column if not exists responsable_nombre text;
```

Sin estas, "Responsable", el correo de notificaciones y "Conectar con Google"
fallan con error controlado — no rompen el resto del panel.

## Acceso de administrador

`/admin` muestra una pantalla de bienvenida; al presionar "Ingresar" pide una contraseña de 8 dígitos. Cada departamento tiene la suya (no debe compartirse) y, según cuál se ingrese, el sistema abre el panel de ese departamento — sin necesidad de elegir departamento a mano. El solicitante nunca ve este flujo: solo escanea un QR o entra a `/` para registrar su ticket.

Cada admin de departamento solo ve y toca lo de su propio departamento — todas las rutas
`/api/admin/*` filtran por `session["department_id"]`, sin excepción, así que aunque haya
varios "sistemas de tickets" (departamentos) uno nunca puede ver los tickets/vehículos de
otro. Verificado creando un segundo departamento de prueba: su sesión mostró 0 tickets
mientras Flota seguía con los suyos, sin cruce de datos.

## Administrador global

Por encima de los admins de cada departamento hay un **Administrador Global**, en
`/global` — una sola contraseña maestra (`GLOBAL_ADMIN_PASSCODE` en `backend/.env`, **no**
un PIN de 8 dígitos: usa algo largo y fuerte, es la llave que abre todo) con sesión propia
(`session["is_global_admin"]`), completamente separada de la sesión de admin de
departamento. Desde `/global/panel` puede:

- Ver todos los departamentos, con badge de si ya tienen PIN configurado y si tienen
  cuenta de Google conectada para correo.
- Ver un resumen agregado (tickets totales/abiertos de todos los departamentos juntos).
- **Crear un departamento nuevo** ("+ Nuevo departamento": slug, nombre, PIN inicial) — se
  crea automáticamente con los mismos dos tipos de ticket que Flota (Reporte de falla,
  Solicitud de vehículo), listo para usarse igual desde el día uno sin tocar SQL.
- **Resetear el PIN** de cualquier departamento (por si se pierde o se compromete) — sin
  poder ver el PIN actual de nadie: está hasheado (`werkzeug.security.generate_password_hash`,
  igual que `scripts/set_passcode.py`), solo se puede regenerar.

Sin `GLOBAL_ADMIN_PASSCODE` configurado, `/global` responde error al iniciar sesión — el
resto de la app sigue funcionando igual.

## Despliegue en Vercel

Un solo proyecto de Vercel apuntando a la raíz del repo. `vercel.json` ya define los dos builds (`backend/run.py` como función Python, `frontend/` como sitio estático) y el ruteo entre ambos. Configura en el proyecto las mismas variables de `backend/.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `FLASK_SECRET_KEY` y `GLOBAL_ADMIN_PASSCODE` (más `SMTP_*`/`GOOGLE_*` si aplican).

## API

- `GET /api/departments/{slug}` — público. Tipos de ticket y catálogo de entidades (p. ej. vehículos) para armar el formulario. No incluye tickets.
- `POST /api/departments/{slug}/tickets` — público. Crea un ticket y su evento `creado`. Rechaza (400) un "Reporte de falla" sin `entity_id`. Acepta `foto_base64` opcional (solo se procesa para reportes) — se comprime y sube a Storage, no se guarda el base64.
- `POST /api/admin/login` / `POST /api/admin/logout` / `GET /api/admin/me` — sesión de administrador por contraseña.
- `GET /api/admin/tickets` — requiere sesión. Tickets del departamento de la sesión activa.
- `PATCH /api/admin/tickets/{ticket_id}/classify` — requiere sesión. Clasifica un ticket de tipo "Reporte de falla" (`incidente_tipo`, `prioridad`).
- `PATCH /api/admin/tickets/{ticket_id}/status` — requiere sesión. Cambia el estado y registra el evento; solo sobre tickets del propio departamento.
- `PATCH /api/admin/tickets/{ticket_id}/responsable` — requiere sesión. Asigna `responsable_nombre` (texto libre) y registra el evento.
- `POST /api/admin/tickets/{ticket_id}/observaciones` — requiere sesión. Agrega una observación (evento `ticket_events` con `accion=observacion`); si `notificar_email` es `true`, se la envía por correo a `solicitante_email`.
- `GET /api/admin/tickets/{ticket_id}/foto` — requiere sesión. Regresa la foto del reporte (JPEG) desde Supabase Storage, si tiene una.
- `GET /api/admin/settings` / `PATCH /api/admin/settings` — requiere sesión. Lee/actualiza `notification_email` del departamento de la sesión (la lectura también regresa `google_connected_email`, si hay cuenta de Google conectada).
- `GET /api/admin/google/connect` — requiere sesión. Redirige a Google para autorizar el envío de correo como esa cuenta.
- `GET /api/admin/google/callback` — Google redirige aquí tras el consentimiento; guarda el refresh token y regresa a `/admin/configuracion`.
- `POST /api/admin/google/disconnect` — requiere sesión. Olvida la cuenta de Google conectada del departamento.
- `GET /api/admin/entities` — requiere sesión. Catálogo completo de vehículos (u otras entidades) del departamento.
- `POST /api/admin/entities` — requiere sesión. Da de alta un vehículo (`codigo`, `nombre`, `atributos`) y genera su QR (`qr_base64` en la respuesta, con logo y leyenda de placa/modelo) — el QR codifica una liga directa a `/?placa=...` en el frontend público.
- `PATCH /api/admin/entities/{entity_id}` — requiere sesión. Edita `codigo`, `nombre` y/o `atributos` (merge parcial) de un vehículo existente. Cambiar la placa invalida cualquier QR ya impreso con la placa anterior.
- `GET /api/admin/entities/{entity_id}/qr` — requiere sesión. Regenera el QR de un vehículo existente como imagen PNG (para reimprimirlo).
- `DELETE /api/admin/entities/{entity_id}` — requiere sesión. Elimina un vehículo del catálogo.
- `GET /api/admin/events` — requiere sesión. Eventos (`ticket_events`) de los tickets del departamento de la sesión, opcionalmente filtrados por `?entity_id=` (línea de tiempo por vehículo) y/o `?ticket_id=` (observaciones de un ticket).
- `POST /api/global/login` / `POST /api/global/logout` / `GET /api/global/me` — sesión de admin global por contraseña maestra (`GLOBAL_ADMIN_PASSCODE`), independiente de las sesiones de departamento.
- `GET /api/global/departments` — requiere sesión global. Todos los departamentos con estatus de PIN, cuenta de Google conectada y conteo de tickets.
- `POST /api/global/departments` — requiere sesión global. Crea un departamento nuevo (`slug`, `name`, `passcode` de 8 dígitos) con los tipos de ticket por defecto ya seedeados.
- `PATCH /api/global/departments/{department_id}/passcode` — requiere sesión global. Resetea el PIN de un departamento (`passcode` de 8 dígitos).
