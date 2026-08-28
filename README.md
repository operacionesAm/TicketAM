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
    qr.py                           # genera el QR de cada vehículo (con logo y leyenda)
    assets/logo-am.png               # logo usado en el QR impreso (copia de frontend/tickets/assets)
    routes/
      public.py                      # /api/departments/* — sin autenticación
      admin.py                        # /api/admin/* — protegidas por sesión

frontend/
  tickets/
    usuario/index.html             # página del solicitante (QR / liga pública) -> "/"
    admin/                         # panel de administrador, en reestructuración a varias
                                    # pantallas (Tickets / Dashboard / Inventario); por ahora
                                    # "tickets.html" sigue siendo el panel completo -> "/admin"
    assets/logo-am.png             # logo, ver también backend/app/assets/
```

> Nota (en progreso): el panel de admin se está dividiendo de una sola página con tabs a
> varias pantallas navegables (`/admin/tickets`, `/admin/dashboard`, `/admin/inventario`).
> Mientras tanto, `/admin` sigue sirviendo el panel completo de siempre desde su nueva
> ubicación en `frontend/tickets/admin/tickets.html`.

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

## Acceso de administrador

`/admin` muestra una pantalla de bienvenida; al presionar "Ingresar" pide una contraseña de 8 dígitos. Cada departamento tiene la suya (no debe compartirse) y, según cuál se ingrese, el sistema abre el panel de ese departamento — sin necesidad de elegir departamento a mano. El solicitante nunca ve este flujo: solo escanea un QR o entra a `/` para registrar su ticket.

## Despliegue en Vercel

Un solo proyecto de Vercel apuntando a la raíz del repo. `vercel.json` ya define los dos builds (`backend/run.py` como función Python, `frontend/` como sitio estático) y el ruteo entre ambos. Configura en el proyecto las mismas variables de `backend/.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` y `FLASK_SECRET_KEY`.

## API

- `GET /api/departments/{slug}` — público. Tipos de ticket y catálogo de entidades (p. ej. vehículos) para armar el formulario. No incluye tickets.
- `POST /api/departments/{slug}/tickets` — público. Crea un ticket y su evento `creado`.
- `POST /api/admin/login` / `POST /api/admin/logout` / `GET /api/admin/me` — sesión de administrador por contraseña.
- `GET /api/admin/tickets` — requiere sesión. Tickets del departamento de la sesión activa.
- `PATCH /api/admin/tickets/{ticket_id}/status` — requiere sesión. Cambia el estado y registra el evento; solo sobre tickets del propio departamento.
- `GET /api/admin/entities` — requiere sesión. Catálogo completo de vehículos (u otras entidades) del departamento.
- `POST /api/admin/entities` — requiere sesión. Da de alta un vehículo (`codigo`, `nombre`, `atributos`) y genera su QR (`qr_base64` en la respuesta, con logo y leyenda de placa/modelo) — el QR codifica una liga directa a `/?placa=...` en el frontend público.
- `PATCH /api/admin/entities/{entity_id}` — requiere sesión. Edita `codigo`, `nombre` y/o `atributos` (merge parcial) de un vehículo existente. Cambiar la placa invalida cualquier QR ya impreso con la placa anterior.
- `GET /api/admin/entities/{entity_id}/qr` — requiere sesión. Regenera el QR de un vehículo existente como imagen PNG (para reimprimirlo).
- `DELETE /api/admin/entities/{entity_id}` — requiere sesión. Elimina un vehículo del catálogo.
- `GET /api/admin/events` — requiere sesión. Eventos (`ticket_events`) de los tickets del departamento de la sesión, opcionalmente filtrados por `?entity_id=` — usado para la línea de tiempo por vehículo.
