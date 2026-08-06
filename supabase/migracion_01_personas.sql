-- ============================================================================
-- Migración 01 · Tabla única de personas
-- ============================================================================
-- Pegar en el SQL Editor de Supabase y darle Run. Se puede repetir sin romper.
--
-- Por qué: antes las personas estaban modeladas de tres formas distintas —los
-- beneficiarios en su tabla, el representante dentro del JSON, el obligado a
-- medias en ambos—. Pero una misma persona puede ser representante,
-- beneficiario y obligado solidario a la vez: en RAMSOJ era los tres. Eso es
-- un renglón con tres banderas, no tres renglones.
--
-- Es el mismo criterio que el manifiesto de firmantes de la etapa 6, que
-- agrupa por conjunto de personas y no de calidades.
--
-- Con esto se puede contestar lo que antes no: en cuántos expedientes aparece
-- el mismo apoderado, que es lo que necesita el screening en listas.
-- ============================================================================

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

  -- Calidades. Una persona puede tener varias en el mismo expediente.
  es_representante  boolean not null default false,
  es_beneficiario   boolean not null default false,
  es_obligado       boolean not null default false,
  es_cofirmante     boolean not null default false,

  -- Solo aplica como beneficiario controlador
  porcentaje        numeric(5,2),
  criterio          text,
  pep               boolean,

  -- Solo aplica como representante legal. El límite del poder es compuerta
  -- de la etapa 6: si es menor a la línea autorizada, no se genera nada.
  cargo             text,
  puede_titulos_credito boolean,
  firma_individual      boolean,
  limite_monto          numeric(14,2),

  creado            timestamptz not null default now()
);

create index if not exists personas_folio_idx on personas (folio);
create index if not exists personas_rfc_idx   on personas (rfc);
create index if not exists personas_curp_idx  on personas (curp);

-- La tabla de beneficiarios queda absorbida por personas.
drop table if exists beneficiarios;

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

alter table personas enable row level security;
