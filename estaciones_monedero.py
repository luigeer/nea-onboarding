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

from datetime import date, datetime, timedelta

import syntage

UMBRAL_MONTO_SIMBOLICO = 50.0

# Mexico no tiene horario de verano desde 2022: restar un offset fijo de 6
# horas basta para pasar de UTC a hora de Ciudad de Mexico, sin necesidad de
# zoneinfo/pytz (que este repo no usa en ningún otro lado).
_OFFSET_MEXICO = timedelta(hours=6)


def _mes_facturacion(issued_at):
    """El mes real de facturación, en hora local de Ciudad de México — no el
    mes que nombra el string UTC que entrega Syntage. Se confirmó contra
    datos reales: Efecticard emite su estado de cuenta a las 23:59:59 hora
    local del último día del mes cubierto, que en UTC ya cae en el primer
    minuto del mes SIGUIENTE (23:59:59 CST = 05:59:59 UTC del día 1).
    Truncar el string UTC sin convertir etiquetaría esa factura con el mes
    equivocado."""
    dt_utc = datetime.strptime(issued_at, "%Y-%m-%d %H:%M:%S")
    return (dt_utc - _OFFSET_MEXICO).strftime("%Y-%m")


def facturas_candidatas(entidad_id, rfc_monedero):
    """Facturas de ese RFC a esta entidad cuyo subtotal es simbólico: la
    señal de que es una factura de servicio de monedero, no una compra
    real de combustible."""
    candidatas = []
    for f in syntage.facturas(entidad_id, rfc_monedero):
        if (f.get("subtotal") or 0) < UMBRAL_MONTO_SIMBOLICO:
            issued_at = f.get("issuedAt") or ""
            candidatas.append({
                "mes": _mes_facturacion(issued_at) if issued_at else "",
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
    últimos `ventana` meses? `por_mes` trae, para cada mes de la ventana que
    sí tiene candidata, la LISTA completa de candidatas de ese mes —no solo
    la primera—: dos tipos distintos de CFDI simbólico del mismo emisor
    pueden caer en el mismo mes (p.ej. el cargo administrativo normal y una
    comisión aparte por fondos insuficientes), y quedarse con la primera
    arbitrariamente podría descartar en silencio la que sí trae el
    complemento de combustible."""
    meses_ventana = set(_ultimos_n_meses(hoy, ventana))
    por_mes = {}
    for c in candidatas:
        if c["mes"] in meses_ventana:
            por_mes.setdefault(c["mes"], []).append(c)
    return len(por_mes) >= minimo, por_mes


def _fecha_ancla(entidad_id, hoy):
    """La ventana de "últimos N meses" se ancla a cuándo Syntage actualizó
    por última vez a esta entidad, no a hoy. Se descubrió corriendo el
    barrido real: varios clientes grandes tienen credencial vigente pero
    llevan semanas o meses sin que Syntage vuelva a extraer sus datos —
    anclar a "hoy" los descarta a todos aunque su patrón de monedero siga
    intacto en los datos que sí existen. Si no se puede saber (entidad de
    prueba, falla de red), se usa hoy — el comportamiento de siempre."""
    try:
        fechas = [c.get("actualizada") for c in syntage.estado_credenciales(entidad_id)
                  if c.get("actualizada")]
    except Exception:
        return hoy
    if not fechas:
        return hoy
    try:
        ancla = datetime.strptime(max(fechas)[:10], "%Y-%m-%d").date()
    except ValueError:
        return hoy
    return min(ancla, hoy)


def plan_descarga(clientes, hoy=None):
    """clientes: la salida de monederos.barrer_entidades_syntage() (ya con
    entidad_id en cada resultado). Devuelve (plan, sin_revisar):

    - plan: exactamente qué facturas descargar a mano: cliente, monedero,
      mes, folio fiscal — solo para los (cliente, monedero) que de verdad
      confirman el patrón de monedero real. Un mes con más de una candidata
      simbólica (ver confirmar_monedero_real) aporta un renglón por cada
      una, no uno solo.
    - sin_revisar: los (cliente, monedero) que no se pudieron revisar porque
      Syntage truena a media consulta (p.ej. una respuesta truncada) —
      mismo patrón que monederos.analizar_cliente(): se anota el motivo y
      se sigue con el resto, en vez de tirar todo el barrido ya hecho.

    La ventana de "últimos 3 meses" se ancla, por cliente, a la fecha de su
    última extracción en Syntage (ver _fecha_ancla) — no a `hoy` a secas."""
    hoy = hoy or date.today()
    plan = []
    sin_revisar = []
    for cliente in clientes:
        ancla = _fecha_ancla(cliente["entidad_id"], hoy)
        for h in cliente.get("hallazgos", []):
            try:
                candidatas = facturas_candidatas(cliente["entidad_id"], h["rfc_monedero"])
            except syntage.ErrorSyntage as e:
                sin_revisar.append({
                    "rfc_cliente": cliente["rfc"],
                    "nombre_cliente": cliente.get("nombre"),
                    "rfc_monedero": h["rfc_monedero"],
                    "nombre_monedero": h["nombre_comercial"],
                    "motivo": "sin acceso a facturas (%s)" % e,
                })
                continue
            es_real, por_mes = confirmar_monedero_real(candidatas, ancla)
            if not es_real:
                continue
            for mes, facturas in sorted(por_mes.items()):
                for factura in facturas:
                    plan.append({
                        "rfc_cliente": cliente["rfc"],
                        "nombre_cliente": cliente.get("nombre"),
                        "rfc_monedero": h["rfc_monedero"],
                        "nombre_monedero": h["nombre_comercial"],
                        "mes": mes,
                        "folio_fiscal": factura["folio_fiscal"],
                    })
    return plan, sin_revisar


def main(argv):
    import monederos

    if len(argv) < 2 or argv[1] != "plan":
        print("Uso: python estaciones_monedero.py plan")
        return 1

    clientes = monederos.barrer_entidades_syntage()
    plan, sin_revisar = plan_descarga(clientes)
    if not plan:
        print("Ningún (cliente, monedero) confirmó el patrón de monedero real todavía.")
    else:
        print("%d factura(s) por descargar a mano desde el panel de Syntage:\n" % len(plan))
        for p in plan:
            # Nombre exacto que espera estado_cuenta_monedero.py: se puede
            # copiar tal cual como nombre de archivo al guardar el PDF.
            nombre_archivo = "%s_%s_%s.pdf" % (p["rfc_cliente"], p["rfc_monedero"], p["mes"])
            print("%-40s %-30s folio %s" % (
                nombre_archivo, p["nombre_monedero"], p["folio_fiscal"]))
    if sin_revisar:
        print("\n%d (cliente, monedero) no se pudo revisar:" % len(sin_revisar))
        for s in sin_revisar:
            print("  %-14s %-30s %s" % (
                s["rfc_cliente"], s["nombre_monedero"], s["motivo"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
