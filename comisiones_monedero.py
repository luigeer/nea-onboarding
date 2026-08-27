# -*- coding: utf-8 -*-
"""
comisiones_monedero.py — ¿Cuánto le cobra el monedero al cliente?
=============================================================================
La comisión NO viene en el CFDI de estado de cuenta de combustible. Ese CFDI
—el que `estaciones_monedero.plan_descarga()` manda descargar— trae las cargas
y las estaciones, y su subtotal es simbólico ($1). La comisión llega en
facturas aparte del mismo emisor, y por eso se saca de la API de Syntage: no
está en los archivos descargados.

Se comprobó con datos reales: sobre 17 clientes y $2.47M de combustible, los
CFDI descargados solo revelaban $22.20 de comisión. Un solo cliente de esos,
consultado en Syntage, tiene **909 facturas** de su monedero y paga entre
$20,000 y $29,000 al mes.

**Por qué clasificar y no sumar.** Los monederos facturan su comisión con
textos que no comparten ni una palabra entre sí, y algunos de esos textos son
trampas. Del barrido de las 909 facturas de un cliente real:

    SERVICIO ADMINISTRATIVO                       285 veces   $516,418
    Comisión                                      175 veces    $35,368
    NO EXISTE COMISION POR RAZONES COMERCIALES    172 veces       $172
    CARGO DE COMISION                             150 veces   $139,954
    CARGO POR EMISION DE PLÁSTICO                  46 veces    $24,691

El tercer renglón contiene la palabra "COMISION" y dice justo lo contrario:
un buscador por subcadena lo cobraría como comisión. Y "SERVICIO
ADMINISTRATIVO", que no la contiene, es el renglón más grande de todos.

**Por qué categorías y no un número.** Dónde termina la comisión y empieza el
servicio aparte es una decisión de negocio, no técnica, y mueve el resultado
casi 4× (en el cliente más grande: 1.20%, 4.37% o 4.80%). Así que se reportan
por separado y se decide en la negociación:

- `explicita`      — se llama comisión con su nombre.
- `administrativa` — se cobra por administrar o dispersar el dinero.
                     Comisión con otro nombre; en el cliente más grande es el
                     renglón mayor de todos.
- `otros`          — servicios que sí son aparte: plásticos, tarjetas,
                     envíos, anualidad, inscripción.
- `fondeo`         — **el dinero, no un cargo.**

**La distinción que sostiene todo: `fondeo`.** Las facturas del monedero
incluyen el saldo que se carga a las tarjetas ("CARGA DE SALDOS",
"HABILITACIÓN DE RECURSOS", "DISPERSION" a secas). Contarlo como cargo daba
comisiones de 3,090%: un cliente real mueve $4.5 millones por su monedero y
paga $68 mil de comisión. Y el filo del cuchillo está en una palabra —
"DISPERSION" es el dinero ($2,197,500 en un caso real), "CARGO POR
DISPERSION" es la cuota por moverlo ($254 en promedio).

**Por qué el porcentaje va sobre el fondeo y no sobre el combustible.** Un
monedero cobra un % del dinero que mueve, y ese dinero puede no ser gasolina:
un cliente carga $2.4M de vales de restaurante, $2.0M de despensa y $73 mil
de gasolina con el mismo monedero. Dividir su comisión entre el combustible
que se midió en los XML —dos o tres meses— le atribuye al combustible una
comisión que es de otro producto. Por eso también se reporta
`proporcion_combustible`: qué parte del fondeo sí es gasolina.

Además se cuenta cuántas veces el monedero declaró explícitamente que NO
cobra comisión (`declara_cero`): es un dato de negociación, no un cero.

Uso:
    python comisiones_monedero.py cliente <RFC_CLIENTE> <RFC_MONEDERO>
"""

import json
import os
import re

import estaciones_monedero
import syntage

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_CACHE = os.path.join(RAIZ, "out", "comisiones")

CATEGORIAS = ("explicita", "administrativa", "otros", "fondeo")

# Se sube cada vez que cambia la forma del desglose o la clasificación. Un
# caché escrito con una versión anterior se descarta y se vuelve a pedir:
# pasó de verdad —se separó el fondeo de los cargos y el caché en disco
# seguía con el desglose viejo—, y leerlo habría dado porcentajes
# equivocados sin un solo aviso.
VERSION_CACHE = 2

# El texto que niega la comisión, aunque contenga la palabra. Se revisa
# ANTES que cualquier otra regla: es la única forma de no cobrarlo.
RE_DECLARA_CERO = re.compile(r"no\s+existe\s+comisi[oó]n", re.IGNORECASE)

# La cuota por dispersar, que NO es lo mismo que el dinero dispersado. Se
# revisa antes que RE_FONDEO porque "CARGO POR DISPERSION" contiene
# "DISPERSION": en datos reales la cuota promedia $254 y el dinero
# $2,197,500. Una palabra de diferencia, tres órdenes de magnitud.
RE_CUOTA_DISPERSION = re.compile(r"cargo\s+(de|por)\s+dispersi[oó]n", re.IGNORECASE)

# FONDEO: el dinero que se carga a las tarjetas, no un cargo. Es la
# distinción que sostiene todo este módulo — contar el fondeo como cargo
# producía comisiones de 3,090%, porque un cliente puede mover $4.5 millones
# por su monedero y pagar $68 mil de comisión.
RE_FONDEO = re.compile(
    r"carga\s+de\s+saldos|habilitaci[oó]n\s+de\s+recursos"
    r"|^dispersi[oó]n$|consumos?\s+de\s+combustible", re.IGNORECASE)

# Comisión dicha con su nombre. Se ancla al inicio para no atrapar textos
# donde "comisión" aparece de pasada dentro de otra cosa.
RE_EXPLICITA = re.compile(r"^(cargo\s+(de|por)\s+)?comisi[oó]n", re.IGNORECASE)

# Comisión con otro nombre: lo que se cobra por administrar el dinero. No
# incluye "servicio de entrega" ni "servicio de emisión", que son servicios
# de verdad — de ahí que se exija la palabra "administrativ".
RE_ADMINISTRATIVA = re.compile(r"administrativ", re.IGNORECASE)

# Qué producto se fondeó. Solo se afirma cuando el concepto lo dice: un
# "DISPERSION" a secas no revela si fue gasolina o despensa, y suponerlo
# atribuiría al combustible una comisión que es de otro producto.
RE_COMBUSTIBLE = re.compile(
    r"gasolina|diesel|dies[eé]l|combustible|magna|premium", re.IGNORECASE)


def clasificar(descripcion):
    """La categoría de un concepto de factura: 'explicita', 'administrativa',
    'otros', 'fondeo' o 'declara_cero'. Ver el encabezado del módulo para el
    por qué de cada una. El orden de las reglas importa: 'CARGO POR
    DISPERSION' tiene que resolverse antes que 'DISPERSION'."""
    texto = (descripcion or "").strip()
    if RE_DECLARA_CERO.search(texto):
        return "declara_cero"
    if RE_CUOTA_DISPERSION.search(texto):
        return "administrativa"
    if RE_FONDEO.search(texto):
        return "fondeo"
    if RE_EXPLICITA.search(texto):
        return "explicita"
    if RE_ADMINISTRATIVA.search(texto):
        return "administrativa"
    return "otros"


def es_combustible(descripcion):
    """¿Este concepto de fondeo dice que es de combustible? Solo se afirma
    cuando el texto lo nombra: un cliente puede mover $4.5M por su monedero y
    que apenas $73 mil sea gasolina — el resto despensa y restaurante. Sin
    esta separación, su comisión se le atribuye al combustible cuando en
    realidad es de otro producto."""
    return bool(RE_COMBUSTIBLE.search((descripcion or "").strip()))


def _cero():
    d = {c: 0.0 for c in CATEGORIAS}
    d["fondeo_combustible"] = 0.0
    return d


def desglosar(facturas):
    """Los montos por mes y por categoría de una lista de facturas de
    Syntage, más el desglose por concepto.

    Solo cuentan las facturas de tipo "I" (Ingreso). Un "P" (Complemento de
    Pago) es el recibo de algo ya facturado —contarlo duplicaría la
    comisión— y un "E" (nota de crédito) cancela en vez de cobrar.

    El monto de cada concepto es el del CONCEPTO, nunca el subtotal de la
    factura: la comisión suele venir dentro de una factura de dispersión de
    cientos de miles de pesos."""
    meses = {}
    total = _cero()
    conceptos = {}
    declara_cero = 0

    for f in facturas:
        if f.get("type") != "I":
            continue
        issued_at = f.get("issuedAt") or ""
        mes = estaciones_monedero._mes_facturacion(issued_at) if issued_at else None
        for item in f.get("items") or []:
            descripcion = (item.get("description") or "").strip()
            categoria = clasificar(descripcion)
            try:
                monto = float(item.get("totalAmount") or 0)
            except (TypeError, ValueError):
                continue
            if categoria == "declara_cero":
                declara_cero += 1
                continue
            if monto <= 0:
                continue
            if mes:
                meses.setdefault(mes, _cero())[categoria] += monto
            total[categoria] += monto
            if categoria == "fondeo" and es_combustible(descripcion):
                if mes:
                    meses[mes]["fondeo_combustible"] += monto
                total["fondeo_combustible"] += monto
            c = conceptos.setdefault(descripcion, {
                "descripcion": descripcion,
                "categoria": categoria,
                "veces": 0,
                "monto": 0.0,
            })
            c["veces"] += 1
            c["monto"] += monto

    for m in meses.values():
        for k in m:
            m[k] = round(m[k], 2)
    for k in total:
        total[k] = round(total[k], 2)
    for c in conceptos.values():
        c["monto"] = round(c["monto"], 2)

    fondeo = total["fondeo"]
    comision = total["explicita"] + total["administrativa"]
    cargos = comision + total["otros"]

    return {
        "meses": meses,
        "total": total,
        "conceptos": sorted(conceptos.values(), key=lambda c: -c["monto"]),
        "version": VERSION_CACHE,
        "declara_cero": declara_cero,
        # Los porcentajes que sirven para comparar pricing: los cargos sobre
        # el FONDEO, que es como cobra un monedero (un % del dinero que
        # mueve). No sobre el combustible medido en los XML: esos son dos o
        # tres meses, y el fondeo puede ser de otro producto.
        "pct_sobre_fondeo": (cargos / fondeo) if fondeo else None,
        "pct_comision_sobre_fondeo": (comision / fondeo) if fondeo else None,
        "proporcion_combustible": ((total["fondeo_combustible"] / fondeo)
                                   if fondeo else None),
        "error": None,
    }


def _vacio(error=None):
    return {"meses": {}, "total": _cero(), "conceptos": [],
            "declara_cero": 0, "pct_sobre_fondeo": None,
            "pct_comision_sobre_fondeo": None, "proporcion_combustible": None,
            "error": error}


def _ruta_cache(carpeta, rfc_cliente, rfc_monedero):
    return os.path.join(carpeta, "%s_%s.json" % (rfc_cliente, rfc_monedero))


def _leer_cache(ruta):
    """El desglose guardado, o None si no se puede usar — porque lo escribió
    una versión anterior del clasificador o porque el archivo está roto. Un
    caché viejo no se corrige a medias: se vuelve a pedir completo."""
    try:
        with open(ruta, encoding="utf-8") as fh:
            guardado = json.load(fh)
    except (ValueError, OSError):
        return None
    if guardado.get("version") != VERSION_CACHE:
        return None
    return guardado


def _de_cliente(rfc_cliente, rfc_monedero):
    """El desglose de un (cliente, monedero) leído de Syntage. Un cliente que
    Syntage no conoce, o al que no se puede consultar, se anota con el motivo
    y devuelve ceros: el barrido de los demás no se tira por uno."""
    try:
        eid = syntage.id_entidad(rfc_cliente)
    except LookupError:
        return _vacio("no está dado de alta en Syntage")
    except Exception as e:
        return _vacio("no se pudo resolver la entidad (%s)" % e)
    try:
        facturas = syntage.facturas(eid, rfc_monedero)
    except Exception as e:
        return _vacio("sin acceso a las facturas (%s)" % e)
    return desglosar(facturas)


def recolectar(pares, carpeta=None, refrescar=False, aviso=None):
    """{(rfc_cliente, rfc_monedero): desglose} para cada par, con caché en
    disco.

    El caché no es una optimización de lujo: un solo cliente grande tiene 909
    facturas de su monedero, y el barrido completo de la cartera tarda
    minutos. Sin él, cada corrida del reporte vuelve a pedirle todo a la API.

    `aviso` es una función opcional que recibe un texto de progreso — sirve
    para que la terminal muestre en qué cliente va sin que este módulo
    imprima nada por su cuenta."""
    carpeta = carpeta or CARPETA_CACHE
    os.makedirs(carpeta, exist_ok=True)
    resultado = {}
    for rfc_cliente, rfc_monedero in pares:
        ruta = _ruta_cache(carpeta, rfc_cliente, rfc_monedero)
        if not refrescar and os.path.exists(ruta):
            guardado = _leer_cache(ruta)
            if guardado is not None:
                resultado[(rfc_cliente, rfc_monedero)] = guardado
                continue
        if aviso:
            aviso("consultando %s / %s" % (rfc_cliente, rfc_monedero))
        desglose = _de_cliente(rfc_cliente, rfc_monedero)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(desglose, fh, ensure_ascii=False, indent=2)
        resultado[(rfc_cliente, rfc_monedero)] = desglose
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
def main(argv):
    if len(argv) < 4 or argv[1] != "cliente":
        print("Uso: python comisiones_monedero.py cliente <RFC_CLIENTE> <RFC_MONEDERO>")
        return 1

    rfc_cliente, rfc_monedero = argv[2].upper(), argv[3].upper()
    d = recolectar([(rfc_cliente, rfc_monedero)],
                   aviso=lambda t: print(t))[(rfc_cliente, rfc_monedero)]
    if d["error"]:
        print("No se pudo consultar: %s" % d["error"])
        return 1

    print("\nConceptos que factura %s a %s:" % (rfc_monedero, rfc_cliente))
    print("  %-46s %-16s %5s %14s" % ("concepto", "categoría", "veces", "monto"))
    for c in d["conceptos"]:
        print("  %-46s %-16s %5d %14s" % (
            c["descripcion"][:46], c["categoria"], c["veces"],
            format(c["monto"], ",.2f")))

    print("\n  %-16s %14s" % ("TOTAL explícita", format(d["total"]["explicita"], ",.2f")))
    print("  %-16s %14s" % ("+ administrativa", format(d["total"]["administrativa"], ",.2f")))
    print("  %-16s %14s" % ("+ otros cargos", format(d["total"]["otros"], ",.2f")))
    if d["declara_cero"]:
        print("\n  %d factura(s) declaran explícitamente que NO cobran comisión."
              % d["declara_cero"])

    print("\nPor mes (%d meses):" % len(d["meses"]))
    for mes in sorted(d["meses"]):
        m = d["meses"][mes]
        print("  %s  explícita %12s  administrativa %12s  otros %10s" % (
            mes, format(m["explicita"], ",.2f"), format(m["administrativa"], ",.2f"),
            format(m["otros"], ",.2f")))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
