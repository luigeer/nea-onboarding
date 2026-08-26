# Conectar estados de cuenta y datos fiscales a nea.py — diseño

## Por qué

La compuerta de riesgo (`puede_pasar_a_riesgo` en [validador.py](../../../validador.py))
exige buró, información fiscal y estados de cuenta procesados. El caso que lo
expuso: el expediente MEZA-01 (Hernán Meza, PFAE) ya tiene en su carpeta
canónica de Drive los 3 estados de cuenta BBVA y puede correr Syntage para
fiscal, pero `python nea.py riesgo MEZA-01` falla con "Falta el reporte de
buró de crédito / Falta la información fiscal / No hay estados de cuenta
procesados" — porque nada en `nea.py` mueve esos documentos de Drive a las
tablas de Supabase que lee `insumos_riesgo.py`.

Al revisar el código resultó que [bbva.py](../../../bbva.py) y
[syntage.py](../../../syntage.py) no están "desconectados": están en estados
muy distintos.

- **`bbva.py`** — parser completo y probado (`encabezado()`, `movimientos()`,
  `cuadra()`), pero **no existe ningún escritor a Supabase** para ningún
  banco. La tabla `estados_cuenta` que lee `insumos_riesgo.cuentas()` no la
  llena nadie hoy.
- **`syntage.py`** / **`info_fiscal.py`** — cliente de API real, con
  `guardar_crudo()` (persiste en `syntage_datos`) y `a_supabase()` (proyecta a
  `info_fiscal`), pero nada llama a ese camino completo con datos reales.
- **Buró de crédito** — el hueco más grande: `syntage.py` tiene un comando
  CLI `buro` que llama a `buro_resumen(eid)`, una función que **no existe**
  en el archivo. No hay ningún escritor para la tabla `buro`. **Queda fuera
  de este diseño**, como tarea aparte (hay que encontrar primero el endpoint
  correcto de Syntage para crédito).

Este diseño cubre solo las dos piezas que sí están completas: estados de
cuenta y fiscal.

## Bancos: uno hoy, extensible después

`ceps.py` (Banco del Bajío) no es un parser equivalente a `bbva.py`: lee el
detalle de los SPEI grandes para comprobarlos contra el CEP de Banxico, no
produce un `encabezado()` con totales ni un `cuadra()`. No sirve para llenar
`estados_cuenta` de la misma forma. Construir eso para Banco del Bajío es un
parser nuevo, no una conexión — queda fuera de este diseño.

Se crea `bancos.py` como registro de parsers, con un contrato común (el que
ya tiene `bbva.py`):

```python
def leer(ruta) -> (encabezado: dict, movimientos: list)
def cuadra(encabezado, movimientos) -> (bool, diagnostico: dict)
```

```python
PARSERS = {"bbva": bbva}

def identificar(ruta):
    """Prueba cada parser registrado. Devuelve (banco, encabezado, movimientos,
    diagnostico) del primero que cuadre, o (None, None, None, None) si
    ninguno lo hace — nunca se descarta un PDF en silencio."""
```

Agregar un banco nuevo más adelante es escribir su `leer()`/`cuadra()` y
añadir una entrada al diccionario `PARSERS` — no toca `nea.py` ni el resto de
`bancos.py`.

## Comando `nea.py estados FOLIO`

1. Baja `1 Documentos del cliente` del expediente vía `drive_cliente.py`
   (`documentos_cliente()` + `descargar()`), a un directorio temporal.
2. Para cada PDF corre `bancos.identificar(ruta)`.
3. Los que cuadran: upsert a la tabla `estados_cuenta` de Supabase (ya
   existe, ver [supabase/migracion_02_riesgo.sql](../../../supabase/migracion_02_riesgo.sql)),
   usando el índice único que ya tiene la tabla,
   `estados_cuenta_periodo_unico` sobre `(folio, banco, cuenta, fecha_final)`
   — correr el comando dos veces no duplica filas.
4. Los que no cuadran con ningún parser conocido: se listan aparte como "no
   reconocido, revisar a mano".
5. Actualiza `exp["cuentas_bancarias"]` (lo que ya lee `validador.py` para la
   compuerta de completitud) agrupando por `(banco, cuenta)`, con sus
   periodos (`fecha_final`, `YYYY-MM`) y `titular_es_cliente`: verdadero si el
   `rfc` del `encabezado()` coincide con `exp["cliente"]["validado"]["rfc"]`
   (para PFAE) o con el RFC del representante validado — una cuenta a nombre
   de otra entidad se guarda igual en `estados_cuenta` (es evidencia), pero
   entra como `titular_es_cliente: False`, tal como ya distingue
   `validador._coherencia`. Llama a `guardar(exp)` como el resto de `nea.py`.
6. Imprime un resumen: PDFs procesados, cuántos cuadraron, cuántos no se
   reconocieron.

### La tabla `estados_cuenta` ya existe — se llena, no se crea

Tiene columnas que `bbva.py` no puede producir (`saldo_minimo`,
`saldo_maximo`, `tipo_cambio`, y las cuatro `*_operativo`, que vienen de algo
llamado "Bank Statement Analyzer" según el comentario de la migración — una
herramienta externa que no está en este repo). Esas quedan en `null`; el
propio esquema ya las trata como opcionales: `cobertura_riesgo` cuenta
`estados_cuenta` (cualquier fila) aparte de `estados_reconciliados` (solo las
que sí traen `numero_depositos_operativo`), y `validador._insumos_modelo`
([validador.py:557-567](../../../validador.py:557)) solo bloquea la
compuerta de riesgo si `estados_cuenta` es 0 — sin reconciliar baja a un
aviso informativo (`BAJA`), no bloquea. Basta con lo que da `encabezado()`.

| Columna | De dónde sale |
|---|---|
| `folio` | argumento del comando |
| `banco`, `cuenta`, `moneda` | `encabezado()` |
| `fecha_inicial`, `fecha_final` | `encabezado()` |
| `saldo_inicial`, `saldo_final`, `saldo_promedio` | `encabezado()` |
| `numero_depositos`, `monto_depositos` | `encabezado()` |
| `numero_retiros`, `monto_retiros` | `encabezado()` |
| `drive_file_id` | trazabilidad: de qué PDF de Drive salió |
| `saldo_minimo`, `saldo_maximo`, `tipo_cambio`, `*_operativo`, `verificado_cep` | `null` — no los produce `bbva.py` |

Upsert con `on_conflict` sobre el índice único que ya existe,
`estados_cuenta_periodo_unico` — `(folio, banco, cuenta, fecha_final)`.

## Comando `nea.py fiscal FOLIO`

1. Busca la entidad de Syntage por el RFC del cliente
   (`syntage.buscar_entidad`) — **nunca la crea**. Darse de alta en Syntage
   requiere que el cliente meta sus propias credenciales del SAT; no es una
   acción que la plataforma pueda tomar por él.
2. Si no existe: aviso en rojo — *"RFC no dado de alta en Syntage. El
   cliente debe registrarse (con sus propias credenciales del SAT). Pedir a
   ventas que lo levante."* — y el comando termina ahí.
3. Si existe: revisa `syntage.extraccion_completa(rfc)`. Si hay extracciones
   corriendo o pendientes, las lista y termina — mismo patrón que ya usa
   `cmd_riesgo` con su propia compuerta: nunca se usan datos a medias.
4. Si está completa: `syntage.extraer_todo(entidad_id)` trae los insights;
   `syntage.guardar_crudo(folio, entidad_id, payloads)` los persiste tal cual
   en `syntage_datos` (ya existe, solo se conecta). Después
   `info_fiscal.desde_insights(...)` proyecta esos payloads a filas de
   `info_fiscal` y `info_fiscal.a_supabase(folio, filas)` las guarda (ambas
   ya existen, solo se conectan).
5. Mismo resumen impreso: qué se extrajo, qué falló — los fallos de
   `extraer_todo` no detienen nada, como ya está diseñado ahí.

## Pruebas

TDD sobre las piezas nuevas y puras, sin red real:

- `bancos.identificar()`: con un PDF que cuadra devuelve el banco correcto;
  con uno que no cuadra con nada, devuelve "no reconocido" sin reventar.
- La función que arma la fila de `estados_cuenta` desde un `encabezado()`:
  dado un encabezado de ejemplo, produce el dict con las columnas correctas.
- La función que decide, en `fiscal`, si la extracción está completa o hay
  que avisar y parar: dado un resultado simulado de
  `syntage.extraccion_completa()`, decide correctamente.

Lo que toca Drive/Supabase/Syntage de verdad no se prueba con red real — se
verifica a mano contra MEZA-01, como ya se hizo con el fix de PFAE
([validador.py](../../../validador.py), etapa 2).

## Fuera de alcance

- Buró de crédito (`buro_resumen` no existe; falta el endpoint de Syntage).
- Banco del Bajío u otro banco además de BBVA (parser nuevo, no conexión).
- Crear entidades en Syntage automáticamente.
