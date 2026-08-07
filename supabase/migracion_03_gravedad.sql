-- ============================================================================
-- Migración 03 · Tres niveles de gravedad
-- ============================================================================
-- Pegar en el SQL Editor de Supabase y darle Run. Se puede repetir sin romper.
--
-- Antes había dos niveles, bloqueante y advertencia. No alcanzan: no es lo
-- mismo que falte un papel a que el que hay no sirva.
--
--   alta        el documento existe pero no es válido: una identificación
--               vencida, una CSF de hace medio año, un contribuyente que no
--               está ACTIVO. No se acepta con justificación: se reemplaza.
--   intermedia  falta un documento o está por vencer. Cierra el paso a riesgo,
--               pero cumplimiento lo puede aceptar por escrito.
--   baja        conviene saberlo y no detiene nada.
--
-- Se conservan los dos nombres viejos para no invalidar lo ya capturado.
-- ============================================================================

alter table observaciones drop constraint if exists observaciones_severidad_check;

alter table observaciones add constraint observaciones_severidad_check
  check (severidad in ('alta', 'intermedia', 'baja',
                       'bloqueante', 'advertencia'));

-- Lo capturado con el esquema viejo se traduce al nuevo.
update observaciones set severidad = 'alta'       where severidad = 'bloqueante';
update observaciones set severidad = 'intermedia' where severidad = 'advertencia';

-- ── Qué le falta a cada expediente para pasar a riesgo ──────────────────────
-- Una observación de gravedad alta solo se cierra resolviéndola. Una
-- intermedia también se puede aceptar, pero nunca sin justificación escrita:
-- sin ese registro la regla no es exigible ante un verificador.
create or replace view revision_expedientes as
select
  e.folio,
  e.razon_social,
  e.etapa,
  count(*) filter (where o.severidad = 'alta'       and o.estado = 'abierta') as altas,
  count(*) filter (where o.severidad = 'intermedia' and o.estado = 'abierta') as intermedias,
  count(*) filter (where o.severidad = 'baja'       and o.estado = 'abierta') as bajas,
  count(*) filter (where o.estado = 'aceptada' and coalesce(o.justificacion, '') = '')
                                                                              as aceptadas_sin_justificar,
  (count(*) filter (where o.severidad in ('alta', 'intermedia')
                      and o.estado = 'abierta') = 0)                          as puede_pasar_a_riesgo
from expedientes e
left join observaciones o on o.folio = e.folio
group by e.folio, e.razon_social, e.etapa;
