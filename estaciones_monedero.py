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
