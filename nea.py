# -*- coding: utf-8 -*-
"""
nea.py — La plataforma de onboarding, en un solo comando
=========================================================
Esto es lo único que necesitas correr. Los demás archivos son las piezas que
este usa por dentro.

    python nea.py                          qué hay y qué sigue
    python nea.py nuevo <csf.pdf>          abre un expediente leyendo la CSF
    python nea.py csf <FOLIO> <pdf> <quién>  agrega otra CSF al expediente
    python nea.py estado <FOLIO>           qué falta para poder generar
    python nea.py generar <FOLIO>          genera el paquete de contratos
    python nea.py subir <FOLIO>            sube el paquete a Drive

Los expedientes se guardan en la carpeta `expedientes/` de tu computadora. Si
configuraste Supabase (ver SETUP_SUPABASE.md), además se sincronizan solos a la
base; si no, funciona igual en local y los sincronizas después.
"""

import json
import os
import sys

# La consola de Windows usa una codificación vieja que rompe los acentos.
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR_EXP = os.path.join(RAIZ, "expedientes")
sys.path.insert(0, RAIZ)

from schema_expediente import expediente_vacio, compuertas_generacion, documentos_aplicables


# ─────────────────────────────────────────────────────────────────────────────
# Presentación
# ─────────────────────────────────────────────────────────────────────────────
def titulo(t):
    print("\n%s\n%s" % (t, "─" * len(t)))


def pesos(n):
    return "$%s" % format(float(n), ",.2f") if n not in (None, "") else "—"


def preguntar(texto, obligatorio=False, default=None):
    pista = " [%s]" % default if default else ""
    while True:
        try:
            r = input("  %s%s: " % (texto, pista)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado.")
            sys.exit(1)
        if not r and default is not None:
            return default
        if r or not obligatorio:
            return r or None
        print("    (este dato es obligatorio)")


def preguntar_si_no(texto, default=False):
    d = "s/N" if not default else "S/n"
    r = (preguntar("%s (%s)" % (texto, d)) or "").lower()
    return default if not r else r.startswith("s")


def preguntar_monto(texto, obligatorio=False):
    while True:
        r = preguntar(texto, obligatorio)
        if r is None:
            return None
        try:
            return float(r.replace(",", "").replace("$", "").strip())
        except ValueError:
            print("    (escribe solo el número, por ejemplo 900000)")


# ─────────────────────────────────────────────────────────────────────────────
# Almacenamiento: archivo local siempre, Supabase si está configurado
# ─────────────────────────────────────────────────────────────────────────────
def ruta_local(folio):
    return os.path.join(DIR_EXP, "%s.json" % folio)


def hay_supabase():
    import db
    env = db._leer_env()
    return bool(env.get("SUPABASE_URL") and env.get("SUPABASE_KEY"))


def guardar(exp, avisar=True):
    """Guarda en disco y, si se puede, en Supabase. El disco nunca falla."""
    os.makedirs(DIR_EXP, exist_ok=True)
    with open(ruta_local(exp["folio"]), "w", encoding="utf-8") as fh:
        json.dump(exp, fh, ensure_ascii=False, indent=2)

    if not hay_supabase():
        if avisar:
            print("  Guardado en %s" % ruta_local(exp["folio"]))
            print("  (Supabase no está configurado; cuando lo esté, se sincroniza solo)")
        return False
    try:
        import db
        db.guardar(exp)
        if avisar:
            print("  Guardado en disco y en Supabase.")
        return True
    except Exception as e:
        import db
        print("  Guardado en disco. No se pudo sincronizar con Supabase:")
        print("  " + db._explicar(e).replace("\n", "\n  "))
        return False


def cargar(folio):
    ruta = ruta_local(folio)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    if hay_supabase():
        import db
        exp = db.cargar(folio)
        guardar(exp, avisar=False)
        return exp
    raise LookupError(
        "No encuentro el expediente %s.\n"
        "Los expedientes viven en la carpeta 'expedientes'. Con 'python nea.py' "
        "ves la lista." % folio)


def expedientes_locales():
    if not os.path.isdir(DIR_EXP):
        return []
    out = []
    for a in sorted(os.listdir(DIR_EXP)):
        if a.endswith(".json"):
            try:
                with open(os.path.join(DIR_EXP, a), encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except (ValueError, OSError):
                pass
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Folio
# ─────────────────────────────────────────────────────────────────────────────
def sugerir_acronimo(razon_social):
    ruido = {"SA", "DE", "CV", "S", "A", "C", "V", "SAPI", "SC", "SRL", "RL",
             "Y", "DEL", "LA", "LOS", "LAS", "EL"}
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in razon_social.upper())
    palabras = [p for p in limpio.split() if p not in ruido and not p.isdigit()]
    return (palabras[0][:6] if palabras else "CLIENTE")


def siguiente_folio(acronimo):
    """El NN es el consecutivo de entidades dentro del grupo."""
    usados = set()
    for exp in expedientes_locales():
        f = exp.get("folio") or ""
        if f.upper().startswith(acronimo.upper() + "-"):
            try:
                usados.add(int(f.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                pass
    if hay_supabase():
        try:
            import db
            for fila in db.listar():
                f = fila.get("folio") or ""
                if f.upper().startswith(acronimo.upper() + "-"):
                    try:
                        usados.add(int(f.rsplit("-", 1)[1]))
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
    n = 1
    while n in usados:
        n += 1
    return "%s-%02d" % (acronimo.upper(), n)


# ─────────────────────────────────────────────────────────────────────────────
# Comandos
# ─────────────────────────────────────────────────────────────────────────────
def cmd_nuevo(ruta_csf):
    from extraer_csf import extraer_csf, a_expediente
    from datetime import date

    if not os.path.exists(ruta_csf):
        print("No encuentro el archivo %s" % ruta_csf)
        return 1

    titulo("Leyendo la Constancia de Situación Fiscal")
    try:
        csf = extraer_csf(ruta_csf)
    except Exception as e:
        print("No pude leer la CSF: %s" % e)
        print("Revisa que sea la constancia del SAT en PDF, no una foto ni un escaneo.")
        return 1

    print("  Razón social:  %s" % csf["razon_social"])
    print("  RFC:           %s" % csf["rfc"])
    print("  Tipo:          %s" % csf["tipo_cliente"].replace("_", " "))
    print("  Situación:     %s" % (csf.get("situacion_contribuyente") or "—"))
    print("  Emitida el:    %s" % (csf.get("fecha_emision") or "—"))

    # Compuerta de rechazo temprano
    estatus = (csf.get("situacion_contribuyente") or "").upper()
    if estatus and estatus != "ACTIVO":
        print("\n  ALTO: el contribuyente está %s, no ACTIVO." % estatus)
        print("  El expediente no debe abrirse. (Especificación, etapa 0.)")
        return 1

    for a in csf.get("alertas", []):
        print("  AVISO: %s" % a)

    # Duplicados por RFC
    for exp in expedientes_locales():
        if (exp.get("cliente", {}).get("validado", {}).get("rfc") or "") == csf["rfc"]:
            print("\n  ALTO: ya existe el expediente %s con ese mismo RFC." % exp["folio"])
            return 1

    titulo("Folio")
    acronimo = preguntar("Acrónimo del grupo", default=sugerir_acronimo(csf["razon_social"]))
    folio = siguiente_folio(acronimo)
    print("  Folio asignado: %s" % folio)

    exp = expediente_vacio()
    exp["folio"] = folio
    exp["grupo"] = {"acronimo": acronimo.upper(), "nombre": acronimo.upper()}
    exp["etapa"] = "recoleccion"
    exp["fechas"]["apertura"] = date.today().isoformat()
    a_expediente(csf, exp)

    titulo("Datos que captura ventas")
    print("  (Enter para dejar en blanco lo que todavía no sepas)\n")
    rep = exp["representante_legal"]["propuesto"]
    rep["nombre"] = preguntar("Representante legal propuesto")
    rep["correo"] = preguntar("Su correo electrónico", obligatorio=bool(rep["nombre"]))
    rep["telefono"] = preguntar("Su teléfono")
    exp["cliente"]["validado"]["correo"] = rep["correo"]
    exp["cliente"]["validado"]["telefono"] = rep["telefono"]

    contacto = preguntar("Contacto operativo")
    if contacto:
        exp["contacto_operativo"] = {
            "nombre": contacto,
            "correo": preguntar("Su correo electrónico"),
        }

    sol = exp["credito"]["solicitada"]
    sol["linea"] = preguntar_monto("Línea solicitada (pesos)")
    sol["plazo"] = preguntar("Plazo", default="Mensual")
    sol["tarjetas"] = preguntar("Número de tarjetas")
    exp["flags"]["domiciliacion"] = preguntar_si_no("¿Requiere domiciliación?")
    exp["quien_lleno"] = os.environ.get("USERNAME") or "—"

    titulo("Guardando")
    guardar(exp)

    print("\n  Expediente %s abierto." % folio)
    print("  Carpeta en Drive que debe existir:")
    print("    %s — %s" % (csf["razon_social"], folio))
    print("\n  Lo que sigue: recolectar documentos. Para ver qué falta:")
    print("    python nea.py estado %s" % folio)
    return 0


def cmd_csf(folio, ruta_csf, sujeto):
    from extraer_csf import extraer_csf, a_obligado_solidario, a_beneficiario

    if sujeto not in ("obligado", "beneficiario"):
        print("El tercer dato debe ser 'obligado' o 'beneficiario'.")
        return 1
    if not os.path.exists(ruta_csf):
        print("No encuentro el archivo %s" % ruta_csf)
        return 1

    exp = cargar(folio)
    csf = extraer_csf(ruta_csf)
    titulo("CSF de %s" % csf["razon_social"])

    try:
        if sujeto == "obligado":
            puestos = a_obligado_solidario(csf, exp)
        else:
            puestos, nuevo = a_beneficiario(csf, exp)
            print("  %s" % ("Beneficiario nuevo; falta su participación, que sale "
                            "de la constitutiva." if nuevo else
                            "Ya estaba listado; se completaron sus campos vacíos."))
    except ValueError as e:
        print("  %s" % e)
        return 1

    print("  Campos llenados: %s" % (", ".join(puestos) if puestos else "ninguno, ya estaban"))
    for a in csf.get("alertas", []):
        print("  AVISO: %s" % a)
    guardar(exp)
    return 0


def cmd_estado(folio=None):
    if folio is None:
        return cmd_inicio()
    exp = cargar(folio)
    val = exp["cliente"]["validado"]

    titulo("%s — %s" % (val.get("razon_social") or "(sin nombre)", exp["folio"]))
    print("  RFC:                %s" % (val.get("rfc") or "—"))
    print("  Tipo de cliente:    %s" % (exp.get("tipo_cliente") or "—").replace("_", " "))
    print("  Etapa:              %s" % exp.get("etapa"))
    print("  Línea solicitada:   %s" % pesos(exp["credito"]["solicitada"].get("linea")))
    print("  Línea autorizada:   %s" % pesos(exp["credito"]["autorizada"].get("linea")))

    bcs = exp.get("beneficiarios_controladores", [])
    print("  Beneficiarios:      %s" % (", ".join(b.get("nombre") or "?" for b in bcs)
                                        if bcs else "ninguno identificado"))

    abiertas = [o for o in exp.get("observaciones", []) if o.get("estado") == "abierta"]
    if abiertas:
        titulo("Observaciones abiertas")
        for o in abiertas:
            print("  · [%s] %s" % (o.get("severidad") or "?", o.get("descripcion")))

    fallas = compuertas_generacion(exp)
    if fallas:
        titulo("Falta esto para poder generar los contratos")
        for f in fallas:
            print("  · %s" % f)
    else:
        titulo("Listo para generar")
        print("  Documentos que se van a generar: %s"
              % ", ".join(documentos_aplicables(exp)))
        print("\n    python nea.py generar %s" % exp["folio"])
    return 0


def cmd_generar(folio):
    import subprocess
    exp = cargar(folio)
    fallas = compuertas_generacion(exp)
    if fallas:
        titulo("No se puede generar todavía")
        for f in fallas:
            print("  · %s" % f)
        return 1

    from adaptadores import campos_en_blanco
    vacios = {}
    for clave in documentos_aplicables(exp):
        for campo in campos_en_blanco(exp, clave):
            vacios.setdefault(campo, []).append(clave)
    if vacios:
        titulo("Estos campos van a salir en blanco en el PDF")
        for campo, docs in sorted(vacios.items()):
            print("  · %-38s (%s)" % (campo, ", ".join(docs)))
        print("\n  Los documentos se generan igual, pero revísalos antes de mandarlos")
        print("  a firma. Para llenarlos, edita %s" % ruta_local(folio))
        if not preguntar_si_no("\n¿Genero de todas formas?", default=True):
            return 1

    destino = os.path.join(RAIZ, "expedientes", "%s_paquete" % folio)
    os.makedirs(destino, exist_ok=True)
    titulo("Generando el paquete de %s" % folio)
    sys.stdout.flush()
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "generar_paquete.py"),
                        ruta_local(folio), destino], cwd=RAIZ, env=entorno)
    if r.returncode == 0:
        exp["etapa"] = "firma"
        guardar(exp, avisar=False)
        print("\n  Los documentos están en:\n    %s" % destino)
        print("\n  Para subirlos a Drive:\n    python nea.py subir %s" % folio)
    return r.returncode


def cmd_subir(folio):
    destino = os.path.join(RAIZ, "expedientes", "%s_paquete" % folio)
    if not os.path.isdir(destino):
        print("Todavía no hay paquete generado para %s." % folio)
        print("Primero: python nea.py generar %s" % folio)
        return 1
    import drive_cliente
    titulo("Subiendo a Drive")
    for f in drive_cliente.subir_paquete(drive_cliente.servicio(), folio, destino):
        print("  Subido: %s" % f["name"])
    return 0


def cmd_inicio():
    exps = expedientes_locales()
    titulo("Onboarding Nea")

    if not hay_supabase():
        print("  Supabase todavía no está configurado (opcional; ver SETUP_SUPABASE.md).")

    if not exps:
        print("\n  No hay expedientes todavía.")
        print("\n  Para abrir el primero, necesitas la Constancia de Situación")
        print("  Fiscal del cliente en PDF:")
        print("\n    python nea.py nuevo ruta\\de\\la\\csf.pdf")
        return 0

    print()
    for exp in exps:
        val = exp.get("cliente", {}).get("validado", {})
        fallan = len(compuertas_generacion(exp))
        estado = "listo para generar" if fallan == 0 else "%d pendiente(s)" % fallan
        print("  %-12s %-40s %-16s %s" % (
            exp.get("folio"), (val.get("razon_social") or "")[:40],
            exp.get("etapa"), estado))
    print("\n  Detalle de uno:  python nea.py estado FOLIO")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
def main(argv):
    if len(argv) < 2:
        return cmd_inicio()
    orden, args = argv[1], argv[2:]
    try:
        if orden == "nuevo" and len(args) == 1:
            return cmd_nuevo(args[0])
        if orden == "csf" and len(args) == 3:
            return cmd_csf(args[0], args[1], args[2])
        if orden == "estado":
            return cmd_estado(args[0] if args else None)
        if orden == "generar" and len(args) == 1:
            return cmd_generar(args[0])
        if orden == "subir" and len(args) == 1:
            return cmd_subir(args[0])
        if orden in ("ayuda", "-h", "--help"):
            print(__doc__)
            return 0
    except LookupError as e:
        print(e)
        return 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
