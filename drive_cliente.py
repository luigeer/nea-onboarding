# -*- coding: utf-8 -*-
"""
drive_cliente.py — Lectura y escritura en la carpeta de expedientes de Drive
=============================================================================
Drive guarda los documentos; Notion guarda el estado. Este módulo cubre la
mitad de Drive: descubrir lo que ventas suelta en `1 Documentos del cliente`,
subir la salida de la etapa 6 a `3 Documentos generados`, y mover los
documentos reemplazados a `0 Superados` (nunca borrarlos).

Estructura canónica de un expediente (ESPECIFICACION.md §3.1):

    RAZÓN SOCIAL — FOLIO/
    ├── 1 Documentos del cliente/
    │   └── 0 Superados/
    ├── 2 Análisis interno/
    ├── 3 Documentos generados/
    └── 4 Documentos firmados/

Autenticación: ver SETUP_DRIVE.md. Todas las llamadas pasan
`supportsAllDrives` para que el día que los expedientes se muevan a la unidad
compartida (pendiente de la especificación §3.1) nada cambie: los
identificadores de carpeta se conservan al mover.

Uso:
    python drive_cliente.py estructura                  árbol completo de expedientes
    python drive_cliente.py nuevo "RAZÓN SOCIAL" FOLIO  crea la carpeta del expediente
    python drive_cliente.py listar FOLIO                documentos del cliente
    python drive_cliente.py bajar FOLIO [directorio]    descarga los documentos del cliente
    python drive_cliente.py subir FOLIO directorio      sube PDFs y manifiesto a 3 Documentos generados
    python drive_cliente.py superar FOLIO FILE_ID       mueve un documento a 0 Superados
    python drive_cliente.py reparar FOLIO               completa y renombra subcarpetas
"""

import io
import json
import os
import sys

CARPETA_RAIZ = os.environ.get("NEA_DRIVE_RAIZ", "17_Q_pWg8VQvgDvR7_HESb8ows5AgYT8A")
DIR_CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".credenciales")
SCOPES = ["https://www.googleapis.com/auth/drive"]

SEPARADOR = " — "   # guion largo: las razones sociales traen comas y guiones cortos

SUBCARPETAS = ("1 Documentos del cliente", "2 Análisis interno",
               "3 Documentos generados", "4 Documentos firmados")
SUPERADOS = "0 Superados"
NOMBRE_VIEJO_3 = "3 Documentos firmados"

CAMPOS = "id, name, mimeType, size, modifiedTime, parents"
MIME_CARPETA = "application/vnd.google-apps.folder"


# ─────────────────────────────────────────────────────────────────────────────
# Autenticación
# ─────────────────────────────────────────────────────────────────────────────
def servicio():
    """Devuelve el cliente de la API de Drive v3.

    Orden de resolución: cuenta de servicio si NEA_DRIVE_SA apunta a su JSON
    (para la tarea programada), y si no, flujo OAuth de aplicación instalada
    con token cacheado (para uso interactivo).
    """
    from googleapiclient.discovery import build

    sa = os.environ.get("NEA_DRIVE_SA")
    if sa:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(sa, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    ruta_token = os.path.join(DIR_CRED, "token.json")
    ruta_cliente = os.path.join(DIR_CRED, "cliente_oauth.json")
    creds = None
    if os.path.exists(ruta_token):
        creds = Credentials.from_authorized_user_file(ruta_token, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(ruta_cliente):
                raise SystemExit(
                    "Falta %s.\nSigue SETUP_DRIVE.md para crear las credenciales OAuth."
                    % ruta_cliente)
            flow = InstalledAppFlow.from_client_secrets_file(ruta_cliente, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(DIR_CRED, exist_ok=True)
        with open(ruta_token, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ─────────────────────────────────────────────────────────────────────────────
# Primitivas
# ─────────────────────────────────────────────────────────────────────────────
def _esc(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _buscar(svc, q, campos=CAMPOS):
    out, token = [], None
    while True:
        r = svc.files().list(
            q="%s and trashed = false" % q, fields="nextPageToken, files(%s)" % campos,
            pageSize=100, pageToken=token,
            supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        out.extend(r.get("files", []))
        token = r.get("nextPageToken")
        if not token:
            return out


def hijos(svc, carpeta_id, solo_carpetas=False):
    q = "'%s' in parents" % carpeta_id
    if solo_carpetas:
        q += " and mimeType = '%s'" % MIME_CARPETA
    return sorted(_buscar(svc, q), key=lambda f: f["name"])


def renombrar(svc, file_id, nombre):
    return svc.files().update(fileId=file_id, body={"name": nombre},
                              supportsAllDrives=True).execute()


def _crear_carpeta(svc, nombre, padre_id):
    return svc.files().create(
        body={"name": nombre, "mimeType": MIME_CARPETA, "parents": [padre_id]},
        fields=CAMPOS, supportsAllDrives=True).execute()


# ─────────────────────────────────────────────────────────────────────────────
# Expedientes
# ─────────────────────────────────────────────────────────────────────────────
def carpeta_expediente(svc, folio):
    """Encuentra la carpeta cuyo nombre termina en '— FOLIO'.

    Se busca por sufijo y no por igualdad porque la parte de la razón social
    puede corregirse (la CSF manda), mientras el folio es estable.
    """
    candidatos = [f for f in _buscar(
        svc, "name contains '%s' and mimeType = '%s'" % (_esc(folio), MIME_CARPETA))
        if f["name"].endswith(SEPARADOR + folio)]
    if not candidatos:
        raise LookupError("No hay carpeta de expediente para el folio %s." % folio)
    if len(candidatos) > 1:
        raise LookupError("Folio %s ambiguo: %s" %
                          (folio, ", ".join(f["name"] for f in candidatos)))
    return candidatos[0]


def asegurar_estructura(svc, expediente_id, avisos=None):
    """Completa las subcarpetas canónicas y devuelve {'1': id, ..., '0': id}.

    Repara el defecto conocido: si '3 Documentos firmados' convive con
    '4 Documentos firmados', o está vacía, se renombra a '3 Documentos
    generados'. Si tiene contenido y no hay carpeta 4, no se toca y se avisa:
    podría contener documentos firmados de verdad.
    """
    avisos = avisos if avisos is not None else []
    actuales = {f["name"]: f for f in hijos(svc, expediente_id, solo_carpetas=True)}

    vieja = actuales.get(NOMBRE_VIEJO_3)
    if vieja and SUBCARPETAS[2] not in actuales:
        if SUBCARPETAS[3] in actuales or not hijos(svc, vieja["id"]):
            renombrar(svc, vieja["id"], SUBCARPETAS[2])
            actuales[SUBCARPETAS[2]] = actuales.pop(NOMBRE_VIEJO_3)
            avisos.append("Renombrada '%s' a '%s'." % (NOMBRE_VIEJO_3, SUBCARPETAS[2]))
        else:
            avisos.append("'%s' tiene contenido y no existe carpeta 4: se deja como "
                          "está, revisar a mano." % NOMBRE_VIEJO_3)

    ids = {}
    for nombre in SUBCARPETAS:
        if nombre not in actuales:
            actuales[nombre] = _crear_carpeta(svc, nombre, expediente_id)
            avisos.append("Creada '%s'." % nombre)
        ids[nombre[0]] = actuales[nombre]["id"]

    dentro_1 = {f["name"]: f for f in hijos(svc, ids["1"], solo_carpetas=True)}
    if SUPERADOS not in dentro_1:
        dentro_1[SUPERADOS] = _crear_carpeta(svc, SUPERADOS, ids["1"])
        avisos.append("Creada '%s' dentro de '%s'." % (SUPERADOS, SUBCARPETAS[0]))
    ids["0"] = dentro_1[SUPERADOS]["id"]
    return ids


def crear_expediente(svc, razon_social, folio):
    """Crea la carpeta 'RAZÓN SOCIAL — FOLIO' con su estructura completa."""
    nombre = "%s%s%s" % (razon_social, SEPARADOR, folio)
    try:
        existente = carpeta_expediente(svc, folio)
        raise FileExistsError("El folio %s ya existe: %s" % (folio, existente["name"]))
    except LookupError:
        pass
    carpeta = _crear_carpeta(svc, nombre, CARPETA_RAIZ)
    asegurar_estructura(svc, carpeta["id"])
    return carpeta


def documentos_cliente(svc, folio):
    """Los archivos vigentes de '1 Documentos del cliente' (sin 0 Superados)."""
    exp = carpeta_expediente(svc, folio)
    ids = asegurar_estructura(svc, exp["id"])
    return [f for f in hijos(svc, ids["1"]) if f["mimeType"] != MIME_CARPETA]


def descargar(svc, file_id, destino):
    """Descarga un archivo binario (los documentos del cliente son PDF/imagen)."""
    from googleapiclient.http import MediaIoBaseDownload
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(destino, "wb") as fh:
        done = False
        descarga = MediaIoBaseDownload(fh, req)
        while not done:
            _, done = descarga.next_chunk()
    return destino


def subir_paquete(svc, folio, dir_local):
    """Sube los PDFs y el manifiesto de la etapa 6 a '3 Documentos generados'.

    Si ya existe un archivo con el mismo nombre, el anterior se mueve a
    '0 Superados': mismo principio que con los documentos del cliente.
    """
    from googleapiclient.http import MediaFileUpload
    exp = carpeta_expediente(svc, folio)
    ids = asegurar_estructura(svc, exp["id"])
    existentes = {f["name"]: f for f in hijos(svc, ids["3"])}

    archivos = sorted(a for a in os.listdir(dir_local)
                      if a.lower().endswith((".pdf", ".json")))
    if not archivos:
        raise FileNotFoundError("No hay PDFs ni manifiesto en %s" % dir_local)

    subidos = []
    for nombre in archivos:
        if nombre in existentes:
            superar(svc, folio, existentes[nombre]["id"], ids=ids)
        mime = "application/pdf" if nombre.lower().endswith(".pdf") else "application/json"
        media = MediaFileUpload(os.path.join(dir_local, nombre), mimetype=mime)
        f = svc.files().create(
            body={"name": nombre, "parents": [ids["3"]]}, media_body=media,
            fields=CAMPOS, supportsAllDrives=True).execute()
        subidos.append(f)
    return subidos


def superar(svc, folio, file_id, ids=None):
    """Mueve un documento a '0 Superados'. No se borra nada: trazabilidad."""
    if ids is None:
        exp = carpeta_expediente(svc, folio)
        ids = asegurar_estructura(svc, exp["id"])
    meta = svc.files().get(fileId=file_id, fields="parents, name",
                           supportsAllDrives=True).execute()
    return svc.files().update(
        fileId=file_id, addParents=ids["0"],
        removeParents=",".join(meta.get("parents", [])),
        supportsAllDrives=True).execute()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def _tam(f):
    n = int(f.get("size", 0) or 0)
    return "%.1f MB" % (n / 1e6) if n >= 1e6 else "%.0f KB" % (n / 1e3)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    orden, args = argv[1], argv[2:]
    svc = servicio()

    if orden == "estructura":
        for exp in hijos(svc, CARPETA_RAIZ, solo_carpetas=True):
            print(exp["name"])
            for sub in hijos(svc, exp["id"], solo_carpetas=True):
                n = len(hijos(svc, sub["id"]))
                print("  %s  (%d)" % (sub["name"], n))

    elif orden == "nuevo" and len(args) == 2:
        carpeta = crear_expediente(svc, args[0], args[1])
        print("Creado: %s\n%s" % (carpeta["name"],
                                  "https://drive.google.com/drive/folders/" + carpeta["id"]))

    elif orden == "listar" and len(args) == 1:
        for f in documentos_cliente(svc, args[0]):
            print("%-60s %10s  %s  %s" % (f["name"], _tam(f),
                                          f["modifiedTime"][:10], f["id"]))

    elif orden == "bajar" and args:
        destino = args[1] if len(args) > 1 else os.path.join("descargas", args[0])
        os.makedirs(destino, exist_ok=True)
        for f in documentos_cliente(svc, args[0]):
            descargar(svc, f["id"], os.path.join(destino, f["name"]))
            print("Bajado: %s" % f["name"])

    elif orden == "subir" and len(args) == 2:
        for f in subir_paquete(svc, args[0], args[1]):
            print("Subido: %s" % f["name"])

    elif orden == "superar" and len(args) == 2:
        f = superar(svc, args[0], args[1])
        print("Movido a %s: %s" % (SUPERADOS, f.get("name", args[1])))

    elif orden == "reparar" and len(args) == 1:
        avisos = []
        exp = carpeta_expediente(svc, args[0])
        asegurar_estructura(svc, exp["id"], avisos)
        print("\n".join(avisos) if avisos else "La estructura ya estaba completa.")

    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
