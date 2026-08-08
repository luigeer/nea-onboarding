-- migracion_07_perfil.sql
-- El perfil de empresa pasa de cinco variables a once, y la mayoría deja de
-- capturarse a mano: estado, antigüedad, actividad económica, empleados,
-- concentración de clientes y proveedores, compras a partes relacionadas y las
-- trece banderas de riesgo salen todas de lo que Syntage ya nos devolvió y que
-- estaba guardado sin usarse.
--
-- Lo que sigue siendo captura del operador:
--   · el código de giro, porque la tabla de seis códigos por ciclo de
--     conversión de efectivo no existe escrita en ningún lado —está pendiente—
--   · la procedencia del prospecto, que solo la sabe ventas
--   · la presencia digital
--
-- La presencia digital deja de ser una nota "Alta/Media/Baja". Pedirle esa
-- nota al operador es pedirle el juicio que debería hacer el modelo: dos
-- analistas veían la misma empresa y escribían cosas distintas. Ahora se
-- capturan hechos —sitio web, cada red con sus seguidores y la fecha de su
-- última publicación— y la nota se calcula. `presencia_redes` se conserva
-- para no perder lo ya capturado, pero el modelo ya no la lee.

create table if not exists perfil_empresa (
  folio             text primary key references expedientes(folio) on delete cascade,
  actualizado       timestamptz not null default now(),

  -- derivado de Syntage
  estado_nombre     text,
  estado_codigo     text,          -- Codigo 1 | Codigo 2 | Codigo 3
  actividad_principal text,
  actividades       jsonb,
  fecha_constitucion date,       -- del alta ante el SAT, no del acta
  empleados         integer,
  cfdi_emitidos     integer,
  anios_con_facturacion integer,
  ultimo_anio_facturado integer,
  ingresos_cfdi     numeric(16,2),
  top_cliente       jsonb,         -- {share, nombre, rfc}
  top_proveedor     jsonb,
  ventas_gobierno   numeric(6,2),
  compras_partes_relacionadas numeric(6,2),
  ventas_partes_relacionadas  numeric(6,2),
  banderas_rojas    text[],
  banderas_evaluadas text[],
  riesgos_detalle   jsonb,

  -- captura del operador
  giro_codigo       text,          -- Codigo 1..6
  procedencia_lead  text,          -- Conocido Nea | Referido Cliente | Linkedin/Expo | otro
  presencia_digital jsonb,         -- {sitio_web, sin_presencia, redes:[{red,url,seguidores,ultima_publicacion}]}
  capturado_por     text
);

comment on table perfil_empresa is
  'Módulo de perfil del modelo de riesgo. Casi todo se deriva de syntage_datos; '
  'solo giro, procedencia del prospecto y presencia digital son captura manual.';

comment on column perfil_empresa.presencia_digital is
  'Hechos, no calificación: {sitio_web, sin_presencia, redes:[{red, url, '
  'seguidores, ultima_publicacion}]}. La nota la calcula perfil_empresa.py.';

alter table perfil_empresa enable row level security;

create index if not exists perfil_empresa_actualizado_idx
  on perfil_empresa (actualizado desc);

-- `perfil_completo` miraba cuatro columnas de `expedientes`, dos de las cuales
-- ahora se derivan solas. Lo que de verdad falta capturar es el giro, la
-- procedencia y la presencia digital.
drop view if exists cobertura_riesgo;

create view cobertura_riesgo as
select
  e.folio,
  e.razon_social,
  e.etapa,
  (select count(*) from estados_cuenta s where s.folio = e.folio)          as estados_cuenta,
  (select count(*) from estados_cuenta s
     where s.folio = e.folio and s.numero_depositos_operativo is not null) as estados_reconciliados,
  (select count(*) from buro b
     where b.folio = e.folio
       and coalesce(b.sujeto, '') not ilike '%obligado solidario%')        as consultas_buro,
  (select count(*) from buro b where b.folio = e.folio)                    as consultas_buro_total,
  (select count(*) from info_fiscal f where f.folio = e.folio)             as ejercicios_fiscales,
  (select count(*) from info_fiscal f
     where f.folio = e.folio
       and (coalesce(f.ingresos_totales, 0) <> 0
            or coalesce(f.utilidad_operacion, 0) <> 0
            or coalesce(f.activo_corto_plazo, 0) <> 0
            or coalesce(f.capital_contable, 0) <> 0))                      as ejercicios_con_datos,
  (select count(*) from perfil_empresa p where p.folio = e.folio)          as perfil_derivado,
  exists (select 1 from perfil_empresa p
            where p.folio = e.folio
              and p.giro_codigo is not null
              and p.procedencia_lead is not null
              and p.presencia_digital is not null)                         as perfil_completo,
  (select count(*) from evaluaciones_riesgo r where r.folio = e.folio)     as evaluaciones,
  (select count(distinct recurso) from syntage_datos s where s.folio = e.folio)
                                                                           as recursos_syntage,
  case when greatest(coalesce(e.linea_autorizada, 0),
                     coalesce(e.linea_solicitada, 0)) > 200000
       then 6 else 3 end                                                   as estados_requeridos
from expedientes e;
