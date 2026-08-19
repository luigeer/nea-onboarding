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

from datetime import date

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
