-- ============================================================================
-- Migración 04 · Consultas de buró sin historial
-- ============================================================================
-- Pegar en el SQL Editor de Supabase y darle Run. Se puede repetir sin romper.
--
-- Una consulta de buró que no encuentra historial **no es lo mismo que una
-- empresa con historial limpio**, y la diferencia vale 25% del modelo.
--
-- Si se capturan los diez campos en cero, el modelo lee "sin deuda vencida,
-- sin mora, sin créditos abiertos" y premia al cliente por un buen historial
-- que en realidad no existe. Lo correcto es dejarlos nulos: el módulo de buró
-- se cae y el score se renormaliza sobre los otros tres.
--
-- Por eso hacen falta dos columnas: para distinguir "no consultamos" de
-- "consultamos y no había nada", que sin ellas se ven igual.
-- ============================================================================

alter table buro add column if not exists folio_consulta text;
alter table buro add column if not exists resultado      text
  check (resultado is null or resultado in ('con_historial', 'sin_historial', 'error'));
alter table buro add column if not exists previsor       text;
alter table buro add column if not exists producto       text;

comment on column buro.resultado is
  'sin_historial: la consulta se hizo y el sujeto no tiene información crediticia. '
  'Los diez campos quedan nulos a propósito y el módulo de buró se excluye del '
  'modelo en lugar de puntuar alto por un historial que no existe.';

-- ── Qué consultas se han hecho ──────────────────────────────────────────────
-- Cada consulta cuesta y deja huella en el historial del consultado: el propio
-- modelo penaliza el número de consultas de los últimos doce meses. Esta vista
-- existe para no repetir una que ya se hizo.
create or replace view consultas_buro as
select
  b.folio,
  e.razon_social,
  b.sujeto,
  b.fecha_consulta,
  b.folio_consulta,
  b.resultado,
  b.score_pyme,
  (current_date - b.fecha_consulta)                       as dias_desde_consulta,
  (current_date - b.fecha_consulta) <= 90                 as vigente
from buro b
join expedientes e on e.folio = b.folio
order by b.fecha_consulta desc;
