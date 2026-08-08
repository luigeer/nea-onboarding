-- migracion_05_cobertura.sql
-- Dos defectos de `cobertura_riesgo`, que es la vista que decide si el modelo
-- puede correr. Un error aquí no produce un score malo: produce un score que
-- parece bueno porque se calculó sobre menos de lo que debía.
--
-- 1) `consultas_buro` contaba también la consulta del obligado solidario. Un
--    expediente con el buró del garante y sin el del acreditado abría la
--    compuerta, y el modelo corría sin el módulo que pesa 25%.
--
-- 2) `estados_requeridos` se decidía sobre `linea_autorizada`, que en la etapa
--    de validación todavía está en null. Resultado: a un cliente que pide
--    $500,000 se le pedían 3 estados de cuenta en vez de 6, justo donde la
--    exposición es mayor. Manda la línea solicitada, y la autorizada solo si
--    ya existe y es mayor.
--
-- Se agrega además `ejercicios_con_datos`, que no bloquea nada: tres
-- declaraciones extraídas y vacías son cobertura completa —eso es lo que el
-- SAT tiene—, pero que estén vacías es una señal que el resumen ejecutivo
-- necesita ver sin volver a consultar las tablas.

create or replace view cobertura_riesgo as
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
  (e.estado_codigo is not null and e.giro_codigo is not null
     and e.presencia_redes is not null and e.procedencia is not null)      as perfil_completo,
  (select count(*) from evaluaciones_riesgo r where r.folio = e.folio)     as evaluaciones,
  (select count(distinct recurso) from syntage_datos s where s.folio = e.folio)
                                                                           as recursos_syntage,
  case when greatest(coalesce(e.linea_autorizada, 0),
                     coalesce(e.linea_solicitada, 0)) > 200000
       then 6 else 3 end                                                   as estados_requeridos
from expedientes e;

-- Si una evaluación se corrió con la compuerta cerrada, el score existe pero no
-- es dictaminable. Guardarlo sin esa marca invita a citarlo después como si lo
-- fuera.
alter table evaluaciones_riesgo
  add column if not exists compuerta_abierta boolean;
