# -*- coding: utf-8 -*-
"""
db.py — La base de datos del onboarding (Supabase)
===================================================
Guarda y consulta expedientes. El expediente completo viaja como JSON en la
columna `datos`; las tablas hijas existen para las preguntas que cruzan
expedientes (exposición agregada, vigencias, rastro de cumplimiento).

Configuración: un archivo `.env` en esta misma carpeta con dos líneas. Los
pasos para obtener esos valores están en SETUP_SUPABASE.md.

    SUPABASE_URL=https://xxxxxxxx.supabase.co
    SUPABASE_KEY=eyJhbGci...

Uso:
    python db.py probar                    verifica la conexión
    python db.py guardar <expediente.json> sube o actualiza un expediente
    python db.py listar                    todos los expedientes y su etapa
    python db.py ver <FOLIO>               baja el expediente a la pantalla
    python db.py bajar <FOLIO> <archivo>   baja el expediente a un archivo
    python db.py exposicion                exposición agregada por obligado
    python db.py vigencias                 documentos que vencen en 30 días
"""

import json
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_ENV = os.path.join(RAIZ, ".env")

TABLAS_HIJAS = ("beneficiarios", "obligados_solidarios", "observaciones", "documentos")


# ─────────────────────────────────────────────────────────────────────────────
# Conexión
# ─────────────────────────────────────────────────────────────────────────────
def _leer_env():
    """Lee .env sin dependencias extra. Las variables de entorno tienen
    prioridad, para que la tarea programada pueda inyectarlas."""
    valores = {}
    if os.path.exists(RUTA_ENV):
        with open(RUTA_ENV, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, _, valor = linea.partition("=")
                valores[clave.strip()] = valor.strip().strip('"').strip("'")
    for clave in ("SUPABASE_URL", "SUPABASE_KEY"):
        if os.environ.get(clave):
            valores[clave] = os.environ[clave]
    return valores


class ErrorDeConfiguracion(SystemExit):
    pass


def cliente():
    """Devuelve el cliente de Supabase, con mensajes claros si algo falta."""
    try:
        from supabase import create_client
    except ImportError:
        raise ErrorDeConfiguracion(
            "Falta la librería de Supabase. Instálala con:\n"
            "    pip install -r requirements.txt")

    env = _leer_env()
    faltan = [c for c in ("SUPABASE_URL", "SUPABASE_KEY") if not env.get(c)]
    if faltan:
        raise ErrorDeConfiguracion(
            "Falta %s en el archivo .env\n\n"
            "Crea un archivo llamado .env en la carpeta del proyecto con:\n"
            "    SUPABASE_URL=https://xxxxxxxx.supabase.co\n"
            "    SUPABASE_KEY=eyJhbGci...\n\n"
            "Los pasos para conseguir esos dos valores están en SETUP_SUPABASE.md."
            % " y ".join(faltan))

    return create_client(env["SUPABASE_URL"], env["SUPABASE_KEY"])


def _explicar(err):
    """Traduce los errores típicos a algo accionable."""
    t = str(err).lower()
    if "getaddrinfo" in t or "name or service" in t or "connection" in t or "timeout" in t:
        return ("No se pudo conectar con Supabase.\n"
                "  · Si el proyecto lleva más de una semana sin uso, el plan gratuito\n"
                "    lo pausa. Entra a supabase.com/dashboard y dale 'Restore';\n"
                "    tarda un par de minutos.\n"
                "  · Si no, revisa tu conexión a internet.")
    if "invalid api key" in t or "jwt" in t or "401" in t or "unauthorized" in t:
        return ("Supabase rechazó la llave.\n"
                "  Revisa SUPABASE_KEY en el archivo .env. Debe ser la llave\n"
                "  'service_role' (Settings → API Keys), no la 'anon'.")
    if "does not exist" in t or "42p01" in t or "pgrst205" in t:
        return ("Las tablas no existen todavía.\n"
                "  Abre el SQL Editor de Supabase, pega el contenido de\n"
                "  supabase/esquema.sql y dale Run.")
    return "Error de Supabase: %s" % err


# ─────────────────────────────────────────────────────────────────────────────
# Escritura
# ─────────────────────────────────────────────────────────────────────────────
def _g(d, ruta, default=None):
    cur = d
    for parte in ruta.split("."):
        if not isinstance(cur, dict) or parte not in cur:
            return default
        cur = cur[parte]
    return cur if cur is not None else default


def _fila_expediente(exp):
    riesgo = (_g(exp, "riesgo_pld.grado") or "").lower() or None
    return {
        "folio": exp["folio"],
        "razon_social": _g(exp, "cliente.validado.razon_social")
                        or _g(exp, "cliente.declarado.razon_social") or "(sin nombre)",
        "rfc": _g(exp, "cliente.validado.rfc") or "",
        "tipo_cliente": exp.get("tipo_cliente"),
        "etapa": exp.get("etapa") or "apertura",
        "grupo": _g(exp, "grupo.acronimo"),
        "linea_solicitada": _g(exp, "credito.solicitada.linea"),
        "linea_modelo": _g(exp, "credito.autorizada.linea_propuesta_modelo"),
        "linea_autorizada": _g(exp, "credito.autorizada.linea"),
        "riesgo_pld": riesgo if riesgo in ("bajo", "medio", "alto") else None,
        "datos": exp,
    }


def guardar(exp, sb=None):
    """Sube o actualiza un expediente completo.

    Las tablas hijas se reemplazan enteras en lugar de intentar conciliar
    renglón por renglón: el expediente en JSON es la verdad y esto es una
    proyección suya para poder consultarla.
    """
    sb = sb or cliente()
    folio = exp.get("folio")
    if not folio:
        raise ValueError("El expediente no tiene folio. Se asigna en la etapa 0.")

    sb.table("expedientes").upsert(_fila_expediente(exp)).execute()

    for tabla in TABLAS_HIJAS:
        sb.table(tabla).delete().eq("folio", folio).execute()

    benes = [{
        "folio": folio,
        "nombre": b.get("nombre") or "(sin nombre)",
        "rfc": b.get("rfc"), "curp": b.get("curp"),
        "porcentaje": _g(b, "participacion.porcentaje"),
        "criterio": exp.get("criterio_identificacion"),
        "pep": None if b.get("pep") is None else str(b.get("pep")).strip().lower() in ("sí", "si", "true", "yes"),
    } for b in exp.get("beneficiarios_controladores", [])]
    if benes:
        sb.table("beneficiarios").insert(benes).execute()

    if _g(exp, "flags.obligado_solidario"):
        os_ = exp.get("obligado_solidario", {})
        es_pf = os_.get("tipo") == "persona_fisica"
        pf = os_.get("persona_fisica", {})
        nombre = (pf.get("nombre") if es_pf else os_.get("razon_social"))
        if nombre:
            sb.table("obligados_solidarios").insert({
                "folio": folio, "tipo": os_.get("tipo"), "nombre": nombre,
                "rfc": (pf.get("rfc") if es_pf else os_.get("rfc")),
                "es_cliente": bool(os_.get("es_cliente")),
                "expediente_ref": os_.get("expediente_ref"),
            }).execute()

    obs = [{
        "folio": folio, "tipo": o.get("tipo"),
        "descripcion": o.get("descripcion") or "",
        "severidad": o.get("severidad"), "estado": o.get("estado"),
        "aceptada_por": o.get("aceptada_por"), "justificacion": o.get("justificacion"),
        "fecha": o.get("fecha"),
    } for o in exp.get("observaciones", []) if o.get("descripcion")]
    if obs:
        sb.table("observaciones").insert(obs).execute()

    docs = [{
        "folio": folio, "tipo": d.get("tipo"), "sujeto": d.get("sujeto"),
        "fecha_emision": d.get("fecha_emision"), "vigente_hasta": d.get("vigente_hasta"),
        "legible": d.get("legible", True), "drive_file_id": d.get("file_id"),
        "superado": bool(d.get("superado_por")),
    } for d in exp.get("documentos", []) if d.get("tipo")]
    if docs:
        sb.table("documentos").insert(docs).execute()

    return folio


# ─────────────────────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────────────────────
def cargar(folio, sb=None):
    """Devuelve el expediente completo tal como se guardó."""
    sb = sb or cliente()
    r = sb.table("expedientes").select("datos").eq("folio", folio).execute()
    if not r.data:
        raise LookupError("No hay expediente con folio %s." % folio)
    return r.data[0]["datos"]


def listar(sb=None):
    sb = sb or cliente()
    return sb.table("expedientes").select(
        "folio, razon_social, tipo_cliente, etapa, linea_autorizada, actualizado"
    ).order("actualizado", desc=True).execute().data


def exposicion(sb=None):
    sb = sb or cliente()
    return sb.table("exposicion_agregada").select("*").order(
        "exposicion_total", desc=True).execute().data


def vigencias(sb=None):
    sb = sb or cliente()
    return sb.table("vigencias_por_vencer").select("*").execute().data


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def _pesos(n):
    return "$%s" % format(float(n), ",.2f") if n is not None else "—"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    orden, args = argv[1], argv[2:]

    try:
        sb = cliente()

        if orden == "probar":
            n = sb.table("expedientes").select("folio", count="exact").execute()
            print("Conexión correcta. Expedientes en la base: %d" % (n.count or 0))

        elif orden == "guardar" and len(args) == 1:
            with open(args[0], encoding="utf-8") as fh:
                exp = json.load(fh)
            print("Guardado: %s" % guardar(exp, sb))

        elif orden == "listar":
            filas = listar(sb)
            if not filas:
                print("La base está vacía. Los expedientes entran conforme se abren.")
            for f in filas:
                print("%-12s %-42s %-26s %14s  %s" % (
                    f["folio"], (f["razon_social"] or "")[:42], f["etapa"],
                    _pesos(f["linea_autorizada"]), (f["actualizado"] or "")[:10]))

        elif orden == "ver" and len(args) == 1:
            print(json.dumps(cargar(args[0], sb), ensure_ascii=False, indent=2))

        elif orden == "bajar" and len(args) == 2:
            with open(args[1], "w", encoding="utf-8") as fh:
                json.dump(cargar(args[0], sb), fh, ensure_ascii=False, indent=2)
            print("Escrito: %s" % args[1])

        elif orden == "exposicion":
            filas = exposicion(sb)
            if not filas:
                print("Ningún expediente tiene obligado solidario todavía.")
            for f in filas:
                print("%-14s %-38s garantiza %d expediente(s)  %14s + propia %s = %s" % (
                    f["rfc"], (f["nombre"] or "")[:38], f["expedientes_garantizados"],
                    _pesos(f["suma_garantizada"]), _pesos(f["linea_propia"]),
                    _pesos(f["exposicion_total"])))

        elif orden == "vigencias":
            filas = vigencias(sb)
            if not filas:
                print("Ningún documento vence en los próximos 30 días.")
            for f in filas:
                print("%-12s %-34s %-24s vence %s (%s días)" % (
                    f["folio"], (f["razon_social"] or "")[:34], f["tipo"],
                    f["vigente_hasta"], f["dias_restantes"]))

        else:
            print(__doc__)
            return 1

    except ErrorDeConfiguracion:
        raise
    except LookupError as e:
        print(e)
        return 1
    except Exception as e:
        print(_explicar(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
