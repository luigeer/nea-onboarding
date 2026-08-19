# -*- coding: utf-8 -*-
"""
syntage.py — Cliente de la API de Syntage
==========================================
Syntage extrae del SAT, del Registro Público de Comercio, del Buró de Crédito y
de otras fuentes. Para la plataforma cubre cuatro etapas distintas:

  etapa 2   `current-powers` da las facultades del representante por apoderado,
            con si es mancomunado y con qué límite. El acta pasa de trabajo
            principal a corroboración.
  etapa 3   `shareholders` y `rpc/socios` dan la estructura accionaria.
  etapa 4   `rpc/actos` dice si hay asambleas posteriores a la constitutiva que
            afecten capital o funcionarios. `background-checks` cubre el
            screening en listas.
  etapa 5   `tax-returns` da la declaración anual y los insights dan las
            señales que el modelo de riesgo no captura pero que sí mueven la
            decisión: concentración de clientes, empleados, intereses
            moratorios, ventas a gobierno.

**La extracción del SAT requiere que el cliente autorice.** Sin credencial
vigente no hay declaración anual ni CFDI, y las credenciales se caen — por eso
existe `revalidate`. Antes de que riesgo dependa de esos datos hay que
verificar la vigencia, que es lo que hace `estado_credenciales()`.

Configuración, en el mismo `.env` que Supabase:

    SYNTAGE_API_KEY=...
    SYNTAGE_ENTORNO=sandbox        # o 'produccion'

Uso:
    python syntage.py probar
    python syntage.py entidad <RFC>
    python syntage.py extracciones <RFC>    ¿ya terminó de bajar todo?
    python syntage.py credenciales <RFC>
    python syntage.py fiscal <RFC>          declaración anual por ejercicio
    python syntage.py extraer <RFC> [--guardar]   todo lo que Syntage sabe
    python syntage.py poderes <RFC>         facultades por apoderado
    python syntage.py accionistas <RFC>
    python syntage.py actos <RFC>           asambleas inscritas en el RPC
"""

import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))

ENTORNOS = {
    "produccion": "https://api.syntage.com",
    "sandbox": "https://api.sandbox.syntage.com",
}

TIEMPO_ESPERA = 60


class ErrorDeConfiguracion(SystemExit):
    pass


class ErrorSyntage(RuntimeError):
    def __init__(self, codigo, cuerpo, ruta):
        self.codigo, self.cuerpo, self.ruta = codigo, cuerpo, ruta
        super().__init__(self._mensaje())

    def _mensaje(self):
        if self.codigo == 401:
            return ("Syntage rechazó la llave (401).\n"
                    "  Revisa SYNTAGE_API_KEY en el .env, y que corresponda al entorno:\n"
                    "  las llaves de sandbox no sirven en producción ni al revés.")
        if self.codigo == 403:
            return ("Syntage negó el acceso (403) a %s.\n"
                    "  Puede ser que tu plan no incluya ese recurso, o que la entidad\n"
                    "  no tenga autorización del cliente para esa fuente." % self.ruta)
        if self.codigo == 404:
            return "Syntage no encontró %s (404)." % self.ruta
        if self.codigo == 429:
            return "Syntage está limitando las peticiones (429). Espera y reintenta."
        return "Syntage respondió %s en %s: %s" % (self.codigo, self.ruta, self.cuerpo[:300])


# ─────────────────────────────────────────────────────────────────────────────
def _config():
    valores = {}
    ruta = os.path.join(RAIZ, ".env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, _, v = linea.partition("=")
                    valores[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("SYNTAGE_API_KEY", "SYNTAGE_ENTORNO"):
        if os.environ.get(k):
            valores[k] = os.environ[k]

    llave = valores.get("SYNTAGE_API_KEY")
    if not llave:
        raise ErrorDeConfiguracion(
            "Falta SYNTAGE_API_KEY en el archivo .env\n\n"
            "Se saca del panel de Syntage, en Settings → API Keys:\n"
            "  sandbox     https://app.sandbox.syntage.com/settings/api-keys\n"
            "  producción  https://app.syntage.com/settings/api-keys\n\n"
            "Agrega al .env estas dos líneas:\n"
            "  SYNTAGE_API_KEY=...\n"
            "  SYNTAGE_ENTORNO=sandbox")

    entorno = (valores.get("SYNTAGE_ENTORNO") or "sandbox").lower()
    if entorno not in ENTORNOS:
        raise ErrorDeConfiguracion(
            "SYNTAGE_ENTORNO debe ser 'sandbox' o 'produccion', no %r." % entorno)
    return llave, ENTORNOS[entorno], entorno


def pedir(ruta, params=None, metodo="GET", cuerpo=None, headers=None):
    """Una llamada a la API. Devuelve el JSON ya parseado."""
    llave, base, _ = _config()
    url = base + ruta
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})

    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("X-API-Key", llave)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if datos:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=TIEMPO_ESPERA) as r:
            texto = r.read().decode("utf-8")
            return json.loads(texto) if texto else {}
    except urllib.error.HTTPError as e:
        raise ErrorSyntage(e.code, e.read().decode("utf-8", "replace"), ruta)
    except urllib.error.URLError as e:
        raise ErrorSyntage(0, "sin conexión: %s" % e.reason, ruta)
    except http.client.HTTPException as e:
        # La conexión abrió pero la respuesta se cortó a medias (típico en
        # barridos largos de muchas páginas). Es tan "sin conexión" como un
        # URLError: sin este catch tumba al llamador entero en vez de dejarlo
        # tratarlo como una falla recuperable de esta petición.
        raise ErrorSyntage(0, "respuesta incompleta: %s" % e, ruta)


def _lista(respuesta):
    """La API devuelve JSON-LD; los listados vienen bajo 'member' o 'data'."""
    if isinstance(respuesta, list):
        return respuesta
    for clave in ("member", "hydra:member", "data", "items"):
        if isinstance(respuesta.get(clave), list):
            return respuesta[clave]
    return [respuesta] if respuesta else []


# ─────────────────────────────────────────────────────────────────────────────
# Entidades
# ─────────────────────────────────────────────────────────────────────────────
def buscar_entidad(rfc):
    """Devuelve la entidad de Syntage cuyo RFC es ese.

    El filtro de la API es de coincidencia parcial, así que hay que comparar
    exacto: buscar 'GPS200810ICA' no debe traer a otro contribuyente cuyo RFC
    lo contenga.
    """
    rfc = rfc.upper().strip()
    for fila in _lista(pedir("/entities", {"taxpayer.id": rfc})):
        if ((fila.get("taxpayer") or {}).get("id") or "").upper() == rfc:
            return fila
    return None


def crear_entidad(rfc, nombre=None):
    return pedir("/entities", metodo="POST",
                 cuerpo={"taxpayerId": rfc.upper(), "name": nombre or rfc.upper()})


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


def entidades(tam_pagina=100):
    """Todas las entidades que Syntage conoce, sin importar de qué cliente o
    prospecto sean. Pagina explícitamente en vez de confiar en que una sola
    llamada sin parámetros traiga todo: el default de la API no está
    documentado y una entidad más allá del corte se perdería en silencio."""
    pagina = 1
    while True:
        lote = _lista(pedir("/entities", {"itemsPerPage": tam_pagina, "page": pagina}))
        if not lote:
            return
        for fila in lote:
            yield fila
        if len(lote) < tam_pagina:
            return
        pagina += 1


def id_entidad(rfc, crear=False):
    e = buscar_entidad(rfc)
    if e is None and crear:
        e = crear_entidad(rfc)
    if e is None:
        raise LookupError(
            "El RFC %s no existe como entidad en Syntage.\n"
            "Se crea con: python syntage.py entidad %s --crear" % (rfc, rfc))
    return e.get("id") or str(e.get("@id", "")).rsplit("/", 1)[-1]


# ─────────────────────────────────────────────────────────────────────────────
# Credenciales del SAT
# ─────────────────────────────────────────────────────────────────────────────
VIGENTES = ("valid", "active")


def _resumir_credencial(c):
    return {"id": c.get("id"), "rfc": c.get("rfc") or c.get("taxpayerId"),
            "tipo": c.get("type"), "estado": c.get("status"),
            "vigente": c.get("status") in VIGENTES,
            "motivo": c.get("statusReason"),
            "actualizada": c.get("updatedAt") or c.get("createdAt")}


def credencial_de(entidad):
    """La credencial viene embebida en la entidad, no hay que pedirla aparte."""
    c = entidad.get("credential")
    return _resumir_credencial(c) if c else None


def estado_credenciales(entidad_id=None):
    """Compuerta antes de que riesgo dependa de datos del SAT.

    Las credenciales se caen y los datos derivados quedan viejos sin avisar,
    por eso existe `revalidate`. Sin credencial vigente no hay declaración
    anual ni CFDI.
    """
    if entidad_id:
        c = credencial_de(pedir("/entities/%s" % entidad_id))
        return [c] if c else []
    return [_resumir_credencial(c) for c in _lista(pedir("/credentials"))]


def revalidar_credencial(credencial_id):
    return pedir("/credentials/%s/revalidate" % credencial_id, metodo="POST")


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 5 · insumos del modelo de riesgo
# ─────────────────────────────────────────────────────────────────────────────
def declaraciones(entidad_id):
    """Declaraciones anuales. Alimenta la tabla info_fiscal."""
    return _lista(pedir("/entities/%s/tax-returns" % entidad_id))


def declaracion_datos(tax_return_id):
    return pedir("/tax-returns/%s/data" % tax_return_id)


def insight(entidad_id, nombre, headers=None, **params):
    return pedir("/entities/%s/insights/%s" % (entidad_id, nombre),
                 params or None, headers=headers)


# Todo lo que Syntage sabe de una entidad. Se extrae completo y se guarda
# completo, no solo lo que el modelo consume hoy: el modelo va a cambiar y no
# queremos volver a extraer, y el resumen ejecutivo debe poder analizar más de
# lo que el score captura.
#
# El buró de crédito **no** está aquí a propósito: se extrae por fuera de
# Syntage por costo, y se captura del reporte PYME Plus.
# Las rutas están verificadas contra la API real: varias no son donde uno
# supondría —las de red y las de comparativo cuelgan de `metrics/`— y el
# balance y el estado de resultados exigen un rango de ejercicios.
RECURSOS = {
    # alimentan directamente al modelo
    "metrics/balance-sheet":              ("balance", None, {"X-Insight-Format": "2022"}),
    "metrics/income-statement":           ("estado de resultados", None,
                                           {"X-Insight-Format": "2022"}),
    "financial-ratios":                   ("razones financieras", None, None),
    "trial-balance":                      ("balanza de comprobación", None, None),
    # señales que el modelo no captura pero que mueven la decisión
    "customer-concentration":             ("concentración de clientes", None, None),
    "supplier-concentration":             ("concentración de proveedores", None, None),
    "employees":                          ("empleados", None, None),
    "government-customers":               ("ventas a gobierno", None, None),
    "moratory-interest":                  ("intereses moratorios", None, None),
    "cash-flow-stats":                    ("flujo de efectivo", None, None),
    "accounts-receivable":                ("cuentas por cobrar", None, None),
    "accounts-payable":                   ("cuentas por pagar", None, None),
    "financial-institutions":             ("instituciones financieras", None, None),
    "invoicing-blacklist":                ("lista negra 69-B", None, None),
    "invoicing-concentration#emitidas":   ("concentración de facturación emitida",
                                           {"options[type]": "issued"}, None),
    "invoicing-concentration#recibidas":  ("concentración de facturación recibida",
                                           {"options[type]": "received"}, None),
    "metrics/invoicing-annual-comparison": ("comparativo anual de facturación", None, None),
    "metrics/scores":                     ("scores", None, None),
    "metrics/customer-network":           ("red de clientes", None, None),
    "metrics/vendor-network":             ("red de proveedores", None, None),
    "sales-revenue":                      ("ingresos por ventas", None, None),
    "expenditures":                       ("gastos", None, None),
    "products-and-services-sold":         ("productos y servicios vendidos", None, None),
    "products-and-services-bought":       ("productos y servicios comprados", None, None),
    "risks":                              ("riesgos", None, None),
    "summary":                            ("resumen", None, None),
    # sociedad y control
    "shareholders":                       ("accionistas", {"relations.relationType": "shareholders"}, None),
    "rpc-shareholders":                   ("accionistas según el RPC", None, None),
    "corporate-structure/current-powers": ("poderes vigentes", None, None),
}


def extracciones(rfc, estado=None):
    """Estado de las extracciones del SAT para ese contribuyente."""
    return _lista(pedir("/extractions",
                        {"taxpayer.id": rfc.upper(), "status": estado}))


def extraccion_completa(rfc):
    """¿Ya terminó de bajar todo? Devuelve (completa, pendientes).

    Compuerta imprescindible antes de que riesgo mire estos datos. Las
    extracciones son asíncronas y tardan horas: un expediente abierto hoy tiene
    la declaración anual a medias, y los insights que la usan devuelven cifras
    parciales **sin marcarlas como parciales**. En la primera prueba real, un
    cliente aparecía con toda su facturación histórica concentrada en el mes en
    curso, solo porque `annual_tax_return` seguía corriendo.
    """
    pendientes = [{"extractor": e.get("extractor"), "estado": e.get("status"),
                   "desde": e.get("createdAt")}
                  for e in extracciones(rfc)
                  if e.get("status") in ("running", "pending", "queued")]
    return (not pendientes), pendientes


def extraer_todo(entidad_id, recursos=None, desde="2019-01-01", hasta=None):
    """Barre todos los insights y devuelve {recurso: payload} más los fallos.

    Lo que falle no detiene el barrido: se anota y se sigue. Un plan sin cierto
    recurso, o una entidad sin autorización para cierta fuente, son casos
    normales y no deben tumbar la extracción completa.
    """
    from datetime import date
    hasta = hasta or date.today().isoformat()
    salida, fallos = {}, {}
    for ruta in (recursos or RECURSOS):
        _, params, headers = RECURSOS.get(ruta, (None, None, None))
        if params:
            params = {k: v.format(desde=desde, hasta=hasta) if isinstance(v, str) else v
                      for k, v in params.items()}
        # El sufijo tras # distingue dos llamadas al mismo endpoint.
        try:
            salida[ruta] = insight(entidad_id, ruta.split("#")[0],
                                   headers=headers, **(params or {}))
        except ErrorSyntage as e:
            fallos[ruta] = str(e).splitlines()[0]
    return salida, fallos


def guardar_crudo(folio, entidad_id, payloads, ejercicio=None, sb=None):
    """Guarda las respuestas tal cual en `syntage_datos`.

    Es la fuente de verdad; `info_fiscal` es una proyección suya para el modelo.
    Cada extracción queda como una foto con su fecha: nada se pisa, así que se
    puede volver a leer con criterios nuevos sin re-extraer.
    """
    import db
    sb = sb or db.cliente()
    filas = [{"folio": folio, "entidad_syntage": entidad_id, "recurso": recurso,
              "ejercicio": ejercicio, "payload": payload}
             for recurso, payload in payloads.items() if payload is not None]
    if filas:
        sb.table("syntage_datos").insert(filas).execute()
    return len(filas)


# ─────────────────────────────────────────────────────────────────────────────
# Etapas 2, 3 y 4 · sociedad y control
# ─────────────────────────────────────────────────────────────────────────────
def poderes(entidad_id):
    """Facultades vigentes por apoderado.

    Devuelve por cada uno si el ejercicio es mancomunado, con quién, y sus
    limitaciones. Es el insumo del árbol de facultades de la etapa 2.

    Reserva: un poder otorgado ante notario y no inscrito no aparece aquí.
    """
    return insight(entidad_id, "corporate-structure/current-powers")


def accionistas(entidad_id):
    return _lista(pedir("/entities/%s/shareholders" % entidad_id))


def actos_rpc(entidad_id):
    """Actos inscritos en el Registro Público de Comercio.

    Sirve para la validación de la etapa 4: si hay asambleas posteriores a la
    constitutiva que afecten capital o funcionarios, hay que pedirlas. Es una
    consulta en lugar de trece documentos.
    """
    return _lista(pedir("/entities/%s/datasources/mx/rpc/actos" % entidad_id))


def screening(entidad_id):
    """Verificación de antecedentes: PEP, medios, penales, legales."""
    return _lista(pedir("/entities/%s/background-checks" % entidad_id))


# ─────────────────────────────────────────────────────────────────────────────
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    orden, args = argv[1], argv[2:]
    try:
        if orden == "probar":
            _, base, entorno = _config()
            r = pedir("/entities", {"itemsPerPage": 1})
            print("Conexión correcta con Syntage (%s, %s)." % (entorno, base))
            print("Entidades visibles: %d" % len(_lista(r)))
            return 0

        if orden == "entidad" and args:
            rfc = args[0]
            e = buscar_entidad(rfc)
            if e is None and "--crear" in args:
                e = crear_entidad(rfc)
                print("Entidad creada.")
            if e is None:
                print("El RFC %s no está dado de alta en Syntage.\n"
                      "Para crearlo: python syntage.py entidad %s --crear" % (rfc, rfc))
                return 1
            print(json.dumps(e, ensure_ascii=False, indent=2))
            return 0

        if not args:
            print(__doc__)
            return 1

        # Va antes de resolver la entidad: se consulta por RFC y sirve aunque
        # la entidad todavía no esté lista.
        if orden == "extracciones":
            completa, pendientes = extraccion_completa(args[0])
            if completa:
                print("Extracción completa. Los datos de Syntage ya son confiables.")
                return 0
            print("ATENCIÓN: %d extracción(es) sin terminar.\n"
                  "Los insights van a devolver cifras parciales sin avisar que lo son;\n"
                  "no bases una decisión de riesgo en ellas todavía.\n" % len(pendientes))
            for p in pendientes:
                print("  %-24s %-10s desde %s" % (p["extractor"], p["estado"], p["desde"]))
            return 0

        eid = id_entidad(args[0])

        if orden == "credenciales":
            filas = estado_credenciales(eid)
            if not filas:
                print("Sin credenciales del SAT. Sin ellas no hay declaración anual\n"
                      "ni CFDI: el cliente tiene que autorizar la extracción.")
            for c in filas:
                print("%-38s %-12s %s" % (c["id"], c["estado"],
                                          "vigente" if c["vigente"] else "REVALIDAR"))
        elif orden == "fiscal":
            for d in declaraciones(eid):
                print(json.dumps(d, ensure_ascii=False))
        elif orden in ("extraer", "senales"):
            datos, fallos = extraer_todo(eid)
            print("Recursos obtenidos: %d de %d" % (len(datos), len(RECURSOS)))
            for k in sorted(datos):
                print("  ok       %-38s %s" % (k, RECURSOS.get(k, ("",))[0]))
            for k in sorted(fallos):
                print("  falta    %-38s %s" % (k, fallos[k]))
            if "--guardar" in args:
                n = guardar_crudo(args[1] if len(args) > 1 else args[0], eid, datos)
                print("\nGuardados %d recursos en syntage_datos." % n)
            else:
                print("\nPara guardarlos en la base: agrega --guardar")
        elif orden == "poderes":
            print(json.dumps(poderes(eid), ensure_ascii=False, indent=2))
        elif orden == "accionistas":
            print(json.dumps(accionistas(eid), ensure_ascii=False, indent=2))
        elif orden == "actos":
            print(json.dumps(actos_rpc(eid), ensure_ascii=False, indent=2))
        elif orden == "buro":
            print(json.dumps(buro_resumen(eid), ensure_ascii=False, indent=2))
        else:
            print(__doc__)
            return 1

    except ErrorDeConfiguracion:
        raise
    except LookupError as e:
        print(e)
        return 1
    except ErrorSyntage as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
