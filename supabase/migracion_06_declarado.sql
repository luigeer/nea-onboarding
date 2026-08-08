-- migracion_06_declarado.sql
-- `info_fiscal` no distinguía un ejercicio sin declarar de uno declarado en
-- ceros, y las dos cosas llegaban al modelo como null.
--
-- Los insights de Syntage devuelven cinco ejercicios de golpe, incluyendo años
-- que todavía no se declaran. En un año NO declarado todos los nodos vienen en
-- null. En uno declarado, el SAT rellena con 0.0 las líneas que calcula y deja
-- en null las que el contribuyente no llenó: ahí un null es un cero declarado.
--
-- La diferencia mueve el score. Con `ingresos_totales` en null, la variable
-- ingreso/monto se cae del promedio y el módulo fiscal se renormaliza sobre lo
-- que queda —el balance—, que en una empresa que nunca operó es su capital
-- fundacional intacto. El módulo termina premiando a quien no facturó.

alter table info_fiscal
  add column if not exists declarado boolean;

comment on column info_fiscal.declarado is
  'true si el ejercicio tiene declaración presentada. Un ejercicio declarado en '
  'ceros no es lo mismo que un ejercicio sin declarar: en el primero los nulls '
  'son ceros declarados, en el segundo no sabemos nada.';
