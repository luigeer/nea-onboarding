# Monedero como Sección del Cliente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir `estaciones_monedero.py` y `estado_cuenta_monedero.py` —que hoy solo viven por CLI— en una sección del expediente del cliente en el front, con tres señales de negocio: adopción/consumo de monedero, estaciones distintas donde carga, y la comisión que le cobra el monedero actual.

**Architecture:** Dos funciones nuevas en `estaciones_monedero.py` (`comision_candidatas`, `revisar_cliente`, más las de persistencia) cubren la Etapa 1 (puro API, sin descargar nada). Una función nueva en `estado_cuenta_monedero.py` (`reporte_cliente`) filtra el reporte ya existente a un solo cliente para la Etapa 2. Una función de cruce (`actualizar_con_reporte`) junta ambas etapas. `front.py` importa los tres módulos y los llama directo desde un tab nuevo — nada de proceso aparte ni tabla nueva en Supabase.

**Tech Stack:** Python 3.10, Streamlit (ya en front.py), `syntage.py`, Supabase vía `db.py`.

**Spec:** [docs/superpowers/specs/2026-08-20-monedero-seccion-cliente-design.md](../specs/2026-08-20-monedero-seccion-cliente-design.md)

## Global Constraints

- Compuerta del proyecto: `python tests/todas.py` debe salir en verde (código 0) después de cada tarea.
- Estilo de pruebas: **no es pytest**. Cada archivo de prueba es un script (`python tests/test_X.py`), usa `check(cond, msg)` que imprime "ok"/"FALLA" y acumula en `fallas`, termina con `sys.exit(1)` si `fallas` no está vacía. Ver `tests/test_estaciones_monedero.py` como referencia exacta de estilo — se prueba con un `syntage`/`db`/`monederos` de mentiras asignado al atributo del módulo (`estaciones_monedero.syntage = FakeSyntage`), nunca mocks de red.
- Nada de datos reales de clientes (RFC, razón social, montos) se commitea al repo. Los fixtures usan datos inventados.
- Docstrings y comentarios en español, solo cuando explican un *por qué* no obvio.
- Umbral de monto simbólico ya existente: `UMBRAL_MONTO_SIMBOLICO = 50.0` en `estaciones_monedero.py` — se reutiliza, no se duplica.
- Ventana de confirmación ya existente: 2 de los últimos 3 meses, anclada a `_fecha_ancla` (última extracción de Syntage), no a "hoy" a secas.
- `_tab_monedero` (Streamlit) no lleva prueba automatizada, igual que el resto de `front.py` — se verifica a mano con `python nea.py front`.
- `front.py` no escribe a disco en ningún otro tab; este tab sí lo hace a propósito (ver spec, sección "Por qué el front escribe a disco aquí"). No generalizar ese patrón a otros tabs.

---

### Task 1: `estaciones_monedero.comision_candidatas()`

**Files:**
- Modify: `estaciones_monedero.py` (agregar función nueva después de `facturas_candidatas`, y corregir una línea de docstring en `monederos.py`)
- Modify: `monederos.py:16` (la línea que dice que no se ha confirmado si Syntage expone la comisión — ya se confirmó)
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: `syntage.facturas(entidad_id, rfc_emisor)` (ya existe).
- Produces: `comision_candidatas(entidad_id, rfc_monedero) -> list[dict]`. Cada dict: `{"mes": "AAAA-MM", "folio_fiscal": str, "monto": float, "fecha": str}`.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estaciones_monedero.py`, después del bloque de `facturas_candidatas()` (después de la línea 91, antes de `# ── confirmar_monedero_real()`):

```python
# ── comision_candidatas(): el concepto "Cargo Administrativo" con monto real ─
# Confirmado contra datos reales: la comisión es un concepto de factura
# aparte del CFDI de $1 que solo confirma el patrón. Cuando viene junto con
# un concepto DISPERSION en la misma factura, el subtotal de la factura
# completa (dispersión + comisión) no es simbólico, así que esa factura no
# aparece en facturas_candidatas() — son señales distintas, no la misma.
FACTURAS_CON_COMISION = [
    {"uuid": "j1", "issuedAt": "2026-06-15 12:00:00", "type": "I", "subtotal": 10300.0,
     "items": [{"description": "DISPERSION", "totalAmount": 10000.0},
               {"description": "Cargo Administrativo", "totalAmount": 300.0}]},
    {"uuid": "j2", "issuedAt": "2026-07-01 05:59:59", "type": "I", "subtotal": 1.0,
     "items": [{"description": "CARGO ADMINISTRATIVO", "totalAmount": 1.0}]},
    {"uuid": "j3", "issuedAt": "2026-07-15 12:00:00", "type": "I", "subtotal": 60000.0,
     "items": [{"description": "DISPERSION", "totalAmount": 60000.0}]},
    {"uuid": "j4-pago", "issuedAt": "2026-07-20 12:00:00", "type": "P", "subtotal": 900.0,
     "items": [{"description": "Cargo Administrativo", "totalAmount": 900.0}]},
]


class _SyntageComision(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_CON_COMISION


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageComision
candidatas_comision = estaciones_monedero.comision_candidatas("cualquier-id", "EFE8908015L3")
estaciones_monedero.syntage = _original_syntage

check(len(candidatas_comision) == 1,
      "solo el Cargo Administrativo de monto real y tipo Ingreso cuenta: %d" % len(candidatas_comision))
check(candidatas_comision[0]["folio_fiscal"] == "j1" and candidatas_comision[0]["monto"] == 300.0,
      "el monto es el del concepto, no el subtotal de la factura completa (10300): %r"
      % candidatas_comision[0])
check(candidatas_comision[0]["mes"] == "2026-06", "el mes sale de issuedAt: %r" % candidatas_comision[0]["mes"])
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `AttributeError: module 'estaciones_monedero' has no attribute 'comision_candidatas'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estaciones_monedero.py`, después de `facturas_candidatas` (después de la línea 64):

```python
def comision_candidatas(entidad_id, rfc_monedero):
    """Conceptos de 'Cargo Administrativo' con monto real: la comisión que
    cobra el monedero. Es una factura distinta (o un concepto dentro de una
    factura de dispersión) al CFDI de $1 que solo confirma el patrón de
    facturas_candidatas() — un monedero puede tener una sin la otra en el
    mismo mes, así que no se filtran juntas."""
    candidatas = []
    for f in syntage.facturas(entidad_id, rfc_monedero):
        if f.get("type") != "I":
            continue
        issued_at = f.get("issuedAt") or ""
        for item in f.get("items") or []:
            desc = (item.get("description") or "").strip().lower()
            monto = item.get("totalAmount")
            if desc == "cargo administrativo" and (monto or 0) >= UMBRAL_MONTO_SIMBOLICO:
                candidatas.append({
                    "mes": _mes_facturacion(issued_at) if issued_at else "",
                    "folio_fiscal": f.get("uuid"),
                    "monto": monto,
                    "fecha": f.get("issuedAt"),
                })
    return candidatas
```

- [ ] **Step 4: Corregir la línea de docstring desactualizada en `monederos.py`**

En `monederos.py`, la línea 16 dice hoy:

```
ha confirmado que Syntage exponga.
```

(dentro de: `"""...La comisión que cobra cada monedero es una pregunta aparte: requiere el detalle de conceptos del CFDI, que todavía no se ha confirmado que Syntage exponga."""`)

Reemplazar ese párrafo completo por:

```
La comisión que cobra cada monedero se resuelve con
`estaciones_monedero.comision_candidatas()`: viene en un concepto de
factura aparte ("Cargo Administrativo") que sí expone la API de Syntage.
```

- [ ] **Step 5: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estaciones_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 6: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 7: Commit**

```bash
git add estaciones_monedero.py monederos.py tests/test_estaciones_monedero.py
git commit -m "La comision del monedero se lee del concepto Cargo Administrativo, via API"
```

---

### Task 2: `estaciones_monedero.revisar_cliente()` y persistencia

**Files:**
- Modify: `estaciones_monedero.py` (imports nuevos, `revisar_cliente`, `guardar_revision`, `cargar_revision`, `_ruta_json`)
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: `db.cargar(folio)`, `monederos._rfc_de_expediente(exp)`, `monederos.analizar_cliente(rfc)`, `syntage.id_entidad(rfc)`, `facturas_candidatas`, `confirmar_monedero_real`, `comision_candidatas`, `_fecha_ancla` (todas ya existen tras la Task 1).
- Produces:
  - `revisar_cliente(folio, hoy=None) -> dict`. Forma:
    ```python
    {"generado_etapa1": "2026-08-20T22:30:00", "generado_etapa2": None,
     "estado": "ok",
     "monederos": [
       {"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard",
        "es_real": True,
        "plan_descarga": [{"mes": "2026-06", "folio_fiscal": "...",
                            "archivo_esperado": "RFC_CLIENTE_EFE8908015L3_2026-06.pdf"}],
        "comision": {"2026-06": {"monto": 300.0, "folios_fiscales": ["j1"]}},
        "reporte": None, "sospechosos": []}
     ]}
    ```
  - `guardar_revision(folio, resultado) -> None`, `cargar_revision(folio) -> dict | None`, `_ruta_json(folio) -> str`. Task 4 y Task 5 dependen de estas cuatro firmas.

- [ ] **Step 1: Agregar los imports que hacen falta**

En `estaciones_monedero.py`, reemplazar el bloque de imports (líneas 17-19):

```python
from datetime import date, datetime, timedelta

import syntage
```

por:

```python
import json
import os
from datetime import date, datetime, timedelta

import db
import monederos
import syntage

RAIZ = os.path.dirname(os.path.abspath(__file__))
```

Y en `main()` (más abajo en el archivo), quitar la línea `import monederos` (ya está importado arriba a nivel de módulo; dejarla duplicada no truena pero es ruido).

- [ ] **Step 2: Escribir la prueba**

Agregar a `tests/test_estaciones_monedero.py`, después del bloque de `_fecha_ancla()` (después de la línea 317, antes del `print()` final):

```python
# ── revisar_cliente(): Etapa 1 completa para UN cliente, y su persistencia ─
class _DbRevisarCliente(object):
    @staticmethod
    def cargar(folio, sb=None):
        return {"cliente": {"validado": {"rfc": "CLI010101AB1"}}}


class _MonederosRevisarCliente(object):
    @staticmethod
    def _rfc_de_expediente(exp):
        return ((exp.get("cliente") or {}).get("validado") or {}).get("rfc")

    @staticmethod
    def analizar_cliente(rfc, entidad_id=None):
        return ([{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard",
                   "razon_social_monedero": "Efectivale", "monto": 500.0,
                   "porcentaje_gasto": 0.04}], "ok")


FACTURAS_REVISAR_CLIENTE = [
    # Patrón simbólico mensual: confirma que es monedero real (junio y julio).
    {"uuid": "k1", "issuedAt": "2026-06-01 05:59:59", "type": "I", "subtotal": 1.0,
     "items": [{"description": "CARGO ADMINISTRATIVO", "totalAmount": 1.0}]},
    {"uuid": "k2", "issuedAt": "2026-07-01 05:59:59", "type": "I", "subtotal": 1.0,
     "items": [{"description": "CARGO ADMINISTRATIVO", "totalAmount": 1.0}]},
    # Comisión real, aparte del patrón simbólico: solo en junio.
    {"uuid": "k3", "issuedAt": "2026-06-15 12:00:00", "type": "I", "subtotal": 10300.0,
     "items": [{"description": "DISPERSION", "totalAmount": 10000.0},
               {"description": "Cargo Administrativo", "totalAmount": 300.0}]},
]


class _SyntageRevisarCliente(object):
    @staticmethod
    def id_entidad(rfc):
        return "eid-1"

    @staticmethod
    def estado_credenciales(entidad_id):
        return []

    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_REVISAR_CLIENTE


_original_db = estaciones_monedero.db
_original_monederos = estaciones_monedero.monederos
_original_syntage = estaciones_monedero.syntage
estaciones_monedero.db = _DbRevisarCliente
estaciones_monedero.monederos = _MonederosRevisarCliente
estaciones_monedero.syntage = _SyntageRevisarCliente

resultado = estaciones_monedero.revisar_cliente("FOL-PRUEBA-001", hoy=date(2026, 8, 19))

estaciones_monedero.db = _original_db
estaciones_monedero.monederos = _original_monederos
estaciones_monedero.syntage = _original_syntage

check(resultado["estado"] == "ok", "el estado de analizar_cliente se propaga: %r" % resultado["estado"])
check(len(resultado["monederos"]) == 1, "un monedero detectado: %d" % len(resultado["monederos"]))
m = resultado["monederos"][0]
check(m["rfc_monedero"] == "EFE8908015L3" and m["es_real"] is True,
      "Efecticard confirmado como monedero real: %r" % m)
check(len(m["plan_descarga"]) == 2,
      "un renglón de descarga por mes confirmado (junio y julio): %d" % len(m["plan_descarga"]))
check(m["plan_descarga"][0]["archivo_esperado"] == "CLI010101AB1_EFE8908015L3_2026-06.pdf",
      "el nombre de archivo esperado sigue la convención: %r" % m["plan_descarga"][0]["archivo_esperado"])
check(m["comision"] == {"2026-06": {"monto": 300.0, "folios_fiscales": ["k3"]}},
      "la comisión de junio se detecta aparte del patrón simbólico: %r" % m["comision"])
check(m["reporte"] is None, "Etapa 2 todavía no corrió")

ruta = estaciones_monedero._ruta_json("FOL-PRUEBA-001")
check(os.path.exists(ruta), "revisar_cliente persiste el resultado en out/")
cargado = estaciones_monedero.cargar_revision("FOL-PRUEBA-001")
check(cargado == resultado, "cargar_revision regresa exactamente lo que se guardó")
os.remove(ruta)

check(estaciones_monedero.cargar_revision("FOLIO-QUE-NO-EXISTE-PRUEBA") is None,
      "sin archivo todavía, cargar_revision regresa None en vez de tronar")


# ── revisar_cliente(): sin RFC validado, no truena ──────────────────────────
class _DbSinRfc(object):
    @staticmethod
    def cargar(folio, sb=None):
        return {"cliente": {}}


_original_db = estaciones_monedero.db
estaciones_monedero.db = _DbSinRfc
resultado_sin_rfc = estaciones_monedero.revisar_cliente("FOL-SIN-RFC")
estaciones_monedero.db = _original_db

check(resultado_sin_rfc["monederos"] == [],
      "sin RFC validado todavía no hay nada que revisar, y no truena")
check("RFC" in resultado_sin_rfc["estado"],
      "el estado explica por qué: %r" % resultado_sin_rfc["estado"])
os.remove(estaciones_monedero._ruta_json("FOL-SIN-RFC"))
```

- [ ] **Step 3: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `AttributeError: module 'estaciones_monedero' has no attribute 'revisar_cliente'` (o `'db'`/`'monederos'` si el Step 1 no se hizo — confirmar que Step 1 sí se aplicó antes de seguir)

- [ ] **Step 4: Escribir la implementación**

Agregar a `estaciones_monedero.py`, al final del archivo (antes de `def main(argv):`):

```python
def _ruta_json(folio):
    return os.path.join(RAIZ, "out", "%s_monedero.json" % folio)


def guardar_revision(folio, resultado):
    """Persiste el resultado en out/{folio}_monedero.json. La descarga
    manual entre Etapa 1 y Etapa 2 puede tardar días: sin esto, el plan y
    la comisión de Etapa 1 se perderían en cuanto se cierre el navegador."""
    ruta = _ruta_json(folio)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)


def cargar_revision(folio):
    """None si todavía no se ha corrido 'Revisar monedero' para este folio."""
    ruta = _ruta_json(folio)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def revisar_cliente(folio, hoy=None):
    """Etapa 1 para un solo cliente, durante su onboarding: qué monedero(s)
    reales tiene confirmados, qué descargar a mano de cada uno, y la
    comisión ya calculable sin descargar nada. Persiste el resultado."""
    hoy = hoy or date.today()
    exp = db.cargar(folio)
    rfc = monederos._rfc_de_expediente(exp)
    if not rfc:
        resultado = {"generado_etapa1": datetime.now().isoformat(),
                     "generado_etapa2": None,
                     "estado": "el cliente todavía no tiene RFC validado",
                     "monederos": []}
        guardar_revision(folio, resultado)
        return resultado

    try:
        eid = syntage.id_entidad(rfc)
    except LookupError:
        eid, estado = None, "no está dado de alta en Syntage"
    except syntage.ErrorSyntage as e:
        eid, estado = None, "sin acceso a la entidad (%s)" % e
    else:
        hallazgos, estado = monederos.analizar_cliente(rfc, entidad_id=eid)

    monederos_resultado = []
    if eid:
        ancla = _fecha_ancla(eid, hoy)
        for h in hallazgos:
            candidatas = facturas_candidatas(eid, h["rfc_monedero"])
            es_real, por_mes = confirmar_monedero_real(candidatas, ancla)
            plan = []
            comision = {}
            if es_real:
                for mes, facturas in sorted(por_mes.items()):
                    for factura in facturas:
                        plan.append({
                            "mes": mes,
                            "folio_fiscal": factura["folio_fiscal"],
                            "archivo_esperado": "%s_%s_%s.pdf" % (rfc, h["rfc_monedero"], mes),
                        })
                for c in comision_candidatas(eid, h["rfc_monedero"]):
                    entrada = comision.setdefault(c["mes"], {"monto": 0.0, "folios_fiscales": []})
                    entrada["monto"] += c["monto"]
                    entrada["folios_fiscales"].append(c["folio_fiscal"])
            monederos_resultado.append({
                "rfc_monedero": h["rfc_monedero"],
                "nombre_comercial": h["nombre_comercial"],
                "es_real": es_real,
                "plan_descarga": plan,
                "comision": comision,
                "reporte": None,
                "sospechosos": [],
            })

    resultado = {"generado_etapa1": datetime.now().isoformat(),
                 "generado_etapa2": None,
                 "estado": estado,
                 "monederos": monederos_resultado}
    guardar_revision(folio, resultado)
    return resultado
```

- [ ] **Step 5: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estaciones_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 6: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 7: Commit**

```bash
git add estaciones_monedero.py tests/test_estaciones_monedero.py
git commit -m "Etapa 1 por cliente: revisar_cliente() persiste plan y comision en out/"
```

---

### Task 3: `estado_cuenta_monedero.reporte_cliente()`

**Files:**
- Modify: `estado_cuenta_monedero.py`
- Test: `tests/test_estado_cuenta_monedero.py`

**Interfaces:**
- Consumes: `reporte_carpeta(carpeta)` (ya existe).
- Produces: `reporte_cliente(rfc_cliente, carpeta="descargas/monederos") -> dict`. Misma forma que un valor de `reporte_carpeta()`: `{"meses": {(mes, rfc_monedero): {...}}, "sospechosos": [...]}`.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estado_cuenta_monedero.py`, después del bloque de `reporte_carpeta()` con XML (después de la línea 319, antes del `print()` final):

```python
# ── reporte_cliente(): reporte_carpeta() filtrado a un solo cliente ────────
XML_OTRO_CLIENTE = XML_DE_PRUEBA.replace(
    'Rfc="CLI020202CD2" Nombre="CLIENTEDEPRUEBA"',
    'Rfc="OTR999999XX9" Nombre="OTROCLIENTE"')

_CARPETA_MULTI_CLIENTE = tempfile.mkdtemp(prefix="_prueba_reporte_cliente_")
with open(os.path.join(_CARPETA_MULTI_CLIENTE, "CLI020202CD2_FIC010101AB1_2026-03.xml"),
          "w", encoding="utf-8") as fh:
    fh.write(XML_DE_PRUEBA)
with open(os.path.join(_CARPETA_MULTI_CLIENTE, "OTR999999XX9_FIC010101AB1_2026-03.xml"),
          "w", encoding="utf-8") as fh:
    fh.write(XML_OTRO_CLIENTE)

try:
    reporte_un_cliente = ecm.reporte_cliente("CLI020202CD2", _CARPETA_MULTI_CLIENTE)
finally:
    shutil.rmtree(_CARPETA_MULTI_CLIENTE, ignore_errors=True)

check(("2026-03", "FIC010101AB1") in reporte_un_cliente["meses"],
      "trae el mes de ESTE cliente: %r" % list(reporte_un_cliente["meses"]))
check(len(reporte_un_cliente["meses"]) == 1,
      "no trae el mes del OTRO cliente que vive en la misma carpeta: %d"
      % len(reporte_un_cliente["meses"]))

reporte_sin_archivos = ecm.reporte_cliente("NADIE0000XXX", tempfile.mkdtemp(prefix="_prueba_vacia_"))
check(reporte_sin_archivos == {"meses": {}, "sospechosos": []},
      "un cliente sin ningún archivo descargado regresa forma vacía, no truena: %r"
      % reporte_sin_archivos)
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `AttributeError: module 'estado_cuenta_monedero' has no attribute 'reporte_cliente'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estado_cuenta_monedero.py`, después de `reporte_carpeta` (después de la línea 275):

```python
def reporte_cliente(rfc_cliente, carpeta="descargas/monederos"):
    """reporte_carpeta() filtrado a un solo cliente. No decide nada de
    comisión: eso ya lo tiene Etapa 1 (estaciones_monedero.revisar_cliente)."""
    reporte = reporte_carpeta(carpeta)
    return reporte.get(rfc_cliente, {"meses": {}, "sospechosos": []})
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 6: Commit**

```bash
git add estado_cuenta_monedero.py tests/test_estado_cuenta_monedero.py
git commit -m "reporte_cliente(): el reporte de un solo cliente, sin leer los demas de la carpeta"
```

---

### Task 4: `estaciones_monedero.actualizar_con_reporte()`

**Files:**
- Modify: `estaciones_monedero.py`
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: la forma de `revisar_cliente()` (Task 2) y la forma de `estado_cuenta_monedero.reporte_cliente()` (Task 3) — este módulo no importa `estado_cuenta_monedero` (evita import circular innecesario; quien orquesta las dos llamadas es `front.py` en la Task 5), solo recibe ambos dicts ya calculados.
- Produces: `actualizar_con_reporte(revision, reporte) -> dict`. Muta y regresa `revision`, con cada `monedero["reporte"]` lleno y `revision["generado_etapa2"]` actualizado.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estaciones_monedero.py`, después del bloque de `revisar_cliente()` (antes del `print()` final):

```python
# ── actualizar_con_reporte(): cruza Etapa 1 (comisión) con Etapa 2 (total) ─
REVISION_DE_PRUEBA = {
    "generado_etapa1": "2026-08-20T22:00:00", "generado_etapa2": None,
    "estado": "ok",
    "monederos": [
        {"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard",
         "es_real": True,
         "plan_descarga": [{"mes": "2026-06", "folio_fiscal": "k1",
                             "archivo_esperado": "CLI010101AB1_EFE8908015L3_2026-06.pdf"}],
         "comision": {"2026-06": {"monto": 300.0, "folios_fiscales": ["k3"]}},
         "reporte": None, "sospechosos": []},
    ],
}

REPORTE_DE_PRUEBA = {
    "meses": {
        ("2026-06", "EFE8908015L3"): {
            "rfc_monedero": "EFE8908015L3",
            "por_estacion": {("FIC120327XYZ", "9999999"): {"cargas": 2, "litros": 41.25, "importe": 865.40}},
            "subtotal": 10000.0,
        },
    },
    "sospechosos": ["ruta/a/un/archivo_sospechoso.pdf"],
}

actualizada = estaciones_monedero.actualizar_con_reporte(REVISION_DE_PRUEBA, REPORTE_DE_PRUEBA)

check(actualizada["generado_etapa2"] is not None, "se marca cuándo corrió la Etapa 2")
m = actualizada["monederos"][0]
check(m["reporte"]["2026-06"]["total_facturado"] == 10000.0,
      "el total facturado sale del subtotal del reporte de Etapa 2: %r" % m["reporte"])
check(abs(m["reporte"]["2026-06"]["porcentaje_comision"] - 0.03) < 0.0001,
      "el %% de comisión es la comisión de Etapa 1 sobre el total de Etapa 2 (300/10000=3%%): %r"
      % m["reporte"]["2026-06"]["porcentaje_comision"])
check(m["reporte"]["2026-06"]["por_estacion"] ==
      [{"rfc_estacion": "FIC120327XYZ", "clave_estacion": "9999999",
        "cargas": 2, "litros": 41.25, "importe": 865.40}],
      "por_estacion se aplana a una lista (las claves tupla no son JSON-serializables): %r"
      % m["reporte"]["2026-06"]["por_estacion"])
check(m["sospechosos"] == ["ruta/a/un/archivo_sospechoso.pdf"],
      "los sospechosos de Etapa 2 se copian al monedero")

# Un mes con comisión de Etapa 1 pero SIN total de Etapa 2 (no se subió ese
# complemento todavía): no se calcula el %, nunca se divide contra nada.
REVISION_MES_SIN_ETAPA2 = {
    "generado_etapa1": "2026-08-20T22:00:00", "generado_etapa2": None, "estado": "ok",
    "monederos": [
        {"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard", "es_real": True,
         "plan_descarga": [], "comision": {"2026-07": {"monto": 450.0, "folios_fiscales": ["k4"]}},
         "reporte": None, "sospechosos": []},
    ],
}
REPORTE_VACIO = {"meses": {}, "sospechosos": []}
actualizada_vacia = estaciones_monedero.actualizar_con_reporte(REVISION_MES_SIN_ETAPA2, REPORTE_VACIO)
check(actualizada_vacia["monederos"][0]["reporte"] == {},
      "sin ningún mes leído en Etapa 2, el reporte queda vacío, no inventa un mes con % en None")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `AttributeError: module 'estaciones_monedero' has no attribute 'actualizar_con_reporte'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estaciones_monedero.py`, al final del archivo (antes de `def main(argv):`):

```python
def actualizar_con_reporte(revision, reporte):
    """Cruza el reporte de Etapa 2 (por (mes, rfc_monedero)) con la revisión
    de Etapa 1: llena 'reporte' con total facturado, estaciones y el % de
    comisión cuando ya se sabe la comisión de ese mes. Las claves compuestas
    (tuplas) de reporte_cliente() se aplanan a algo serializable en JSON."""
    for m in revision["monederos"]:
        m["reporte"] = {}
        for (mes, rfc_monedero), datos in reporte.get("meses", {}).items():
            if rfc_monedero != m["rfc_monedero"]:
                continue
            comision_mes = m.get("comision", {}).get(mes)
            porcentaje = None
            if comision_mes and datos.get("subtotal"):
                porcentaje = comision_mes["monto"] / datos["subtotal"]
            m["reporte"][mes] = {
                "total_facturado": datos.get("subtotal"),
                "porcentaje_comision": porcentaje,
                "por_estacion": [
                    {"rfc_estacion": rfc_est, "clave_estacion": clave_est,
                     "cargas": a["cargas"], "litros": a["litros"], "importe": a["importe"]}
                    for (rfc_est, clave_est), a in (datos.get("por_estacion") or {}).items()
                ],
            }
        m["sospechosos"] = reporte.get("sospechosos", [])
    revision["generado_etapa2"] = datetime.now().isoformat()
    return revision
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estaciones_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 6: Commit**

```bash
git add estaciones_monedero.py tests/test_estaciones_monedero.py
git commit -m "Cruzar Etapa 1 y Etapa 2: el porcentaje de comision solo si ambas existen para ese mes"
```

---

### Task 5: El tab `_tab_monedero` en `front.py`

**Files:**
- Modify: `front.py`

**Interfaces:**
- Consumes: `estaciones_monedero.cargar_revision(folio)`, `estaciones_monedero.revisar_cliente(folio)`, `estaciones_monedero.actualizar_con_reporte(revision, reporte)`, `estaciones_monedero.guardar_revision(folio, revision)` (Task 2 y 4), `estado_cuenta_monedero.reporte_cliente(rfc_cliente)` (Task 3), `monederos._rfc_de_expediente(exp)` (ya existe).
- Produces: nada que otra tarea consuma — es la última pieza del plan.

Esta tarea no lleva prueba automatizada (Streamlit): se verifica a mano.

- [ ] **Step 1: Agregar la pestaña a `vista_cliente`**

En `front.py`, modificar la lista de `tabs` (línea 197-199):

```python
    tabs = st.tabs(["Score", "Perfil", "Observaciones", "Banco y fiscal",
                    "Documentos", "Historial", "Resumen ejecutivo",
                    "Alta en la base operativa"])
```

por:

```python
    tabs = st.tabs(["Score", "Perfil", "Observaciones", "Banco y fiscal",
                    "Documentos", "Historial", "Resumen ejecutivo",
                    "Alta en la base operativa", "Monedero"])
```

Y agregar, después del bloque `with tabs[7]:` (línea 215-216):

```python
    with tabs[8]:
        _tab_monedero(folio, exp)
```

- [ ] **Step 2: Escribir `_tab_monedero` — estado inicial y botón de Etapa 1**

Agregar a `front.py`, después de `_tab_alta` (después de la línea 536, antes de la línea de separador `# ─────` que abre `def main():`):

```python
# ─────────────────────────────────────────────────────────────────────────────
# Monedero — adopción, estaciones y comisión del monedero de combustible
# actual del cliente. A diferencia del resto de este front, SÍ escribe a
# disco (out/{folio}_monedero.json): la descarga manual entre las dos
# etapas puede tardar días, y st.session_state no sobrevive a que el
# operador cierre el navegador. Ver spec en
# docs/superpowers/specs/2026-08-20-monedero-seccion-cliente-design.md.
# ─────────────────────────────────────────────────────────────────────────────
def _tab_monedero(folio, exp):
    import estaciones_monedero as em
    import monederos

    st.caption("Informativo — no bloquea el avance del expediente. Solo tiene "
               "sentido correrlo mientras el cliente está en onboarding activo.")

    revision = em.cargar_revision(folio)

    if st.button("Revisar monedero" if revision is None else "Volver a revisar monedero"):
        with st.spinner("Consultando Syntage..."):
            try:
                em.revisar_cliente(folio)
            except Exception as e:
                st.error("No se pudo: %s" % e)
                return
        st.rerun()

    if revision is None:
        st.write("Todavía no se ha revisado. El botón de arriba consulta "
                 "Syntage (sin descargar nada) y dice si el cliente usa un "
                 "monedero real, y cuánto le cobra de comisión.")
        return

    if not revision["monederos"]:
        st.info("No se detectó monedero real en los últimos meses. (%s)"
                 % revision["estado"])
        return

    rfc_cliente = monederos._rfc_de_expediente(exp)
    for m in revision["monederos"]:
        st.markdown("#### %s (%s)" % (m["nombre_comercial"], m["rfc_monedero"]))
        if not m["es_real"]:
            st.write("No confirmó el patrón de monedero real — parece compra "
                     "directa en una gasolinera que también tiene monedero de marca.")
            continue

        if m["comision"]:
            for mes, c in sorted(m["comision"].items()):
                st.write("**Comisión %s:** $%s" % (mes, format(c["monto"], ",.2f")))

        st.write("**Qué descargar del panel de Syntage:**")
        import pandas as pd
        st.dataframe(pd.DataFrame([{
            "Mes": p["mes"], "Archivo esperado": p["archivo_esperado"],
            "Folio fiscal": p["folio_fiscal"],
        } for p in m["plan_descarga"]]), use_container_width=True, hide_index=True)

        _tab_monedero_reporte(folio, rfc_cliente, m, revision)
```

- [ ] **Step 3: Verificar a mano que el estado inicial se ve bien**

Run: `python nea.py front`

Abrir un cliente cualquiera y entrar a la pestaña "Monedero". Expected: se ve el texto explicativo y el botón "Revisar monedero", sin errores en la terminal ni en la página.

- [ ] **Step 4: Escribir el botón de Etapa 2 y el reporte**

Agregar a `front.py`, inmediatamente después de `_tab_monedero` (mismo bloque):

```python
def _tab_monedero_reporte(folio, rfc_cliente, m, revision):
    import estaciones_monedero as em
    import estado_cuenta_monedero as ecm

    if st.button("Leer descargas", key="leer_%s_%s" % (folio, m["rfc_monedero"])):
        with st.spinner("Leyendo los PDF/XML descargados..."):
            try:
                reporte = ecm.reporte_cliente(rfc_cliente)
                revision = em.actualizar_con_reporte(revision, reporte)
                em.guardar_revision(folio, revision)
            except Exception as e:
                st.error("No se pudo: %s" % e)
                return
        st.rerun()

    if not m["reporte"]:
        st.caption("Todavía no se han leído descargas para este monedero.")
        return

    import pandas as pd
    filas_mes, filas_estacion = [], []
    for mes, d in sorted(m["reporte"].items()):
        pct = d["porcentaje_comision"]
        filas_mes.append({
            "Mes": mes, "Total facturado": d["total_facturado"],
            "% comisión": ("%.2f%%" % (pct * 100)) if pct is not None
                          else "falta subir el complemento de este mes",
        })
        for e in d["por_estacion"]:
            filas_estacion.append({"Mes": mes, "RFC estación": e["rfc_estacion"],
                                    "Clave": e["clave_estacion"], "Cargas": e["cargas"],
                                    "Litros": e["litros"], "Importe": e["importe"]})

    st.write("**Por mes:**")
    st.dataframe(pd.DataFrame(filas_mes), use_container_width=True, hide_index=True)

    if filas_estacion:
        estaciones_distintas = {(f["RFC estación"], f["Clave"]) for f in filas_estacion}
        st.write("**Por estación** (%d distinta(s) en los meses leídos):" % len(estaciones_distintas))
        st.dataframe(pd.DataFrame(filas_estacion), use_container_width=True, hide_index=True)

    if m["sospechosos"]:
        with st.expander("⚠ %d archivo(s) sospechoso(s) — no cuadraron o no se pudieron usar"
                         % len(m["sospechosos"])):
            for s in m["sospechosos"]:
                st.write(s)
```

- [ ] **Step 5: Verificar a mano el flujo completo**

Run: `python nea.py front`

Con un cliente que tenga `out/{folio}_monedero.json` de una corrida anterior de Etapa 1 (o corriendo "Revisar monedero" contra uno real), y con al menos un PDF/XML de prueba colocado en `descargas/monederos/` siguiendo la convención de nombre:

1. La comisión en pesos se ve antes de leer ninguna descarga.
2. Al dar clic en "Leer descargas", aparece la tabla por mes y por estación.
3. Si el mes de la comisión no tiene complemento subido, ese mes dice "falta subir el complemento de este mes" en vez de mostrar un porcentaje.
4. Cerrar y volver a abrir el tablero (`Ctrl+C` y `python nea.py front` de nuevo): el reporte sigue ahí sin tener que volver a correr nada — confirma que `out/{folio}_monedero.json` persistió.

- [ ] **Step 6: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.` (esta tarea no agrega pruebas nuevas, pero confirma que nada se rompió).

- [ ] **Step 7: Commit**

```bash
git add front.py
git commit -m "Monedero como pestana del cliente: adopcion, estaciones y comision"
```

---

## Al terminar

En este punto, desde el tablero (`python nea.py front`), en la pestaña "Monedero" de cualquier cliente en onboarding activo:

- Un botón revisa Syntage y dice si el cliente usa monedero real, qué facturas bajar a mano de cada uno, y cuánto le cobran de comisión — sin descargar nada.
- Una vez descargados esos PDF/XML a `descargas/monederos/` con la convención de nombre ya existente, otro botón lee esas descargas y muestra, por mes y por estación, cuánto facturó y qué % de comisión representa eso.
- Todo el resultado persiste en `out/{folio}_monedero.json`, así que no se pierde entre visitas al tablero.
- Sigue pendiente (fuera de este plan, a propósito): un barrido periódico sobre toda la cartera, o una tabla en Supabase — ninguno de los dos tiene un consumidor real todavía.
