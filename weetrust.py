# -*- coding: utf-8 -*-
"""
weetrust.py — Cliente de WeeTrust, solo hasta borrador
=======================================================
Sube el PDF unido, lo corta en divisiones y asigna los firmantes con su nivel de
verificación. **No manda a firma.** No hay aquí una función que envíe, y eso es
una decisión de diseño, no un pendiente.

**Por qué el envío no se automatiza.** WeeTrust no tiene ambiente de pruebas:
cada llamada va a producción. Y `PUT /documents/signatory` **manda los correos
por default** —así lo documenta WeeTrust—, así que este cliente fuerza
`disableMailing: true` en cada llamada, sin dejar forma de apagarlo. El envío lo
hace una persona desde la plataforma, viendo el documento ya dividido. Un bug
aquí no se deshace: le llega un contrato a un cliente real.

Lo que sí hace, y es la parte que se equivoca al hacerla a mano:

  · unir los PDF y calcular en qué páginas cortar (`splitPage`)
  · poner `identification: "face"` con `check: true` al representante del
    cliente, y firma simple a los nuestros
  · precargar el asunto y el mensaje del correo, para que cuando alguien le dé
    enviar salga el texto correcto y no uno improvisado

Documentado en https://developer.weetrust.mx/reference/ — verificado agosto 2026:
`POST /documents` con headers `user-id`, `token` y `splitPage`;
`PUT /documents/signatory` con `documentID`, `signatory[]`, `title`, `message`,
`disableMailing`.
"""

import json
import os
import urllib.error
import urllib.request

import firma

# Produccion es api.weetrust.MX; el sandbox de la documentacion es
# api-sandbox.weetrust.COM.MX. Son dominios distintos, asi que inferir el de
# produccion quitandole "-sandbox" al del sandbox da un host que no existe: lo
# intente y el DNS no resuelve. Se deja el verificado, y WEETRUST_BASE en el .env
# lo sobreescribe si algun dia cambia.
BASE = "https://api.weetrust.mx"

# Cómo se traduce el nivel del plan de firma a lo que pide WeeTrust.
#
#   firma simple           sin `identification`: se firma con el enlace y ya.
#   identidad y background `identification: "face"` más `check: true`. Es "face"
#                          y no "id" porque la biometría facial deja mejor
#                          soportada la identificación en el expediente: queda
#                          la selfie contra la credencial, no solo la foto de la
#                          credencial. Y `check` solo aplica con "face".
NIVELES = {
    firma.SIMPLE: {},
    firma.IDENTIDAD: {"identification": "face", "check": True},
}


class ErrorWeeTrust(Exception):
    pass


def _base():
    """La URL base, del .env si está, y si no la de producción verificada."""
    import db
    return (db._leer_env().get("WEETRUST_BASE") or "").rstrip("/") or BASE


def _config():
    """Las credenciales, del .env. Nunca se escriben en el código."""
    import db
    env = db._leer_env()
    usuario = env.get("WEETRUST_USER_ID")
    llave = env.get("WEETRUST_API_KEY")
    if not (usuario and llave):
        raise ErrorWeeTrust(
            "Faltan WEETRUST_USER_ID y WEETRUST_API_KEY en el .env.\n"
            "Se piden en la plataforma de WeeTrust; van en el mismo archivo que\n"
            "las llaves de Supabase y Syntage, que está en .gitignore.")
    return usuario, llave


def token():
    """El token de acceso. Vive pocos minutos, así que se pide en cada corrida.

    Verificado contra la API en agosto 2026, porque no está en la documentación
    pública: la llave va en el header **`api-key`** —no en el cuerpo, y no se
    llama `X-API-Key`— junto con `user-id`, y la petición va **sin cuerpo**. El
    token viene en `responseData.accessToken`.

    Los dos intentos anteriores fallaron y vale dejarlo escrito: con la llave en
    el cuerpo devuelve un 400 cuyo mensaje habla de `user-id`, que manda a buscar
    el problema al lado equivocado.
    """
    usuario, llave = _config()
    r = _pedir("POST", "/access/token",
               headers={"api-key": llave, "user-id": usuario})
    acceso = (r.get("responseData") or {}).get("accessToken")
    if not acceso:
        raise ErrorWeeTrust("La autenticación no devolvió accessToken. "
                            "Respuesta: %s" % json.dumps(r)[:300])
    return acceso


def _pedir(metodo, ruta, cuerpo=None, headers=None, token_acceso=None):
    cabeceras = {"Content-Type": "application/json", "Accept": "application/json"}
    if token_acceso:
        cabeceras["token"] = token_acceso
    cabeceras.update(headers or {})

    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    pet = urllib.request.Request(_base() + ruta, data=datos, headers=cabeceras,
                                 method=metodo)
    try:
        with urllib.request.urlopen(pet, timeout=60) as r:
            texto = r.read().decode("utf-8")
            return json.loads(texto) if texto else {}
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:500]
        raise ErrorWeeTrust("%s %s -> HTTP %s\n%s" % (metodo, ruta, e.code, detalle))
    except urllib.error.URLError as e:
        raise ErrorWeeTrust("No se pudo conectar a %s: %s" % (_base(), e.reason))


# ─────────────────────────────────────────────────────────────────────────────
def paginas_de_corte(plan_firma):
    """Los números de página donde WeeTrust debe cortar, para `splitPage`.

    El corte va en la primera página de cada división a partir de la segunda: si
    la división 2 empieza en la página 18, ahí se corta. La primera no lleva
    corte porque el documento ya empieza ahí.
    """
    return [d["pagina_inicial"] for d in plan_firma["divisiones"][1:]
            if d.get("pagina_inicial")]


def firmantes_de(division, exp=None):
    """Los `signatory` de una división, con su nivel de verificación."""
    from schema_expediente import _get

    fuera = []
    for f in division["firmantes"]:
        correo = f.get("correo")
        if not correo and exp is not None and "cliente" in (f.get("roles") or []):
            correo = _get(exp, "representante_legal.propuesto.correo")
        s = {"name": f["nombre"], "emailID": correo}
        s.update(NIVELES.get(f["nivel"], {}))
        fuera.append(s)
    return fuera


def subir_borrador(plan_firma, ruta_pdf, exp=None, asunto=None, mensaje=None):
    """Sube el PDF unido, lo divide y asigna firmantes. **Sin enviar.**

    Devuelve lo que responde WeeTrust en cada paso, para poder verificar contra
    la plataforma. `disableMailing` va en `True` y no es parametrizable: si algún
    día hace falta enviar desde aquí, que sea un cambio de código explícito y
    revisado, no una bandera que alguien pasa por error.
    """
    import base64

    acceso = token()
    usuario, _ = _config()

    with open(ruta_pdf, "rb") as fh:
        contenido = base64.b64encode(fh.read()).decode("ascii")

    cortes = paginas_de_corte(plan_firma)
    headers = {"user-id": usuario}
    if cortes:
        headers["splitPage"] = ",".join(str(p) for p in cortes)

    subida = _pedir("POST", "/documents", cuerpo={"document": contenido},
                    headers=headers, token_acceso=acceso)

    # Con `splitPage`, WeeTrust crea un documento por división. Se emparejan en
    # orden; si el número no coincide se detiene en vez de asignar firmantes a
    # la división equivocada, que sería peor que no asignarlos.
    ids = _ids_de(subida)
    if len(ids) != len(plan_firma["divisiones"]):
        raise ErrorWeeTrust(
            "WeeTrust devolvió %d documento(s) y el plan tiene %d división(es). "
            "No se asignan firmantes: hay que revisar el corte a mano.\n%s"
            % (len(ids), len(plan_firma["divisiones"]), json.dumps(subida)[:400]))

    resultados = [{"paso": "documents", "respuesta": subida}]
    for doc_id, division in zip(ids, plan_firma["divisiones"]):
        cuerpo = {
            "documentID": doc_id,
            "signatory": firmantes_de(division, exp),
            "title": asunto or firma.ASUNTO,
            "message": mensaje or "",
            # NO SE TOCA. Ver el encabezado del módulo.
            "disableMailing": True,
        }
        resultados.append({
            "paso": "signatory", "division": division["division"],
            "documentID": doc_id,
            "respuesta": _pedir("PUT", "/documents/signatory", cuerpo=cuerpo,
                                headers={"user-id": usuario}, token_acceso=acceso),
        })
    return resultados


def _ids_de(respuesta):
    """Saca los documentID de la respuesta, tolerando varias formas.

    WeeTrust no documenta la forma exacta cuando se usa `splitPage`, así que se
    prueban las que aparecen en la referencia y, si ninguna calza, se devuelve
    vacío para que el llamador se detenga con la respuesta cruda a la vista.
    """
    if isinstance(respuesta, dict):
        for clave in ("documentIDs", "documentsID", "documents", "data"):
            v = respuesta.get(clave)
            if isinstance(v, list) and v:
                return [x.get("documentID") or x.get("_id") or x
                        if isinstance(x, dict) else x for x in v]
        uno = respuesta.get("documentID") or respuesta.get("_id")
        if uno:
            return [uno]
    if isinstance(respuesta, list):
        return [x.get("documentID") or x.get("_id") for x in respuesta
                if isinstance(x, dict)]
    return []
