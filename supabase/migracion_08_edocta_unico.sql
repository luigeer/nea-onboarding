-- migracion_08_edocta_unico.sql
-- `estados_cuenta` no tenía restricción única, así que `upsert` se comportaba
-- como insert y duplicaba periodos en silencio. Un periodo duplicado no rompe
-- nada visible: el modelo lo promedia dos veces y el saldo típico del cliente
-- sale sesgado hacia ese mes. Pasó al reprocesar un estado de cuenta que ya
-- estaba cargado.
--
-- La llave natural es la cuenta y su fecha de corte: un banco no emite dos
-- estados del mismo periodo para la misma cuenta.

delete from estados_cuenta e
where exists (
  select 1 from estados_cuenta d
  where d.folio = e.folio
    and coalesce(d.banco, '') = coalesce(e.banco, '')
    and coalesce(d.cuenta, '') = coalesce(e.cuenta, '')
    and d.fecha_final = e.fecha_final
    and d.creado < e.creado
);

create unique index if not exists estados_cuenta_periodo_unico
  on estados_cuenta (folio, coalesce(banco, ''), coalesce(cuenta, ''), fecha_final);
