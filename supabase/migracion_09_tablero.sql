-- migracion_09_tablero.sql
-- "¿Dónde están atorados?" no se puede contestar con los datos que había: la
-- tabla `expedientes` guarda la etapa actual y cuándo se actualizó por última
-- vez, y eso no es lo mismo. Un expediente que cambió de etapa ayer y otro que
-- lleva tres semanas parado en la misma etapa pero se le tocó una observación
-- ayer se ven idénticos.
--
-- La bitácora se llena con un disparador y no desde el código, a propósito: hay
-- varias rutas que mueven la etapa —el CLI, un script suelto, yo editando la
-- tabla— y una bitácora que dependa de que cada una se acuerde de escribirla
-- miente justo cuando más se necesita.

create table if not exists bitacora_etapas (
  id          bigserial primary key,
  folio       text not null references expedientes(folio) on delete cascade,
  etapa_de    text,
  etapa_a     text not null,
  entro_el    timestamptz not null default now()
);

create index if not exists bitacora_etapas_folio_idx
  on bitacora_etapas (folio, entro_el desc);

comment on table bitacora_etapas is
  'Cada cambio de etapa de un expediente. La llena un disparador, no el codigo: '
  'varias rutas mueven la etapa y una bitacora que dependa de que cada una se '
  'acuerde de escribirla miente cuando mas se necesita.';

create or replace function registrar_cambio_etapa()
returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    insert into bitacora_etapas (folio, etapa_de, etapa_a)
      values (new.folio, null, new.etapa);
  elsif new.etapa is distinct from old.etapa then
    insert into bitacora_etapas (folio, etapa_de, etapa_a)
      values (new.folio, old.etapa, new.etapa);
  end if;
  return new;
end $$;

drop trigger if exists expedientes_bitacora_etapas on expedientes;
create trigger expedientes_bitacora_etapas
  after insert or update of etapa on expedientes
  for each row execute function registrar_cambio_etapa();

-- Sembrar lo que ya existe: sin esto los expedientes abiertos antes de la
-- bitácora salen sin fecha de entrada y el tablero los reporta como si acabaran
-- de llegar.
insert into bitacora_etapas (folio, etapa_de, etapa_a, entro_el)
select e.folio, null, e.etapa, coalesce(e.actualizado, e.creado, now())
from expedientes e
where not exists (select 1 from bitacora_etapas b where b.folio = e.folio);

alter table bitacora_etapas enable row level security;


-- ── El tablero ───────────────────────────────────────────────────────────────
-- Un renglón por expediente, con lo que hace falta para decidir a cuál dedicarle
-- el día. Los bloqueos concretos no salen de aquí: los calcula el código, que es
-- donde viven las compuertas. Esta vista da los hechos.
create or replace view tablero as
with etapa_actual as (
  select folio, max(entro_el) as entro_el
  from bitacora_etapas group by folio
),
ultima_eval as (
  select r.folio, r.score, r.veredicto, r.compuerta_abierta, r.fecha
  from evaluaciones_riesgo r
  join (select folio, max(fecha) as fecha from evaluaciones_riesgo group by folio) u
    on u.folio = r.folio and u.fecha = r.fecha
),
obs as (
  select e.folio,
         count(*) filter (where o->>'estado' = 'abierta')                    as abiertas,
         count(*) filter (where o->>'estado' = 'abierta'
                            and o->>'severidad' = 'alta')                    as abiertas_altas,
         count(*) filter (where o->>'estado' = 'abierta'
                            and o->>'severidad' = 'intermedia')              as abiertas_intermedias,
         count(*) filter (where o->>'estado' = 'abierta'
                            and coalesce(o->>'pedir', '') <> '')             as pendientes_cliente,
         count(*) filter (where o->>'estado' = 'aceptada')                   as riesgos_asumidos
  from expedientes e
  left join lateral jsonb_array_elements(
    case when jsonb_typeof(e.datos->'observaciones') = 'array'
         then e.datos->'observaciones' else '[]'::jsonb end) o on true
  group by e.folio
)
select
  e.folio,
  e.grupo,
  e.razon_social,
  e.etapa,
  a.entro_el                                                    as etapa_desde,
  greatest(0, extract(day from now() - a.entro_el)::int)         as dias_en_etapa,
  e.linea_solicitada,
  e.linea_autorizada,
  v.score,
  v.veredicto,
  v.compuerta_abierta,
  coalesce(o.abiertas, 0)              as observaciones_abiertas,
  coalesce(o.abiertas_altas, 0)        as abiertas_altas,
  coalesce(o.abiertas_intermedias, 0)  as abiertas_intermedias,
  coalesce(o.pendientes_cliente, 0)    as pendientes_cliente,
  coalesce(o.riesgos_asumidos, 0)      as riesgos_asumidos,
  c.estados_cuenta,
  c.estados_requeridos,
  c.consultas_buro,
  c.ejercicios_con_datos,
  c.perfil_completo,
  e.creado,
  e.actualizado
from expedientes e
left join etapa_actual a on a.folio = e.folio
left join ultima_eval  v on v.folio = e.folio
left join obs          o on o.folio = e.folio
left join cobertura_riesgo c on c.folio = e.folio;

comment on view tablero is
  'Un renglon por expediente con lo necesario para decidir a cual dedicarle el '
  'dia. Los bloqueos concretos los calcula el codigo: las compuertas viven ahi.';
