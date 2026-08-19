# Estaciones por cliente de monedero — diseño

## Por qué

Ya sabemos qué clientes tienen facturas de un RFC del padrón de monederos
([monederos.py](../../../monederos.py)) y cuánto les factura ese RFC en total
(`clientes_monedero.md`). Pero esa cifra mezcla dos cosas distintas:

- Facturación real de un **monedero** (Efecticard, Sí Vale, Toka, Clara,
  Broxel, Edenred, Pluxee): estas empresas no venden gasolina, así que
  cualquier factura suya es evidencia de monedero.
- Facturación de una **gasolinera que además tiene su propio monedero de
  marca** (Petro-7, Hidrosina, Ultra Gas, Ultragas Control Card, +Cargas,
  MI MONEDERO FERCHEGAS, GOSMO, ONE CARD GAS, Ecovale...): una factura suya
  puede ser una carga directa en su propia estación (sin monedero de por
  medio) o el estado de cuenta real del monedero.

`supplier-concentration` no distingue entre las dos, así que la cifra de
`clientes_monedero.md` puede estar inflada para estos casos. Este trabajo
corrige eso y responde lo que sigue: con qué monedero(s) trabaja cada
cliente, en cuántas estaciones distintas carga, y cuánto le facturan al mes
y por estación — usando los últimos 3 meses.

## Cómo se distingue lo real de lo directo

Un monedero real emite, junto con su CFDI normal (que suele traer un
concepto simbólico — "CARGO ADMINISTRATIVO" de $1 con descuento de $1, o
"Comisión por fondos insuficientes" de unos pesos), un complemento
**"Estado de Cuenta de Combustibles para Monederos Electrónicos"** — un
complemento estandarizado por el SAT, igual en estructura sin importar qué
monedero lo emite. Ese complemento trae el detalle real: cada carga, con su
RFC de estación, clave de estación, litros e importe.

Una carga directa en una gasolinera-que-también-es-monedero no trae ese
complemento: es un CFDI normal por el monto real de la gasolina.

La señal para distinguirlos sin abrir cada factura: el patrón de **monto
simbólico recurrente, uno por mes**. Si un RFC le factura a un cliente ese
patrón en al menos 2 de los últimos 3 meses, es monedero real. Si no, fue
compra directa.

## Qué ya se confirmó (spike manual)

- `/entities/{id}/invoices` (Syntage) no está en el repo, pero existe y
  funciona; devuelve el CFDI completo incluyendo `items`, `subtotal`,
  `discount`, `issuedAt`.
- Ese endpoint **no** trae el complemento de combustible — solo los
  conceptos base del CFDI. No hay ruta de la API pública que devuelva el
  XML o el PDF completo con el complemento.
- El PDF si se puede descargar a mano desde el panel de Syntage (así se
  consiguieron los dos ejemplos de esta conversación).
- `pdfplumber.extract_tables()` sí separa las celdas de estas tablas de
  forma limpia (a diferencia de `extract_text()`, que pega las palabras).
  Cada bloque de cargo es una tabla de 4 filas: encabezado, datos,
  encabezado de traslados, datos de traslados.
- El bloque resumen ("Versión / Tipo de Operación / Número de Cuenta /
  Subtotal / Total") da un total declarado contra el cual cuadrar la suma
  de cargos parseados — mismo principio que ya usa
  [bbva.py](../../../bbva.py) (`cuadra()`).

## Alcance

Etapa 1 corre sobre **todos** los clientes y monederos que ya detectamos
(no solo un top 30 preseleccionado): la cifra real de facturación —y por
tanto quién consume más y a quién le cobran más— no se conoce hasta
después de esta etapa, así que preseleccionar de antemano perdería casos.

## Arquitectura — dos módulos nuevos

### `estaciones_monedero.py` (Etapa 1, solo API — sin descargar nada)

- `facturas_candidatas(entidad_id, rfc_monedero, desde, hasta)`: pide a
  Syntage las facturas de ese emisor para esa entidad en el rango de
  fechas, y regresa las que calzan con el patrón de monto simbólico: un
  subtotal por debajo de un umbral bajo (los dos ejemplos reales son $1.00
  y $2.09; se usa $50 como corte, generoso a propósito porque lo que de
  verdad separa "monedero real" de "compra directa" es la recurrencia
  mensual, no el monto exacto).
- `confirmar_monedero_real(entidad_id, rfc_monedero, hoy)`: agrupa las
  candidatas por mes sobre los últimos 3 meses; si hay candidata en al
  menos 2 de esos 3 meses, es monedero real. Devuelve
  `(es_real, facturas_por_mes)`.
- `plan_descarga(clientes)`: recorre cada cliente y cada monedero que se le
  detectó antes; para los confirmados, arma la lista de qué descargar a
  mano: RFC cliente, RFC y nombre del monedero, mes, folio fiscal (UUID) de
  la factura candidata de ese mes, para ubicarla fácil en el panel de
  Syntage.

### `estado_cuenta_monedero.py` (Etapa 2 — parser de los PDF ya descargados)

- `leer_pdf(ruta)`: con pdfplumber, recorre todas las páginas y junta:
  - encabezado: RFC/nombre emisor, RFC/nombre receptor, folio fiscal
  - resumen de cuenta: versión, tipo de operación, número de cuenta,
    subtotal y total declarados (puede haber cuentas — tarjetas — distintas
    dentro del mismo estado de cuenta; el subtotal/total declarado es del
    estado de cuenta completo)
  - cada cargo: identificador de tarjeta, fecha y hora (vienen pegadas sin
    separador — `2026-03-0919:06:04` — se separan por posición fija
    `AAAA-MM-DD` + `HH:MM:SS`), RFC de estación, clave de estación,
    cantidad, tipo/nombre de combustible, folio de operación, valor
    unitario, importe
- `cuadra(cargos, subtotal_declarado)`: la suma de importes debe coincidir
  con el subtotal declarado. Si no cuadra, el PDF se marca sospechoso —
  nunca se descarta en silencio ni se usa a medias.
- `agregar_por_estacion(cargos)`: agrupa por (RFC de estación, clave de
  estación) → número de cargas, litros, importe total.

### Reporte final

Une las dos etapas: por cliente, monedero(s) confirmado(s), número de
estaciones distintas donde cargó en los últimos 3 meses, monto total
transaccionado por mes, monto por estación.

## Convención de archivos

`descargas/monederos/{RFC_CLIENTE}_{RFC_MONEDERO}_{AAAA-MM}.pdf`. El parser
no depende del nombre del archivo (lee RFC y fechas del propio PDF); el
nombre es solo para organizar la descarga manual.

## Manejo de errores

- PDF que no cuadra contra su subtotal declarado → se reporta como
  sospechoso, no entra al reporte agregado.
- Mes sin PDF descargado → se marca "falta este mes", nunca se rellena con
  cero.
- Cliente sin entidad en Syntage o con extracción incompleta → mismo
  patrón que ya usa `monederos.analizar_cliente()`.

## Pruebas

Los dos PDF de ejemplo de esta conversación traen RFC y razón social de
clientes reales — no se pueden commitear al repo. Las pruebas de
`estado_cuenta_monedero.py` simulan el retorno de `extract_tables()` con
datos inventados (mismo patrón que `test_insumos_riesgo.py` simula
Supabase), no generan PDFs sintéticos. Las pruebas de
`estaciones_monedero.py` simulan `syntage.pedir`/`syntage.insight` con
facturas inventadas, mismo patrón que ya usa `test_monederos.py`.

## Qué queda fuera (a propósito)

- La comisión que cobra cada monedero (tercera pregunta original) sigue
  pendiente: no se resuelve con este complemento, que da litros e importe
  de la gasolina, no la comisión del servicio.
- Automatizar la descarga del PDF vía la plataforma web de Syntage (no la
  API pública) queda fuera: requeriría replicar llamadas internas no
  documentadas de su frontend, que es frágil y no se investigó.
