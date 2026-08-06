-- ============================================================================
-- Nea — Plataforma de onboarding · Esquema de la base
-- ============================================================================
-- Cómo usarlo: copia TODO este archivo, pégalo en el SQL Editor de Supabase y
-- dale "Run". Se puede volver a ejecutar sin romper nada (todo es IF NOT
-- EXISTS / OR REPLACE).
--
-- Diseño: la tabla `expedientes` guarda el expediente completo en la columna
-- `datos` (formato JSON, los 116 campos del schema) más unas cuantas columnas
-- "promovidas" que son por las que se filtra y se hacen cuentas. Así no hay
-- que modelar 116 columnas y nada se pierde.
--
-- Las tablas hijas existen porque responden preguntas que cruzan expedientes:
-- la exposición agregada de un obligado solidario, las vigencias por vencer y
-- el rastro de quién aceptó cada observación.
-- ============================================================================

-- ── Expedientes ─────────────────────────────────────────────────────────────
create table if not exists expedientes (
  folio             text primary key,
  razon_social      text not null,
  rfc               text not null,
  tipo_cliente      text not null
                    check (tipo_cliente in ('persona_moral', 'pfae', 'persona_fisica')),
  etapa             text not null default 'apertura',
  grupo             text,
  linea_solicitada  numeric(14,2),
  linea_modelo      numeric(14,2),   -- lo que propone el modelo de riesgo
  linea_autorizada  numeric(14,2),   -- lo que autoriza Luis; el modelo propone, no aprueba
  riesgo_pld        text check (riesgo_pld in ('bajo', 'medio', 'alto')),
  carpeta_drive     text,
  motivo_rechazo    text,
  datos             jsonb not null default '{}'::jsonb,
  creado            timestamptz not null default now(),
  actualizado       timestamptz not null default now()
);

create index if not exists expedientes_rfc_idx   on expedientes (rfc);
create index if not exists expedientes_etapa_idx on expedientes (etapa);

-- ── Personas ────────────────────────────────────────────────────────────────
-- Una fila por persona física, con sus calidades como banderas. Una misma
-- persona puede ser representante legal, beneficiario controlador y obligado
-- solidario a la vez; eso es un renglón con tres banderas, no tres renglones.
-- Mismo criterio que el manifiesto de firmantes de la etapa 6, que agrupa por
-- conjunto de personas y no de calidades.
create table if not exists personas (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,

  nombre            text not null,
  rfc               text,
  curp              text,
  fecha_nacimiento  text,          -- como lo da la CURP: dd/mm/aaaa
  lugar_nacimiento  text,
  nacionalidad      text,
  ocupacion         text,
  domicilio         text,
  correo            text,
  telefono          text,
  id_tipo           text,
  id_numero         text,

  es_representante  boolean not null default false,
  es_beneficiario   boolean not null default false,
  es_obligado       boolean not null default false,
  es_cofirmante     boolean not null default false,

  -- Solo como beneficiario controlador
  porcentaje        numeric(5,2),
  criterio          text,          -- participacion | control_efectivo
  pep               boolean,

  -- Solo como representante legal. El límite del poder es compuerta de la
  -- etapa 6: si es menor a la línea autorizada, no se genera nada.
  cargo                 text,
  puede_titulos_credito boolean,
  firma_individual      boolean,
  limite_monto          numeric(14,2),

  creado            timestamptz not null default now()
);

create index if not exists personas_folio_idx on personas (folio);
create index if not exists personas_rfc_idx   on personas (rfc);
create index if not exists personas_curp_idx  on personas (curp);

-- ── Obligados solidarios ────────────────────────────────────────────────────
create table if not exists obligados_solidarios (
  id              uuid primary key default gen_random_uuid(),
  folio           text not null references expedientes(folio) on delete cascade,
  tipo            text check (tipo in ('persona_moral', 'persona_fisica')),
  nombre          text not null,
  rfc             text,
  es_cliente      boolean not null default false,
  expediente_ref  text,
  creado          timestamptz not null default now()
);

create index if not exists obligados_rfc_idx on obligados_solidarios (rfc);

-- ── Observaciones ───────────────────────────────────────────────────────────
-- El rastro de cumplimiento: una advertencia aceptada sin justificación escrita
-- no es exigible, así que aquí queda quién la aceptó y por qué.
create table if not exists observaciones (
  id            uuid primary key default gen_random_uuid(),
  folio         text not null references expedientes(folio) on delete cascade,
  tipo          text,
  descripcion   text not null,
  severidad     text check (severidad in ('bloqueante', 'advertencia')),
  estado        text check (estado in ('abierta', 'resuelta', 'aceptada')),
  aceptada_por  text,
  justificacion text,
  fecha         date not null default current_date
);

-- ── Documentos ──────────────────────────────────────────────────────────────
create table if not exists documentos (
  id             uuid primary key default gen_random_uuid(),
  folio          text not null references expedientes(folio) on delete cascade,
  tipo           text not null,
  sujeto         text,           -- de quién es, cuando hay varios (beneficiarios)
  fecha_emision  date,
  vigente_hasta  date,
  legible        boolean not null default true,
  drive_file_id  text,
  superado       boolean not null default false
);

create index if not exists documentos_vigencia_idx on documentos (vigente_hasta);

-- ── Exposición agregada ─────────────────────────────────────────────────────
-- La pregunta que hoy no se puede contestar porque cada expediente se analiza
-- aislado: si una tenedora tiene línea propia de un millón y garantiza dos
-- millones más, la exposición real es de tres.
create or replace view exposicion_agregada as
with garantias as (
  select
    o.rfc,
    max(o.nombre)                        as nombre,
    count(distinct o.folio)              as expedientes_garantizados,
    coalesce(sum(e.linea_autorizada), 0) as suma_garantizada
  from obligados_solidarios o
  join expedientes e on e.folio = o.folio
  where o.rfc is not null
  group by o.rfc
)
select
  g.rfc,
  g.nombre,
  g.expedientes_garantizados,
  g.suma_garantizada,
  coalesce(p.linea_autorizada, 0)                       as linea_propia,
  g.suma_garantizada + coalesce(p.linea_autorizada, 0)  as exposicion_total
from garantias g
left join expedientes p on p.rfc = g.rfc;

-- ── Una persona a través de varios expedientes ──────────────────────────────
-- El insumo del screening en listas: quién se repite y con qué calidad.
create or replace view personas_recurrentes as
select
  coalesce(nullif(rfc, ''), nullif(curp, ''), upper(nombre)) as identificador,
  max(nombre)                  as nombre,
  count(distinct folio)        as expedientes,
  array_agg(distinct folio)    as folios,
  bool_or(es_representante)    as fue_representante,
  bool_or(es_beneficiario)     as fue_beneficiario,
  bool_or(es_obligado)         as fue_obligado
from personas
group by 1
having count(distinct folio) > 1;

-- ── Documentos por vencer ───────────────────────────────────────────────────
create or replace view vigencias_por_vencer as
select
  d.folio,
  e.razon_social,
  d.tipo,
  d.sujeto,
  d.vigente_hasta,
  (d.vigente_hasta - current_date) as dias_restantes
from documentos d
join expedientes e on e.folio = d.folio
where d.superado = false
  and d.vigente_hasta is not null
  and d.vigente_hasta <= current_date + 30
order by d.vigente_hasta;

-- ── Marca de tiempo automática ──────────────────────────────────────────────
create or replace function tocar_actualizado() returns trigger as $$
begin
  new.actualizado = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists expedientes_actualizado on expedientes;
create trigger expedientes_actualizado
  before update on expedientes
  for each row execute function tocar_actualizado();

-- ── Seguridad ───────────────────────────────────────────────────────────────
-- Se prende RLS sin políticas: eso significa que la llave pública (anon) NO
-- puede leer ni escribir nada. Solo la llave de servicio, que vive en tu
-- archivo .env local y nunca sale de tu computadora, tiene acceso.
-- Aquí hay CURP, RFC y domicilios de personas reales: es el default correcto.
alter table expedientes          enable row level security;
alter table personas             enable row level security;
alter table obligados_solidarios enable row level security;
alter table observaciones        enable row level security;
alter table documentos           enable row level security;
