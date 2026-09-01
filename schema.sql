create extension if not exists pgcrypto;

create table if not exists departments (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  admin_passcode_hash text,
  notification_email text,
  google_refresh_token text,
  google_connected_email text,
  created_at timestamptz not null default now()
);

alter table departments add column if not exists notification_email text;
alter table departments add column if not exists google_refresh_token text;
alter table departments add column if not exists google_connected_email text;

create table if not exists department_members (
  department_id uuid references departments(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  role text not null check (role in ('agente', 'admin_departamento', 'admin_global')),
  primary key (department_id, user_id)
);

create table if not exists ticket_types (
  id uuid primary key default gen_random_uuid(),
  department_id uuid not null references departments(id) on delete cascade,
  name text not null,
  campos_config jsonb not null default '[]'::jsonb,
  estados jsonb not null default '["Abierto", "En progreso", "Resuelto", "Cerrado"]'::jsonb,
  created_at timestamptz not null default now(),
  unique (department_id, name)
);

create table if not exists entities (
  id uuid primary key default gen_random_uuid(),
  department_id uuid not null references departments(id) on delete cascade,
  codigo text not null,
  nombre text,
  atributos jsonb not null default '{}'::jsonb,
  unique (department_id, codigo)
);

create table if not exists tickets (
  id uuid primary key default gen_random_uuid(),
  folio text unique not null default ('TKT-' || upper(substr(gen_random_uuid()::text, 1, 8))),
  department_id uuid not null references departments(id) on delete restrict,
  ticket_type_id uuid not null references ticket_types(id) on delete restrict,
  entity_id uuid references entities(id) on delete set null,
  solicitante_nombre text not null,
  solicitante_email text not null,
  estado text not null default 'Abierto',
  campos jsonb not null default '{}'::jsonb,
  incidente_tipo text,
  prioridad text check (prioridad is null or prioridad in ('Alta', 'Media', 'Baja')),
  responsable_id uuid references auth.users(id) on delete set null,
  responsable_nombre text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

alter table tickets add column if not exists incidente_tipo text;
alter table tickets add column if not exists prioridad text;
alter table tickets add column if not exists responsable_nombre text;

create table if not exists ticket_events (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id) on delete cascade,
  accion text not null,
  estado_anterior text,
  estado_nuevo text,
  comentario text,
  actor_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

alter table departments enable row level security;
alter table department_members enable row level security;
alter table ticket_types enable row level security;
alter table entities enable row level security;
alter table tickets enable row level security;
alter table ticket_events enable row level security;

create or replace function is_department_member(target_department uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (
  select 1 from department_members
  where department_id = target_department and user_id = auth.uid()
); $$;

create policy "members read departments" on departments for select to authenticated using (is_department_member(id));
create policy "public reads ticket types" on ticket_types for select to anon, authenticated using (true);
create policy "members manage ticket types" on ticket_types for all to authenticated using (is_department_member(department_id)) with check (is_department_member(department_id));
create policy "members manage entities" on entities for all to authenticated using (is_department_member(department_id)) with check (is_department_member(department_id));
create policy "public creates tickets" on tickets for insert to anon, authenticated with check (true);
create policy "members read tickets" on tickets for select to authenticated using (is_department_member(department_id));
create policy "members update tickets" on tickets for update to authenticated using (is_department_member(department_id)) with check (is_department_member(department_id));
create policy "members read events" on ticket_events for select to authenticated using (exists (select 1 from tickets where tickets.id = ticket_events.ticket_id and is_department_member(tickets.department_id)));
create policy "ticket creation logs events" on ticket_events for insert to anon, authenticated with check (true);

insert into departments (slug, name) values ('flota', 'Flota') on conflict (slug) do nothing;

insert into ticket_types (department_id, name, campos_config, estados)
select id, 'Reporte de falla',
  '[{"key":"departamento_solicitante","label":"Departamento","type":"text","required":true},
    {"key":"numero_nomina","label":"Número de nómina","type":"text","required":false},
    {"key":"descripcion","label":"Describe la falla","type":"textarea","required":true}]'::jsonb,
  '["Abierto","Pendiente","En progreso","Resuelto","Cerrado"]'::jsonb
from departments where slug = 'flota'
on conflict (department_id, name) do nothing;

insert into ticket_types (department_id, name, campos_config, estados)
select id, 'Solicitud de vehículo',
  '[{"key":"departamento_solicitante","label":"Departamento","type":"text","required":true},
    {"key":"numero_nomina","label":"Número de nómina","type":"text","required":true},
    {"key":"proposito","label":"Propósito / Destino","type":"text","required":true}]'::jsonb,
  '["Abierto","Pendiente","Asignado","Negado"]'::jsonb
from departments where slug = 'flota'
on conflict (department_id, name) do nothing;

insert into entities (department_id, codigo, nombre, atributos)
select id, v.placa, v.marca || ' ' || v.modelo, v.atributos
from departments,
  (values
    ('ABC-123', 'Nissan', 'NP300', '{"año":"2022","estado":"Disponible","departamento":"Flota"}'::jsonb),
    ('XYZ-789', 'Toyota', 'Hilux', '{"año":"2021","estado":"Disponible","departamento":"Flota"}'::jsonb),
    ('DEF-456', 'Chevrolet', 'Silverado', '{"año":"2023","estado":"En taller","departamento":"Flota"}'::jsonb)
  ) as v(placa, marca, modelo, atributos)
where departments.slug = 'flota'
on conflict (department_id, codigo) do nothing;
