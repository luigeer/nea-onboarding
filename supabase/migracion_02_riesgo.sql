-- ============================================================================
-- Migración 02 · Los insumos del modelo de riesgo
-- ============================================================================
-- Pegar en el SQL Editor de Supabase y darle Run. Se puede repetir sin romper.
--
-- Hasta ahora la base guardaba el resultado del modelo pero no sus insumos: la
-- línea autorizada estaba, pero no el buró, ni las cifras de los estados de
-- cuenta, ni la declaración anual. Si alguien pregunta por qué se autorizó una
-- línea, el expediente no lo puede contestar.
--
-- Cuatro tablas, una por módulo del modelo, más el rastro de cada evaluación.
-- ============================================================================

-- ── Perfil de empresa ───────────────────────────────────────────────────────
-- Es uno a uno con el expediente, así que van como columnas y no como tabla.
-- El estado y el giro son códigos de las tablas del modelo; la antigüedad y el
-- monto ya se derivan de la constitutiva y del crédito solicitado.
alter table expedientes add column if not exists estado_codigo    text;
alter table expedientes add column if not exists giro_codigo      text;
alter table expedientes add column if not exists presencia_redes  text;
alter table expedientes add column if not exists procedencia      text;

-- ── Estados de cuenta ───────────────────────────────────────────────────────
-- Un renglón por cuenta y periodo, con las catorce cifras que produce el Bank
-- Statement Analyzer.
--
-- Las columnas *_operativo son las cifras reconciliadas: sin traspasos entre
-- cuentas propias, sin disposiciones de crédito, sin ciclos de inversión
-- overnight. El modelo las prefiere cuando existen, porque los conteos de
-- encabezado premian a quien mueve dinero entre sus propias cuentas.
create table if not exists estados_cuenta (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,

  banco             text,
  cuenta            text,          -- últimos 4 dígitos
  moneda            text not null default 'MXN',
  tipo_cambio       numeric(12,4), -- pesos por unidad, si no es MXN
  fecha_inicial     date,
  fecha_final       date,

  saldo_inicial     numeric(16,2),
  numero_depositos  integer,
  monto_depositos   numeric(16,2),
  numero_retiros    integer,
  monto_retiros     numeric(16,2),
  saldo_final       numeric(16,2),
  saldo_promedio    numeric(16,2),
  saldo_minimo      numeric(16,2),
  saldo_maximo      numeric(16,2),

  numero_depositos_operativo  integer,
  numero_retiros_operativo    integer,
  monto_depositos_operativo   numeric(16,2),
  monto_retiros_operativo     numeric(16,2),

  verificado_cep    boolean,       -- verificación SPEI contra el CEP de Banxico
  drive_file_id     text,
  creado            timestamptz not null default now()
);

create index if not exists edoscta_folio_idx on estados_cuenta (folio);
create index if not exists edoscta_fecha_idx on estados_cuenta (folio, fecha_final desc);

-- ── Buró de crédito ─────────────────────────────────────────────────────────
-- El buró se extrae por fuera de Syntage, por costo, así que estos campos se
-- capturan del reporte PYME Plus. Un renglón por consulta: se puede volver a
-- consultar y hay que poder comparar contra la anterior.
create table if not exists buro (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,
  fecha_consulta    date not null default current_date,
  sujeto            text,          -- de quién es; normalmente la persona moral

  ocurrencias_mora              integer,
  saldo_vencido                 numeric(16,2),
  saldo_actual                  numeric(16,2),
  peor_edo_6m                   integer,
  consultas_12m                 integer,
  creditos_abiertos_ultimo_ano  integer,
  creditos_abiertos             integer,
  avales                        integer,
  score_pyme                    integer,
  prevenciones                  text,   -- null | Amarilla | Roja

  drive_file_id     text,
  creado            timestamptz not null default now()
);

create index if not exists buro_folio_idx on buro (folio, fecha_consulta desc);

-- ── Información fiscal ──────────────────────────────────────────────────────
-- Un renglón por ejercicio. La fuente importa: no es lo mismo un dato extraído
-- por API con autorización del cliente que uno tecleado a mano.
create table if not exists info_fiscal (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,
  ejercicio         integer not null,
  fuente            text not null default 'manual'
                    check (fuente in ('manual', 'syntage', 'belvo', 'declaracion')),

  ingresos_totales      numeric(18,2),
  utilidad_operacion    numeric(18,2),
  activo_corto_plazo    numeric(18,2),
  pasivo_corto_plazo    numeric(18,2),
  capital_contable      numeric(18,2),
  inventarios           numeric(18,2),
  dictaminados          boolean,

  -- Señales que el modelo no consume pero que sí mueven la decisión.
  ingresos_partes_relacionadas numeric(18,2),
  ingresos_gobierno            numeric(18,2),
  dias_para_cobrar             integer,
  dias_para_pagar              integer,

  obtenido          date,
  creado            timestamptz not null default now()
);

create unique index if not exists info_fiscal_unica
  on info_fiscal (folio, ejercicio, fuente);

-- ── Syntage en crudo ────────────────────────────────────────────────────────
-- Se guarda **todo** lo que devuelve Syntage, no solo lo que el modelo consume
-- hoy. Dos razones: el modelo va a cambiar y no queremos volver a extraer, y el
-- resumen ejecutivo debe poder analizar más de lo que el score captura.
--
-- Esta tabla es la fuente de verdad; `info_fiscal` es una proyección suya para
-- las consultas del modelo, igual que `expedientes.datos` frente a sus columnas
-- promovidas. Cada extracción queda como una foto con su fecha: nada se pisa.
create table if not exists syntage_datos (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,
  entidad_syntage   text,          -- entityId del lado de Syntage
  recurso           text not null, -- 'tax-returns', 'insights/customer-concentration', ...
  ejercicio         integer,       -- si el recurso es por año
  obtenido          timestamptz not null default now(),
  payload           jsonb not null,
  creado_por        text
);

create index if not exists syntage_folio_idx   on syntage_datos (folio, recurso, obtenido desc);
create index if not exists syntage_recurso_idx on syntage_datos (recurso);
create index if not exists syntage_payload_idx on syntage_datos using gin (payload);

-- La foto más reciente de cada recurso por expediente. Es lo que se consulta
-- normalmente; el historial completo sigue en la tabla.
create or replace view syntage_vigente as
select distinct on (folio, recurso, coalesce(ejercicio, -1))
  folio, recurso, ejercicio, obtenido, payload
from syntage_datos
order by folio, recurso, coalesce(ejercicio, -1), obtenido desc;

-- ── Evaluaciones del modelo ─────────────────────────────────────────────────
-- El rastro de la decisión. Un renglón por corrida: si el expediente vuelve de
-- recolección y se recalcula, queda la historia.
--
-- El modelo propone, no aprueba. Por eso la línea propuesta y la autorizada son
-- columnas distintas, y `senales_no_modeladas` existe para lo que el score no
-- captura pero sí mueve la decisión — capital contable negativo, concentración
-- de clientes, nómina en cero con ingresos altos.
create table if not exists evaluaciones_riesgo (
  id                uuid primary key default gen_random_uuid(),
  folio             text not null references expedientes(folio) on delete cascade,
  fecha             timestamptz not null default now(),

  score             numeric(6,4),
  veredicto         text,          -- Aprobado | Comité | Rechazado | Sin datos suficientes
  vetos             text[],

  modulo_perfil          numeric(6,4),
  modulo_buro            numeric(6,4),
  modulo_edos_cuenta     numeric(6,4),
  modulo_declaracion     numeric(6,4),
  modulos_sin_datos      text[],

  linea_propuesta   numeric(14,2),
  linea_autorizada  numeric(14,2),
  autorizada_por    text,
  senales_no_modeladas text,
  justificacion     text,          -- por qué se apartó del modelo, si se apartó

  version_modelo    text,
  detalle           jsonb,         -- desglose por variable, tal como lo devuelve el código
  creado_por        text
);

create index if not exists evaluaciones_folio_idx on evaluaciones_riesgo (folio, fecha desc);

-- ── Cobertura de insumos ────────────────────────────────────────────────────
-- Qué le falta a cada expediente para poder correr el modelo. Es la vista que
-- contesta "por qué no puedo evaluar a este cliente todavía".
create or replace view cobertura_riesgo as
select
  e.folio,
  e.razon_social,
  e.etapa,
  (select count(*) from estados_cuenta s where s.folio = e.folio)          as estados_cuenta,
  (select count(*) from estados_cuenta s
     where s.folio = e.folio and s.numero_depositos_operativo is not null) as estados_reconciliados,
  (select count(*) from buro b where b.folio = e.folio)                    as consultas_buro,
  (select count(*) from info_fiscal f where f.folio = e.folio)             as ejercicios_fiscales,
  (e.estado_codigo is not null and e.giro_codigo is not null
     and e.presencia_redes is not null and e.procedencia is not null)      as perfil_completo,
  (select count(*) from evaluaciones_riesgo r where r.folio = e.folio)     as evaluaciones,
  (select count(distinct recurso) from syntage_datos s where s.folio = e.folio)
                                                                           as recursos_syntage,
  case when e.linea_autorizada > 200000 then 6 else 3 end                  as estados_requeridos
from expedientes e;

alter table estados_cuenta      enable row level security;
alter table buro                enable row level security;
alter table info_fiscal         enable row level security;
alter table syntage_datos       enable row level security;
alter table evaluaciones_riesgo enable row level security;
