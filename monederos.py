# -*- coding: utf-8 -*-
"""
monederos.py — ¿Qué clientes usan monedero electrónico de gasolina?
=====================================================================
Investigación de una sola pasada: cruzar a los proveedores de cada cliente
—que Syntage ya extrajo del SAT— contra el padrón público de emisores de
monedero electrónico de combustible autorizados por el SAT. Si un RFC de
proveedor aparece en el padrón, ese cliente le paga gasolina a un monedero, y
Syntage ya sabe cuánto y qué tan concentrado está ese gasto.

El padrón es dato público (RFC, nombre comercial y razón social del SAT), así
que sí puede vivir en este repo. Los RFC de los prospectos, no: por eso el
cruce se corre contra Supabase y el resultado se ve en pantalla, no se commitea.

Esto responde las primeras dos preguntas —¿usa monedero? ¿cuál?— con lo que ya
trae `supplier-concentration`. La comisión que cobra cada monedero se resuelve
con `estaciones_monedero.comision_candidatas()`: viene en un concepto de
factura aparte ("Cargo Administrativo") que sí expone la API de Syntage.

Uso:
    python monederos.py padron              lista el padrón completo
    python monederos.py cliente <RFC>        cruza un solo cliente contra el padrón
    python monederos.py todos                barre los folios con expediente en Supabase
    python monederos.py entidades            barre TODAS las entidades que Syntage conoce
                                              (incluye prospectos sin expediente todavía)
"""

import sys

import db
import syntage

# RFC, nombre(s) comercial(es), razón social y año de alta ante el SAT como
# emisor de monedero electrónico de combustible. Fuente: padrón público del
# SAT que el usuario compiló a mano; se transcribe tal cual.
PADRON = [
    {"rfc": "ATA191211GF3", "nombre_comercial": "MONEDERO ALTEC",
     "razon_social": "Alianza Tecnológica Avanzada Systems, S.A. de C.V.", "anio": 2026},
    {"rfc": "CCO230329KC2", "nombre_comercial": "MAS BENEFITS COMBUSTIBLE",
     "razon_social": "Clic Connect, S.A.P.I. de C.V.", "anio": 2026},
    {"rfc": "CIP2306125C8", "nombre_comercial": "clara fleet card",
     "razon_social": "Clara IP, S.A.P.I. de C.V.", "anio": 2026},
    {"rfc": "SIA030228F63", "nombre_comercial": "Go Tanque Lleno",
     "razon_social": "Sistema Inteligente de Administración del Sureste, S.A. de C.V.", "anio": 2025},
    {"rfc": "BFE150903SR1", "nombre_comercial": "Nexogaz",
     "razon_social": "Border Fuels and Energy, S.A. de C.V.", "anio": 2025},
    {"rfc": "DSM140213AM0", "nombre_comercial": "Obtén Más Combustible",
     "razon_social": "Dispersiones Sociales de México, S.A.P.I. de C.V.", "anio": 2023},
    {"rfc": "CBP200228JM9", "nombre_comercial": "Energy Point",
     "razon_social": "Controladora Burgos Plus, S.A. de C.V.", "anio": 2023},
    {"rfc": "MGA070920FIA", "nombre_comercial": "Abimerhi",
     "razon_social": "Mayorista de Gas, S.A. de C.V.", "anio": 2023},
    {"rfc": "SCI180314EQ4", "nombre_comercial": "TOKENGAS",
     "razon_social": "Sinmex Consorcio Inteligente, S.A. de C.V.", "anio": 2022},
    {"rfc": "TFM191231NA7", "nombre_comercial": "NEA CONTROL",
     "razon_social": "Grit Mobility, S.A. de C.V.", "anio": 2022},
    {"rfc": "SFS920210NY3", "nombre_comercial": "+Cargas",
     "razon_social": "Servicio Fácil del Sureste, S.A. de C.V.", "anio": 2022},
    {"rfc": "SCN170724GP6", "nombre_comercial": "CNG+ / TAP",
     "razon_social": "Sistema CNG, S.A. de C.V.", "anio": 2021},
    {"rfc": "BGM141113GEA", "nombre_comercial": "Shell Fleet Navigator",
     "razon_social": "Shell Solutions México, S.A. de C.V.", "anio": 2020},
    {"rfc": "IVA180321RH3", "nombre_comercial": "INTELYVALE GASOLINA",
     "razon_social": "Intely Vale, S.A.P.I. de C.V.", "anio": 2019},
    {"rfc": "IMP170425TP3", "nombre_comercial": "Inntec combustible",
     "razon_social": "Intec Medios de Pago, S.A. de C.V.", "anio": 2019},
    {"rfc": "VTO1508246S6", "nombre_comercial": "MINU Combustible",
     "razon_social": "Vale Total, S.A. de C.V.", "anio": 2018},
    {"rfc": "FIN080710J59", "nombre_comercial": "cobee",
     "razon_social": "Finutil, S.A. de C.V.", "anio": 2017},
    {"rfc": "PET150518QLA", "nombre_comercial": "PETROCARD",
     "razon_social": "Petrocard, S.A. de C.V.", "anio": 2016},
    {"rfc": "OSO101216GS5", "nombre_comercial": "ONE CARD GAS",
     "razon_social": "Ocsi Soluciones, S.A. de C.V.", "anio": 2015},
    {"rfc": "PTR080730J62", "nombre_comercial": "PREVIVALE BY GRUPOKLU COMBUSTIBLE",
     "razon_social": "Previsión del Trabajo, S.A. de C.V.", "anio": 2015},
    {"rfc": "EFE8908015L3",
     "nombre_comercial": "Efecticard / Efecticard Corporativo Vale Combustible / "
                          "Efecticard Combustible eCard / Efectitag Combustible Plus",
     "razon_social": "Efectivale, S. de R.L. de C.V.", "anio": 2015},
    {"rfc": "PME811211B20", "nombre_comercial": "Movilidad / Control Flota",
     "razon_social": "Pluxee México, S.A. de C.V.", "anio": 2015},
    {"rfc": "TIN090211JC9", "nombre_comercial": "Toka® Combustible / Toka Data Control",
     "razon_social": "Toka Internacional, S.A.P.I. de C.V.", "anio": 2015},
    {"rfc": "OPA010719SF0", "nombre_comercial": "Ecovale",
     "razon_social": "Operadora de Programas de Abasto Múltiple, S.A. de C.V.", "anio": 2015},
    {"rfc": "SBR130327HU9", "nombre_comercial": "TENGO",
     "razon_social": "Servicios Broxel, S.A.P.I. de C.V.", "anio": 2015},
    {"rfc": "PUN9810229R0",
     "nombre_comercial": "Gasolina Magna Fleet / Gasolina Premium Fleet / "
                          "Diesel Fleet / Gas L.P. Fleet",
     "razon_social": "Sí Vale México, S.A de C.V.", "anio": 2014},
    {"rfc": "RGE121004UK6", "nombre_comercial": "Recargas Energex",
     "razon_social": "Recargas Grupo Energéticos, S.A. de C.V.", "anio": 2013},
    {"rfc": "GFE9707075U3", "nombre_comercial": "MI MONEDERO FERCHEGAS",
     "razon_social": "Grupo Ferche, S.A. de C.V.", "anio": 2013},
    {"rfc": "NCO110519633", "nombre_comercial": "PowerGAS",
     "razon_social": "NX Control, S.A. de C.V.", "anio": 2012},
    {"rfc": "ASE930924SS7", "nombre_comercial": "Ticket Car Edenred",
     "razon_social": "Edenred México, S.A. de C.V.", "anio": 2012},
    {"rfc": "CIC011107RR1", "nombre_comercial": "GasoMatic",
     "razon_social": "Control Integral de Combustibles, S.A. de C.V.", "anio": 2011},
    {"rfc": "MEG1001294K5", "nombre_comercial": "Monedero electrónico Megasur",
     "razon_social": "Megasur, S.A. de C.V.", "anio": 2011},
    {"rfc": "ICI070810GM0", "nombre_comercial": "ICIGAS",
     "razon_social": "Ingeniería de Control Integral en Gasolineras, S.A. de C.V.", "anio": 2011},
    {"rfc": "GME080312617", "nombre_comercial": "GOSMO / TAG (anillo) GOSMO",
     "razon_social": "Gasngo México S.A. de C.V.", "anio": 2010},
    {"rfc": "PET040903DH1", "nombre_comercial": "Petro-7",
     "razon_social": "Petromax, S.A. de C.V.", "anio": 2009},
    {"rfc": "OSE060323UN7", "nombre_comercial": "La Caja",
     "razon_social": "Operadora y Servicios Empresariales PPA, S.A. de C.V.", "anio": 2009},
    {"rfc": "GEN050428H66", "nombre_comercial": "Enerkard",
     "razon_social": "Grupo Enerkom, S.A. de C.V.", "anio": 2007},
    {"rfc": "ERE010302IP6", "nombre_comercial": "ENERCARD",
     "razon_social": "Energéticos en Red Electrónica, S.A. de C.V.", "anio": 2006},
    {"rfc": "ONO9507278T4", "nombre_comercial": "Ultra Gas",
     "razon_social": "Orsan del Norte, S.A. de C.V.", "anio": 2006},
    {"rfc": "VME051118LM8", "nombre_comercial": "Punto Clave",
     "razon_social": "Vales y Monederos Electrónicos PUNTOCLAVE, S.A. de C.V.", "anio": 2006},
    {"rfc": "ESA930602UV1", "nombre_comercial": "Ultragas Control Card",
     "razon_social": "Estaciones de Servicio Auto, S.A. de C.V.", "anio": 2006},
    {"rfc": "ESE930624B79", "nombre_comercial": "Ultragas Control Card",
     "razon_social": "Estaciones de Servicio, S.A. de C.V.", "anio": 2006},
    {"rfc": "IUG990906214", "nombre_comercial": "Ultra Gas / Ultra Gas (TAG)",
     "razon_social": "Informática UG, S.A. de C.V.", "anio": 2006},
    {"rfc": "PIN990817EQ0", "nombre_comercial": "Vale Inbursa",
     "razon_social": "Promotora Inbursa, S.A. de C.V.", "anio": 2005},
    {"rfc": "CGP970522EE4", "nombre_comercial": "Hidrosina Plus / Hidrotag",
     "razon_social": "Consorcio Gasolinero Plus, S.A de C.V.", "anio": 2005},
    {"rfc": "TGA110411QF9", "nombre_comercial": "Transfer Gas",
     "razon_social": "Transfer Gas, S.A. de C.V.", "anio": 2005},
]

_PADRON_POR_RFC = {m["rfc"]: m for m in PADRON}


def detectar_monederos(proveedores):
    """De la lista de proveedores que da `supplier-concentration`, cuáles son
    monederos del padrón. `proveedores` trae la forma que Syntage devuelve:
    dicts con al menos `rfc`, `total` y `share` (`name` es el de Syntage, no
    el que se reporta — el hallazgo usa el nombre comercial del padrón)."""
    hallazgos = []
    for p in proveedores:
        rfc = (p.get("rfc") or "").upper()
        monedero = _PADRON_POR_RFC.get(rfc)
        if not monedero:
            continue
        hallazgos.append({
            "rfc_monedero": rfc,
            "nombre_comercial": monedero["nombre_comercial"],
            "razon_social_monedero": monedero["razon_social"],
            "monto": p.get("total"),
            "porcentaje_gasto": p.get("share"),
        })
    return hallazgos


def _rfc_de_expediente(datos):
    return ((datos.get("cliente") or {}).get("validado") or {}).get("rfc")


def _rfc_de_entidad_syntage(entidad):
    return (entidad.get("taxpayer") or {}).get("id")


_TAM_PAGINA_PROVEEDORES = 100  # el máximo que acepta el insight; pedir más truena con 400


def _proveedores_completos(eid):
    """Todos los proveedores de `supplier-concentration`, no solo el default.

    Sin `options[limit]`, Syntage devuelve nada más el top 10 por
    participación. Un monedero que le pesa poco al gasto total del cliente
    —el caso real de Efecticard en LOGISTICA FICTICIA, 0.05% del gasto entre
    1,200 proveedores— queda fuera en silencio si no se pagina hasta el final.
    """
    proveedores = []
    offset = 0
    while True:
        r = syntage.insight(eid, "supplier-concentration",
                            **{"options[limit]": _TAM_PAGINA_PROVEEDORES,
                               "options[offset]": offset})
        pagina = r.get("data") if isinstance(r, dict) else r
        pagina = pagina or []
        proveedores.extend(pagina)
        if len(pagina) < _TAM_PAGINA_PROVEEDORES:
            return proveedores
        offset += _TAM_PAGINA_PROVEEDORES


def analizar_cliente(rfc, entidad_id=None):
    """Cruza un cliente contra el padrón. Devuelve (hallazgos, estado);
    estado explica por qué no hay hallazgos cuando la causa no es de negocio
    —extracción a medias, sin acceso al insight, una falla de red a media
    respuesta— para no confundirlo con 'este cliente no usa monedero'."""
    try:
        completa, pendientes = syntage.extraccion_completa(rfc)
    except syntage.ErrorSyntage as e:
        return [], "sin acceso a extracciones (%s)" % e
    if not completa:
        return [], "extracción incompleta (%d recurso(s) pendiente(s))" % len(pendientes)

    try:
        eid = entidad_id or syntage.id_entidad(rfc)
    except LookupError:
        return [], "no está dado de alta en Syntage"
    except syntage.ErrorSyntage as e:
        return [], "sin acceso a la entidad (%s)" % e

    try:
        proveedores = _proveedores_completos(eid)
    except syntage.ErrorSyntage as e:
        return [], "sin acceso a concentración de proveedores (%s)" % e

    return detectar_monederos(proveedores), "ok"


def barrer_clientes(sb=None):
    """Recorre todos los folios de Supabase y cruza cada uno contra el padrón."""
    sb = sb or db.cliente()
    resultados = []
    for fila in db.listar(sb):
        folio = fila["folio"]
        try:
            datos = db.cargar(folio, sb)
        except LookupError:
            continue
        rfc = _rfc_de_expediente(datos)
        if not rfc:
            continue
        hallazgos, estado = analizar_cliente(rfc)
        resultados.append({
            "folio": folio,
            "razon_social": fila.get("razon_social"),
            "rfc": rfc,
            "hallazgos": hallazgos,
            "estado": estado,
        })
    return resultados


def barrer_entidades_syntage():
    """Recorre TODAS las entidades que Syntage conoce —no solo las que ya
    tienen expediente en Supabase— y cruza cada una contra el padrón. Es el
    universo real de "a quién le tenemos información de facturación": incluye
    prospectos que nunca llegaron a expediente."""
    resultados = []
    for entidad in syntage.entidades():
        rfc = _rfc_de_entidad_syntage(entidad)
        if not rfc:
            continue
        hallazgos, estado = analizar_cliente(rfc, entidad_id=entidad.get("id"))
        resultados.append({
            "rfc": rfc,
            "nombre": (entidad.get("taxpayer") or {}).get("name") or entidad.get("name"),
            "entidad_id": entidad.get("id"),
            "hallazgos": hallazgos,
            "estado": estado,
        })
    return resultados


def _pesos(n):
    return "$%s" % format(n or 0, ",.0f")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    orden, args = argv[1], argv[2:]

    if orden == "padron":
        for m in PADRON:
            print("%-14s %-42s %s" % (m["rfc"], m["nombre_comercial"][:42], m["razon_social"]))
        return 0

    if orden == "cliente" and args:
        rfc = args[0].upper()
        hallazgos, estado = analizar_cliente(rfc)
        if estado != "ok":
            print("%s: %s" % (rfc, estado))
            return 1
        if not hallazgos:
            print("%s: ningún proveedor coincide con el padrón de monederos." % rfc)
            return 0
        for h in hallazgos:
            print("%s usa %-30s %14s  (%.1f%% de su gasto en proveedores)" % (
                rfc, h["nombre_comercial"], _pesos(h["monto"]), h["porcentaje_gasto"] or 0))
        return 0

    if orden == "todos":
        resultados = barrer_clientes()
        con_monedero = [r for r in resultados if r["hallazgos"]]
        print("%d expediente(s) revisado(s), %d con monedero detectado.\n" % (
            len(resultados), len(con_monedero)))
        for r in con_monedero:
            print("%-12s %-38s %s" % (r["folio"], (r["razon_social"] or "")[:38], r["rfc"]))
            for h in r["hallazgos"]:
                print("             usa %-30s %14s  (%.1f%%)" % (
                    h["nombre_comercial"], _pesos(h["monto"]), h["porcentaje_gasto"] or 0))
        sin_revisar = [r for r in resultados if r["estado"] != "ok"]
        if sin_revisar:
            print("\n%d expediente(s) sin cruzar:" % len(sin_revisar))
            for r in sin_revisar:
                print("  %-12s %-38s %s" % (r["folio"], (r["razon_social"] or "")[:38], r["estado"]))
        return 0

    if orden == "entidades":
        resultados = barrer_entidades_syntage()
        con_monedero = [r for r in resultados if r["hallazgos"]]
        con_info = [r for r in resultados if r["estado"] == "ok"]
        print("%d entidad(es) en Syntage, %d con información de facturación utilizable, "
              "%d con monedero detectado.\n" % (len(resultados), len(con_info), len(con_monedero)))
        for r in con_monedero:
            print("%-14s %-38s" % (r["rfc"], (r["nombre"] or "")[:38]))
            for h in r["hallazgos"]:
                print("               usa %-30s %14s  (%.1f%%)" % (
                    h["nombre_comercial"], _pesos(h["monto"]), h["porcentaje_gasto"] or 0))
        sin_revisar = [r for r in resultados if r["estado"] != "ok"]
        if sin_revisar:
            resumen = {}
            for r in sin_revisar:
                resumen[r["estado"]] = resumen.get(r["estado"], 0) + 1
            print("\n%d entidad(es) sin cruzar:" % len(sin_revisar))
            for estado, n in sorted(resumen.items(), key=lambda kv: -kv[1]):
                print("  %3d  %s" % (n, estado))
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
