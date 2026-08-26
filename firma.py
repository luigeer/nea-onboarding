# -*- coding: utf-8 -*-
"""
firma.py — El plan de firma y el PDF unido para WeeTrust
=========================================================
WeeTrust sube **un documento por llamada** y asigna los firmantes por
`documentID`. Para que el cliente firme una sola vez —y no reciba un correo por
documento— hay que unir los PDF en uno y cortarlo en *divisiones*: cada división
es un documento firmable dentro del archivo unido.

Este módulo hace la parte determinista y verificable:

  `plan()`   qué documento va en cada división, en qué orden, quién firma cada
             división y con qué nivel de verificación.
  `unir()`   escribe el PDF unido en ese orden y devuelve el rango de páginas de
             cada división, que es lo que WeeTrust pide para dividir.

**Lo que este módulo NO hace: mandar a firma.** No hay una sola llamada HTTP
aquí. Enviar un documento a firma es irreversible y le llega a un cliente real;
esa decisión la toma una persona, viendo el plan. El módulo deja el archivo y las
instrucciones listas.

Las reglas de división son de negocio, no técnicas:

  · El contrato y las adendas de obligado solidario **siempre** van juntos. Son
    un solo acuerdo: la adenda no significa nada sin el contrato que garantiza.
  · Si hay domiciliación, el formato de beneficiario controlador y el expediente
    PLD van juntos; si no la hay, van en divisiones separadas.
  · La autorización de domiciliación va aparte: está dirigida al banco, no a Nea.

Niveles de verificación, también de negocio:

  · Nea firma simple. Es nuestra propia firma y la identidad no está en duda.
  · El representante legal del cliente firma con verificación de identidad y
    background check. Es la firma que sostiene la exigibilidad del contrato.
"""

import os

SIMPLE = "simple"
IDENTIDAD = "identidad_y_background"

# El orden dentro del PDF unido. Importa porque las divisiones son rangos de
# página contiguos: si el orden cambia, los rangos dejan de cerrar.
ORDEN = ["contrato", "contrato_pfae", "adenda_os_pm", "adenda_os_pf", "beneficiario_controlador",
         "pld_pm", "pld_pf", "anexo_razonado", "domiciliacion"]

ETIQUETAS = {
    "contrato": "Carátula del Contrato de Crédito",
    "contrato_pfae": "Carátula del Contrato de Crédito",
    "adenda_os_pm": "Adenda de Obligado Solidario (persona moral)",
    "adenda_os_pf": "Adenda de Obligado Solidario (persona física)",
    "beneficiario_controlador": "Formato de Beneficiario Controlador",
    "pld_pm": "Expediente de Identificación PLD",
    "pld_pf": "Expediente de Identificación PLD",
    "anexo_razonado": "Anexo de Análisis Razonado",
    "domiciliacion": "Autorización de Domiciliación",
}


def _division_de(clave, hay_domiciliacion):
    """A qué división pertenece cada documento.

    Devuelve el nombre de la división. Los que comparten nombre se firman juntos.
    """
    if clave in ("contrato", "contrato_pfae", "adenda_os_pm", "adenda_os_pf"):
        return "Contrato y obligación solidaria"
    if clave == "domiciliacion":
        return "Autorización de domiciliación"
    if clave in ("beneficiario_controlador", "pld_pm", "pld_pf"):
        # La regla la fija el negocio: con domiciliación se agrupan, sin ella se
        # separan. No hay una razón técnica; se respeta como está escrita.
        return ("Identificación del cliente" if hay_domiciliacion
                else ETIQUETAS[clave])
    return ETIQUETAS.get(clave, clave)


def _nivel(firmante):
    """Simple para Nea, verificación completa para el cliente.

    El rol viene del manifiesto, que es la única fuente de quién firma qué.
    """
    if firmante.get("rol") in ("nea", "cumplimiento"):
        return SIMPLE
    return IDENTIDAD


def plan(manifiesto, exp=None):
    """El plan de firma: divisiones en orden, con sus documentos y firmantes.

    `manifiesto` es el que escribe `generar_paquete.py`. De ahí sale quién firma
    cada documento, para no volver a deducirlo: esa lógica ya vive en un solo
    lugar y duplicarla es cómo se separan.
    """
    docs = {d["clave"]: d for d in manifiesto.get("documentos", [])}
    hay_dom = "domiciliacion" in docs

    divisiones, orden_div = {}, []
    for clave in ORDEN:
        if clave not in docs:
            continue
        nombre = _division_de(clave, hay_dom)
        if nombre not in divisiones:
            divisiones[nombre] = {"division": nombre, "documentos": [],
                                  "firmantes": []}
            orden_div.append(nombre)
        divisiones[nombre]["documentos"].append({
            "clave": clave, "archivo": docs[clave]["archivo"],
            "etiqueta": ETIQUETAS.get(clave, clave),
        })
        for f in docs[clave].get("firmantes") or []:
            nombre_f = f.get("nombre")
            if not nombre_f:
                continue
            ya = next((x for x in divisiones[nombre]["firmantes"]
                       if x["nombre"] == nombre_f), None)
            if ya:
                # Una persona puede firmar dos documentos de la misma división
                # con roles distintos —Marcos es representante legal y oficial de
                # cumplimiento—. Se conserva el nivel más exigente.
                if ya["nivel"] == SIMPLE and _nivel(f) == IDENTIDAD:
                    ya["nivel"] = IDENTIDAD
                if f.get("rol") not in ya["roles"]:
                    ya["roles"].append(f.get("rol"))
                continue
            divisiones[nombre]["firmantes"].append({
                "nombre": nombre_f,
                "roles": [f.get("rol")],
                "cargo": f.get("cargo"),
                "correo": f.get("correo"),
                "nivel": _nivel(f),
            })

    return {"folio": manifiesto.get("folio"),
            "divisiones": [divisiones[n] for n in orden_div]}


def unir(plan_firma, dir_paquete, destino):
    """Escribe el PDF unido en el orden del plan y devuelve los rangos.

    Cada división queda con `pagina_inicial` y `pagina_final`, contadas desde 1,
    que es lo que hay que teclear en WeeTrust para dividir.
    """
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    pagina = 1
    for div in plan_firma["divisiones"]:
        div["pagina_inicial"] = pagina
        for doc in div["documentos"]:
            ruta = os.path.join(dir_paquete, doc["archivo"])
            lector = PdfReader(ruta)
            doc["paginas"] = len(lector.pages)
            doc["pagina_inicial"] = pagina
            for p in lector.pages:
                escritor.add_page(p)
            pagina += doc["paginas"]
        div["pagina_final"] = pagina - 1

    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with open(destino, "wb") as fh:
        escritor.write(fh)
    plan_firma["archivo_unido"] = os.path.basename(destino)
    plan_firma["paginas_totales"] = pagina - 1
    return plan_firma


# ─────────────────────────────────────────────────────────────────────────────
# El correo
# ─────────────────────────────────────────────────────────────────────────────
ASUNTO = "Contrato de Crédito Nea"


def mensaje(exp):
    """El texto del correo que acompaña la solicitud de firma.

    Es lo primero que el cliente lee de nosotros después de haber entregado
    documentos durante semanas, así que abre agradeciendo y dice en tres renglones
    qué tiene que hacer. Lo que no hace es explicar el producto: eso ya lo vendió
    el ejecutivo, y repetirlo aquí retrasa la firma.
    """
    from schema_expediente import _get

    razon = _get(exp, "cliente.validado.razon_social") or "su empresa"
    rep = _get(exp, "representante_legal.validado.nombre") or ""
    linea = _get(exp, "credito.autorizada.linea")
    plazo = (_get(exp, "credito.autorizada.plazo") or "").lower()
    nombre_corto = rep.split()[0].capitalize() if rep else ""

    monto = "$%s" % format(float(linea), ",.2f") if linea else "su línea"
    saludo = "Estimado %s:" % nombre_corto if nombre_corto else "Estimado cliente:"

    return """%s

Bienvenido a Nea. Su línea de crédito de %s con pago %s quedó autorizada
a nombre de %s, y con este correo le enviamos los documentos para firma.

Cómo firmar:

1. Abra el enlace de este correo desde su celular. Va a necesitar la cámara.
2. Tenga a la mano su identificación oficial vigente, la misma que nos entregó.
3. La plataforma le va a pedir una foto de su identificación y una selfie para
   verificar que es usted. Es un requisito de la regulación y toma menos de dos
   minutos.
4. Revise cada documento y fírmelos. Son varios y se firman en una sola sesión.

Al terminar recibirá una copia de todo lo firmado. Una vez firmados los
documentos, su representante comercial se pondrá en contacto con ustedes para
agendar la capacitación y que puedan empezar a usar la plataforma cuanto antes.

Si algo no funciona o tiene alguna duda antes de firmar, responda a este correo
y lo resolvemos.

Gracias por la confianza,
Equipo Nea
Grit Payment Solutions, S.A.P.I. de C.V.""" % (saludo, monto, plazo, razon)


# ─────────────────────────────────────────────────────────────────────────────
def texto_plan(plan_firma, exp=None):
    """El plan en texto, para revisarlo antes de tocar WeeTrust."""
    L = ["PLAN DE FIRMA — %s" % plan_firma.get("folio"),
         "=" * (17 + len(str(plan_firma.get("folio")))), ""]
    if plan_firma.get("archivo_unido"):
        L.append("Archivo a subir: %s  (%d páginas)"
                 % (plan_firma["archivo_unido"], plan_firma["paginas_totales"]))
        L.append("")
    L.append("Se sube UN archivo y se corta en %d división(es):"
             % len(plan_firma["divisiones"]))
    L.append("")
    for i, div in enumerate(plan_firma["divisiones"], 1):
        rango = ""
        if div.get("pagina_inicial"):
            rango = ("  páginas %d–%d" % (div["pagina_inicial"], div["pagina_final"])
                     if div["pagina_final"] > div["pagina_inicial"]
                     else "  página %d" % div["pagina_inicial"])
        L.append("División %d: %s%s" % (i, div["division"], rango))
        for doc in div["documentos"]:
            L.append("    · %-46s p.%d (%d pág.)"
                     % (doc["etiqueta"], doc.get("pagina_inicial", 0),
                        doc.get("paginas", 0)))
        for f in div["firmantes"]:
            nivel = ("firma simple" if f["nivel"] == SIMPLE
                     else "firma con verificación de identidad y background check")
            L.append("    firma: %-34s %s" % (f["nombre"], nivel))
        L.append("")
    L.append("Asunto del correo: %s" % ASUNTO)
    L.append("")
    L.append("NO se envía nada: el documento queda precargado como borrador y lo")
    L.append("manda a firma una persona, después de revisar este plan.")
    return "\n".join(L)
