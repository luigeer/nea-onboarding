# Aumentos de línea de crédito — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la plataforma registre y evalúe aumentos de línea de clientes que ya operan, incluidos los que son anteriores al sistema y no tienen expediente.

**Architecture:** Se extiende el expediente que ya existe con un historial de aumentos y un bloque de uso de la tarjeta; se agrega un lector del Excel de uso que deriva los atrasos en vez de capturarlos; y se agrega un módulo y una función de score propios del aumento. Nada de la ruta de originación cambia de comportamiento: ni `evaluar()`, ni `compuertas_generacion()`, ni `cmd_nuevo` sin su bandera nueva.

**Tech Stack:** Python 3, biblioteca estándar, `openpyxl` para el Excel. Sin framework de pruebas: los tests son scripts de Python que se corren solos, como el resto del repo.

**Spec:** `docs/superpowers/specs/2026-08-19-aumentos-de-linea-design.md`

## Global Constraints

- **La compuerta del proyecto es `python tests/todas.py` y el veredicto es el código de salida**, nunca el texto. Ningún paso se declara terminado sin correrla.
- **TDD sin excepción:** primero la prueba que falla, se corre para verla fallar, luego el código mínimo.
- **Estilo de pruebas del repo:** scripts planos, sin pytest. Cada archivo define `fallas = []` y `def check(cond, msg)`, imprime `ok`/`FALLA` por línea, y termina con `sys.exit(1)` si hay fallas. Se corren con `python tests/test_X.py`. Ver `tests/test_bbva.py` como molde.
- **Cero datos personales en el repo.** Todos los datos de prueba son inventados. Los expedientes y descargas ya están en `.gitignore`.
- **`schema_expediente.py` no importa nada más que `datetime`.** Es la fuente única de verdad y se mantiene sin dependencias: si una compuerta necesita un dato que vive fuera del expediente, se le pasa como parámetro.
- **Los comentarios explican por qué, no qué.** El repo documenta la decisión y el error que la motivó; se sigue esa costumbre.
- Idioma del código, comentarios y mensajes: **español**, sin acentos en los identificadores.
- `UMBRAL_AUMENTO_MAYOR = 150000.0` · `ESTADOS_CUENTA_AUMENTO = 3` · `VERSION_AUMENTO = "2026.08-aumentos"`

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `uso_plataforma.py` (nuevo) | Leer el Excel de uso, cuadrar el saldo de cada ciclo, derivar atrasos, resumir. Sin conocimiento del expediente. |
| `schema_expediente.py` (modificar) | `historial_aumentos`, bloque `uso_plataforma`, umbrales, y las dos compuertas del aumento. |
| `modelo_riesgo.py` (modificar) | `_uso_plataforma()`, `PESOS_MODULO_AUMENTO`, `evaluar_aumento()`. |
| `nea.py` (modificar) | Etapa `operando`, `nuevo --heredado`, y los comandos `uso` y `aumento *`. |
| `requirements.txt` (modificar) | Declarar `openpyxl`. |
| `tests/test_uso_plataforma.py` (nuevo) | Cuadre, derivación de atrasos, resumen. |
| `tests/test_compuertas_aumento.py` (nuevo) | Las dos compuertas nuevas + regresión de `compuertas_generacion`. |
| `tests/test_modelo_aumento.py` (nuevo) | El módulo de uso, la renormalización, y regresión de `evaluar()`. |

**Orden de dependencias:** Tareas 1–3 construyen `uso_plataforma.py` de abajo hacia arriba. Tareas 4–5 el esquema. Tareas 6–7 el modelo. Tareas 8–10 la interfaz. Cada tarea deja la compuerta verde.

---

### Task 1: Lector del Excel — parseo tolerante y cuadre del saldo

El Excel sale de una consulta a la base de la plataforma. Sus fechas vienen como texto en inglés (`"Aug. 10, 2026"`, `"July 31, 2026, 11:59 p.m."`, con `midnight` y `noon`) y sus encabezados traen los acentos corrompidos. El cuadre es lo que hace confiable todo lo demás: si el saldo de un ciclo no cierra, no se usa el archivo.

**Files:**
- Create: `uso_plataforma.py`
- Modify: `requirements.txt`
- Test: `tests/test_uso_plataforma.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `ErrorDeFormato(Exception)`
  - `PESTANAS = ("Transacciones", "Depositos", "Estado de Cuenta", "Comisiones")`
  - `_sin_acentos(texto) -> str`
  - `_fecha(valor) -> datetime.date | None`
  - `_indice_columna(encabezados, nombre) -> int` (lanza `ErrorDeFormato` si no está)
  - `leer(ruta) -> dict` con las llaves `transacciones`, `depositos`, `ciclos`, `comisiones`
  - `cuadra(datos, tolerancia=0.02) -> (bool, dict)`

Formas de los registros que produce `leer()` y que todas las tareas siguientes consumen:

```python
# transaccion
{"fecha": date, "comercio": str, "usuario": str, "tarjeta": str, "monto": float}
# deposito
{"fecha": date, "concepto": str, "monto": float}
# ciclo
{"id": str, "inicio": date, "corte": date, "pago": date,
 "saldo_inicio": float, "saldo_corte": float}
# comision
{"fecha": date, "nombre": str, "importe": float, "iva": float}
```

- [ ] **Step 1: Declarar openpyxl**

En `requirements.txt`, después del bloque de generación y lectura de documentos:

```
openpyxl>=3.1
```

- [ ] **Step 2: Escribir la prueba que falla**

Crear `tests/test_uso_plataforma.py`:

```python
# -*- coding: utf-8 -*-
"""
Pruebas del lector del Excel de uso de la plataforma.

Lo que se prueba es donde está el juicio, no la mecánica de openpyxl:

- que las fechas en texto se parseen, incluidas 'midnight' y 'noon', porque de
  la fecha de pago depende si hubo atraso;
- que un encabezado con el acento corrompido siga reconociéndose, porque el
  export llega así y depender del acento rompe el lector en silencio;
- que `cuadra` diga que NO cuando el saldo del ciclo no cierra, que es lo único
  que impide que un archivo mal leído entre al modelo como si fuera bueno.

Todos los datos son inventados.

Se corre con:
    python tests/test_uso_plataforma.py
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uso_plataforma as up

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── las fechas del export vienen como texto en ingles ────────────────────────
print("Parseo de fechas")
check(up._fecha("Aug. 10, 2026") == datetime.date(2026, 8, 10),
      "el mes abreviado con punto se parsea")
check(up._fecha("July 31, 2026, 11:59 p.m.") == datetime.date(2026, 7, 31),
      "el mes completo con hora se parsea")
check(up._fecha("June 17, 2026, midnight") == datetime.date(2026, 6, 17),
      "'midnight' no tumba el parseo")
check(up._fecha("July 1, 2026, noon") == datetime.date(2026, 7, 1),
      "'noon' tampoco")
check(up._fecha(datetime.datetime(2026, 6, 23, 11, 0)) == datetime.date(2026, 6, 23),
      "una fecha que ya viene como fecha se respeta")
check(up._fecha("no es fecha") is None, "lo que no es fecha devuelve None, no explota")

# ── el encabezado llega con los acentos corrompidos ──────────────────────────
print()
print("Encabezados con acentos corrompidos")
enc = ["Fecha de transacci\ufffdn", "Importe", "IVA", "Empresa",
       "Nombre de la comisi\ufffdn"]
check(up._indice_columna(enc, "Nombre de la comision") == 4,
      "la columna se encuentra aunque el acento venga corrompido")
check(up._indice_columna(enc, "Importe") == 1,
      "una columna sin acento se encuentra igual")
try:
    up._indice_columna(enc, "Columna Que No Existe")
    check(False, "una columna ausente debe lanzar ErrorDeFormato")
except up.ErrorDeFormato:
    check(True, "una columna ausente lanza ErrorDeFormato, no IndexError")

# ── el cuadre del saldo por ciclo ────────────────────────────────────────────
print()
print("Cuadre del saldo de cada ciclo")


def datos_que_cuadran():
    """saldo_corte = saldo_inicio + transacciones + comisiones con IVA - pagos"""
    return {
        "ciclos": [{"id": "1", "inicio": datetime.date(2026, 6, 1),
                    "corte": datetime.date(2026, 6, 30),
                    "pago": datetime.date(2026, 7, 10),
                    "saldo_inicio": 0.0, "saldo_corte": 1116.0}],
        "transacciones": [
            {"fecha": datetime.date(2026, 6, 5), "comercio": "X", "usuario": "a",
             "tarjeta": "1111", "monto": 1000.0}],
        "comisiones": [
            {"fecha": datetime.date(2026, 6, 1), "nombre": "Comision por financiamiento",
             "importe": 100.0, "iva": 16.0}],
        "depositos": [],
    }


ok, diag = up.cuadra(datos_que_cuadran())
check(ok, "cuando el saldo cierra al centavo, cuadra")

d = datos_que_cuadran()
d["comisiones"] = []
ok, diag = up.cuadra(d)
check(not ok, "si se ignoran las comisiones el saldo no cierra: NO cuadra")
check(diag["1"]["diferencia"] == -116.0,
      "y el diagnostico dice de cuanto es la diferencia y en que ciclo")

d = datos_que_cuadran()
d["depositos"] = [{"fecha": datetime.date(2026, 6, 20), "concepto": "pago",
                   "monto": 500.0}]
ok, _ = up.cuadra(d)
check(not ok, "un pago dentro del ciclo baja el saldo al corte: si no se resta, NO cuadra")

d = datos_que_cuadran()
d["ciclos"][0]["saldo_corte"] = 1116.01
ok, _ = up.cuadra(d)
check(ok, "un centavo de diferencia entra en la tolerancia")

d = datos_que_cuadran()
d["ciclos"][0]["saldo_corte"] = 1117.0
ok, _ = up.cuadra(d)
check(not ok, "un peso de diferencia no entra en la tolerancia")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
```

- [ ] **Step 3: Correr la prueba para verla fallar**

Run: `python tests/test_uso_plataforma.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'uso_plataforma'`

- [ ] **Step 4: Escribir el lector**

Crear `uso_plataforma.py`:

```python
# -*- coding: utf-8 -*-
"""
uso_plataforma.py — Lee el uso de la tarjeta Nea de un cliente que ya opera
===========================================================================
Entra el libro de Excel que sale de consultar la base de datos de la plataforma;
salen los datos normalizados y, sobre todo, **los atrasos derivados**. Los
atrasos no se capturan a mano: se calculan cruzando lo exigible de cada corte
contra los pagos acreditados a la fecha de vencimiento. Un dato capturado a mano
es un dato que alguien puede teclear distinto de la realidad.

**Por qué un cuadre.** Igual que `bbva.py` compara lo parseado contra los totales
que declara el banco, aquí se comprueba que el saldo de cada ciclo cierre:

    saldo al corte = saldo inicial + transacciones + comisiones con IVA - pagos

Si no cierra, el archivo no se usa. Un archivo mal leído entra al modelo de
riesgo como si fuera bueno y nadie lo nota. La verificación se corrió contra un
export real de dos ciclos y cerró al centavo en los dos.

**Por qué tolerar los acentos rotos.** El export llega con los encabezados
corrompidos —donde va la vocal acentuada aparece un caracter de reemplazo—, así
que "Nombre de la comisión" no coincide por igualdad literal. Se compara sin
acentos y sin depender de ellos.

**Las fechas vienen como texto en inglés** en tres de las cuatro pestañas
("Aug. 10, 2026", "July 31, 2026, 11:59 p.m.", con 'midnight' y 'noon'), y como
fecha real en la de transacciones. Se aceptan las dos formas.
"""

import datetime
import re
import unicodedata

PESTANAS = ("Transacciones", "Depositos", "Estado de Cuenta", "Comisiones")

MESES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}

RE_FECHA_TEXTO = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})")


class ErrorDeFormato(Exception):
    """El libro no tiene la forma que este lector espera."""


def _sin_acentos(texto):
    """Minúsculas, sin acentos y sin el caracter de reemplazo del export.

    El export corrompe los acentos, así que 'comisi\ufffdn' y 'comision' tienen
    que verse iguales. Se quitan los acentos reales y se borra el caracter de
    reemplazo, en vez de traducirlo: no se sabe qué vocal era.
    """
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\ufffd", "").replace("?", "")
    return " ".join(t.lower().split())


def _fecha(valor):
    """La fecha de un valor del Excel, venga como fecha o como texto en inglés."""
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    m = RE_FECHA_TEXTO.search(str(valor or ""))
    if not m:
        return None
    mes = MESES.get(m.group(1).lower())
    if not mes:
        return None
    try:
        return datetime.date(int(m.group(3)), mes, int(m.group(2)))
    except ValueError:
        return None


def _indice_columna(encabezados, nombre):
    """La posición de una columna, comparando sin acentos.

    Lanza ErrorDeFormato en vez de devolver -1: una columna que no está es un
    archivo que no se puede leer, y hay que decirlo donde pasa.
    """
    buscado = _sin_acentos(nombre)
    for i, e in enumerate(encabezados):
        if _sin_acentos(e) == buscado:
            return i
    raise ErrorDeFormato(
        "No encuentro la columna %r. Las que hay: %s"
        % (nombre, ", ".join(str(e) for e in encabezados)))


def _num(valor, default=0.0):
    if valor is None or valor == "-":
        return default
    try:
        return float(str(valor).replace(",", "").replace("$", "").strip())
    except ValueError:
        return default


def _hoja(libro, nombre):
    for hoja in libro.worksheets:
        if _sin_acentos(hoja.title) == _sin_acentos(nombre):
            return hoja
    raise ErrorDeFormato(
        "El libro no tiene la pestana %r. Las que tiene: %s"
        % (nombre, ", ".join(h.title for h in libro.worksheets)))


def _filas(hoja):
    """(encabezados, filas de datos) de una hoja."""
    todo = list(hoja.iter_rows(values_only=True))
    if not todo:
        raise ErrorDeFormato("La pestana %r esta vacia." % hoja.title)
    return todo[0], [f for f in todo[1:] if any(c is not None for c in f)]


def leer(ruta):
    """Los datos de uso normalizados. Lanza ErrorDeFormato si el libro no calza."""
    import openpyxl
    libro = openpyxl.load_workbook(ruta, data_only=True)

    enc, filas = _filas(_hoja(libro, "Transacciones"))
    i_f = _indice_columna(enc, "Fecha Aprobacion")
    i_c = _indice_columna(enc, "Merchant Name")
    i_u = _indice_columna(enc, "Usuario")
    i_t = _indice_columna(enc, "Ultimos 4 digitos")
    i_m = _indice_columna(enc, "Monto")
    transacciones = [{"fecha": _fecha(f[i_f]), "comercio": str(f[i_c] or ""),
                      "usuario": str(f[i_u] or ""), "tarjeta": str(f[i_t] or ""),
                      "monto": _num(f[i_m])} for f in filas]

    enc, filas = _filas(_hoja(libro, "Depositos"))
    i_f = _indice_columna(enc, "Fecha de operacion")
    i_c = _indice_columna(enc, "Concepto")
    i_m = _indice_columna(enc, "Monto")
    depositos = [{"fecha": _fecha(f[i_f]), "concepto": str(f[i_c] or ""),
                  "monto": _num(f[i_m])} for f in filas]

    enc, filas = _filas(_hoja(libro, "Estado de Cuenta"))
    i_id = _indice_columna(enc, "ID")
    i_i = _indice_columna(enc, "Fecha de inicio.")
    i_co = _indice_columna(enc, "Fecha de corte.")
    i_pa = _indice_columna(enc, "Fecha de pago.")
    i_si = _indice_columna(enc, "Saldo al inicio")
    i_sc = _indice_columna(enc, "Saldo al corte")
    ciclos = [{"id": str(f[i_id]), "inicio": _fecha(f[i_i]), "corte": _fecha(f[i_co]),
               "pago": _fecha(f[i_pa]), "saldo_inicio": _num(f[i_si]),
               "saldo_corte": _num(f[i_sc])} for f in filas]

    enc, filas = _filas(_hoja(libro, "Comisiones"))
    i_f = _indice_columna(enc, "Fecha de transaccion")
    i_im = _indice_columna(enc, "Importe")
    i_iv = _indice_columna(enc, "IVA")
    i_n = _indice_columna(enc, "Nombre de la comision")
    comisiones = [{"fecha": _fecha(f[i_f]), "nombre": str(f[i_n] or ""),
                   "importe": _num(f[i_im]), "iva": _num(f[i_iv])} for f in filas]

    return {"transacciones": transacciones, "depositos": depositos,
            "ciclos": ciclos, "comisiones": comisiones}


def cuadra(datos, tolerancia=0.02):
    """¿Cierra el saldo de cada ciclo? Devuelve (bool, diagnóstico por ciclo).

    Es el equivalente de `bbva.cuadra`: si no cierra, el archivo no se usa. La
    fórmula está verificada contra un export real; las transacciones cuentan por
    su fecha de aprobación y las comisiones con su IVA, porque así es como el
    estado de cuenta las suma.
    """
    diagnostico = {}
    ok = True
    for c in datos["ciclos"]:
        if not (c["inicio"] and c["corte"]):
            ok = False
            diagnostico[c["id"]] = {"diferencia": None,
                                    "nota": "el ciclo no trae fechas legibles"}
            continue
        a, b = c["inicio"], c["corte"]
        cargos = sum(t["monto"] for t in datos["transacciones"]
                     if t["fecha"] and a <= t["fecha"] <= b)
        cargos += sum(m["importe"] + m["iva"] for m in datos["comisiones"]
                      if m["fecha"] and a <= m["fecha"] <= b)
        pagos = sum(d["monto"] for d in datos["depositos"]
                    if d["fecha"] and a <= d["fecha"] <= b)
        calculado = c["saldo_inicio"] + cargos - pagos
        diferencia = round(calculado - c["saldo_corte"], 2)
        diagnostico[c["id"]] = {"calculado": round(calculado, 2),
                                "declarado": c["saldo_corte"],
                                "diferencia": diferencia}
        if abs(diferencia) > tolerancia:
            ok = False
    if not datos["ciclos"]:
        return False, {"nota": "el libro no trae ningun estado de cuenta"}
    return ok, diagnostico
```

- [ ] **Step 5: Correr la prueba para verla pasar**

Run: `python tests/test_uso_plataforma.py`
Expected: PASS — `Todas las pruebas pasaron.`

- [ ] **Step 6: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0, `Todo verde.`

- [ ] **Step 7: Commit**

```bash
git add uso_plataforma.py tests/test_uso_plataforma.py requirements.txt
git commit -m "El uso de la tarjeta se lee y se cuadra antes de creerle"
```

---

### Task 2: Derivación de los atrasos

Los tres datos que pesan más en la decisión —cuántos atrasos, por cuánto monto y de cuántos días— salen de cruzar los cortes contra los depósitos. El caso difícil no es el atraso: es el ciclo que **todavía no vence**, que no se puede evaluar y que si se cuenta como cumplido premia a quien no ha pagado.

**Files:**
- Modify: `uso_plataforma.py`
- Test: `tests/test_uso_plataforma.py`

**Interfaces:**
- Consumes: de la Tarea 1, `leer()` y las formas de `ciclo` y `deposito`.
- Produces:
  - `ultima_fecha(datos) -> date | None`
  - `ciclos_evaluados(datos) -> list[dict]` con, por ciclo: `id`, `corte`, `pago`, `exigible`, `acreditado`, `faltante`, `dias_atraso`, `proporcion_faltante`, `pendiente`, `abierto`
  - `atrasos(datos) -> dict` con `cuantos`, `peor_dias`, `monto_mayor`, `proporcion_mayor`, `ciclos_evaluables`

Reglas, en orden:

1. Los ciclos se ordenan por fecha de corte. Cada uno tiene por exigible su `saldo_corte`.
2. Un depósito se aplica primero a los cortes anteriores. Se lleva un acumulado `comprometido` con la suma de lo exigible de los ciclos ya procesados; lo que un ciclo tiene disponible es lo acreditado menos ese acumulado.
3. Si la fecha de pago del ciclo es posterior a la última fecha que trae el archivo, el ciclo está **pendiente**: no se evalúa y no cuenta como cumplido ni como atraso.
4. Si el disponible a la fecha de pago cubre lo exigible, `dias_atraso = 0`.
5. Si no, hay atraso. Los días son los que pasaron del vencimiento al depósito que lo cubrió. Si nunca se cubrió, `abierto = True` y los días se cuentan contra la última fecha del archivo, no contra hoy: el score de un archivo tiene que dar lo mismo hoy que en un mes.

- [ ] **Step 1: Escribir la prueba que falla**

Agregar a `tests/test_uso_plataforma.py`, antes del bloque final que imprime el resultado:

```python
# ── la derivacion del atraso ─────────────────────────────────────────────────
print()
print("Derivacion del atraso")


def d(dia, mes=7, ano=2026):
    return datetime.date(ano, mes, dia)


def caso(ciclos, depositos, transacciones=None):
    """Solo lo que la derivacion mira: ciclos y depositos."""
    return {"ciclos": ciclos, "depositos": depositos,
            "transacciones": transacciones or [], "comisiones": []}


def ciclo(id, corte, pago, exigible, inicio=None):
    return {"id": id, "inicio": inicio or corte, "corte": corte, "pago": pago,
            "saldo_inicio": 0.0, "saldo_corte": exigible}


def pago(fecha, monto):
    return {"fecha": fecha, "concepto": "pago", "monto": monto}


# pagado completo y antes del vencimiento
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)], [pago(d(9), 1000.0)]))
check(r["cuantos"] == 0 and r["peor_dias"] == 0,
      "pagado completo antes del vencimiento: cero atrasos")

# pagado el mismo dia del vencimiento: no es atraso
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)], [pago(d(10), 1000.0)]))
check(r["cuantos"] == 0, "pagar el mismo dia del vencimiento no es atraso")

# un dia tarde
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)], [pago(d(11), 1000.0)]))
check(r["cuantos"] == 1 and r["peor_dias"] == 1,
      "un dia tarde es un atraso de un dia")

# pagado en parcialidades que suman, la ultima el dia del vencimiento
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)],
                    [pago(d(3), 400.0), pago(d(7), 300.0), pago(d(10), 300.0)]))
check(r["cuantos"] == 0,
      "tres parcialidades que suman lo exigible al vencimiento no son atraso")

# faltante parcial, cubierto tarde
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)],
                    [pago(d(9), 900.0), pago(d(15), 100.0)]))
check(r["cuantos"] == 1 and r["peor_dias"] == 5, "el faltante parcial cuenta y son 5 dias")
check(r["monto_mayor"] == 100.0, "el monto del atraso es lo que falto, no lo exigible")
check(abs(r["proporcion_mayor"] - 0.10) < 1e-9,
      "la proporcion es el faltante entre lo exigible")

# nunca cubierto: se cuenta contra la ultima fecha del archivo, no contra hoy
r = up.atrasos(caso([ciclo("1", d(30, 6), d(10), 1000.0)],
                    [pago(d(9), 200.0)],
                    transacciones=[{"fecha": d(25), "comercio": "X", "usuario": "a",
                                    "tarjeta": "1", "monto": 5.0}]))
check(r["cuantos"] == 1 and r["peor_dias"] == 15,
      "un atraso abierto se mide contra la ultima fecha del archivo")
check(up.ciclos_evaluados(caso([ciclo("1", d(30, 6), d(10), 1000.0)],
                               [pago(d(9), 200.0)]))[0]["abierto"] is True,
      "y queda marcado como abierto")

# el ciclo que todavia no vence no se evalua
datos = caso([ciclo("1", d(30, 6), d(10), 1000.0),
              ciclo("2", d(31), d(10, 8), 2000.0)],
             [pago(d(9), 1000.0)])
r = up.atrasos(datos)
check(r["ciclos_evaluables"] == 1,
      "un ciclo cuyo vencimiento es posterior a los datos no se evalua")
check(r["cuantos"] == 0,
      "y no se cuenta como atraso: no hay con que saber si pago")
check(up.ciclos_evaluados(datos)[1]["pendiente"] is True, "queda marcado como pendiente")

# dos ciclos, el pago se aplica primero al mas viejo
datos = caso([ciclo("1", d(30, 6), d(10), 1000.0),
              ciclo("2", d(31), d(10, 8), 1000.0)],
             [pago(d(9), 1000.0), pago(d(9, 8), 1000.0),
              pago(d(20, 8), 1.0)])
r = up.atrasos(datos)
check(r["cuantos"] == 0,
      "el deposito se aplica al corte mas viejo primero: ningun ciclo queda corto")

# reincidencia
datos = caso([ciclo("1", d(30, 6), d(10), 1000.0),
              ciclo("2", d(31), d(10, 8), 1000.0)],
             [pago(d(12), 1000.0), pago(d(14, 8), 1000.0),
              pago(d(20, 8), 1.0)])
r = up.atrasos(datos)
check(r["cuantos"] == 2, "dos ciclos con atraso cuentan dos")
check(r["peor_dias"] == 4, "y el peor es el mas largo de los dos")

# sin ciclos evaluables no se inventa un dato favorable
r = up.atrasos(caso([], []))
check(r["peor_dias"] is None and r["cuantos"] == 0,
      "sin ciclos evaluables el peor atraso es None, no cero: la ausencia de un "
      "dato no es un dato favorable")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_uso_plataforma.py`
Expected: FAIL — `AttributeError: module 'uso_plataforma' has no attribute 'atrasos'`

- [ ] **Step 3: Escribir la derivación**

Agregar a `uso_plataforma.py`:

```python
def ultima_fecha(datos):
    """La fecha más reciente que trae el archivo, de cualquier pestaña.

    Sirve de 'hoy' para los atrasos abiertos. Se usa esta y no `date.today()` a
    propósito: el score de un archivo tiene que dar lo mismo hoy que en un mes,
    o dos corridas del mismo expediente se contradicen sin que nada haya cambiado.
    """
    fechas = [t["fecha"] for t in datos["transacciones"]]
    fechas += [d["fecha"] for d in datos["depositos"]]
    fechas += [m["fecha"] for m in datos["comisiones"]]
    fechas += [c["corte"] for c in datos["ciclos"]]
    limpias = [f for f in fechas if f is not None]
    return max(limpias) if limpias else None


def ciclos_evaluados(datos):
    """Cada ciclo con su atraso resuelto, en orden de corte.

    El pago se aplica primero a los cortes anteriores: `comprometido` lleva lo
    exigible de los ciclos ya procesados, así que un depósito no cubre dos veces.
    """
    ciclos = sorted([c for c in datos["ciclos"] if c["corte"] and c["pago"]],
                    key=lambda c: c["corte"])
    depositos = sorted([d for d in datos["depositos"] if d["fecha"]],
                       key=lambda d: d["fecha"])
    corte_datos = ultima_fecha(datos)

    salida = []
    comprometido = 0.0
    for c in ciclos:
        exigible = c["saldo_corte"]
        fila = {"id": c["id"], "corte": c["corte"], "pago": c["pago"],
                "exigible": exigible, "pendiente": False, "abierto": False,
                "acreditado": None, "faltante": 0.0, "dias_atraso": None,
                "proporcion_faltante": None}

        # El ciclo que todavia no vence no se puede juzgar. Contarlo como
        # cumplido premiaria a quien no ha tenido que pagar.
        if corte_datos is not None and c["pago"] > corte_datos:
            fila["pendiente"] = True
            salida.append(fila)
            comprometido += exigible
            continue

        acreditado = sum(x["monto"] for x in depositos
                         if x["fecha"] <= c["pago"]) - comprometido
        fila["acreditado"] = round(acreditado, 2)
        faltante = round(exigible - acreditado, 2)

        if faltante <= 0.005:
            fila["dias_atraso"] = 0
        else:
            fila["faltante"] = faltante
            fila["proporcion_faltante"] = (faltante / exigible) if exigible else None
            corrido = 0.0
            cubierto = None
            for x in depositos:
                corrido += x["monto"]
                if corrido - comprometido >= exigible - 0.005:
                    cubierto = x["fecha"]
                    break
            if cubierto is not None:
                fila["dias_atraso"] = (cubierto - c["pago"]).days
            else:
                fila["abierto"] = True
                fila["dias_atraso"] = ((corte_datos - c["pago"]).days
                                       if corte_datos else None)

        salida.append(fila)
        comprometido += exigible
    return salida


def atrasos(datos):
    """Resumen de atrasos: cuántos, el peor en días, y el mayor en monto."""
    filas = [f for f in ciclos_evaluados(datos) if not f["pendiente"]]
    con_atraso = [f for f in filas if f["dias_atraso"]]

    dias = [f["dias_atraso"] for f in con_atraso if f["dias_atraso"] is not None]
    montos = [f["faltante"] for f in con_atraso]
    props = [f["proporcion_faltante"] for f in con_atraso
             if f["proporcion_faltante"] is not None]

    # Sin ciclos evaluables `peor_dias` queda en None y la variable se cae del
    # modelo. Poner 0 diria 'nunca se atraso', que no es lo que sabemos.
    if not filas:
        peor = None
    else:
        peor = max(dias) if dias else 0

    return {"cuantos": len(con_atraso),
            "peor_dias": peor,
            "monto_mayor": max(montos) if montos else 0.0,
            "proporcion_mayor": max(props) if props else None,
            "ciclos_evaluables": len(filas)}
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_uso_plataforma.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 6: Commit**

```bash
git add uso_plataforma.py tests/test_uso_plataforma.py
git commit -m "Los atrasos se derivan de los cortes, no se capturan"
```

---

### Task 3: Clasificación de comercios y resumen del uso

El resumen es lo que se guarda en el expediente y lo que lee el modelo. La clasificación de comercios sigue el principio que `giros.py` ya dejó escrito: se **sugiere** por palabra clave y el operador confirma, porque una coincidencia de texto no sustituye un juicio de negocio. Lo que no se pudo clasificar se reporta, no se puntúa.

**Files:**
- Modify: `uso_plataforma.py`
- Test: `tests/test_uso_plataforma.py`

**Interfaces:**
- Consumes: de las Tareas 1–2, `leer()`, `atrasos()`, `ciclos_evaluados()`, `ultima_fecha()`.
- Produces:
  - `CATEGORIAS: dict[str, tuple[str, ...]]` — categoría → palabras clave
  - `clasificar_comercio(nombre) -> str` (una categoría, o `"sin_clasificar"`)
  - `clasificar_comercios(transacciones) -> dict[str, dict]` — categoría → `{"monto", "numero", "comercios"}`
  - `resumir(datos, linea_vigente=None, archivo=None, ronda_aumento=None, categorias_esperadas=None) -> dict` — el bloque `uso_plataforma` del expediente, serializable a JSON (fechas en ISO)

- [ ] **Step 1: Escribir la prueba que falla**

Agregar a `tests/test_uso_plataforma.py`, antes del bloque final:

```python
# ── clasificacion de comercios ───────────────────────────────────────────────
print()
print("Clasificacion de comercios")
check(up.clasificar_comercio("OXXO GAS ZINACANTEPEC") == "combustible",
      "una gasolinera se clasifica como combustible")
check(up.clasificar_comercio("SUPER SERVICIO RUDEM") == "combustible",
      "'servicio' con 'super' tambien es gasolinera en Mexico")
check(up.clasificar_comercio("WWW.EASYTRIP.COM.MX") == "casetas",
      "EasyTrip es peaje")
check(up.clasificar_comercio("Retiro de Efectivo") == "efectivo",
      "el retiro de efectivo es su propia categoria")
check(up.clasificar_comercio("ZZZ COMERCIO RARISIMO") == "sin_clasificar",
      "lo que no coincide queda sin clasificar, no en una categoria de relleno")

g = up.clasificar_comercios([
    {"fecha": d(1), "comercio": "OXXO GAS SUR", "usuario": "a", "tarjeta": "1",
     "monto": 1000.0},
    {"fecha": d(2), "comercio": "WWW.EASYTRIP.COM.MX", "usuario": "a",
     "tarjeta": "1", "monto": 500.0},
    {"fecha": d(3), "comercio": "ZZZ RARO", "usuario": "a", "tarjeta": "1",
     "monto": 250.0},
])
check(g["combustible"]["monto"] == 1000.0, "el monto se agrupa por categoria")
check(g["sin_clasificar"]["monto"] == 250.0, "y lo no clasificado queda visible")
check("ZZZ RARO" in g["sin_clasificar"]["comercios"],
      "con el nombre del comercio, para poder clasificarlo a mano despues")

# ── el resumen que se guarda en el expediente ────────────────────────────────
print()
print("Resumen para el expediente")
datos = {
    "ciclos": [ciclo("1", d(30, 6), d(10), 1000.0, inicio=d(1, 6))],
    "depositos": [pago(d(9), 1000.0)],
    "transacciones": [
        {"fecha": d(5, 6), "comercio": "OXXO GAS SUR", "usuario": "a@x.com",
         "tarjeta": "1111", "monto": 600.0},
        {"fecha": d(6, 6), "comercio": "WWW.EASYTRIP.COM.MX", "usuario": "b@x.com",
         "tarjeta": "2222", "monto": 300.0},
    ],
    "comisiones": [{"fecha": d(1, 6), "nombre": "Comision por financiamiento",
                    "importe": 100.0, "iva": 16.0}],
}
r = up.resumir(datos, linea_vigente=2000.0, archivo="uso.xlsx", ronda_aumento=0)
check(r["gasto_total"] == 900.0, "el gasto total es la suma de las transacciones")
check(r["usuarios"] == 2 and r["tarjetas"] == 2, "cuenta usuarios y tarjetas distintos")
check(r["comercios"] == 2, "y comercios distintos")
check(r["atrasos"]["cuantos"] == 0, "trae el resumen de atrasos")
check(r["ronda_aumento"] == 0 and r["archivo"] == "uso.xlsx",
      "y de que ronda y archivo salio")
check(r["comisiones_por_tipo"]["Comision por financiamiento"]["monto"] == 100.0,
      "las comisiones se agrupan por su nombre, para poder verificar la mensualidad")
check(isinstance(r["periodo"]["desde"], str) and "-" in r["periodo"]["desde"],
      "las fechas salen como texto ISO: el expediente se guarda como JSON")
import json
json.dumps(r)
check(True, "el resumen completo es serializable a JSON")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_uso_plataforma.py`
Expected: FAIL — `AttributeError: module 'uso_plataforma' has no attribute 'clasificar_comercio'`

- [ ] **Step 3: Escribir la clasificación y el resumen**

Agregar a `uso_plataforma.py`:

```python
# Categorías de comercio por palabra clave. Igual que en `giros.py`, esto
# **sugiere**: el operador confirma cuáles son las esperadas para el cliente. Lo
# que no coincide queda en `sin_clasificar` y se reporta con nombre, para poder
# clasificarlo a mano; nunca cae en una categoría de relleno que lo haría
# invisible.
#
# El efectivo va aparte y nunca es una categoría esperada: en una tarjeta de
# flotilla el retiro de efectivo no es gasto controlado, y esa es justamente la
# señal que se quiere ver.
CATEGORIAS = {
    "efectivo": ("retiro de efectivo", "cajero", "atm", "disposicion de efectivo"),
    "combustible": ("gas", "gasolin", "servicio", "pemex", "shell", "mobil",
                    "combustible", "diesel", "oxxo gas", "rendichicas"),
    "casetas": ("easytrip", "caseta", "peaje", "televia", "iave", "capufe",
                "autopista"),
    "refacciones": ("refaccion", "llanta", "autozone", "rueda", "taller",
                    "lubricante", "aceite"),
    "logistica": ("hubsite", "flete", "paqueter", "transporte", "aduana"),
    "alimentos": ("restaurant", "cafe", "super", "walmart", "soriana", "food"),
    "financiero": ("bancomer", "banco", "banamex", "hsbc", "santander",
                   "banorte", "bbva"),
}


def clasificar_comercio(nombre):
    """La categoría sugerida para un comercio, o 'sin_clasificar'.

    El orden importa: 'efectivo' se evalúa primero porque un retiro en un cajero
    de gasolinera es efectivo, no combustible. Y 'casetas' antes que
    'combustible' porque varias casetas traen la palabra 'servicio'.
    """
    t = _sin_acentos(nombre)
    for categoria in ("efectivo", "casetas", "refacciones", "logistica",
                      "combustible", "financiero", "alimentos"):
        if any(p in t for p in CATEGORIAS[categoria]):
            return categoria
    return "sin_clasificar"


def clasificar_comercios(transacciones):
    """Gasto agrupado por categoría, con los nombres de los comercios."""
    grupos = {}
    for t in transacciones:
        cat = clasificar_comercio(t["comercio"])
        g = grupos.setdefault(cat, {"monto": 0.0, "numero": 0, "comercios": []})
        g["monto"] = round(g["monto"] + t["monto"], 2)
        g["numero"] += 1
        if t["comercio"] not in g["comercios"]:
            g["comercios"].append(t["comercio"])
    return grupos


def _iso(f):
    return f.isoformat() if f is not None else None


def resumir(datos, linea_vigente=None, archivo=None, ronda_aumento=None,
            categorias_esperadas=None):
    """El bloque `uso_plataforma` del expediente. Serializable a JSON.

    Se guarda en vez de recalcularse en cada comando: así queda constancia de con
    qué datos se calculó el score, que es la misma razón por la que el modelo
    guarda su VERSION.
    """
    tx = datos["transacciones"]
    total = round(sum(t["monto"] for t in tx), 2)

    por_mes = {}
    for t in tx:
        if t["fecha"]:
            k = t["fecha"].strftime("%Y-%m")
            por_mes[k] = round(por_mes.get(k, 0.0) + t["monto"], 2)

    por_comercio = {}
    for t in tx:
        por_comercio[t["comercio"]] = por_comercio.get(t["comercio"], 0.0) + t["monto"]
    mayor = max(por_comercio.values()) if por_comercio else None

    comisiones = {}
    for m in datos["comisiones"]:
        g = comisiones.setdefault(m["nombre"], {"monto": 0.0, "iva": 0.0,
                                                "numero": 0, "fechas": []})
        g["monto"] = round(g["monto"] + m["importe"], 2)
        g["iva"] = round(g["iva"] + m["iva"], 2)
        g["numero"] += 1
        g["fechas"].append(_iso(m["fecha"]))

    fechas = [t["fecha"] for t in tx if t["fecha"]]
    # El gasto mensual promedio ignora los meses parciales de las puntas: un mes
    # a medias no es un mes de gasto y promediarlo con los completos subestima
    # la utilizacion.
    meses_completos = [v for k, v in sorted(por_mes.items())][1:-1] or list(por_mes.values())
    promedio_mes = (round(sum(meses_completos) / len(meses_completos), 2)
                    if meses_completos else None)

    return {
        "ronda_aumento": ronda_aumento,
        "archivo": archivo,
        "fecha_lectura": _iso(ultima_fecha(datos)),
        "periodo": {"desde": _iso(min(fechas) if fechas else None),
                    "hasta": _iso(max(fechas) if fechas else None)},
        "gasto_total": total,
        "gasto_por_mes": por_mes,
        "gasto_mensual_promedio": promedio_mes,
        "usuarios": len({t["usuario"] for t in tx if t["usuario"]}),
        "tarjetas": len({t["tarjeta"] for t in tx if t["tarjeta"]}),
        "comercios": len(por_comercio),
        "concentracion_mayor": (round(mayor / total, 4) if mayor and total else None),
        "categorias": clasificar_comercios(tx),
        "categorias_esperadas": categorias_esperadas,
        "comisiones_por_tipo": comisiones,
        "linea_vigente": linea_vigente,
        "ciclos": [dict(f, corte=_iso(f["corte"]), pago=_iso(f["pago"]))
                   for f in ciclos_evaluados(datos)],
        "atrasos": atrasos(datos),
    }
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_uso_plataforma.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 6: Commit**

```bash
git add uso_plataforma.py tests/test_uso_plataforma.py
git commit -m "El uso se resume en lo que el expediente guarda"
```

---

### Task 4: El esquema — historial de aumentos y bloque de uso

**Files:**
- Modify: `schema_expediente.py`
- Test: `tests/test_compuertas_aumento.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `UMBRAL_AUMENTO_MAYOR = 150000.0`, `ESTADOS_CUENTA_AUMENTO = 3`
  - En `expediente_vacio()`: `"historial_aumentos": []` y `"uso_plataforma": None`
  - `aumento_vacio() -> dict`
  - `ronda_abierta(exp) -> (int | None, dict | None)`
  - `incremento(ronda) -> float | None`
  - `requiere_estados_cuenta(ronda) -> bool`

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_compuertas_aumento.py`:

```python
# -*- coding: utf-8 -*-
"""
Pruebas del esquema y las compuertas del aumento de linea.

Un aumento no genera contrato, asi que las nueve compuertas de generacion no
aplican. Lo que se prueba aqui es lo que si decide:

- que la ronda abierta se encuentre y no se confunda con las ya cerradas;
- que los estados de cuenta bancarios se pidan SOLO cuando el incremento pasa el
  umbral o cuando alguien registro la excepcion con su nombre, porque el default
  del negocio es no volver a pedirlos;
- que la compuerta de cierre no deje cerrar sin la evidencia de quien autorizo;
- y que `compuertas_generacion` siga dando exactamente lo mismo que antes, que es
  la garantia de que la ruta de originacion no se movio.

Todos los datos son inventados.

Se corre con:
    python tests/test_compuertas_aumento.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schema_expediente as se

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── el esquema ───────────────────────────────────────────────────────────────
print("Estructura del expediente")
exp = se.expediente_vacio()
check(exp["historial_aumentos"] == [], "nace con el historial de aumentos vacio")
check(exp["uso_plataforma"] is None, "y sin bloque de uso de plataforma")

a = se.aumento_vacio()
for campo in ("fecha_solicitud", "linea_previa", "monto_solicitado",
              "estados_cuenta_excepcion", "riesgo", "monto_aprobado",
              "fecha_decision", "autorizado_por", "estado"):
    check(campo in a, "la ronda trae el campo %s" % campo)
check(a["estado"] == "abierta", "una ronda nueva nace abierta")

# ── la ronda abierta ─────────────────────────────────────────────────────────
print()
print("Encontrar la ronda abierta")
i, r = se.ronda_abierta(exp)
check(i is None and r is None, "sin rondas no hay ronda abierta")

exp["historial_aumentos"] = [
    dict(se.aumento_vacio(), estado="cerrada", monto_solicitado=100000.0),
    dict(se.aumento_vacio(), estado="abierta", monto_solicitado=120000.0),
]
i, r = se.ronda_abierta(exp)
check(i == 1 and r["monto_solicitado"] == 120000.0,
      "encuentra la abierta y no la cerrada")

exp["historial_aumentos"][1]["estado"] = "cerrada"
i, r = se.ronda_abierta(exp)
check(i is None, "si todas estan cerradas no hay ronda abierta")

# ── cuando se piden estados de cuenta ────────────────────────────────────────
print()
print("Los estados de cuenta se piden por excepcion, no por regla")
r = dict(se.aumento_vacio(), linea_previa=100000.0, monto_solicitado=200000.0)
check(se.incremento(r) == 100000.0, "el incremento es lo solicitado menos lo vigente")
check(se.requiere_estados_cuenta(r) is False,
      "un incremento de 100 mil NO exige estados de cuenta: el default es no pedirlos")

r = dict(se.aumento_vacio(), linea_previa=100000.0, monto_solicitado=260000.0)
check(se.requiere_estados_cuenta(r) is True,
      "un incremento de 160 mil si los exige, por pasar el umbral de 150 mil")

r = dict(se.aumento_vacio(), linea_previa=100000.0, monto_solicitado=250000.0)
check(se.requiere_estados_cuenta(r) is False,
      "exactamente 150 mil no pasa el umbral: la regla dice 'mayor a'")

r = dict(se.aumento_vacio(), linea_previa=100000.0, monto_solicitado=120000.0,
         estados_cuenta_excepcion={"motivo": "concentracion de un solo pagador",
                                   "decidida_por": "Quien Decide",
                                   "fecha": "2026-08-19"})
check(se.requiere_estados_cuenta(r) is True,
      "la excepcion registrada los exige aunque el incremento sea chico")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_compuertas_aumento.py`
Expected: FAIL — `KeyError: 'historial_aumentos'`

- [ ] **Step 3: Modificar el esquema**

En `schema_expediente.py`, junto a los umbrales que ya están arriba del archivo:

```python
# Un aumento no vuelve a pedir estados de cuenta bancarios. La excepcion es que
# el incremento sea grande, o que alguien decida pedirlos por el caso concreto
# —y entonces queda su nombre, igual que en una observacion aceptada—.
UMBRAL_AUMENTO_MAYOR = 150000.0
ESTADOS_CUENTA_AUMENTO = 3
```

En `expediente_vacio()`, después del bloque `"credito"`:

```python
        # Una entrada por ronda de aumento. `credito.autorizada.linea` sigue
        # siendo la linea vigente; aqui queda como se llego a ella. Sin este
        # historial, la pregunta "cuando paso de 50 a 120 mil y con que
        # evidencia" no tiene respuesta en un ano.
        "historial_aumentos": [],
        # Lo que sale de leer el Excel de uso de la tarjeta. Se guarda en vez de
        # recalcularse para que quede constancia de con que datos se califico.
        "uso_plataforma": None,
```

Y en el comentario del arreglo `documentos`, documentar el campo nuevo — es la fuente única de verdad y un campo que no está aquí no existe:

```python
        "documentos": [],                  # {tipo, file_id, fecha_emision, vigente_hasta,
                                           #  legible, superado_por, inscrito,
                                           #  ronda_aumento}
                                           # `ronda_aumento` es el indice en
                                           # historial_aumentos, o None para los
                                           # documentos de la apertura original.
                                           # Los papeles de cada ronda viven aqui
                                           # y no duplicados en la ronda: las
                                           # reglas de vigencia ya son de este
                                           # arreglo.
```

Y al final del archivo:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Aumentos de linea
# ─────────────────────────────────────────────────────────────────────────────
def aumento_vacio():
    """Una ronda de aumento, con todo en None."""
    return {
        "fecha_solicitud": None,
        "linea_previa": None,           # la vigente antes de esta ronda
        "monto_solicitado": None,
        "estados_cuenta_excepcion": None,   # {motivo, decidida_por, fecha}
        "riesgo": {"score": None, "version": None, "fecha_evaluacion": None},
        "monto_aprobado": None,
        "fecha_decision": None,
        "autorizado_por": None,
        "estado": "abierta",            # abierta | cerrada
    }


def ronda_abierta(exp):
    """(indice, ronda) de la unica ronda abierta, o (None, None).

    Se busca de atras hacia adelante: si por un error quedaran dos abiertas, la
    reciente es la que se esta trabajando.
    """
    rondas = _get(exp, "historial_aumentos", [])
    for i in range(len(rondas) - 1, -1, -1):
        if rondas[i].get("estado") == "abierta":
            return i, rondas[i]
    return None, None


def incremento(ronda):
    """Lo solicitado menos la linea vigente. None si falta alguno de los dos."""
    sol, prev = ronda.get("monto_solicitado"), ronda.get("linea_previa")
    if sol is None or prev is None:
        return None
    return float(sol) - float(prev)


def requiere_estados_cuenta(ronda):
    """¿Esta ronda exige estados de cuenta bancarios?

    El default del negocio es NO volver a pedirlos. Solo dos cosas los piden:
    que el incremento pase el umbral, o que alguien haya registrado la excepcion
    —con su nombre, porque es una decision, no una condicion del sistema—.
    """
    if ronda.get("estados_cuenta_excepcion"):
        return True
    inc = incremento(ronda)
    return inc is not None and inc > UMBRAL_AUMENTO_MAYOR
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_compuertas_aumento.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0 — importa especialmente que `test_validador.py` siga verde, porque lee el expediente completo.

- [ ] **Step 6: Commit**

```bash
git add schema_expediente.py tests/test_compuertas_aumento.py
git commit -m "El expediente recuerda como llego a su linea"
```

---

### Task 5: Las dos compuertas del aumento

`schema_expediente.py` no importa nada más que `datetime`, y Syntage no vive en el expediente: `syntage.guardar_crudo()` deja los recursos en su propia tabla, por folio. Por eso la fecha de la extracción **se pasa como parámetro** en vez de consultarla aquí.

**Files:**
- Modify: `schema_expediente.py`
- Test: `tests/test_compuertas_aumento.py`

**Interfaces:**
- Consumes: de la Tarea 4, `ronda_abierta()`, `requiere_estados_cuenta()`, `ESTADOS_CUENTA_AUMENTO`.
- Produces:
  - `compuertas_riesgo_aumento(exp, fecha_syntage=None) -> list[str]`
  - `compuertas_cierre_aumento(exp) -> list[str]`

- [ ] **Step 1: Escribir la prueba que falla**

Agregar a `tests/test_compuertas_aumento.py`, antes del bloque final:

```python
# ── la compuerta de riesgo ───────────────────────────────────────────────────
print()
print("Compuerta de riesgo del aumento")


def exp_con_ronda(**cambios):
    """Expediente con una ronda abierta y todo lo que la compuerta pide."""
    e = se.expediente_vacio()
    e["folio"] = "PRUE-01"
    e["tipo_cliente"] = "persona_moral"
    e["credito"]["autorizada"]["linea"] = 100000.0
    ronda = dict(se.aumento_vacio(), fecha_solicitud="2026-08-01",
                 linea_previa=100000.0, monto_solicitado=120000.0)
    ronda.update(cambios.pop("ronda", {}))
    e["historial_aumentos"] = [ronda]
    e["documentos"] = [{"tipo": "buro", "fecha_emision": "2026-08-05"}]
    e["uso_plataforma"] = {"ronda_aumento": 0, "atrasos": {"cuantos": 0}}
    for k, v in cambios.items():
        e[k] = v
    return e


e = exp_con_ronda()
fallas_c = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(fallas_c == [],
      "con Syntage, buro y uso al dia, y sin exigir banco, la compuerta abre")

check(se.compuertas_riesgo_aumento(se.expediente_vacio()) != [],
      "sin ronda abierta la compuerta no abre")

f = se.compuertas_riesgo_aumento(exp_con_ronda(), fecha_syntage=None)
check(any("syntage" in x.lower() for x in f), "sin extraccion de Syntage no abre")

f = se.compuertas_riesgo_aumento(exp_con_ronda(), fecha_syntage="2026-07-01")
check(any("syntage" in x.lower() for x in f),
      "una extraccion anterior a la solicitud no sirve: el aumento se juzga con "
      "datos frescos")

e = exp_con_ronda()
e["documentos"] = [{"tipo": "buro", "fecha_emision": "2026-07-01"}]
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(any("buro" in x.lower() for x in f), "un buro anterior a la solicitud no sirve")

e = exp_con_ronda()
e["documentos"] = []
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(any("buro" in x.lower() for x in f), "sin buro no abre: se actualiza en cada aumento")

e = exp_con_ronda()
e["uso_plataforma"] = None
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(any("uso" in x.lower() for x in f), "sin el uso de la plataforma capturado no abre")

e = exp_con_ronda()
e["uso_plataforma"] = {"ronda_aumento": 0, "atrasos": {}}
e["historial_aumentos"].append(dict(se.aumento_vacio(), fecha_solicitud="2026-09-01",
                                    linea_previa=120000.0, monto_solicitado=150000.0))
e["historial_aumentos"][0]["estado"] = "cerrada"
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-09-02")
check(any("uso" in x.lower() for x in f),
      "un uso leido para la ronda anterior no sirve para la nueva")

# los estados de cuenta, solo cuando aplican
e = exp_con_ronda(ronda={"monto_solicitado": 300000.0})
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(any("estado" in x.lower() and "cuenta" in x.lower() for x in f),
      "un incremento de 200 mil si exige estados de cuenta y no estan")

e = exp_con_ronda(ronda={"monto_solicitado": 300000.0})
e["cuentas_bancarias"] = [{"titular_es_cliente": True,
                           "periodos": [{}, {}, {}]}]
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(f == [], "con los tres estados de cuenta, abre")

e = exp_con_ronda(ronda={"monto_solicitado": 300000.0})
e["cuentas_bancarias"] = [{"titular_es_cliente": True, "periodos": [{}, {}]}]
f = se.compuertas_riesgo_aumento(e, fecha_syntage="2026-08-04")
check(any("estado" in x.lower() for x in f), "con dos no alcanza: son tres")

# ── la compuerta de cierre ───────────────────────────────────────────────────
print()
print("Compuerta de cierre del aumento")


def exp_para_cerrar(**cambios):
    e = exp_con_ronda()
    r = e["historial_aumentos"][0]
    r["monto_aprobado"] = 120000.0
    r["autorizado_por"] = "Quien Autoriza"
    r.update(cambios)
    e["documentos"] += [
        {"tipo": "cotizacion", "ronda_aumento": 0, "fecha_emision": "2026-08-01"},
        {"tipo": "autorizacion_aumento", "ronda_aumento": 0,
         "fecha_emision": "2026-08-15"},
    ]
    return e


check(se.compuertas_cierre_aumento(exp_para_cerrar()) == [],
      "aprobado por el monto solicitado, con cotizacion y evidencia: cierra")

e = exp_para_cerrar()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "autorizacion_aumento"]
f = se.compuertas_cierre_aumento(e)
check(any("autorizacion" in x.lower() for x in f),
      "sin la evidencia de la autorizacion no cierra")

e = exp_para_cerrar()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "cotizacion"]
f = se.compuertas_cierre_aumento(e)
check(any("cotizacion" in x.lower() for x in f), "sin cotizacion no cierra")

e = exp_para_cerrar(autorizado_por=None)
f = se.compuertas_cierre_aumento(e)
check(any("autoriz" in x.lower() for x in f),
      "sin el nombre de quien autorizo no cierra: la evidencia sin nombre no dice quien")

# aprobado por menos: exige cotizacion nueva
e = exp_para_cerrar(monto_aprobado=90000.0)
f = se.compuertas_cierre_aumento(e)
check(any("menor" in x.lower() or "aprobad" in x.lower() for x in f),
      "aprobado por menos de lo solicitado exige la cotizacion del monto aprobado")

e = exp_para_cerrar(monto_aprobado=90000.0)
e["documentos"].append({"tipo": "cotizacion_aprobada", "ronda_aumento": 0,
                        "fecha_emision": "2026-08-16"})
check(se.compuertas_cierre_aumento(e) == [],
      "con la cotizacion del monto aprobado, cierra")

# ── regresion: la ruta de originacion no se movio ────────────────────────────
print()
print("Regresion de la ruta de originacion")
vacio = se.expediente_vacio()
antes = se.compuertas_generacion(vacio)
check(len(antes) > 0, "un expediente vacio sigue sin poder generar")
check(any("linea autorizada" in x.lower() for x in antes),
      "y sigue diciendo que falta la linea autorizada")
check(se.documentos_aplicables(dict(vacio, tipo_cliente="persona_moral"))
      == ["contrato", "pld_pm", "anexo_razonado"],
      "la matriz de documentos de una persona moral no cambio")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_compuertas_aumento.py`
Expected: FAIL — `AttributeError: module 'schema_expediente' has no attribute 'compuertas_riesgo_aumento'`

- [ ] **Step 3: Escribir las compuertas**

Agregar a `schema_expediente.py`, después de `requiere_estados_cuenta`:

```python
def _documentos_de_ronda(exp, indice, tipo):
    return [d for d in _get(exp, "documentos", [])
            if d.get("tipo") == tipo and d.get("ronda_aumento") == indice]


def compuertas_riesgo_aumento(exp, fecha_syntage=None):
    """Lo que falta antes de correr el modelo sobre una ronda de aumento.

    Devuelve lista de strings; vacia significa que se puede correr.

    `fecha_syntage` entra como parametro porque Syntage no es un documento del
    expediente: `syntage.guardar_crudo()` deja los recursos en su propia tabla,
    por folio. Consultarla desde aqui obligaria a este archivo a importar la base
    de datos, y es la fuente unica de verdad: se mantiene sin dependencias.
    """
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        return ["No hay ronda de aumento abierta."]

    fallas = []
    solicitud = ronda.get("fecha_solicitud")

    if ronda.get("monto_solicitado") is None:
        fallas.append("La ronda no tiene monto solicitado.")
    if ronda.get("linea_previa") is None:
        fallas.append("La ronda no tiene linea previa. Sin ella no se puede saber "
                      "de cuanto es el incremento ni calcular la utilizacion.")

    # ── Syntage ─────────────────────────────────────────────────────────────
    if not fecha_syntage:
        fallas.append("Sin extraccion de Syntage. Se actualiza en cada aumento.")
    elif solicitud and str(fecha_syntage) < str(solicitud):
        fallas.append("La extraccion de Syntage es del %s, anterior a la solicitud "
                      "del %s. El aumento se juzga con datos frescos."
                      % (fecha_syntage, solicitud))

    # ── buro ────────────────────────────────────────────────────────────────
    buros = [d for d in _get(exp, "documentos", []) if d.get("tipo") == "buro"]
    reciente = max((d.get("fecha_emision") or "" for d in buros), default="")
    if not buros:
        fallas.append("Sin reporte de buro. Se genera para cada aumento.")
    elif solicitud and reciente < str(solicitud):
        fallas.append("El buro mas reciente es del %s, anterior a la solicitud del "
                      "%s. Se actualiza en cada aumento." % (reciente or "?", solicitud))

    # ── uso de la plataforma ────────────────────────────────────────────────
    uso = _get(exp, "uso_plataforma")
    if not uso:
        fallas.append("Sin el uso de la tarjeta capturado. Corre: nea.py uso <folio> "
                      "<excel>")
    elif uso.get("ronda_aumento") != indice:
        fallas.append("El uso capturado corresponde a la ronda %s, no a la actual. "
                      "Se vuelve a leer para cada aumento."
                      % uso.get("ronda_aumento"))

    # ── estados de cuenta, solo por excepcion ───────────────────────────────
    if requiere_estados_cuenta(ronda):
        cuentas = _get(exp, "cuentas_bancarias", [])
        principal = next((c for c in cuentas if c.get("titular_es_cliente")), None)
        n = len(principal.get("periodos", [])) if principal else 0
        if n < ESTADOS_CUENTA_AUMENTO:
            inc = incremento(ronda)
            por = ("la excepcion registrada" if ronda.get("estados_cuenta_excepcion")
                   else "un incremento de $%s" % format(float(inc or 0), ",.2f"))
            fallas.append("Por %s se requieren %d estados de cuenta; hay %d."
                          % (por, ESTADOS_CUENTA_AUMENTO, n))

    return fallas


def compuertas_cierre_aumento(exp):
    """Lo que falta para cerrar una ronda ya decidida.

    Devuelve lista de strings; vacia significa que se puede cerrar.
    """
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        return ["No hay ronda de aumento abierta."]

    fallas = []
    aprobado = ronda.get("monto_aprobado")
    solicitado = ronda.get("monto_solicitado")

    if aprobado is None:
        fallas.append("La ronda no tiene monto aprobado.")
    # Una evidencia sin nombre no dice quien respondio por la decision, que es
    # justo lo que este registro existe para contestar en un ano.
    if not ronda.get("autorizado_por"):
        fallas.append("Sin el nombre de quien autorizo el aumento.")

    if not _documentos_de_ronda(exp, indice, "cotizacion"):
        fallas.append("Sin la cotizacion de la solicitud en esta ronda.")
    if not _documentos_de_ronda(exp, indice, "autorizacion_aumento"):
        fallas.append("Sin la evidencia de la autorizacion (captura del correo o "
                      "del WhatsApp) en esta ronda.")

    if (aprobado is not None and solicitado is not None
            and float(aprobado) < float(solicitado)
            and not _documentos_de_ronda(exp, indice, "cotizacion_aprobada")):
        fallas.append("Se aprobo $%s, menor a los $%s solicitados: falta la "
                      "cotizacion nueva por el monto aprobado."
                      % (format(float(aprobado), ",.2f"),
                         format(float(solicitado), ",.2f")))

    return fallas
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_compuertas_aumento.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 6: Commit**

```bash
git add schema_expediente.py tests/test_compuertas_aumento.py
git commit -m "Las compuertas del aumento piden lo del aumento, no lo del contrato"
```

---

### Task 6: El módulo de riesgo del uso de plataforma

Un módulo del modelo es una función que devuelve `{nombre_variable: (peso, puntaje)}`. `_ponderar()` renormaliza sobre las variables que tienen dato, así que una variable sin dato se cae sola — el principio del archivo: la ausencia de un dato no es un dato desfavorable.

**Files:**
- Modify: `modelo_riesgo.py`
- Test: `tests/test_modelo_aumento.py`

**Interfaces:**
- Consumes: de `modelo_riesgo.py`, `_escalon()`, `_div()`. De la Tarea 3, la forma del bloque `uso_plataforma`.
- Produces:
  - `PESOS_USO: dict[str, float]`
  - `_uso_plataforma(uso) -> dict[str, tuple[float, float | None]]` con las variables `atrasos`, `alineacion_giro`, `usuarios_activos`, `utilizacion_promedio`

**Política de crédito de esta tarea** (los números son de negocio, no técnicos):

| Variable | Peso | Escala |
|---|---|---|
| `atrasos` | 0.45 | 0 días → 1.00 · 1–2 → 0.85 · 3–7 → 0.60 · 8–29 → 0.35 · 30+ → 0.10 |
| `alineacion_giro` | 0.25 | proporción del gasto en categorías esperadas: ≥0.90 → 1.00 · >0.75 → 0.75 · >0.50 → 0.50 · >0.25 → 0.25 · resto → 0.00 |
| `usuarios_activos` | 0.15 | ≥5 → 1.00 · ≥3 → 0.75 · 2 → 0.50 · 1 → 0.25 |
| `utilizacion_promedio` | 0.15 | ≥0.80 → 1.00 · ≥0.60 → 0.85 · ≥0.40 → 0.70 · ≥0.20 → 0.50 · resto → 0.25 |

Ajustes sobre `atrasos`, **solo si hubo al menos un atraso**: −0.10 por cada ciclo con atraso además del primero; +0.10 si la proporción no cubierta fue menor a 5%, −0.10 si fue mayor a 50%. Piso 0.10, techo 0.95.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_modelo_aumento.py`:

```python
# -*- coding: utf-8 -*-
"""
Pruebas del modelo de riesgo de un aumento de linea.

Un aumento se juzga con algo que un cliente nuevo no tiene: como uso la tarjeta.
Lo que se prueba es donde esta el juicio de negocio:

- que la escala de atrasos distinga el error operativo de patear el pago, porque
  uno o dos dias suele ser un descuadre y treinta es otra cosa;
- que un atraso nunca puntue igual que ningun atraso, por mas pequeno que fuera;
- que la ausencia de un dato NO cuente como dato desfavorable, que es el
  principio del archivo;
- que al faltar el modulo de estados de cuenta —el caso normal, porque no se
  piden— los otros cuatro se renormalicen solos;
- y que `evaluar()` siga dando exactamente lo mismo que antes.

Todos los datos son inventados.

Se corre con:
    python tests/test_modelo_aumento.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import modelo_riesgo as mr

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def uso(peor_dias=0, cuantos=0, proporcion=None, usuarios=4, evaluables=3,
        esperadas=("combustible", "casetas"), categorias=None, promedio=8000.0,
        linea=10000.0):
    return {
        "atrasos": {"peor_dias": peor_dias, "cuantos": cuantos,
                    "proporcion_mayor": proporcion, "ciclos_evaluables": evaluables,
                    "monto_mayor": 0.0},
        "usuarios": usuarios,
        "categorias": categorias or {"combustible": {"monto": 9000.0},
                                     "casetas": {"monto": 1000.0}},
        "categorias_esperadas": list(esperadas) if esperadas else None,
        "gasto_mensual_promedio": promedio,
        "linea_vigente": linea,
    }


def puntaje(v, nombre):
    return v[nombre][1]


# ── la escala de atrasos ─────────────────────────────────────────────────────
print("La escala de atrasos distingue el error del incumplimiento")
check(puntaje(mr._uso_plataforma(uso(peor_dias=0, cuantos=0)), "atrasos") == 1.00,
      "sin atrasos, 1.00")
check(puntaje(mr._uso_plataforma(uso(peor_dias=1, cuantos=1)), "atrasos") == 0.85,
      "un dia de atraso es 0.85: suele ser un descuadre, no falta de fondos")
check(puntaje(mr._uso_plataforma(uso(peor_dias=2, cuantos=1)), "atrasos") == 0.85,
      "dos dias tambien")
check(puntaje(mr._uso_plataforma(uso(peor_dias=5, cuantos=1)), "atrasos") == 0.60,
      "cinco dias ya es 0.60")
check(puntaje(mr._uso_plataforma(uso(peor_dias=20, cuantos=1)), "atrasos") == 0.35,
      "veinte dias es 0.35")
check(puntaje(mr._uso_plataforma(uso(peor_dias=45, cuantos=1)), "atrasos") == 0.10,
      "cuarenta y cinco dias es el piso, 0.10")

print()
print("Los ajustes de reincidencia y proporcion")
p = puntaje(mr._uso_plataforma(uso(peor_dias=1, cuantos=3)), "atrasos")
check(abs(p - 0.65) < 1e-9,
      "tres ciclos con atraso restan 0.10 por cada uno despues del primero")

p = puntaje(mr._uso_plataforma(uso(peor_dias=1, cuantos=1, proporcion=0.01)),
            "atrasos")
check(abs(p - 0.95) < 1e-9,
      "faltar menos del 5% suma 0.10: es un descuadre, no falta de fondos")

p = puntaje(mr._uso_plataforma(uso(peor_dias=1, cuantos=1, proporcion=0.80)),
            "atrasos")
check(abs(p - 0.75) < 1e-9, "faltar mas del 50% resta 0.10")

p = puntaje(mr._uso_plataforma(uso(peor_dias=1, cuantos=1, proporcion=0.001)),
            "atrasos")
check(p <= 0.95,
      "el techo es 0.95: un ciclo con atraso NUNCA puntua igual que ninguno")

p = puntaje(mr._uso_plataforma(uso(peor_dias=60, cuantos=5, proporcion=0.9)),
            "atrasos")
check(p == 0.10, "el piso es 0.10, por malo que sea")

print()
print("La ausencia de un dato no es un dato desfavorable")
v = mr._uso_plataforma(uso(peor_dias=None, cuantos=0, evaluables=0))
check(puntaje(v, "atrasos") is None,
      "sin ciclos evaluables la variable de atrasos se cae, no puntua cero")
v = mr._uso_plataforma(uso(esperadas=None))
check(puntaje(v, "alineacion_giro") is None,
      "sin categorias esperadas confirmadas por el operador, no se puntua la "
      "alineacion: clasificar por palabra clave no es un juicio de negocio")
v = mr._uso_plataforma(uso(linea=None))
check(puntaje(v, "utilizacion_promedio") is None,
      "sin linea vigente no hay utilizacion que calcular")
check(mr._uso_plataforma(None) == {} or all(
    p is None for _, p in mr._uso_plataforma(None).values()),
    "sin bloque de uso, ninguna variable puntua")

print()
print("Alineacion al giro")
v = mr._uso_plataforma(uso(categorias={"combustible": {"monto": 9500.0},
                                       "casetas": {"monto": 500.0}}))
check(puntaje(v, "alineacion_giro") == 1.00,
      "todo el gasto en categorias esperadas es 1.00")

v = mr._uso_plataforma(uso(categorias={"combustible": {"monto": 5000.0},
                                       "efectivo": {"monto": 5000.0}}))
check(puntaje(v, "alineacion_giro") == 0.50,
      "la mitad en efectivo baja la alineacion: en una flotilla el efectivo no "
      "es gasto controlado")

v = mr._uso_plataforma(uso(
    categorias={"combustible": {"monto": 5000.0},
                "sin_clasificar": {"monto": 5000.0}}))
check(puntaje(v, "alineacion_giro") == 1.00,
      "lo no clasificado se reporta pero no se puntua: sale del denominador")

print()
print("Usuarios y utilizacion")
check(puntaje(mr._uso_plataforma(uso(usuarios=1)), "usuarios_activos") == 0.25,
      "un solo usuario puntua bajo: el negocio quiere estar permeado en la empresa")
check(puntaje(mr._uso_plataforma(uso(usuarios=6)), "usuarios_activos") == 1.00,
      "seis usuarios, 1.00")
check(puntaje(mr._uso_plataforma(uso(promedio=9000.0, linea=10000.0)),
              "utilizacion_promedio") == 1.00,
      "usar el 90% de la linea justifica el aumento")
check(puntaje(mr._uso_plataforma(uso(promedio=500.0, linea=10000.0)),
              "utilizacion_promedio") == 0.25,
      "usar el 5% no lo justifica")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_modelo_aumento.py`
Expected: FAIL — `AttributeError: module 'modelo_riesgo' has no attribute '_uso_plataforma'`

- [ ] **Step 3: Escribir el módulo**

Agregar a `modelo_riesgo.py`, después de `_declaracion_anual`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Modulo 5 · uso de la tarjeta Nea (solo en aumentos)
# ─────────────────────────────────────────────────────────────────────────────
# Un cliente nuevo no tiene este modulo: no ha usado nada. En un aumento es la
# evidencia mas directa que hay —como pago, en que gasto, quien gasto— y por eso
# pesa mas que cualquier otro modulo.
PESOS_USO = {"atrasos": 0.45, "alineacion_giro": 0.25,
             "usuarios_activos": 0.15, "utilizacion_promedio": 0.15}

# El efectivo nunca es una categoria esperada: en una tarjeta de flotilla un
# retiro en cajero no es gasto controlado, y esa es la senal que se busca.
CATEGORIAS_NUNCA_ESPERADAS = ("efectivo",)


def _uso_plataforma(uso):
    """Variables del uso de la tarjeta. `uso` es el bloque del expediente."""
    uso = uso or {}
    v = {}
    a = uso.get("atrasos") or {}

    # ── atrasos ─────────────────────────────────────────────────────────────
    # Uno o dos dias suele ser un descuadre operativo; treinta dias generando
    # moratorios es otra cosa. La escala tiene que distinguirlas o el peso mas
    # alto del modulo castiga igual dos hechos que no se parecen.
    peor = a.get("peor_dias")
    if not a.get("ciclos_evaluables"):
        peor = None
    base = _escalon(peor, [
        (lambda x: x <= 0, 1.00),
        (lambda x: x <= 2, 0.85),
        (lambda x: x <= 7, 0.60),
        (lambda x: x <= 29, 0.35)], 0.10)

    cuantos = a.get("cuantos") or 0
    if base is not None and cuantos:
        base -= 0.10 * (cuantos - 1)
        prop = a.get("proporcion_mayor")
        if prop is not None:
            if prop < 0.05:
                base += 0.10
            elif prop > 0.50:
                base -= 0.10
        # Un ciclo con atraso nunca puntua igual que ninguno, por chico que fuera.
        base = max(0.10, min(0.95, base))
    v["atrasos"] = (PESOS_USO["atrasos"], base)

    # ── alineacion al giro ──────────────────────────────────────────────────
    # Solo se puntua si el operador confirmo cuales son las categorias esperadas.
    # Clasificar comercios por palabra clave sugiere; no es un juicio de negocio,
    # y `giros.py` ya dejo escrito por que eso no se sustituye.
    esperadas = uso.get("categorias_esperadas")
    categorias = uso.get("categorias") or {}
    alineacion = None
    if esperadas:
        esperadas = [e for e in esperadas if e not in CATEGORIAS_NUNCA_ESPERADAS]
        # Lo no clasificado sale del denominador: se reporta, no se puntua.
        base_gasto = sum(g.get("monto", 0.0) for k, g in categorias.items()
                         if k != "sin_clasificar")
        alineado = sum(g.get("monto", 0.0) for k, g in categorias.items()
                       if k in esperadas)
        alineacion = _div(alineado, base_gasto)
    v["alineacion_giro"] = (PESOS_USO["alineacion_giro"], _escalon(alineacion, [
        (lambda x: x >= 0.90, 1.00), (lambda x: x > 0.75, 0.75),
        (lambda x: x > 0.50, 0.50), (lambda x: x > 0.25, 0.25)], 0.0))

    # ── usuarios activos ────────────────────────────────────────────────────
    # Mas usuarios es mejor: el objetivo es estar permeados en la empresa. Un
    # solo usuario concentra el uso —y el riesgo— en una persona.
    usuarios = uso.get("usuarios") or None
    v["usuarios_activos"] = (PESOS_USO["usuarios_activos"], _escalon(usuarios, [
        (lambda x: x >= 5, 1.00), (lambda x: x >= 3, 0.75),
        (lambda x: x == 2, 0.50)], 0.25))

    # ── utilizacion promedio ────────────────────────────────────────────────
    # En un aumento, usar mucho la linea es lo que lo justifica: un cliente al
    # 10% no necesita mas linea. El riesgo de exceso no vive aqui —el saldo se
    # paga completo o se bloquea la tarjeta— sino en la variable de atrasos.
    utilizacion = _div(uso.get("gasto_mensual_promedio"), uso.get("linea_vigente"))
    v["utilizacion_promedio"] = (PESOS_USO["utilizacion_promedio"],
                                 _escalon(utilizacion, [
                                     (lambda x: x >= 0.80, 1.00),
                                     (lambda x: x >= 0.60, 0.85),
                                     (lambda x: x >= 0.40, 0.70),
                                     (lambda x: x >= 0.20, 0.50)], 0.25))
    return v
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_modelo_aumento.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 6: Commit**

```bash
git add modelo_riesgo.py tests/test_modelo_aumento.py
git commit -m "El uso de la tarjeta se califica, con los atrasos al frente"
```

---

### Task 7: `evaluar_aumento()`

**Files:**
- Modify: `modelo_riesgo.py`
- Test: `tests/test_modelo_aumento.py`

**Interfaces:**
- Consumes: de la Tarea 6, `_uso_plataforma()`, `PESOS_USO`. De `modelo_riesgo.py`, `_buro()`, `_edos_cuenta()`, `_declaracion_anual()`, `_ponderar()`.
- Produces:
  - `PESOS_MODULO_AUMENTO: dict[str, float]`
  - `VERSION_AUMENTO = "2026.08-aumentos"`
  - `evaluar_aumento(perfil, buro, declaracion, cuentas, uso, monto_solicitado, hoy=None) -> dict` con las llaves `score`, `veredicto`, `version`, `monto_solicitado`, `monto_aprobado`, `vetos`, `modulos`, `variables`, `modulos_sin_datos`

**Decisión que esta tarea fija y que la especificación no cubría:** en un aumento **no aplica** `FACTOR_AMPLIACION`. Que el modelo proponga 1.2× lo pedido tiene sentido al originar, cuando la cotización es una hipótesis; en un aumento el cliente pidió una cifra concreta y ofrecerle más de lo que pidió no es una decisión que el modelo deba tomar solo.

- [ ] **Step 1: Escribir la prueba que falla**

Agregar a `tests/test_modelo_aumento.py`, antes del bloque final:

```python
# ── evaluar_aumento ──────────────────────────────────────────────────────────
print()
print("evaluar_aumento")


def buro_bueno():
    return {"score_pyme": 700, "creditos_activos": 2, "saldo_vencido": 0,
            "peor_atraso_meses": 0, "consultas_12m": 1}


def declaracion_buena():
    return {"ingresos": 15000000.0, "utilidad": 1200000.0, "activo": 5000000.0,
            "pasivo": 2000000.0, "capital": 3000000.0}


def perfil_bueno():
    return {"antiguedad_anios": 12, "codigo_giro": "Codigo 2", "empleados": 30,
            "estado": "Nuevo Leon"}


r = mr.evaluar_aumento(perfil_bueno(), buro_bueno(), declaracion_buena(),
                       cuentas=[], uso=uso(), monto_solicitado=120000.0)
check(r["version"] == mr.VERSION_AUMENTO,
      "el resultado trae su version: un score de aumento no es comparable contra "
      "uno de originacion")
check("uso_plataforma" in r["modulos"], "el modulo de uso entra al score")
check("edos_cuenta" in r["modulos_sin_datos"],
      "sin estados de cuenta ese modulo se declara sin datos, no se inventa")
check(r["score"] is not None, "y aun asi hay score: los otros cuatro se renormalizan")
check(r["monto_solicitado"] == 120000.0, "el monto solicitado va en el resultado")

print()
print("La renormalizacion cuando no hay estados de cuenta")
suma = sum(mr.PESOS_MODULO_AUMENTO.values())
check(abs(suma - 1.0) < 1e-9, "los cinco pesos del aumento suman 1.00")
check(mr.PESOS_MODULO_AUMENTO["uso_plataforma"] == 0.275,
      "el uso de la plataforma pesa 27.5%, el mas alto")

# el mismo caso con estados de cuenta debe mover el score, no ignorarlos
cuentas = [[{"saldo_inicial": 100000.0, "saldo_final": 150000.0,
             "saldo_promedio": 300000.0, "saldo_min": 150000.0,
             "saldo_max": 600000.0, "num_depositos": 45, "num_retiros": 45}]]
con = mr.evaluar_aumento(perfil_bueno(), buro_bueno(), declaracion_buena(),
                         cuentas=cuentas, uso=uso(), monto_solicitado=120000.0)
check("edos_cuenta" not in con["modulos_sin_datos"],
      "con estados de cuenta el modulo entra")
check(con["score"] != r["score"],
      "y el score cambia: entrar al promedio tiene efecto")

print()
print("El veredicto")
malo = uso(peor_dias=60, cuantos=4, proporcion=0.9, usuarios=1, promedio=500.0)
r_malo = mr.evaluar_aumento(perfil_bueno(), buro_bueno(), declaracion_buena(),
                            cuentas=[], uso=malo, monto_solicitado=120000.0)
check(r_malo["score"] < r["score"],
      "un historial de pago malo baja el score del aumento")

check(r["monto_aprobado"] in (0.0, 120000.0),
      "el modelo nunca propone mas de lo solicitado en un aumento: no aplica el "
      "factor de ampliacion de originacion")

print()
print("Regresion: evaluar() no se movio")
antes = mr.evaluar(dict(perfil_bueno(), monto_solicitado=120000.0), buro_bueno(),
                   declaracion_buena(), cuentas=[])
check(set(antes["modulos"]) == {"perfil_empresa", "buro", "edos_cuenta",
                                "declaracion_anual"},
      "evaluar() sigue teniendo exactamente sus cuatro modulos, sin el de uso")
check(sum(mr.PESOS_MODULO.values()) == 1.0,
      "y sus pesos originales siguen sumando 1.00")
check(mr.VERSION != mr.VERSION_AUMENTO,
      "las dos versiones son distintas, para no confundir los dos scores")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
```

- [ ] **Step 2: Correr la prueba para verla fallar**

Run: `python tests/test_modelo_aumento.py`
Expected: FAIL — `AttributeError: module 'modelo_riesgo' has no attribute 'evaluar_aumento'`

- [ ] **Step 3: Escribir `evaluar_aumento`**

Agregar a `modelo_riesgo.py`, junto a `PESOS_MODULO`:

```python
# Un aumento se juzga con cinco modulos, no con cuatro, y el nuevo es el que mas
# pesa: es la unica evidencia directa de como se comporta ESTE cliente con
# NUESTRO producto. Todo lo demas es inferencia sobre el negocio.
#
# En el caso normal no hay estados de cuenta —no se vuelven a pedir— y ese modulo
# se cae solo, con la renormalizacion que ya existe: uso 32.4%, declaracion
# 26.5%, buro 26.5%, perfil 14.7%. No hay logica especial para los dos casos.
PESOS_MODULO_AUMENTO = {
    "uso_plataforma": 0.275,
    "declaracion_anual": 0.225,
    "buro": 0.225,
    "edos_cuenta": 0.15,
    "perfil_empresa": 0.125,
}

VERSION_AUMENTO = "2026.08-aumentos"
```

Y al final del archivo:

```python
def evaluar_aumento(perfil, buro, declaracion, cuentas, uso, monto_solicitado,
                    hoy=None):
    """El score de una ronda de aumento, con su desglose.

    Es una funcion aparte de `evaluar()` a proposito. Comparten los modulos que
    se pueden compartir, pero el score que sale de aqui **no es comparable**
    contra uno de originacion: se calcula con otros modulos y otros pesos. Por
    eso lleva su propia version, y por eso no se hizo como una bandera de
    `evaluar()` —una bandera invita a comparar los dos numeros como si midieran
    lo mismo—.
    """
    hoy = hoy or date.today()
    perfil = dict(perfil or {}, monto_solicitado=monto_solicitado)

    vars_buro, vetos = _buro(buro, legado=False)
    import perfil_empresa as _pe
    modulos = {
        "uso_plataforma": _uso_plataforma(uso),
        "perfil_empresa": _pe.evaluar(perfil, hoy),
        "buro": vars_buro,
        "edos_cuenta": _edos_cuenta(cuentas, monto_solicitado, legado=False),
        "declaracion_anual": _declaracion_anual(declaracion, monto_solicitado,
                                                legado=False),
    }

    resultados, num, den = {}, 0.0, 0.0
    for nombre, variables in modulos.items():
        r = _ponderar(variables, legado=False)
        resultados[nombre] = r
        if r is not None:
            num += PESOS_MODULO_AUMENTO[nombre] * r
            den += PESOS_MODULO_AUMENTO[nombre]

    score = None if den == 0 else num / den

    # A diferencia de originacion, aqui NO se aplica FACTOR_AMPLIACION. Al
    # originar la cotizacion es una hipotesis y proponer mas tiene sentido; en un
    # aumento el cliente pidio una cifra, y ofrecerle mas de lo que pidio no es
    # una decision que el modelo deba tomar solo.
    if "exclusion" in vetos:
        veredicto, aprobado = "Rechazado", 0.0
    elif score is None:
        veredicto, aprobado = "Sin datos suficientes", 0.0
    elif "comite" in vetos:
        veredicto, aprobado = "Comité", 0.0
    elif score >= UMBRAL_APROBADO:
        veredicto, aprobado = "Aprobado", monto_solicitado
    elif score >= UMBRAL_COMITE:
        veredicto, aprobado = "Comité", 0.0
    else:
        veredicto, aprobado = "Rechazado", 0.0

    return {
        "score": score,
        "veredicto": veredicto,
        "version": VERSION_AUMENTO,
        "monto_solicitado": monto_solicitado,
        "monto_aprobado": aprobado,
        "vetos": vetos,
        "modulos": resultados,
        "variables": {m: {k: {"peso": p, "puntaje": s} for k, (p, s) in vs.items()}
                      for m, vs in modulos.items()},
        "modulos_sin_datos": [m for m, r in resultados.items() if r is None],
    }
```

- [ ] **Step 4: Correr la prueba para verla pasar**

Run: `python tests/test_modelo_aumento.py`
Expected: PASS

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0 — `test_modelo_riesgo.py` verde es la prueba de que originación no se movió.

- [ ] **Step 6: Commit**

```bash
git add modelo_riesgo.py tests/test_modelo_aumento.py
git commit -m "Un aumento se califica con su propio modelo y su propia version"
```

---

### Task 8: Etapa `operando` y `nuevo --heredado`

**Files:**
- Modify: `nea.py:868` (la lista `ETAPAS`), `nea.py:255` (`cmd_nuevo`), `nea.py` (el despacho en `main`)

**Interfaces:**
- Consumes: de la Tarea 4, el esquema con `historial_aumentos`.
- Produces: `cmd_nuevo(ruta_csf, heredado=False)`; `"operando"` al final de `ETAPAS`.

- [ ] **Step 1: Agregar la etapa**

En `nea.py`, reemplazar la línea de `ETAPAS`:

```python
# `operando` es un cliente que ya opera: no esta en el pipeline de apertura de
# cuentas nuevas y por eso va al final. NO se agrega a DIAS_ATORADO a proposito:
# un cliente que ya opera no esta atorado en nada, y sacarlo con `!` en el
# tablero de onboardings seria ruido permanente.
ETAPAS = ["apertura", "validacion", "riesgo", "generacion", "firma", "cerrado",
          "operando"]
```

- [ ] **Step 2: Cambiar la firma de `cmd_nuevo`**

Reemplazar `def cmd_nuevo(ruta_csf):` por:

```python
def cmd_nuevo(ruta_csf, heredado=False):
    """Abre un expediente desde la CSF.

    `heredado` es para un cliente que YA opera y es anterior a esta plataforma:
    abre en etapa `operando` y no pregunta los datos que solo sirven para generar
    contratos, porque ese cliente ya firmo el suyo fuera del sistema. Todo lo
    demas —contribuyente ACTIVO, duplicados por RFC, folio— es igual.
    """
```

- [ ] **Step 3: Usar la bandera en la etapa**

Reemplazar `exp["etapa"] = "recoleccion"` por:

```python
    exp["etapa"] = "operando" if heredado else "recoleccion"
```

- [ ] **Step 4: Saltar las preguntas que no aplican**

Envolver el bloque que va desde `titulo("Datos que captura ventas")` hasta la línea de `exp["flags"]["domiciliacion"] = ...` en un `if not heredado:`, y dejar el bloque de `quien_lleno` fuera del `if` para que se pregunte siempre. Después del `if`, agregar la rama del heredado:

```python
    if heredado:
        titulo("Cliente que ya opera")
        print("  No se preguntan representante propuesto, tarjetas ni")
        print("  domiciliacion: este cliente ya firmo su contrato fuera de la")
        print("  plataforma y esos datos no se van a usar para generar nada.")
        print("  Su linea vigente se captura al abrir la ronda de aumento.")
```

- [ ] **Step 5: Cambiar el mensaje de cierre**

Reemplazar las últimas cuatro líneas de impresión de `cmd_nuevo` por:

```python
    print("\n  Expediente %s abierto." % folio)
    print("  Carpeta en Drive que debe existir:")
    print("    %s — %s" % (csf["razon_social"], folio))
    if heredado:
        print("\n  Lo que sigue: abrir la ronda de aumento.")
        print("    python nea.py aumento nuevo %s <monto> --linea-actual <monto>"
              % folio)
    else:
        print("\n  Lo que sigue: recolectar documentos. Para ver qué falta:")
        print("    python nea.py estado %s" % folio)
    return 0
```

- [ ] **Step 6: Aceptar la bandera en el despacho**

En `main`, reemplazar la línea de `nuevo`:

```python
        if orden == "nuevo" and args:
            rutas = [a for a in args if not a.startswith("--")]
            if len(rutas) == 1:
                return cmd_nuevo(rutas[0], heredado="--heredado" in args)
```

- [ ] **Step 7: Verificar a mano que la ruta normal no cambió**

Run: `python nea.py ayuda`
Expected: imprime la ayuda y sale con 0.

Run: `python nea.py nuevo`
Expected: imprime la ayuda y sale con 1 (sin ruta, no hace nada).

- [ ] **Step 8: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 9: Commit**

```bash
git add nea.py
git commit -m "Un cliente que ya opera se abre operando, no en recoleccion"
```

---

### Task 9: Los comandos de la ronda de aumento

**Files:**
- Modify: `nea.py`

**Interfaces:**
- Consumes: de la Tarea 3, `uso_plataforma.leer/cuadra/resumir`. De las Tareas 4–5, `aumento_vacio`, `ronda_abierta`, `compuertas_riesgo_aumento`, `compuertas_cierre_aumento`, `requiere_estados_cuenta`. De la Tarea 7, `evaluar_aumento`. De `nea.py`, `cargar`, `guardar`, `titulo`, `preguntar_monto`, `hay_supabase`.
- Produces: `cmd_uso`, `cmd_aumento_nuevo`, `cmd_aumento_estado`, `cmd_aumento_riesgo`, `cmd_aumento_cerrar`, `_fecha_syntage`, `_copiar_documento`.

- [ ] **Step 1: Escribir los comandos**

Agregar a `nea.py`, antes de `def main`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Aumentos de linea
# ─────────────────────────────────────────────────────────────────────────────
def _fecha_syntage(folio):
    """La fecha de la extraccion de Syntage mas reciente de este folio.

    Vive en Supabase, no en el expediente, asi que se consulta aqui y se le pasa
    a la compuerta. Sin Supabase no se puede saber, y eso NO se reporta como
    'esta al dia': se devuelve None y la compuerta lo trata como faltante.
    """
    if not hay_supabase():
        return None
    try:
        import db
        sb = db.cliente()
        filas = (sb.table("syntage_crudo").select("creado_el")
                 .eq("folio", folio).order("creado_el", desc=True)
                 .limit(1).execute().data or [])
        return (filas[0]["creado_el"] or "")[:10] if filas else None
    except Exception:
        return None


def _copiar_documento(exp, ruta, tipo, indice_ronda):
    """Copia un archivo a la carpeta del expediente y lo registra.

    La carpeta del vendedor no se toca: los documentos se copian a la nuestra,
    que es la regla que ya sigue el resto del proyecto.
    """
    import shutil
    from datetime import date
    if not os.path.exists(ruta):
        raise LookupError("No encuentro el archivo %s" % ruta)
    destino_dir = os.path.join(DIR_EXP, "%s_aumento_%d" % (exp["folio"], indice_ronda))
    os.makedirs(destino_dir, exist_ok=True)
    nombre = "%s%s" % (tipo, os.path.splitext(ruta)[1])
    destino = os.path.join(destino_dir, nombre)
    shutil.copy2(ruta, destino)
    exp["documentos"].append({
        "tipo": tipo, "file_id": destino, "ronda_aumento": indice_ronda,
        "fecha_emision": date.today().isoformat(), "legible": True,
        "superado_por": None, "inscrito": None,
    })
    return destino


def cmd_aumento_nuevo(folio, monto, linea_actual=None):
    """Abre una ronda de aumento."""
    from datetime import date
    from schema_expediente import aumento_vacio, ronda_abierta

    exp = cargar(folio)
    i, abierta = ronda_abierta(exp)
    if abierta is not None:
        print("Ya hay una ronda de aumento abierta (la %d), por $%s."
              % (i, format(float(abierta.get("monto_solicitado") or 0), ",.2f")))
        print("Cierrala antes de abrir otra:")
        print("  python nea.py aumento estado %s" % folio)
        return 1

    vigente = exp["credito"]["autorizada"].get("linea")
    if vigente is None:
        if linea_actual is None:
            print("Este expediente no tiene linea autorizada registrada.")
            print("Es un cliente anterior a la plataforma: hay que capturar su")
            print("linea vigente, porque de ella dependen la regla de los")
            print("$150,000 y la utilizacion promedio.")
            print("\n  python nea.py aumento nuevo %s %s --linea-actual <monto>"
                  % (folio, monto))
            return 1
        vigente = float(linea_actual)
        exp["credito"]["autorizada"]["linea"] = vigente
        print("  Linea vigente registrada: $%s" % format(vigente, ",.2f"))
    elif linea_actual is not None:
        print("El expediente ya tiene linea autorizada de $%s."
              % format(float(vigente), ",.2f"))
        print("No se teclea otra vez: si esta mal, se corrige en el expediente.")
        return 1

    ronda = aumento_vacio()
    ronda["fecha_solicitud"] = date.today().isoformat()
    ronda["linea_previa"] = float(vigente)
    ronda["monto_solicitado"] = float(monto)
    exp["historial_aumentos"].append(ronda)
    indice = len(exp["historial_aumentos"]) - 1

    titulo("Ronda de aumento %d de %s" % (indice, folio))
    print("  Linea vigente:      $%s" % format(float(vigente), ",.2f"))
    print("  Linea solicitada:   $%s" % format(float(monto), ",.2f"))
    print("  Incremento:         $%s" % format(float(monto) - float(vigente), ",.2f"))

    from schema_expediente import requiere_estados_cuenta, UMBRAL_AUMENTO_MAYOR
    if requiere_estados_cuenta(ronda):
        print("\n  El incremento pasa los $%s: se requieren 3 estados de cuenta"
              % format(UMBRAL_AUMENTO_MAYOR, ",.2f"))
        print("  bancarios frescos.")
    else:
        print("\n  El incremento no pasa los $%s: no se piden estados de cuenta"
              % format(UMBRAL_AUMENTO_MAYOR, ",.2f"))
        print("  bancarios, salvo que decidas pedirlos por el caso.")

    guardar(exp)
    print("\n  Lo que sigue: actualizar Syntage y buro, y leer el uso:")
    print("    python nea.py uso %s <excel.xlsx>" % folio)
    print("    python nea.py aumento estado %s" % folio)
    return 0


def cmd_uso(folio, ruta_excel):
    """Lee el Excel de uso de la tarjeta y lo guarda en el expediente."""
    import uso_plataforma as up
    from schema_expediente import ronda_abierta

    exp = cargar(folio)
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        print("No hay ronda de aumento abierta en %s." % folio)
        print("  python nea.py aumento nuevo %s <monto>" % folio)
        return 1

    if not os.path.exists(ruta_excel):
        print("No encuentro el archivo %s" % ruta_excel)
        return 1

    titulo("Leyendo el uso de la tarjeta")
    try:
        datos = up.leer(ruta_excel)
    except up.ErrorDeFormato as e:
        print("El archivo no tiene la forma esperada:")
        print("  %s" % e)
        print("\nDebe ser el libro con las cuatro pestanas: Transacciones,")
        print("Depositos, Estado de Cuenta y Comisiones.")
        return 1

    ok, diagnostico = up.cuadra(datos)
    if not ok:
        print("  El saldo de los ciclos NO cuadra. No se guarda nada.")
        print("  saldo al corte = saldo inicial + transacciones + comisiones")
        print("                   con IVA - pagos del ciclo")
        for ciclo, d in diagnostico.items():
            if isinstance(d, dict) and d.get("diferencia"):
                print("    ciclo %s: calculado %s, declarado %s, diferencia %s"
                      % (ciclo, d.get("calculado"), d.get("declarado"),
                         d["diferencia"]))
        print("\n  Un archivo mal leido entra al modelo como si fuera bueno.")
        return 1
    print("  Cuadra: el saldo de los %d ciclos cierra." % len(datos["ciclos"]))

    resumen = up.resumir(datos, linea_vigente=ronda.get("linea_previa"),
                         archivo=os.path.basename(ruta_excel),
                         ronda_aumento=indice)

    sin_clasificar = (resumen["categorias"].get("sin_clasificar") or {})
    categorias = [k for k in resumen["categorias"] if k != "sin_clasificar"]
    if categorias:
        titulo("Confirma el giro del gasto")
        print("  El gasto cayo en estas categorias:")
        for k in categorias:
            g = resumen["categorias"][k]
            print("    %-14s $%12s  (%d movimientos)"
                  % (k, format(g["monto"], ",.2f"), g["numero"]))
        if sin_clasificar:
            print("\n  Sin clasificar: $%s en %d movimientos. No se puntuan;"
                  % (format(sin_clasificar["monto"], ",.2f"),
                     sin_clasificar["numero"]))
            print("  quedan reportados:")
            for c in sin_clasificar["comercios"][:10]:
                print("    %s" % c)
        print("\n  Cuales son ESPERADAS para el giro de este cliente?")
        print("  (separa con comas; el efectivo nunca cuenta como esperado)")
        respuesta = preguntar("Categorias esperadas",
                              default=",".join(categorias[:2]))
        resumen["categorias_esperadas"] = [c.strip() for c in (respuesta or "").split(",")
                                           if c.strip()]

    exp["uso_plataforma"] = resumen
    titulo("Resumen")
    print("  Periodo:            %s a %s" % (resumen["periodo"]["desde"],
                                             resumen["periodo"]["hasta"]))
    print("  Gasto total:        $%s" % format(resumen["gasto_total"], ",.2f"))
    if resumen["gasto_mensual_promedio"]:
        print("  Promedio mensual:   $%s"
              % format(resumen["gasto_mensual_promedio"], ",.2f"))
    print("  Usuarios/tarjetas:  %s / %s" % (resumen["usuarios"], resumen["tarjetas"]))
    print("  Comercios:          %s" % resumen["comercios"])
    a = resumen["atrasos"]
    print("  Ciclos evaluables:  %s" % a["ciclos_evaluables"])
    if a["peor_dias"] is None:
        print("  Atrasos:            sin ciclos vencidos que evaluar")
    elif a["cuantos"] == 0:
        print("  Atrasos:            ninguno")
    else:
        print("  Atrasos:            %d, el peor de %d dias, hasta $%s sin cubrir"
              % (a["cuantos"], a["peor_dias"], format(a["monto_mayor"], ",.2f")))

    mens = resumen["comisiones_por_tipo"].get("Comision por financiamiento")
    if mens:
        print("\n  Mensualidad cobrada: %d cargos por $%s en total."
              % (mens["numero"], format(mens["monto"], ",.2f")))
        print("  Verifica que coincida con la cotizada. No entra al score: es el")
        print("  precio del producto, no comportamiento del cliente.")

    guardar(exp)
    print("\n  Lo que sigue:")
    print("    python nea.py aumento estado %s" % folio)
    return 0


def cmd_aumento_estado(folio):
    """Que falta en la ronda de aumento abierta."""
    from schema_expediente import (compuertas_riesgo_aumento,
                                   compuertas_cierre_aumento, ronda_abierta)
    exp = cargar(folio)
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        print("No hay ronda de aumento abierta en %s." % folio)
        return 1

    titulo("Ronda de aumento %d de %s" % (indice, folio))
    print("  Linea vigente:    $%s"
          % format(float(ronda.get("linea_previa") or 0), ",.2f"))
    print("  Solicitado:       $%s"
          % format(float(ronda.get("monto_solicitado") or 0), ",.2f"))
    print("  Solicitado el:    %s" % ronda.get("fecha_solicitud"))

    riesgo = compuertas_riesgo_aumento(exp, fecha_syntage=_fecha_syntage(folio))
    titulo("Para correr el modelo")
    if not riesgo:
        print("  Nada pendiente. Corre: python nea.py aumento riesgo %s" % folio)
    else:
        for f in riesgo:
            print("  - %s" % f)

    if ronda.get("riesgo", {}).get("score") is not None:
        titulo("Para cerrar la ronda")
        cierre = compuertas_cierre_aumento(exp)
        if not cierre:
            print("  Nada pendiente.")
        else:
            for f in cierre:
                print("  - %s" % f)
    return 0


def cmd_aumento_riesgo(folio):
    """Corre el modelo sobre la ronda abierta."""
    from datetime import date
    from schema_expediente import compuertas_riesgo_aumento, ronda_abierta
    import modelo_riesgo
    import insumos_riesgo

    exp = cargar(folio)
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        print("No hay ronda de aumento abierta en %s." % folio)
        return 1

    fallas = compuertas_riesgo_aumento(exp, fecha_syntage=_fecha_syntage(folio))
    if fallas:
        titulo("La compuerta de riesgo esta cerrada")
        for f in fallas:
            print("  - %s" % f)
        print("\n  Un score sobre modulos incompletos no es un score bajo: es un")
        print("  numero que no describe a nadie y que luego se cita como si si.")
        return 1

    insumos = insumos_riesgo.armar(exp)
    r = modelo_riesgo.evaluar_aumento(
        perfil=insumos["perfil"], buro=insumos["buro"],
        declaracion=insumos["declaracion"], cuentas=insumos["cuentas"],
        uso=exp.get("uso_plataforma"),
        monto_solicitado=float(ronda["monto_solicitado"]))

    titulo("Score del aumento — %s, ronda %d" % (folio, indice))
    print("  Score:      %.4f" % r["score"] if r["score"] is not None
          else "  Score:      sin datos")
    print("  Veredicto:  %s" % r["veredicto"])
    print("  Version:    %s" % r["version"])
    if r["modulos_sin_datos"]:
        print("  Sin datos:  %s" % ", ".join(r["modulos_sin_datos"]))
        print("              (los demas se renormalizan entre ellos)")

    titulo("Por modulo")
    for nombre, valor in r["modulos"].items():
        peso = modelo_riesgo.PESOS_MODULO_AUMENTO[nombre]
        print("  %-20s peso %5.1f%%   %s"
              % (nombre, peso * 100,
                 "sin datos" if valor is None else "%.4f" % valor))

    titulo("El uso de la tarjeta, variable por variable")
    for k, d in r["variables"]["uso_plataforma"].items():
        print("  %-22s peso %4.0f%%   %s"
              % (k, d["peso"] * 100,
                 "sin datos" if d["puntaje"] is None else "%.2f" % d["puntaje"]))

    # Lo que NO entra al numero se reporta aparte, igual que el resumen
    # ejecutivo separa lo que el score no captura.
    uso = exp.get("uso_plataforma") or {}
    titulo("Contexto que no entra al score")
    if uso.get("concentracion_mayor"):
        print("  Concentracion del mayor comercio: %.1f%%"
              % (uso["concentracion_mayor"] * 100))
    efectivo = (uso.get("categorias") or {}).get("efectivo")
    if efectivo:
        print("  Retiros de efectivo: %d por $%s"
              % (efectivo["numero"], format(efectivo["monto"], ",.2f")))
    mens = (uso.get("comisiones_por_tipo") or {}).get("Comision por financiamiento")
    if mens:
        print("  Mensualidad cobrada: %d cargos, $%s en total"
              % (mens["numero"], format(mens["monto"], ",.2f")))
        print("  (verifica contra la cotizada)")
    sinc = (uso.get("categorias") or {}).get("sin_clasificar")
    if sinc:
        print("  Gasto sin clasificar: $%s en %d movimientos, fuera del score"
              % (format(sinc["monto"], ",.2f"), sinc["numero"]))

    ronda["riesgo"] = {"score": r["score"], "version": r["version"],
                       "fecha_evaluacion": date.today().isoformat()}
    guardar(exp)

    print("\n  El modelo no autoriza. Cuando decidas:")
    print("    python nea.py aumento cerrar %s --aprobado <monto> \\" % folio)
    print("        --evidencia <captura.png>")
    return 0


def cmd_aumento_cerrar(folio, aprobado, evidencia, cotizacion=None,
                       cotizacion_aprobada=None, autorizado_por=None):
    """Cierra la ronda abierta y actualiza la linea vigente."""
    from datetime import date
    from schema_expediente import compuertas_cierre_aumento, ronda_abierta

    exp = cargar(folio)
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        print("No hay ronda de aumento abierta en %s." % folio)
        return 1
    if ronda.get("riesgo", {}).get("score") is None:
        print("Esta ronda no tiene score todavia.")
        print("  python nea.py aumento riesgo %s" % folio)
        return 1

    ronda["monto_aprobado"] = float(aprobado)
    ronda["fecha_decision"] = date.today().isoformat()
    ronda["autorizado_por"] = autorizado_por or preguntar(
        "Quien autorizo el aumento (nombre completo)", obligatorio=True)

    for ruta, tipo in ((evidencia, "autorizacion_aumento"),
                       (cotizacion, "cotizacion"),
                       (cotizacion_aprobada, "cotizacion_aprobada")):
        if ruta:
            destino = _copiar_documento(exp, ruta, tipo, indice)
            print("  %-22s -> %s" % (tipo, destino))

    fallas = compuertas_cierre_aumento(exp)
    if fallas:
        titulo("No se puede cerrar todavia")
        for f in fallas:
            print("  - %s" % f)
        # Se guarda lo que ya se capturo: perder la evidencia recien copiada
        # obligaria a volver a subirla.
        guardar(exp, avisar=False)
        return 1

    previa = float(ronda["linea_previa"])
    exp["credito"]["autorizada"]["linea"] = float(aprobado)
    exp["credito"]["autorizada"]["fecha"] = ronda["fecha_decision"]
    exp["credito"]["autorizada"]["autorizada_por"] = ronda["autorizado_por"]
    ronda["estado"] = "cerrada"
    if exp.get("etapa") != "operando":
        exp["etapa"] = "operando"

    titulo("Ronda %d cerrada" % indice)
    print("  Linea anterior:   $%s" % format(previa, ",.2f"))
    print("  Linea vigente:    $%s" % format(float(aprobado), ",.2f"))
    print("  Autorizo:         %s" % ronda["autorizado_por"])
    if float(aprobado) < float(ronda["monto_solicitado"]):
        print("  (se aprobo menos de los $%s solicitados)"
              % format(float(ronda["monto_solicitado"]), ",.2f"))
    guardar(exp)
    print("\n  Falta darla de alta en la plataforma operativa: este comando no")
    print("  la mueve alla.")
    return 0
```

- [ ] **Step 1b: El comando que registra la excepción de estados de cuenta**

Sin esto, `estados_cuenta_excepcion` no tiene quién lo escriba y la excepción que el negocio sí usa quedaría fuera del sistema. Agregar a `nea.py`, después de `cmd_aumento_nuevo`:

```python
def cmd_aumento_excepcion(folio, motivo=None):
    """Registra que en ESTA ronda si se piden estados de cuenta bancarios.

    Es una decision, no una condicion que el sistema deduzca: por eso queda con
    el motivo y el nombre de quien la tomo, igual que una observacion aceptada.
    El default del negocio es no volver a pedir estados de cuenta en un aumento.
    """
    from datetime import date
    from schema_expediente import ronda_abierta, ESTADOS_CUENTA_AUMENTO

    exp = cargar(folio)
    indice, ronda = ronda_abierta(exp)
    if ronda is None:
        print("No hay ronda de aumento abierta en %s." % folio)
        return 1
    if ronda.get("estados_cuenta_excepcion"):
        print("Esta ronda ya tiene la excepcion registrada:")
        print("  %s" % ronda["estados_cuenta_excepcion"].get("motivo"))
        return 1

    motivo = motivo or preguntar(
        "Por que se piden estados de cuenta en esta ronda", obligatorio=True)
    ronda["estados_cuenta_excepcion"] = {
        "motivo": motivo,
        "decidida_por": preguntar("Quien lo decide (nombre completo)",
                                  obligatorio=True),
        "fecha": date.today().isoformat(),
    }
    guardar(exp)
    titulo("Excepcion registrada en la ronda %d" % indice)
    print("  Ahora esta ronda exige %d estados de cuenta bancarios."
          % ESTADOS_CUENTA_AUMENTO)
    print("  Para ver que falta: python nea.py aumento estado %s" % folio)
    return 0
```

- [ ] **Step 2: Conectar el despacho**

En `main`, antes de la línea de `ayuda`:

```python
        if orden == "uso" and len(args) == 2:
            return cmd_uso(args[0], args[1])
        if orden == "aumento" and args:
            sub, resto = args[0], args[1:]

            def opcion(nombre):
                for a in resto:
                    if a.startswith("--%s=" % nombre):
                        return a.split("=", 1)[1]
                if "--%s" % nombre in resto:
                    i = resto.index("--%s" % nombre)
                    if i + 1 < len(resto):
                        return resto[i + 1]
                return None

            sueltos = []
            saltar = False
            for a in resto:
                if saltar:
                    saltar = False
                    continue
                if a.startswith("--"):
                    saltar = "=" not in a
                    continue
                sueltos.append(a)

            if sub == "nuevo" and len(sueltos) == 2:
                return cmd_aumento_nuevo(sueltos[0], sueltos[1],
                                         linea_actual=opcion("linea-actual"))
            if sub == "estado" and len(sueltos) == 1:
                return cmd_aumento_estado(sueltos[0])
            if sub == "excepcion-banco" and len(sueltos) == 1:
                return cmd_aumento_excepcion(sueltos[0], motivo=opcion("motivo"))
            if sub == "riesgo" and len(sueltos) == 1:
                return cmd_aumento_riesgo(sueltos[0])
            if sub == "cerrar" and len(sueltos) == 1:
                aprobado = opcion("aprobado")
                evidencia = opcion("evidencia")
                if not aprobado or not evidencia:
                    print("Faltan --aprobado y --evidencia.")
                    return 1
                return cmd_aumento_cerrar(
                    sueltos[0], aprobado, evidencia,
                    cotizacion=opcion("cotizacion"),
                    cotizacion_aprobada=opcion("cotizacion-aprobada"),
                    autorizado_por=opcion("autorizo"))
            if sub == "tablero":
                return cmd_aumento_tablero()
```

- [ ] **Step 3: Actualizar la ayuda**

En el docstring de `nea.py`, agregar al listado de comandos:

```
    python nea.py nuevo <csf.pdf> --heredado    cliente que YA opera, sin folio
    python nea.py uso <folio> <excel.xlsx>      lee el uso de la tarjeta Nea
    python nea.py aumento nuevo <folio> <monto> [--linea-actual <monto>]
    python nea.py aumento estado <folio>        que falta en la ronda abierta
    python nea.py aumento excepcion-banco <folio>   pedir edos de cuenta por el caso
    python nea.py aumento riesgo <folio>        corre el modelo del aumento
    python nea.py aumento cerrar <folio> --aprobado <monto> --evidencia <ruta>
    python nea.py aumento tablero               las rondas abiertas
```

- [ ] **Step 4: Verificar a mano contra un expediente de prueba**

Run:
```bash
python nea.py aumento estado NOEXISTE
```
Expected: un mensaje claro de que no existe el expediente y salida distinta de 0, **no** una traza de Python.

Run:
```bash
python nea.py aumento
```
Expected: imprime la ayuda, salida 1.

- [ ] **Step 5: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 6: Commit**

```bash
git add nea.py
git commit -m "Una ronda de aumento se abre, se lee, se califica y se cierra"
```

---

### Task 10: El tablero de aumentos

El tablero de onboardings lee una vista de Supabase; este no lo necesita, porque todo lo que muestra vive en el expediente. Se lee de disco para que funcione sin internet, como el resto de la plataforma.

**Files:**
- Modify: `nea.py`

**Interfaces:**
- Consumes: `expedientes_locales()`, `compuertas_riesgo_aumento`, `compuertas_cierre_aumento`, `ronda_abierta`, `_fecha_syntage`.
- Produces: `cmd_aumento_tablero() -> int`

- [ ] **Step 1: Escribir el tablero**

Agregar a `nea.py`, después de `cmd_aumento_cerrar`:

```python
def cmd_aumento_tablero():
    """Las rondas de aumento abiertas, y que detiene a cada una.

    Aparte del tablero de onboardings a proposito: un cliente que ya opera no es
    un prospecto, y mezclarlos hace que ninguno de los dos se lea. Este lee de
    disco y no necesita Supabase, porque todo lo que muestra vive en el
    expediente.
    """
    from datetime import date
    from schema_expediente import (compuertas_riesgo_aumento,
                                   compuertas_cierre_aumento, ronda_abierta)

    filas = []
    for exp in expedientes_locales():
        indice, ronda = ronda_abierta(exp)
        if ronda is None:
            continue
        solicitud = ronda.get("fecha_solicitud")
        dias = None
        if solicitud:
            try:
                dias = (date.today() - date.fromisoformat(solicitud)).days
            except ValueError:
                dias = None

        if ronda.get("riesgo", {}).get("score") is None:
            pendientes = compuertas_riesgo_aumento(
                exp, fecha_syntage=_fecha_syntage(exp["folio"]))
            detiene = pendientes[0] if pendientes else "listo para correr el modelo"
        else:
            pendientes = compuertas_cierre_aumento(exp)
            detiene = (pendientes[0] if pendientes
                       else "listo para cerrar")

        filas.append({
            "folio": exp["folio"],
            "cliente": (exp.get("cliente", {}).get("validado", {})
                        .get("razon_social") or "—"),
            "vigente": ronda.get("linea_previa"),
            "solicitado": ronda.get("monto_solicitado"),
            "score": ronda.get("riesgo", {}).get("score"),
            "dias": dias,
            "detiene": detiene,
        })

    if not filas:
        titulo("Aumentos de linea")
        print("  No hay rondas de aumento abiertas.")
        return 0

    filas.sort(key=lambda f: -(f["dias"] or 0))
    titulo("Aumentos de linea — %d ronda(s) abierta(s)" % len(filas))
    print("  %-10s %-26s %11s %11s %6s %5s %s"
          % ("FOLIO", "CLIENTE", "VIGENTE", "SOLICITADO", "SCORE", "DIAS",
             "QUE LO DETIENE"))
    print("  " + "-" * 108)
    for f in filas:
        print("  %-10s %-26s %11s %11s %6s %5s %s"
              % (f["folio"], f["cliente"][:26],
                 format(float(f["vigente"] or 0), ",.0f"),
                 format(float(f["solicitado"] or 0), ",.0f"),
                 "—" if f["score"] is None else "%.2f" % f["score"],
                 "—" if f["dias"] is None else f["dias"],
                 f["detiene"][:44]))
    return 0
```

- [ ] **Step 2: Verificar a mano**

Run: `python nea.py aumento tablero`
Expected: si no hay rondas abiertas, imprime "No hay rondas de aumento abiertas." y sale con 0. Sin traza de Python y sin exigir Supabase.

- [ ] **Step 3: Correr la compuerta del proyecto**

Run: `python tests/todas.py`
Expected: exit code 0

- [ ] **Step 4: Actualizar la documentación de operación**

En `OPERAR.md`, agregar una sección nueva al final, antes de "Si algo se rompe":

```markdown
## Un aumento de linea

Un cliente que ya opera y pide mas linea no firma contrato nuevo. Lo que se
actualiza es Syntage, el buro, y el uso de su tarjeta.

Si el cliente es anterior a la plataforma y no tiene folio, primero se abre su
expediente. La CSF se baja de Syntage:

```bash
python nea.py nuevo "C:\ruta\csf.pdf" --heredado
```

Despues, la ronda:

```bash
python nea.py aumento nuevo DEMO-01 120000 --linea-actual 80000
python nea.py uso DEMO-01 "C:\ruta\uso.xlsx"
python nea.py aumento estado DEMO-01
python nea.py aumento riesgo DEMO-01
```

`uso` lee el Excel que sale de consultar la base de la plataforma y **cuadra el
saldo de cada ciclo antes de guardarlo**: si no cierra, no se guarda. De ahi
salen los atrasos, que no se capturan a mano.

Los estados de cuenta bancarios **no** se piden, salvo que el incremento pase los
$150,000. Si por el caso concreto los quieres pedir de todos modos:

```bash
python nea.py aumento excepcion-banco DEMO-01
```

Pregunta el motivo y quien lo decide, y los queda pidiendo en esa ronda. Es una
decision con nombre, no una condicion que el sistema deduzca.

Cuando la autorizacion llegue por correo o WhatsApp:

```bash
python nea.py aumento cerrar DEMO-01 --aprobado 120000 --evidencia "C:\ruta\captura.png"
```

Si se aprobo menos de lo solicitado, hace falta tambien la cotizacion nueva:

```bash
python nea.py aumento cerrar DEMO-01 --aprobado 90000 \
    --evidencia "C:\ruta\captura.png" \
    --cotizacion-aprobada "C:\ruta\cotizacion_90k.pdf"
```

Para ver todas las rondas abiertas:

```bash
python nea.py aumento tablero
```
```

- [ ] **Step 5: Commit**

```bash
git add nea.py OPERAR.md
git commit -m "Las rondas de aumento tienen su propio tablero"
```

---

## Riesgos y puntos de atención

**Lo que puede no calzar con el código real.** Estas tres cosas se verificaron leyendo el repo, pero el que ejecute debe confirmarlas en el primer paso que las toque, y ajustar sin cambiar el diseño:

1. `insumos_riesgo.armar(exp)` se usa en la Tarea 9 asumiendo que devuelve `{"perfil", "buro", "declaracion", "cuentas"}`, que es la forma que `cmd_riesgo` ya consume. Si la firma real difiere, se adapta la llamada — no la función.
2. `_fecha_syntage` asume una tabla `syntage_crudo` con columnas `folio` y `creado_el`. `syntage.guardar_crudo()` es quien la escribe; confirmar el nombre real de tabla y columna ahí antes de la Tarea 9.
3. `preguntar` y `preguntar_monto` existen en `nea.py` y se usan tal cual. `preguntar(..., obligatorio=True)` se usa en la Tarea 9 con la firma que ya tiene `cmd_nuevo`.

**Lo que es política de crédito y no técnica.** Los números de las Tareas 6 y 7 son decisiones de negocio, ya aprobadas en la especificación pero fáciles de mover después: la escala de atrasos, los ajustes de reincidencia y proporción, los cortes de usuarios y utilización, y los cinco pesos por módulo. Cambiarlos es editar una tabla, no reescribir lógica — y cuando se cambien hay que subir `VERSION_AUMENTO`, porque un score viejo se calculó con otras reglas.

**Lo que este plan deja fuera** (de la especificación, sin cambio): conectar la base de la plataforma directamente, descargar la CSF desde la API de Syntage, un comando de autorización, y el front.
