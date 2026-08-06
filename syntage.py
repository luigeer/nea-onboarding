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
    python syntage.py credenciales <RFC>
    python syntage.py fiscal <RFC>          declaración anual por ejercicio
    python syntage.py extraer <RFC> [--guardar]   todo lo que Syntage sabe
    python syntage.py poderes <RFC>         facultades por apoderado
    python syntage.py accionistas <RFC>
    python syntage.py actos <RFC>           asambleas inscritas en el RPC
"""

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


def pedir(ruta, params=None, metodo="GET", cuerpo=None):
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
    """Devuelve la entidad de Syntage cuyo identificador fiscal es ese RFC."""
    for fila in _lista(pedir("/entities", {"taxpayerId": rfc.upper()})):
        return fila
    return None


def crear_entidad(rfc, nombre=None):
    return pedir("/entities", metodo="POST",
                 cuerpo={"taxpayerId": rfc.upper(), "name": nombre or rfc.upper()})


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
def estado_credenciales(entidad_id=None):
    """Compuerta antes de que riesgo dependa de datos del SAT.

    Las credenciales se caen y los datos derivados quedan viejos sin avisar.
    """
    filas = _lista(pedir("/credentials", {"entityId": entidad_id} if entidad_id else None))
    return [{"id": c.get("id"), "rfc": c.get("taxpayerId") or c.get("rfc"),
             "estado": c.get("status"), "vigente": c.get("status") in ("valid", "active"),
             "actualizada": c.get("updatedAt") or c.get("createdAt")} for c in filas]


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


def insight(entidad_id, nombre, **params):
    return pedir("/entities/%s/insights/%s" % (entidad_id, nombre), params or None)


# Todo lo que Syntage sabe de una entidad. Se extrae completo y se guarda
# completo, no solo lo que el modelo consume hoy: el modelo va a cambiar y no
# queremos volver a extraer, y el resumen ejecutivo debe poder analizar más de
# lo que el score captura.
#
# El buró de crédito **no** está aquí a propósito: se extrae por fuera de
# Syntage por costo, y se captura del reporte PYME Plus.
RECURSOS = {
    # alimentan directamente al modelo
    "metrics/balance-sheet":            "balance",
    "metrics/income-statement":         "estado de resultados",
    "financial-ratios":                 "razones financieras",
    # señales que el modelo no captura pero que mueven la decisión
    "customer-concentration":           "concentración de clientes",
    "vendor-concentration":             "concentración de proveedores",
    "employees":                        "empleados",
    "government-customers":             "ventas a gobierno",
    "moratory-interest":                "intereses moratorios",
    "cash-flow-stats":                  "flujo de efectivo",
    "accounts-receivable":              "cuentas por cobrar",
    "accounts-payable":                 "cuentas por pagar",
    "financial-institutions":           "instituciones financieras",
    "invoicing-blacklist":              "lista negra 69-B",
    "invoicing-annual-comparison":      "comparativo anual de facturación",
    "sales-revenue":                    "ingresos por ventas",
    "expenditures":                     "gastos",
    "risks":                            "riesgos",
    "scores":                           "scores",
    "summary":                          "resumen",
    "trial-balance":                    "balanza de comprobación",
    "customer-network":                 "red de clientes",
    "vendor-network":                   "red de proveedores",
    # sociedad y control
    "shareholders":                     "accionistas",
    "rpc-shareholders":                 "accionistas según el RPC",
    "corporate-structure/current-powers": "poderes vigentes",
}


def extraer_todo(entidad_id, recursos=None):
    """Barre todos los insights y devuelve {recurso: payload} más los fallos.

    Lo que falle no detiene el barrido: se anota y se sigue. Un plan sin cierto
    recurso, o una entidad sin autorización para cierta fuente, son casos
    normales y no deben tumbar la extracción completa.
    """
    salida, fallos = {}, {}
    for ruta in (recursos or RECURSOS):
        try:
            salida[ruta] = insight(entidad_id, ruta)
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
                print("  ok       %-38s %s" % (k, RECURSOS.get(k, "")))
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
