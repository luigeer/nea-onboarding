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


def _pedir(metodo, ruta, cuerpo=None, headers=None, token_acceso=None,
           archivo=None, espera=180):
    """Una llamada a la API. `archivo` es (nombre, bytes) y va como multipart.

    La documentación dice que el archivo puede ir "como cadena base64 o multipart
    dentro de la estructura JSON", que son dos cosas distintas. Con base64 dentro
    del JSON la petición se cuelga: 1.3 MB de texto y el servidor nunca contesta.
    Multipart sí responde, y es lo que decía la especificación original.

    La espera es de tres minutos porque subir un contrato de 24 páginas no es
    instantáneo y un timeout corto deja la duda de si el documento se creó o no
    —que es peor que esperar—.
    """
    cabeceras = {"Accept": "application/json"}
    if token_acceso:
        cabeceras["token"] = token_acceso
    cabeceras.update(headers or {})

    if archivo is not None:
        nombre, contenido = archivo
        limite = "----NeaOnboarding%d" % len(contenido)
        partes = []
        for clave, valor in (cuerpo or {}).items():
            partes.append(
                ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (limite, clave, valor)).encode("utf-8"))
        partes.append(
            ("--%s\r\nContent-Disposition: form-data; name=\"document\"; "
             "filename=\"%s\"\r\nContent-Type: application/pdf\r\n\r\n"
             % (limite, nombre)).encode("utf-8"))
        partes.append(contenido)
        partes.append(("\r\n--%s--\r\n" % limite).encode("utf-8"))
        datos = b"".join(partes)
        cabeceras["Content-Type"] = "multipart/form-data; boundary=%s" % limite
    else:
        cabeceras["Content-Type"] = "application/json"
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None

    pet = urllib.request.Request(_base() + ruta, data=datos, headers=cabeceras,
                                 method=metodo)
    try:
        with urllib.request.urlopen(pet, timeout=espera) as r:
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


def firmantes_de(division, exp=None, redirigir_a=None):
    """Los `signatory` de una división, con su nivel de verificación.

    `redirigir_a` manda TODOS los correos a una sola dirección. Es para probar
    con un documento real sin arriesgar que le llegue algo a un cliente: aunque
    `disableMailing` evita el envío, si esa bandera no se comportara como está
    documentada, el correo llega a quien prueba y no al cliente. Es explícito a
    propósito —hay que pasarlo— porque un default que redirige correos es un
    default que algún día manda un contrato al lugar equivocado.
    """
    from schema_expediente import _get

    fuera = []
    for f in division["firmantes"]:
        correo = f.get("correo")
        if not correo and exp is not None and "cliente" in (f.get("roles") or []):
            correo = _get(exp, "representante_legal.propuesto.correo")
        if redirigir_a:
            correo = _con_sufijo(redirigir_a, f["nombre"])
        s = {"name": f["nombre"], "emailID": correo}
        s.update(NIVELES.get(f["nivel"], {}))
        fuera.append(s)
    return fuera


def _con_sufijo(correo, nombre):
    """`luis@getnea.com` + "DIEGO RAMIREZ" -> `luis+diego@getnea.com`.

    WeeTrust rechaza el documento con "Some emails are repeated" si dos firmantes
    comparten correo, así que redirigir todo a una sola dirección no funciona. El
    sufijo después del `+` lo ignora la entrega —el correo llega igual a la misma
    bandeja— y a la API le basta para verlos como distintos.
    """
    usuario, _, dominio = correo.partition("@")
    if not dominio:
        return correo
    slug = "".join(c for c in nombre.split()[0].lower() if c.isalnum()) or "firmante"
    return "%s+%s@%s" % (usuario.split("+")[0], slug, dominio)


def subir_borrador(plan_firma, ruta_pdf, exp=None, asunto=None, mensaje=None,
                   redirigir_a=None):
    """Sube el PDF unido y lo divide. **Nada más.** Queda en DRAFT.

    Aquí NO se asignan firmantes, y eso se descubrió probando contra la API:

    **`PUT /documents/signatory` saca el documento de DRAFT y lo pasa a PENDING**,
    y además genera de inmediato las URL de firma —`signing.url`, con vigencia de
    30 días— para cada firmante. `disableMailing: true` evita los correos, y se
    verificó que los evita (`emailTracking` vacío), pero los enlaces quedan vivos:
    cualquiera que los tenga puede firmar. Eso no es un borrador.

    **Y la configuración de verificación no persiste.** Se mandó `identification:
    "face"` con `check: true` y el firmante quedó guardado sin esos campos, con
    `identitySessionId` vacío. O sea que automatizarla no solo saca el documento
    de borrador: tampoco logra lo que se quería.

    Así que la integración hace lo que sí aporta y es seguro —subir el archivo
    unido con los cortes en las páginas correctas, que es la parte que se equivoca
    a mano— y el resto se configura en la plataforma, donde además se ve.
    """
    acceso = token()
    usuario, _ = _config()

    with open(ruta_pdf, "rb") as fh:
        contenido = fh.read()

    cortes = paginas_de_corte(plan_firma)
    headers = {"user-id": usuario}
    if cortes:
        headers["splitPage"] = ",".join(str(p) for p in cortes)

    subida = _pedir("POST", "/documents", headers=headers, token_acceso=acceso,
                    archivo=(os.path.basename(ruta_pdf), contenido))

    d = subida.get("responseData") or {}
    ids = _ids_de(subida)
    aviso = None
    if len(ids) != len(plan_firma["divisiones"]):
        # No se aborta: el documento ya está subido y ya vive en la plataforma.
        # Avisar sirve; fingir que no pasó, no.
        aviso = ("WeeTrust reporta %d documento(s) y el plan tiene %d división(es). "
                 "Hay que revisar el corte en la plataforma."
                 % (len(ids), len(plan_firma["divisiones"])))

    return {
        "documentID": d.get("documentID"),
        "status": d.get("status"),
        "divisiones": ids,
        "url_archivo": (d.get("documentFileObj") or {}).get("url"),
        "aviso": aviso,
        # Lo que hay que capturar en la plataforma, para no deducirlo ahí.
        "firmantes_sugeridos": [
            {"division": div["division"],
             "paginas": "%s-%s" % (div.get("pagina_inicial"), div.get("pagina_final")),
             "firmantes": firmantes_de(div, exp, redirigir_a)}
            for div in plan_firma["divisiones"]],
    }


def _ids_de(respuesta):
    """Los documentID de una subida, en el orden de las divisiones.

    Verificado contra la API: `POST /documents` con `splitPage` devuelve el
    documento **de la última división** en `responseData.documentID`, y las
    anteriores en `responseData.splitChildDocumentId`, separadas por comas. Así
    que el orden correcto es los hijos primero y el devuelto al final.

    Los hijos NO se pueden consultar mientras el documento está en DRAFT: `GET
    /documents/{id}` responde "Document not found" y tampoco aparecen en el
    listado. Se materializan cuando el documento sale de borrador. Por eso los
    firmantes se asignan al documento padre y no división por división.
    """
    d = respuesta.get("responseData") if isinstance(respuesta, dict) else None
    d = d if isinstance(d, dict) else (respuesta if isinstance(respuesta, dict) else {})
    padre = d.get("documentID") or d.get("_id")
    hijos = [x for x in (d.get("splitChildDocumentId") or "").split(",") if x]
    return hijos + ([padre] if padre else [])
