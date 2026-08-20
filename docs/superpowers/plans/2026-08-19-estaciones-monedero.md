# Estaciones por Cliente de Monedero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distinguir facturación real de monedero de compra directa en gasolinera, y a partir de ahí extraer detalle por estación (litros, importe, cuántas estaciones distintas) de los complementos de estado de cuenta que emiten los monederos.

**Architecture:** Dos módulos nuevos. `estaciones_monedero.py` habla solo con la API de Syntage — sin descargar nada — para confirmar cuáles (cliente, monedero) son relación real (patrón de monto simbólico recurrente mensual) y arma la lista exacta de qué facturas bajar a mano. `estado_cuenta_monedero.py` parsea con pdfplumber los PDF ya descargados (complemento SAT estandarizado, igual para cualquier monedero) y agrega por estación.

**Tech Stack:** Python 3.10, `pdfplumber` (ya en requirements.txt), API de Syntage vía `syntage.py`.

**Spec:** [docs/superpowers/specs/2026-08-19-estaciones-monedero-design.md](../specs/2026-08-19-estaciones-monedero-design.md)

## Global Constraints

- Compuerta del proyecto: `python tests/todas.py` debe salir en verde (código 0) después de cada tarea.
- Estilo de pruebas de este repo: **no es pytest**. Cada archivo de prueba es un script que se corre con `python tests/test_X.py`, usa un helper `check(cond, msg)` que imprime "ok"/"FALLA" y acumula en una lista `fallas`, y termina con `sys.exit(1)` si `fallas` no está vacía. Ver `tests/test_monederos.py` como referencia exacta de estilo — los pasos de este plan siguen ese mismo patrón, no `assert` ni `pytest.raises`.
- Nada de datos reales de clientes (RFC, razón social, montos) se commitea al repo. Las pruebas usan datos inventados.
- Docstrings y comentarios en español, solo cuando explican un *por qué* no obvio — no describir *qué* hace el código.
- Umbral de monto simbólico: **$50 pesos** de subtotal.
- Ventana de confirmación: candidata en al menos **2 de los últimos 3 meses**.
- Convención de archivo descargado: `descargas/monederos/{RFC_CLIENTE}_{RFC_MONEDERO}_{AAAA-MM}.pdf`.

---

### Task 1: `syntage.facturas()` — facturas de un emisor a una entidad

**Files:**
- Modify: `syntage.py` (agregar función nueva, después de `crear_entidad`/`entidades`, alrededor de la línea 190)

**Interfaces:**
- Produces: `syntage.facturas(entidad_id: str, rfc_emisor: str, tam_pagina: int = 100) -> list[dict]`. Cada dict es el objeto de factura tal como lo devuelve Syntage (`subtotal`, `discount`, `issuedAt`, `uuid`, ...).

Este módulo es el cliente de la API — como el resto de `syntage.py`, no tiene archivo de prueba dedicado (así está en todo el repo: `db.py`, `syntage.py` no se prueban con mocks de red, solo la lógica de negocio que los envuelve). En vez de un test automatizado, este task incluye una verificación manual contra la API real.

- [ ] **Step 1: Agregar la función**

Insertar después de `crear_entidad` (alrededor de la línea 173 de `syntage.py`):

```python
def facturas(entidad_id, rfc_emisor, tam_pagina=100):
    """Facturas que un RFC (típicamente un monedero) le emitió a esta
    entidad. Se probó a mano contra la API real: `page` truena con 400
    ("Only cursor pagination is available for this endpoint"), y el header
    de paginación por cursor documentado por Syntage no expone un link de
    "siguiente" utilizable en la práctica para este endpoint. Para el caso
    real —facturas de servicio de un emisor a un cliente— un tam_pagina
    generoso ya trae todo: se probó pidiendo hasta 500 contra un caso con
    55 facturas históricas y el resultado no cambió. Si algún día un
    (cliente, emisor) tuviera más de tam_pagina facturas, se señala en vez
    de recortar en silencio."""
    lote = _lista(pedir("/entities/%s/invoices" % entidad_id,
                        {"issuer.rfc": rfc_emisor.upper(), "itemsPerPage": tam_pagina}))
    if len(lote) == tam_pagina:
        raise ErrorSyntage(
            0, "%s tiene %d o más facturas de %s: puede haber más que no se "
               "están viendo (este endpoint no soporta paginar más allá del "
               "primer lote)." % (entidad_id, tam_pagina, rfc_emisor),
            "/entities/%s/invoices" % entidad_id)
    return lote
```

- [ ] **Step 2: Verificar a mano contra la API real**

Run:
```bash
python -c "
import sys; sys.path.insert(0, '.')
import syntage
eid = syntage.id_entidad('LOG150312XX3')
r = syntage.facturas(eid, 'EFE8908015L3')
print('facturas:', len(r))
print('primera:', r[0]['uuid'], r[0]['subtotal'], r[0]['issuedAt'])
"
```
Expected: imprime un número de facturas mayor a 0 y los datos de la primera, sin traceback. (LOG150312XX3 es LOGISTICA FICTICIA DE MEXICO, ya sabemos que tiene facturas de EFE8908015L3/Efecticard de investigación previa en esta conversación.)

- [ ] **Step 3: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.` y código de salida 0.

- [ ] **Step 4: Commit**

```bash
git add syntage.py
git commit -m "Syntage ya puede listar las facturas que un emisor le hizo a una entidad"
```

---

### Task 2: `monederos.barrer_entidades_syntage()` — agregar `entidad_id` al resultado

**Files:**
- Modify: `monederos.py:243-260` (función `barrer_entidades_syntage`)
- Test: `tests/test_monederos.py` (el bloque de prueba de `barrer_entidades_syntage`, buscar `ENTIDADES_DE_PRUEBA` / `_SyntageEntidadesConFalla`)

**Interfaces:**
- Consumes: nada nuevo.
- Produces: cada dict de `barrer_entidades_syntage()` ahora trae también la clave `"entidad_id"` (el mismo valor que ya se usaba internamente para llamar a `analizar_cliente`). Task 5 (`plan_descarga`) depende de esta clave.

- [ ] **Step 1: Actualizar la prueba existente para exigir la clave nueva**

En `tests/test_monederos.py`, en el bloque que empieza con `resultados = monederos.barrer_entidades_syntage()` (después de restaurar `monederos.syntage = _original_syntage`), agregar:

```python
check(resultados[0]["entidad_id"] == "e1" and resultados[2]["entidad_id"] == "e3",
      "cada resultado trae su entidad_id de Syntage, no solo el RFC")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_monederos.py`
Expected: `FALLA cada resultado trae su entidad_id de Syntage, no solo el RFC` (con `KeyError` o el check en falso — cualquiera de las dos formas de fallar es válida aquí, lo que importa es que no está en verde).

- [ ] **Step 3: Agregar la clave en `barrer_entidades_syntage`**

En `monederos.py`, dentro de `resultados.append({...})` en `barrer_entidades_syntage` (línea ~254-259), agregar la clave:

```python
        resultados.append({
            "rfc": rfc,
            "nombre": (entidad.get("taxpayer") or {}).get("name") or entidad.get("name"),
            "entidad_id": entidad.get("id"),
            "hallazgos": hallazgos,
            "estado": estado,
        })
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_monederos.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 6: Commit**

```bash
git add monederos.py tests/test_monederos.py
git commit -m "El barrido de entidades ya trae el entidad_id de Syntage en cada resultado"
```

---

### Task 3: `estaciones_monedero.facturas_candidatas()`

**Files:**
- Create: `estaciones_monedero.py`
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: `syntage.facturas(entidad_id, rfc_emisor)` (Task 1).
- Produces: `facturas_candidatas(entidad_id: str, rfc_monedero: str) -> list[dict]`. Cada dict: `{"mes": "AAAA-MM", "folio_fiscal": str, "subtotal": float, "fecha": str}`.

- [ ] **Step 1: Escribir la prueba (con un `syntage` de mentiras)**

Crear `tests/test_estaciones_monedero.py`:

```python
# -*- coding: utf-8 -*-
"""
Pruebas de estaciones_monedero.py.

No se llama a Syntage de verdad: se simula con facturas inventadas. La
lógica que sí importa probar es "¿este subtotal cuenta como monto
simbólico?" y "¿aparece el patrón en 2 de los últimos 3 meses?" — no la
llamada de red en sí.

Se corre con:
    python tests/test_estaciones_monedero.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estaciones_monedero

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── facturas_candidatas(): filtra por monto simbólico ───────────────────────
FACTURAS_MIXTAS = [
    {"uuid": "f1", "subtotal": 1.0, "issuedAt": "2026-06-01 05:59:59"},
    {"uuid": "f2", "subtotal": 45230.50, "issuedAt": "2026-06-15 10:00:00"},
    {"uuid": "f3", "subtotal": 2.09, "issuedAt": "2026-07-01 05:59:59"},
]


class _SyntageDeMentiras(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_MIXTAS


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageDeMentiras
candidatas = estaciones_monedero.facturas_candidatas("cualquier-id", "EFE8908015L3")
estaciones_monedero.syntage = _original_syntage

check(len(candidatas) == 2,
      "solo las facturas de monto simbólico cuentan como candidatas: %d" % len(candidatas))
check({c["folio_fiscal"] for c in candidatas} == {"f1", "f3"},
      "la de $45,230.50 (compra real) queda fuera")
check(candidatas[0]["mes"] == "2026-06",
      "el mes sale de issuedAt, truncado a AAAA-MM: %r" % candidatas[0]["mes"])


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `ModuleNotFoundError: No module named 'estaciones_monedero'`

- [ ] **Step 3: Escribir la implementación mínima**

Crear `estaciones_monedero.py`:

```python
# -*- coding: utf-8 -*-
"""
estaciones_monedero.py — ¿Es monedero real o compra directa en gasolinera?
=============================================================================
Ver el diseño completo en
docs/superpowers/specs/2026-08-19-estaciones-monedero-design.md.

En corto: una gasolinera-que-también-tiene-monedero-de-marca (Petro-7,
Hidrosina, Ultra Gas...) puede facturarle a un cliente por una carga
directa en su propia estación, sin que haya monedero de por medio. Un
monedero real, en cambio, factura un monto simbólico recurrente cada mes
(el CFDI de $1 con descuento de $1, o similar) y adjunta el detalle real
como un complemento aparte. Este módulo detecta ese patrón por API, sin
descargar nada, para no confundir una cosa con la otra.
"""

import syntage

UMBRAL_MONTO_SIMBOLICO = 50.0


def facturas_candidatas(entidad_id, rfc_monedero):
    """Facturas de ese RFC a esta entidad cuyo subtotal es simbólico: la
    señal de que es una factura de servicio de monedero, no una compra
    real de combustible."""
    candidatas = []
    for f in syntage.facturas(entidad_id, rfc_monedero):
        if (f.get("subtotal") or 0) < UMBRAL_MONTO_SIMBOLICO:
            candidatas.append({
                "mes": (f.get("issuedAt") or "")[:7],
                "folio_fiscal": f.get("uuid"),
                "subtotal": f.get("subtotal"),
                "fecha": f.get("issuedAt"),
            })
    return candidatas
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
git commit -m "Detectar facturas de monto simbolico como candidatas a monedero real"
```

---

### Task 4: `estaciones_monedero.confirmar_monedero_real()`

**Files:**
- Modify: `estaciones_monedero.py`
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: la lista que produce `facturas_candidatas()` (Task 3) — no llama a Syntage directamente, recibe la lista ya calculada.
- Produces: `confirmar_monedero_real(candidatas: list[dict], hoy: date, minimo: int = 2, ventana: int = 3) -> tuple[bool, dict]`. El segundo elemento es `{mes: candidata}` solo para los meses de la ventana que sí tienen candidata.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estaciones_monedero.py`, antes del bloque final de `print()`/`sys.exit`:

```python
# ── confirmar_monedero_real(): patrón mensual sobre una ventana fija ───────
HOY = date(2026, 8, 19)

CANDIDATAS_REALES = [
    {"mes": "2026-06", "folio_fiscal": "f1", "subtotal": 1.0, "fecha": "2026-06-01"},
    {"mes": "2026-07", "folio_fiscal": "f2", "subtotal": 1.0, "fecha": "2026-07-01"},
    {"mes": "2025-01", "folio_fiscal": "viejo", "subtotal": 1.0, "fecha": "2025-01-01"},
]
es_real, por_mes = estaciones_monedero.confirmar_monedero_real(CANDIDATAS_REALES, HOY)
check(es_real, "2 de los últimos 3 meses (junio y julio 2026) confirman monedero real")
check(set(por_mes) == {"2026-06", "2026-07"},
      "solo los meses dentro de la ventana quedan en el resultado: %r" % set(por_mes))
check("2025-01" not in por_mes, "una candidata vieja fuera de la ventana no cuenta")

CANDIDATA_UNICA = [
    {"mes": "2026-08", "folio_fiscal": "f3", "subtotal": 1.0, "fecha": "2026-08-01"},
]
es_real_unica, _ = estaciones_monedero.confirmar_monedero_real(CANDIDATA_UNICA, HOY)
check(not es_real_unica, "1 sola coincidencia en la ventana no basta (se requieren 2)")

es_real_vacia, por_mes_vacio = estaciones_monedero.confirmar_monedero_real([], HOY)
check(not es_real_vacia and por_mes_vacio == {}, "sin candidatas no hay monedero real")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `AttributeError: module 'estaciones_monedero' has no attribute 'confirmar_monedero_real'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estaciones_monedero.py`:

```python
def _ultimos_n_meses(hoy, n):
    meses = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        meses.append("%04d-%02d" % (anio, mes))
        mes -= 1
        if mes == 0:
            mes, anio = 12, anio - 1
    return meses


def confirmar_monedero_real(candidatas, hoy, minimo=2, ventana=3):
    """¿Aparece el patrón de monto simbólico en al menos `minimo` de los
    últimos `ventana` meses? `por_mes` solo trae los meses de la ventana
    que sí tienen candidata, para que el plan de descarga (Task 5) sepa
    exactamente cuál factura ir a buscar en cada mes."""
    meses_ventana = set(_ultimos_n_meses(hoy, ventana))
    por_mes = {}
    for c in candidatas:
        if c["mes"] in meses_ventana and c["mes"] not in por_mes:
            por_mes[c["mes"]] = c
    return len(por_mes) >= minimo, por_mes
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estaciones_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`

- [ ] **Step 6: Commit**

```bash
git add estaciones_monedero.py tests/test_estaciones_monedero.py
git commit -m "Confirmar monedero real por recurrencia mensual, no por una sola factura"
```

---

### Task 5: `estaciones_monedero.plan_descarga()`

**Files:**
- Modify: `estaciones_monedero.py`
- Test: `tests/test_estaciones_monedero.py`

**Interfaces:**
- Consumes: la forma exacta que produce `monederos.barrer_entidades_syntage()` tras la Task 2 — lista de dicts con `rfc`, `nombre`, `entidad_id`, `hallazgos` (lista de dicts con `rfc_monedero`, `nombre_comercial`), `estado`. Y `facturas_candidatas()` / `confirmar_monedero_real()` de este mismo módulo.
- Produces: `plan_descarga(clientes: list[dict], hoy: date = None) -> list[dict]`. Cada dict: `{"rfc_cliente", "nombre_cliente", "rfc_monedero", "nombre_monedero", "mes", "folio_fiscal"}`.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estaciones_monedero.py`:

```python
# ── plan_descarga(): une facturas_candidatas + confirmar_monedero_real ─────
CLIENTES_DE_PRUEBA = [
    {"rfc": "CLI001", "nombre": "CLIENTE UNO", "entidad_id": "e1",
     "hallazgos": [{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard"},
                   {"rfc_monedero": "PET7000000XX", "nombre_comercial": "Petro-7"}],
     "estado": "ok"},
]

FACTURAS_POR_MONEDERO = {
    # Efecticard: patron real, 2 de 3 meses.
    "EFE8908015L3": [
        {"uuid": "fa", "subtotal": 1.0, "issuedAt": "2026-06-01 00:00:00"},
        {"uuid": "fb", "subtotal": 1.0, "issuedAt": "2026-07-01 00:00:00"},
    ],
    # Petro-7: una sola factura y de monto real -> no es monedero, fue
    # compra directa en la estacion.
    "PET7000000XX": [
        {"uuid": "fc", "subtotal": 3200.0, "issuedAt": "2026-07-15 00:00:00"},
    ],
}


class _SyntagePlanDescarga(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_POR_MONEDERO.get(rfc_emisor, [])


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntagePlanDescarga
plan = estaciones_monedero.plan_descarga(CLIENTES_DE_PRUEBA, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(plan) == 2,
      "Efecticard confirmado deja 2 renglones (uno por mes), Petro-7 queda fuera: %d" % len(plan))
check(all(p["rfc_monedero"] == "EFE8908015L3" for p in plan),
      "ningun renglon del plan es de Petro-7 (no paso el patron de recurrencia)")
check({p["mes"] for p in plan} == {"2026-06", "2026-07"},
      "los meses del plan son los que si tuvieron factura candidata")
check(plan[0]["rfc_cliente"] == "CLI001" and plan[0]["nombre_monedero"] == "Efecticard",
      "el renglon trae el contexto completo para ubicar la factura a mano")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estaciones_monedero.py`
Expected: `AttributeError: module 'estaciones_monedero' has no attribute 'plan_descarga'`

- [ ] **Step 3: Escribir la implementación**

En `estaciones_monedero.py`, agregar `from datetime import date` **antes** de la línea `import syntage` que ya existe desde la Task 3 (no duplicar ese import):

```python
from datetime import date

import syntage
```

Y agregar la función nueva al final del archivo:

```python
def plan_descarga(clientes, hoy=None):
    """clientes: la salida de monederos.barrer_entidades_syntage() (ya con
    entidad_id en cada resultado). Devuelve exactamente qué facturas
    descargar a mano: cliente, monedero, mes, folio fiscal — solo para los
    (cliente, monedero) que de verdad confirman el patrón de monedero
    real."""
    hoy = hoy or date.today()
    plan = []
    for cliente in clientes:
        for h in cliente.get("hallazgos", []):
            candidatas = facturas_candidatas(cliente["entidad_id"], h["rfc_monedero"])
            es_real, por_mes = confirmar_monedero_real(candidatas, hoy)
            if not es_real:
                continue
            for mes, factura in sorted(por_mes.items()):
                plan.append({
                    "rfc_cliente": cliente["rfc"],
                    "nombre_cliente": cliente.get("nombre"),
                    "rfc_monedero": h["rfc_monedero"],
                    "nombre_monedero": h["nombre_comercial"],
                    "mes": mes,
                    "folio_fiscal": factura["folio_fiscal"],
                })
    return plan
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estaciones_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`

- [ ] **Step 6: Agregar un CLI mínimo**

Agregar al final de `estaciones_monedero.py`:

```python
def main(argv):
    import monederos

    if len(argv) < 2 or argv[1] != "plan":
        print("Uso: python estaciones_monedero.py plan")
        return 1

    clientes = monederos.barrer_entidades_syntage()
    plan = plan_descarga(clientes)
    if not plan:
        print("Ningún (cliente, monedero) confirmó el patrón de monedero real todavía.")
        return 0
    print("%d factura(s) por descargar a mano desde el panel de Syntage:\n" % len(plan))
    for p in plan:
        print("%-14s %-30s %-38s %s  folio %s" % (
            p["rfc_cliente"], (p["nombre_cliente"] or "")[:30],
            p["nombre_monedero"], p["mes"], p["folio_fiscal"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
```

- [ ] **Step 7: Correr la compuerta completa una vez más**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 8: Commit**

```bash
git add estaciones_monedero.py tests/test_estaciones_monedero.py
git commit -m "Armar el plan de descarga: que factura de que cliente y mes ir a buscar"
```

---

### Task 6: `estado_cuenta_monedero._encabezado()` — RFC emisor/receptor/folio fiscal

**Files:**
- Create: `estado_cuenta_monedero.py`
- Test: `tests/test_estado_cuenta_monedero.py`

**Interfaces:**
- Produces: `_encabezado(texto_pagina1: str) -> dict` con claves `rfc_emisor`, `rfc_receptor`, `folio_fiscal`.

Esta prueba usa un fragmento de texto **inventado** con la misma forma que produce `pdfplumber.extract_text()` sobre la página 1 (las etiquetas de dos palabras salen pegadas, ej. `RFCemisor`) — se confirmó a mano contra un PDF real de este mismo tipo de complemento, pero el texto de prueba usa un RFC y nombre ficticios.

- [ ] **Step 1: Escribir la prueba**

Crear `tests/test_estado_cuenta_monedero.py`:

```python
# -*- coding: utf-8 -*-
"""
Pruebas de estado_cuenta_monedero.py.

El texto y las tablas de prueba son inventados, pero con la misma forma
exacta que produce pdfplumber sobre un PDF real de este complemento (se
confirmó a mano contra un PDF de ejemplo real, que no se sube al repo por
traer RFC y razón social de un cliente).

Se corre con:
    python tests/test_estado_cuenta_monedero.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estado_cuenta_monedero as ecm

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── _encabezado(): texto de pdfplumber, etiquetas de dos palabras pegadas ──
TEXTO_PAGINA1 = (
    "RFCemisor: FIC010101AB1 Foliofiscal: 11111111-2222-3333-4444-555555555555\n"
    "Nombreemisor: FICTICIAWALLET No.deseriedelCSD: 00001000000000000000\n"
    "Folio: 1\n"
    "RFCreceptor: CLI020202CD2 Codigopostal,fechayhorade 06600 2026-04-0122:22:37\n"
    "Nombrereceptor: CLIENTEDEPRUEBA emision:\n"
)

enc = ecm._encabezado(TEXTO_PAGINA1)
check(enc["rfc_emisor"] == "FIC010101AB1", "RFC emisor: %r" % enc["rfc_emisor"])
check(enc["rfc_receptor"] == "CLI020202CD2", "RFC receptor: %r" % enc["rfc_receptor"])
check(enc["folio_fiscal"] == "11111111-2222-3333-4444-555555555555",
      "folio fiscal (UUID): %r" % enc["folio_fiscal"])

enc_vacio = ecm._encabezado("texto sin ninguna de las etiquetas esperadas")
check(enc_vacio == {"rfc_emisor": None, "rfc_receptor": None, "folio_fiscal": None},
      "un texto sin las etiquetas no truena, regresa Nones")


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `ModuleNotFoundError: No module named 'estado_cuenta_monedero'`

- [ ] **Step 3: Escribir la implementación mínima**

Crear `estado_cuenta_monedero.py`:

```python
# -*- coding: utf-8 -*-
"""
estado_cuenta_monedero.py — El complemento de combustible, de PDF a datos
============================================================================
Ver el diseño completo en
docs/superpowers/specs/2026-08-19-estaciones-monedero-design.md.

"Estado de Cuenta de Combustibles para Monederos Electrónicos" es un
complemento estandarizado por el SAT: la misma estructura de tablas sin
importar qué monedero lo emite (se confirmó comparando un PDF de Efecticard
y uno de Sí Vale — columnas idénticas). Por eso un solo parser sirve para
todos, y no hace falta uno por monedero.

**Por qué extract_tables() y no extract_text().** El PDF usa celdas de
tabla sin espacio entre ellas; `extract_text()` pega las palabras
("ClavedeEstación", "RFCemisor") y vuelve ambiguo separar campos que a su
vez tienen texto libre. `extract_tables()` respeta el límite de cada
celda. El encabezado (RFC emisor/receptor, folio fiscal) es la excepción:
esas etiquetas sí van en texto corrido, no en una tabla con bordes, así que
se leen con regex sobre extract_text() de la primera página.

**Por qué se cuadra contra el subtotal declarado.** El resumen de cuenta
("Versión / Tipo de Operación / Número de Cuenta / Subtotal / Total") lo
calcula el propio monedero. Si la suma de los cargos que se lograron
parsear no coincide, algo se leyó mal o incompleto — un PDF así se marca
sospechoso en vez de usarse a medias, mismo principio que ya usa
`bbva.cuadra()` para los estados de cuenta bancarios.
"""

import re

RE_RFC_EMISOR = re.compile(r"RFCemisor:\s*(\S+)")
RE_RFC_RECEPTOR = re.compile(r"RFCreceptor:\s*(\S+)")
RE_FOLIO_FISCAL = re.compile(r"Foliofiscal:\s*(\S+)")


def _encabezado(texto_pagina1):
    """RFC emisor/receptor y folio fiscal: vienen en texto corrido de la
    página 1, no en una tabla con bordes."""
    e = RE_RFC_EMISOR.search(texto_pagina1)
    r = RE_RFC_RECEPTOR.search(texto_pagina1)
    f = RE_FOLIO_FISCAL.search(texto_pagina1)
    return {
        "rfc_emisor": e.group(1) if e else None,
        "rfc_receptor": r.group(1) if r else None,
        "folio_fiscal": f.group(1) if f else None,
    }
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`

- [ ] **Step 6: Commit**

```bash
git add estado_cuenta_monedero.py tests/test_estado_cuenta_monedero.py
git commit -m "Leer RFC emisor, receptor y folio fiscal del encabezado del complemento"
```

---

### Task 7: `estado_cuenta_monedero._resumen_cuenta()` y `_cargos()`

**Files:**
- Modify: `estado_cuenta_monedero.py`
- Test: `tests/test_estado_cuenta_monedero.py`

**Interfaces:**
- Produces:
  - `_resumen_cuenta(tablas: list[list[list]]) -> dict | None` con `version`, `tipo_operacion`, `numero_cuenta`, `subtotal`, `total`.
  - `_cargos(tablas: list[list[list]]) -> list[dict]`, cada dict con `identificador`, `fecha` (AAAA-MM-DD), `hora` (HH:MM:SS), `rfc_estacion`, `clave_estacion`, `cantidad`, `tipo_combustible`, `nombre_combustible`, `folio_operacion`, `valor_unitario`, `importe`.

Los fixtures de tabla de este test son la forma **exacta** que devuelve `pagina.extract_tables()` sobre un PDF real de este complemento (confirmado a mano con pdfplumber contra un PDF de ejemplo, con los valores de RFC/estación cambiados a inventados).

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estado_cuenta_monedero.py`, antes del bloque final de `print()`/`sys.exit`:

```python
# ── _resumen_cuenta(): la tabla resumen del estado de cuenta ───────────────
TABLA_RESUMEN = [
    ["Versión", "TipodeOperación", "NúmerodeCuenta", "Subtotal", "Total"],
    ["1.2", "Tarjeta", "F116300001", "50863.30", "58770.30"],
]
TABLA_NO_RESUMEN = [["Identificador", "Fecha"], ["dato", "dato"]]

resumen = ecm._resumen_cuenta([TABLA_NO_RESUMEN, TABLA_RESUMEN])
check(resumen is not None, "encuentra la tabla resumen aunque no sea la primera")
check(resumen["numero_cuenta"] == "F116300001", "número de cuenta: %r" % resumen["numero_cuenta"])
check(resumen["subtotal"] == 50863.30 and resumen["total"] == 58770.30,
      "subtotal y total salen como float: %r / %r" % (resumen["subtotal"], resumen["total"]))

check(ecm._resumen_cuenta([TABLA_NO_RESUMEN]) is None,
      "sin tabla resumen en esta página, regresa None (no truena)")


# ── _cargos(): cada bloque de cargo es una tabla de 4 filas ────────────────
# Forma real confirmada con pdfplumber.extract_tables() contra un PDF de
# ejemplo (RFC y clave de estación cambiados aquí a valores inventados).
TABLA_CARGO = [
    ["Identificador", "Fecha", None, "RFC", "ClavedeEstación", "Cantidad",
     "TipodeCombustible", "Unidad", "NombreCombustible", "FoliodeOperación"],
    ["XXXXXXXXXXXX\n0001", "2026-03-0919:06:04", None, "FIC120327XYZ", "9999999",
     "44.164", "1", "LTS", "GasolinaMagnaFleet", "388927"],
    ["ValorUnitario", None, "Importe", None, None, None, None, None, None, None],
    ["20.590", None, "909.35", None, None, None, None, None, None, None],
]
TABLA_TRASLADOS = [["Impuesto", "Tasao\nCuota", "Importe"], ["IVA", "0.16", "141.32"]]

cargos = ecm._cargos([TABLA_CARGO, TABLA_TRASLADOS])
check(len(cargos) == 1, "una tabla de traslados no se confunde con un cargo: %d" % len(cargos))
c = cargos[0]
check(c["fecha"] == "2026-03-09" and c["hora"] == "19:06:04",
      "fecha y hora se separan aunque vengan pegadas: %r %r" % (c["fecha"], c["hora"]))
check(c["rfc_estacion"] == "FIC120327XYZ", "RFC de estación: %r" % c["rfc_estacion"])
check(c["clave_estacion"] == "9999999", "clave de estación: %r" % c["clave_estacion"])
check(c["cantidad"] == 44.164, "litros: %r" % c["cantidad"])
check(c["nombre_combustible"] == "GasolinaMagnaFleet", "nombre del combustible: %r" % c["nombre_combustible"])
check(c["valor_unitario"] == 20.590 and c["importe"] == 909.35,
      "valor unitario e importe: %r / %r" % (c["valor_unitario"], c["importe"]))

check(ecm._cargos([TABLA_TRASLADOS]) == [], "una página sin ningún bloque de cargo regresa lista vacía")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `AttributeError: module 'estado_cuenta_monedero' has no attribute '_resumen_cuenta'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estado_cuenta_monedero.py`:

```python
RE_FECHA_HORA = re.compile(r"^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})$")


def _resumen_cuenta(tablas):
    """La tabla 'Versión / Tipo de Operación / Número de Cuenta / Subtotal /
    Total'. No siempre está en la misma página que los cargos, así que se
    busca en vez de asumir su posición."""
    for t in tablas:
        if t and t[0][:1] == ["Versión"]:
            fila = t[1]
            return {
                "version": fila[0],
                "tipo_operacion": fila[1],
                "numero_cuenta": fila[2],
                "subtotal": float(fila[3]),
                "total": float(fila[4]),
            }
    return None


def _cargos(tablas):
    """Cada bloque de cargo es una tabla de 4 filas: encabezado, datos,
    encabezado de 'Valor Unitario/Importe', datos de esos dos. Se
    distingue de la tabla de 'Traslados' (que también tiene forma de
    tabla chica) por su propio encabezado ('Identificador', 'Fecha')."""
    cargos = []
    for t in tablas:
        if not t or len(t) < 4 or t[0][0] != "Identificador" or t[0][1] != "Fecha":
            continue
        datos = t[1]
        m = RE_FECHA_HORA.match(datos[1] or "")
        fecha, hora = (m.group(1), m.group(2)) if m else (datos[1], None)
        valor_importe = t[3]
        cargos.append({
            "identificador": datos[0],
            "fecha": fecha,
            "hora": hora,
            "rfc_estacion": datos[3],
            "clave_estacion": datos[4],
            "cantidad": float(datos[5]) if datos[5] else None,
            "tipo_combustible": datos[6],
            "nombre_combustible": datos[8],
            "folio_operacion": datos[9],
            "valor_unitario": float(valor_importe[0]) if valor_importe[0] else None,
            "importe": float(valor_importe[2]) if valor_importe[2] else None,
        })
    return cargos
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`

- [ ] **Step 6: Commit**

```bash
git add estado_cuenta_monedero.py tests/test_estado_cuenta_monedero.py
git commit -m "Parsear el resumen de cuenta y cada cargo del complemento de combustible"
```

---

### Task 8: `estado_cuenta_monedero.cuadra()` y `agregar_por_estacion()`

**Files:**
- Modify: `estado_cuenta_monedero.py`
- Test: `tests/test_estado_cuenta_monedero.py`

**Interfaces:**
- Consumes: la forma que producen `_cargos()` y `_resumen_cuenta()` (Task 7).
- Produces:
  - `cuadra(cargos: list[dict], resumen: dict | None, tolerancia: float = 0.05) -> bool`
  - `agregar_por_estacion(cargos: list[dict]) -> dict[tuple[str, str], dict]`, valor con `cargas`, `litros`, `importe`.

- [ ] **Step 1: Escribir la prueba**

Agregar a `tests/test_estado_cuenta_monedero.py`:

```python
# ── cuadra(): la suma de importes contra el subtotal declarado ────────────
CARGOS_DE_PRUEBA = [
    {"rfc_estacion": "FIC120327XYZ", "clave_estacion": "9999999", "cantidad": 44.164, "importe": 909.35},
    {"rfc_estacion": "FIC120327XYZ", "clave_estacion": "9999999", "cantidad": 20.0, "importe": 410.00},
    {"rfc_estacion": "OTR050101ABC", "clave_estacion": "1234567", "cantidad": 30.0, "importe": 615.00},
]

check(ecm.cuadra(CARGOS_DE_PRUEBA, {"subtotal": 1934.35}),
      "la suma de importes (1934.35) cuadra contra el subtotal declarado")
check(not ecm.cuadra(CARGOS_DE_PRUEBA, {"subtotal": 5000.0}),
      "una diferencia grande no cuadra: el PDF se marca sospechoso")
check(not ecm.cuadra(CARGOS_DE_PRUEBA, None),
      "sin resumen de cuenta (no se encontró la tabla), nunca cuadra")


# ── agregar_por_estacion(): por (RFC, clave) de estación ───────────────────
agregado = ecm.agregar_por_estacion(CARGOS_DE_PRUEBA)
check(len(agregado) == 2, "dos estaciones distintas: %d" % len(agregado))
clave_repetida = ("FIC120327XYZ", "9999999")
check(agregado[clave_repetida]["cargas"] == 2,
      "dos cargos en la misma estación se agregan, no se cuentan como estaciones distintas")
check(abs(agregado[clave_repetida]["importe"] - 1319.35) < 0.01,
      "importe total de esa estación: %r" % agregado[clave_repetida]["importe"])
check(abs(agregado[clave_repetida]["litros"] - 64.164) < 0.01,
      "litros totales de esa estación: %r" % agregado[clave_repetida]["litros"])
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `AttributeError: module 'estado_cuenta_monedero' has no attribute 'cuadra'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estado_cuenta_monedero.py`:

```python
def cuadra(cargos, resumen, tolerancia=0.05):
    """La suma de importes debe coincidir con el subtotal que declaró el
    propio monedero. Si no cuadra, el PDF se marca sospechoso — nunca se
    usa a medias."""
    if resumen is None:
        return False
    suma = sum(c["importe"] or 0 for c in cargos)
    return abs(suma - resumen["subtotal"]) <= tolerancia


def agregar_por_estacion(cargos):
    """(RFC de estación, clave de estación) -> número de cargas, litros e
    importe total. La clave es el par, no solo la clave de estación: dos
    monederos distintos podrían coincidir en la clave interna."""
    agregado = {}
    for c in cargos:
        clave = (c["rfc_estacion"], c["clave_estacion"])
        a = agregado.setdefault(clave, {"cargas": 0, "litros": 0.0, "importe": 0.0})
        a["cargas"] += 1
        a["litros"] += c["cantidad"] or 0
        a["importe"] += c["importe"] or 0
    return agregado
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Correr la compuerta completa**

Run: `python tests/todas.py`

- [ ] **Step 6: Commit**

```bash
git add estado_cuenta_monedero.py tests/test_estado_cuenta_monedero.py
git commit -m "Cuadrar los cargos contra el subtotal declarado y agregar por estacion"
```

---

### Task 9: `estado_cuenta_monedero.leer_pdf()` — juntar todo, de un PDF real

**Files:**
- Modify: `estado_cuenta_monedero.py`

**Interfaces:**
- Produces: `leer_pdf(ruta: str) -> dict` con claves `encabezado`, `resumen`, `cargos` (las mismas formas de las tareas 6-7).

Esta es la única pieza de este módulo que toca pdfplumber/disco directamente — como el resto del repo (`db.py`, `syntage.py`), el I/O real no lleva prueba automatizada con mocks; se verifica a mano contra un PDF real.

- [ ] **Step 1: Escribir la función**

Agregar `import pdfplumber` **después** de la línea `import re` que ya existe desde la Task 6 (no duplicar `import re`). El bloque de imports debe quedar:

```python
import re

import pdfplumber
```

Y al final del archivo:

```python
def leer_pdf(ruta):
    """Todo lo que trae un PDF de complemento: encabezado, resumen de
    cuenta y cargos, juntando todas sus páginas. El resumen de cuenta se
    busca en cada página hasta encontrarlo porque no siempre está en la
    primera."""
    with pdfplumber.open(ruta) as pdf:
        encabezado = _encabezado(pdf.pages[0].extract_text() or "")
        resumen = None
        cargos = []
        for pagina in pdf.pages:
            tablas = pagina.extract_tables()
            if resumen is None:
                resumen = _resumen_cuenta(tablas)
            cargos.extend(_cargos(tablas))
    return {"encabezado": encabezado, "resumen": resumen, "cargos": cargos}
```

- [ ] **Step 2: Verificar a mano contra un PDF real**

Usando uno de los PDF de ejemplo de esta conversación (no viven en el repo; usar la ruta local donde el usuario los tenga descargados):

```bash
python -c "
import sys; sys.path.insert(0, '.')
import estado_cuenta_monedero as ecm
r = ecm.leer_pdf(r'C:\Users\luisg\Downloads\d638421f-3e79-493c-8c17-18ab9b5e1876.pdf')
print('encabezado:', r['encabezado'])
print('resumen:', r['resumen'])
print('cargos encontrados:', len(r['cargos']))
print('cuadra:', ecm.cuadra(r['cargos'], r['resumen']))
print('estaciones distintas:', len(ecm.agregar_por_estacion(r['cargos'])))
"
```
Expected: `encabezado` con el RFC emisor/receptor reales de ese PDF, `resumen` con subtotal/total, `cuadra: True`, y un número de estaciones mayor a 0, sin traceback.

- [ ] **Step 3: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.` (esta tarea no agrega pruebas nuevas, pero confirma que nada se rompió).

- [ ] **Step 4: Commit**

```bash
git add estado_cuenta_monedero.py
git commit -m "Leer un PDF de complemento completo: encabezado, resumen y cargos juntos"
```

---

### Task 10: `estado_cuenta_monedero.reporte_carpeta()` — el reporte final

**Files:**
- Modify: `estado_cuenta_monedero.py`
- Test: `tests/test_estado_cuenta_monedero.py`

**Interfaces:**
- Produces:
  - `_partes_nombre(nombre_archivo: str) -> tuple[str, str, str] | None` — separa `RFC_CLIENTE`, `RFC_MONEDERO`, `AAAA-MM` del nombre de archivo (`{RFC_CLIENTE}_{RFC_MONEDERO}_{AAAA-MM}.pdf`), o `None` si no calza con la convención.
  - `reporte_carpeta(carpeta: str) -> dict` — por RFC de cliente: `meses` (por mes: monedero, estaciones agregadas, total del mes) y `sospechosos` (rutas de PDF que no cuadraron o no calzan con la convención de nombre).

Solo `_partes_nombre` se prueba de forma unitaria (es la única lógica pura de esta pieza); `reporte_carpeta` en sí es orquestación de I/O (glob + `leer_pdf`) y se verifica a mano, igual que `leer_pdf`.

- [ ] **Step 1: Escribir la prueba de `_partes_nombre`**

Agregar a `tests/test_estado_cuenta_monedero.py`:

```python
# ── _partes_nombre(): RFC_CLIENTE_RFC_MONEDERO_AAAA-MM.pdf ─────────────────
check(ecm._partes_nombre("LOG150312XX3_EFE8908015L3_2026-06.pdf") ==
      ("LOG150312XX3", "EFE8908015L3", "2026-06"),
      "separa las tres partes del nombre de archivo")
check(ecm._partes_nombre("nombre-que-no-calza.pdf") is None,
      "un nombre que no sigue la convención regresa None, no truena")
```

- [ ] **Step 2: Correr la prueba y confirmar que falla**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `AttributeError: module 'estado_cuenta_monedero' has no attribute '_partes_nombre'`

- [ ] **Step 3: Escribir la implementación**

Agregar a `estado_cuenta_monedero.py`:

```python
def _partes_nombre(nombre_archivo):
    """RFC_CLIENTE_RFC_MONEDERO_AAAA-MM.pdf -> (rfc_cliente, rfc_monedero,
    mes). El parser no depende de esto para leer el PDF —lee RFC y fechas
    del propio documento—; es solo para organizar la descarga manual."""
    nombre, ext = os.path.splitext(os.path.basename(nombre_archivo))
    if ext.lower() != ".pdf":
        return None
    partes = nombre.split("_")
    if len(partes) != 3:
        return None
    return tuple(partes)


def reporte_carpeta(carpeta):
    """Lee todos los PDF de una carpeta y arma el reporte final: por
    cliente, cada mes con su monedero, estaciones agregadas y total; y los
    PDF sospechosos (no cuadraron, o su nombre no sigue la convención) por
    separado, nunca mezclados en el agregado."""
    resultado = {}
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.pdf"))):
        partes = _partes_nombre(ruta)
        if partes is None:
            resultado.setdefault("_sin_clasificar", {"meses": {}, "sospechosos": []})
            resultado["_sin_clasificar"]["sospechosos"].append(ruta)
            continue
        rfc_cliente, rfc_monedero, mes = partes
        cliente = resultado.setdefault(rfc_cliente, {"meses": {}, "sospechosos": []})
        datos = leer_pdf(ruta)
        if not cuadra(datos["cargos"], datos["resumen"]):
            cliente["sospechosos"].append(ruta)
            continue
        cliente["meses"][mes] = {
            "rfc_monedero": rfc_monedero,
            "por_estacion": agregar_por_estacion(datos["cargos"]),
            "total": datos["resumen"]["subtotal"] if datos["resumen"] else None,
        }
    return resultado
```

Y agregar `import glob` y `import os` **antes** de la línea `import re` que ya existe desde la Task 6 (no duplicar `import re` ni `import pdfplumber`, que ya están desde las Tasks 6 y 9). El bloque de imports debe quedar:

```python
import glob
import os
import re

import pdfplumber
```

- [ ] **Step 4: Correr la prueba y confirmar que pasa**

Run: `python tests/test_estado_cuenta_monedero.py`
Expected: `Todas las pruebas pasaron.`

- [ ] **Step 5: Agregar un CLI mínimo**

Agregar al final de `estado_cuenta_monedero.py`:

```python
def main(argv):
    if len(argv) < 3 or argv[1] != "reporte":
        print("Uso: python estado_cuenta_monedero.py reporte <carpeta>")
        return 1

    reporte = reporte_carpeta(argv[2])
    for rfc_cliente, datos in reporte.items():
        if rfc_cliente == "_sin_clasificar":
            continue
        print("\n%s" % rfc_cliente)
        estaciones_totales = set()
        for mes, d in sorted(datos["meses"].items()):
            estaciones_totales.update(d["por_estacion"].keys())
            print("  %s  %-16s  $%s" % (
                mes, d["rfc_monedero"], format(d["total"] or 0, ",.2f")))
            for (rfc_est, clave_est), agregado in d["por_estacion"].items():
                print("      estacion %s/%s: %d carga(s), $%s" % (
                    rfc_est, clave_est, agregado["cargas"],
                    format(agregado["importe"], ",.2f")))
        print("  -> %d estacion(es) distinta(s) en los meses con PDF" % len(estaciones_totales))
        if datos["sospechosos"]:
            print("  ATENCION: %d PDF no cuadraron o no se pudieron usar:" % len(datos["sospechosos"]))
            for s in datos["sospechosos"]:
                print("    %s" % s)
    if reporte.get("_sin_clasificar", {}).get("sospechosos"):
        print("\nArchivos que no siguen la convención de nombre:")
        for s in reporte["_sin_clasificar"]["sospechosos"]:
            print("  %s" % s)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
```

- [ ] **Step 6: Correr la compuerta completa**

Run: `python tests/todas.py`
Expected: `Todo verde.`

- [ ] **Step 7: Commit**

```bash
git add estado_cuenta_monedero.py tests/test_estado_cuenta_monedero.py
git commit -m "Armar el reporte final: cliente x estacion x mes a partir de la carpeta de PDFs"
```

---

## Al terminar

En este punto:

- `python estaciones_monedero.py plan` dice exactamente qué facturas bajar a mano del panel de Syntage (cliente, monedero, mes, folio fiscal), ya filtradas para que solo aparezcan relaciones de monedero confirmadas — no compras directas en una gasolinera-que-también-es-monedero.
- Una vez descargados esos PDF a `descargas/monederos/` con la convención de nombre, `python estado_cuenta_monedero.py reporte descargas/monederos` da el reporte final: por cliente, en cuántas estaciones distintas cargó, cuánto le facturaron por mes y por estación.
- La comisión que cobra cada monedero (tercera pregunta original de la conversación) sigue pendiente — este complemento da litros e importe de la gasolina, no la comisión del servicio. Queda para un siguiente spike.
