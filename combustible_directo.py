# -*- coding: utf-8 -*-
"""
combustible_directo.py — Gasolina comprada sin monedero de por medio
=============================================================================
Hay clientes que no usan monedero: le compran la gasolina **directo** a una
gasolinera, factura por factura, con los litros y el precio en los conceptos.
Se descubrió al buscar los estados de cuenta que faltaban de cinco clientes:
dos de ellos —$1.1 millones de combustible entre los dos— no tenían ninguno
porque nunca tuvieron monedero.

**Por qué se veían como clientes de monedero.** El emisor que les factura
está en el padrón del SAT de emisores de monedero (`monederos.PADRON`):
es una gasolinera que *además* tiene monedero de marca. Ese es exactamente el
caso que `estaciones_monedero.py` fue escrito para no confundir, pero visto
desde el otro lado — ahí la pregunta era "¿este CFDI simbólico es un estado
de cuenta?"; aquí es "¿estas facturas con litros son compra directa?".

**Este análisis va APARTE del de monederos, a propósito.** Son dos negocios
distintos: a un cliente de monedero se le compite con pricing de comisión; a
uno que compra directo se le compite con la red de estaciones. Mezclarlos en
la misma tabla haría ver un cliente sin comisión como si tuviera comisión
cero, y sumaría al ranking de estaciones de monedero un volumen que nunca
pasó por un monedero.

**La estación se identifica por permiso CRE, no por RFC del emisor.** Un solo
emisor factura por 35 permisos distintos en datos reales: agrupar por RFC
juntaría 35 gasolineras en un renglón. El permiso viene en
`identificationNumber` de cada concepto ("PL/1443/EXP/ES/2015 - 322059").

**La detección va por la clave del SAT, no por el texto.** `MAGNA`,
`PREMIUM` y `PEMEX DIESEL` son las descripciones de hoy, pero la clave
(`ClaveProdServ`) es catálogo: 15101514 magna, 15101515 premium, 15101505
diesel — toda la serie 1510 son combustibles. La unidad NO sirve de filtro:
49 de 410 conceptos reales traen `unitCode` "10" en vez de "LTR", con la
misma clave y la misma descripción.

Uso:
    python combustible_directo.py cliente <RFC_CLIENTE> <RFC_GASOLINERA>
"""

import json
import os

import estaciones_monedero
import syntage

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_CACHE = os.path.join(RAIZ, "out", "combustible_directo")

# Se sube cuando cambia la forma del desglose: un caché escrito por una
# versión anterior se descarta en vez de producir números mal en silencio.
VERSION_CACHE = 1

# La serie 1510 del catálogo ClaveProdServ del SAT son los combustibles.
# Los lubricantes viven en 1512, así que el prefijo no los atrapa.
PREFIJO_COMBUSTIBLE = "1510"


def es_combustible(item):
    """¿Este concepto de factura es una carga de combustible? Manda la clave
    del SAT, no la descripción ni la unidad. Y se exige cantidad: un concepto
    sin litros no es una carga que se pueda medir."""
    clave = str((item or {}).get("productIdentification") or "")
    if not clave.startswith(PREFIJO_COMBUSTIBLE):
        return False
    try:
        return float(item.get("quantity") or 0) > 0
    except (TypeError, ValueError):
        return False


def _permiso(item):
    """El permiso CRE de la estación, sin el folio de la operación que va
    después del guion: 'PL/1443/EXP/ES/2015 - 322059' -> 'PL/1443/EXP/ES/2015'."""
    return ((item.get("identificationNumber") or "").split(" - ")[0]).strip()


def _precio(importe, litros):
    return (importe / litros) if litros else None


def desglosar(facturas):
    """Lo que un emisor le facturó de combustible a un cliente: totales, por
    mes y por estación (permiso CRE).

    Se descartan las facturas que no son de ingreso (un complemento de pago no
    es una compra) y las que Syntage detectó pero no tiene: `xml: False`
    significa que el documento nunca se extrajo, y sus montos vienen vacíos —
    contarlas sumaría ceros que se ven como datos."""
    facturas_usadas = 0
    litros = importe = 0.0
    meses = {}
    estaciones = {}

    for f in facturas:
        if f.get("type") != "I" or not f.get("xml"):
            continue
        conceptos = [i for i in (f.get("items") or []) if es_combustible(i)]
        if not conceptos:
            continue
        facturas_usadas += 1
        issued_at = f.get("issuedAt") or ""
        mes = (estaciones_monedero._mes_facturacion(issued_at)
               if issued_at else None)
        rfc_emisor = ((f.get("issuer") or {}).get("rfc")) or None

        for i in conceptos:
            l = float(i.get("quantity") or 0)
            m = float(i.get("totalAmount") or 0)
            litros += l
            importe += m
            if mes:
                x = meses.setdefault(mes, {"litros": 0.0, "importe": 0.0, "cargas": 0})
                x["litros"] += l
                x["importe"] += m
                x["cargas"] += 1
            clave = (rfc_emisor, _permiso(i))
            e = estaciones.setdefault(clave, {
                "rfc_emisor": clave[0],
                "permiso": clave[1],
                "nombre_emisor": (f.get("issuer") or {}).get("name"),
                "cargas": 0,
                "litros": 0.0,
                "importe": 0.0,
                "combustibles_set": set(),
                "meses_set": set(),
            })
            e["cargas"] += 1
            e["litros"] += l
            e["importe"] += m
            if i.get("description"):
                e["combustibles_set"].add((i.get("description") or "").strip())
            if mes:
                e["meses_set"].add(mes)

    filas_estaciones = [{
        "rfc_emisor": e["rfc_emisor"],
        "permiso": e["permiso"],
        "nombre_emisor": e["nombre_emisor"],
        "cargas": e["cargas"],
        "litros": round(e["litros"], 2),
        "importe": round(e["importe"], 2),
        "precio_litro": _precio(e["importe"], e["litros"]),
        "combustibles": sorted(e["combustibles_set"]),
        "meses_activos": len(e["meses_set"]),
    } for e in estaciones.values()]
    filas_estaciones.sort(key=lambda f: -f["importe"])

    for x in meses.values():
        x["litros"] = round(x["litros"], 2)
        x["importe"] = round(x["importe"], 2)

    return {
        "version": VERSION_CACHE,
        "facturas": facturas_usadas,
        "litros": round(litros, 2),
        "importe": round(importe, 2),
        "precio_litro": _precio(importe, litros),
        "meses": meses,
        "estaciones": filas_estaciones,
        "error": None,
    }


def _vacio(error=None):
    return {"version": VERSION_CACHE, "facturas": 0, "litros": 0.0,
            "importe": 0.0, "precio_litro": None, "meses": {},
            "estaciones": [], "error": error}


def _ruta_cache(carpeta, rfc_cliente, rfc_emisor):
    return os.path.join(carpeta, "%s_%s.json" % (rfc_cliente, rfc_emisor))


def _leer_cache(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            guardado = json.load(fh)
    except (ValueError, OSError):
        return None
    if guardado.get("version") != VERSION_CACHE:
        return None
    return guardado


def _de_cliente(rfc_cliente, rfc_emisor):
    try:
        eid = syntage.id_entidad(rfc_cliente)
    except LookupError:
        return _vacio("no está dado de alta en Syntage")
    except Exception as e:
        return _vacio("no se pudo resolver la entidad (%s)" % e)
    try:
        facturas = syntage.facturas(eid, rfc_emisor)
    except Exception as e:
        return _vacio("sin acceso a las facturas (%s)" % e)
    return desglosar(facturas)


def recolectar(pares, carpeta=None, refrescar=False, aviso=None):
    """{(rfc_cliente, rfc_emisor): desglose} para cada par, con caché en
    disco. Mismo patrón que `comisiones_monedero.recolectar()`: un cliente
    grande tiene cientos de facturas y el barrido tarda minutos."""
    carpeta = carpeta or CARPETA_CACHE
    os.makedirs(carpeta, exist_ok=True)
    resultado = {}
    for rfc_cliente, rfc_emisor in pares:
        ruta = _ruta_cache(carpeta, rfc_cliente, rfc_emisor)
        if not refrescar and os.path.exists(ruta):
            guardado = _leer_cache(ruta)
            if guardado is not None:
                resultado[(rfc_cliente, rfc_emisor)] = guardado
                continue
        if aviso:
            aviso("consultando %s / %s" % (rfc_cliente, rfc_emisor))
        desglose = _de_cliente(rfc_cliente, rfc_emisor)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(desglose, fh, ensure_ascii=False, indent=2)
        resultado[(rfc_cliente, rfc_emisor)] = desglose
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
def main(argv):
    if len(argv) < 4 or argv[1] != "cliente":
        print("Uso: python combustible_directo.py cliente <RFC_CLIENTE> "
              "<RFC_GASOLINERA>")
        return 1

    rfc_cliente, rfc_emisor = argv[2].upper(), argv[3].upper()
    d = recolectar([(rfc_cliente, rfc_emisor)],
                   aviso=lambda t: print(t))[(rfc_cliente, rfc_emisor)]
    if d["error"]:
        print("No se pudo consultar: %s" % d["error"])
        return 1

    print("\n%d factura(s) de combustible directo | %s litros | $%s | $%s/litro"
          % (d["facturas"], format(d["litros"], ",.2f"),
             format(d["importe"], ",.2f"),
             format(d["precio_litro"] or 0, ",.3f")))

    print("\nPor estación (permiso CRE):")
    print("  %-24s %10s %14s %10s %7s  %s" % (
        "permiso", "litros", "importe", "$/litro", "cargas", "combustibles"))
    for e in d["estaciones"]:
        print("  %-24s %10s %14s %10s %7d  %s" % (
            e["permiso"] or "(sin permiso)", format(e["litros"], ",.2f"),
            format(e["importe"], ",.2f"), format(e["precio_litro"] or 0, ",.3f"),
            e["cargas"], ", ".join(e["combustibles"])[:30]))

    print("\nPor mes:")
    for mes in sorted(d["meses"]):
        m = d["meses"][mes]
        print("  %s  %10s litros  %14s  %d carga(s)" % (
            mes, format(m["litros"], ",.2f"), format(m["importe"], ",.2f"),
            m["cargas"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
