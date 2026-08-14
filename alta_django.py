# -*- coding: utf-8 -*-
"""
alta_django.py — Los campos del alta manual en la base operativa
=================================================================
Mientras no haya conexión directa con el Django operativo, el alta se hace a
mano. Este módulo arma **exactamente** los campos de ese formulario, en el orden
en que aparecen en pantalla y con el formato que el formulario espera, para que
el operador copie y pegue sin traducir nada.

Las seis secciones y sus campos salen de las capturas del formulario, no de lo
que nosotros creemos que debería pedir. El orden importa: es el orden en que se
llena.

Tres decisiones que valen la pena explicar:

1. **Las fechas siempre en `aaaa-mm-dd`.** El expediente guarda fechas en varios
   formatos según de dónde vinieron —el formato de Beneficiario Controlador de la
   UIF pide `dd/mm/aaaa`, la CSF trae `aaaa-mm-dd`—. Aquí se normaliza todo. Un
   `19/06/1998` pegado en un campo que espera `1998-06-19` no falla: se guarda
   otra fecha.

2. **El nombre se parte y se valida contra la CURP.** El formulario pide nombre,
   apellido paterno y apellido materno por separado; nosotros guardamos el nombre
   completo. Partirlo por espacios es una adivinanza —"MARIA DE LA LUZ GARCIA
   SOTO" tiene cuatro maneras de partirse—. Los primeros cuatro caracteres de la
   CURP son la inicial del paterno, su primera vocal interna, la inicial del
   materno y la inicial del nombre: con eso la partición se **comprueba** en vez
   de suponerse. Si no cuadra, se dice que no cuadra.

3. **Lo que no tenemos se declara faltante, no se deja en blanco.** Un campo
   vacío en pantalla se lee como "no aplica"; uno marcado FALTA se lee como
   "hay que conseguirlo". No es lo mismo.

Los campos que el Django llena solo (Clabe stp, Fecha de pago, Estado) van
marcados como del sistema: en la captura aparecen como texto, no como campo.
"""

import re

import giros

# ── el catálogo del SAT que el formulario usa con clave ──────────────────────
# El formulario tiene un dropdown con la clave delante; la CSF trae el nombre
# largo sin clave. Sin este mapeo el operador tiene que buscar la clave a mano.
REGIMENES_FISCALES = {
    "regimen general de ley personas morales": "601 General de Ley Personas Morales",
    "general de ley personas morales": "601 General de Ley Personas Morales",
    "personas morales con fines no lucrativos": "603 Personas Morales con Fines no Lucrativos",
    "sociedades cooperativas de produccion que optan por diferir sus ingresos":
        "620 Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
    "regimen de las actividades empresariales con ingresos a traves de plataformas tecnologicas":
        "625 Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
    "regimen simplificado de confianza": "626 Régimen Simplificado de Confianza",
    "opcional para grupos de sociedades": "623 Opcional para Grupos de Sociedades",
    "coordinados": "624 Coordinados",
    "actividades agricolas, ganaderas, silvicolas y pesqueras":
        "622 Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
}

REGIMENES_CAPITAL = {
    "sociedad anonima de capital variable": "S.A. de C.V.",
    "sociedad anonima": "S.A.",
    "sociedad anonima promotora de inversion de capital variable": "S.A.P.I. de C.V.",
    "sociedad de responsabilidad limitada de capital variable": "S. de R.L. de C.V.",
    "sociedad de responsabilidad limitada": "S. de R.L.",
    "sociedad civil": "S.C.",
    "asociacion civil": "A.C.",
    "sociedad por acciones simplificada": "S.A.S.",
}

VOCALES = "AEIOU"

# El RENAPO ignora estas partículas al formar la CURP: "DE LA CRUZ" entra como
# CRUZ. Sin esto la comprobación rechaza justo los apellidos compuestos, que son
# los que más se parten mal a mano.
PARTICULAS = {"DA", "DAS", "DE", "DEL", "DER", "DI", "DIE", "DD", "EL", "LA",
              "LAS", "LO", "LOS", "LE", "LES", "MAC", "MC", "VAN", "VON", "Y"}

# El RENAPO toma la inicial del segundo nombre cuando el primero es uno de
# estos. Se aceptan las dos lecturas: aquí se comprueba una partición, no se
# genera una CURP, y hay CURPs emitidas con la inicial del primero.
NOMBRES_GENERICOS = {"MARIA", "MA", "MA.", "M", "JOSE", "J", "J."}

# Los cinco vínculos del formulario, en el orden de la captura.
VINCULOS = ["Participación directa o indirecta en el capital social",
            "Derechos de voto",
            "Facultades de decisión en órganos de administración",
            "Beneficio económico final del servicio u operación",
            "Otro medio de control (especificar)"]

FALTA = "FALTA"
SISTEMA = "— lo pone el sistema —"

# El comprobante de domicilio del beneficiario controlador no se pide. La
# decisión es de Nea (Luis Gómez Montijano, 2026-08-12) y tiene fundamento: el
# formulario no lo marca obligatorio y la CSF del beneficiario ya trae su
# domicilio fiscal, que es el dato que se necesita identificar. Va documentado
# aquí y no como campo faltante: si mañana se pide, se cambia esto y no hay que
# reconstruir por qué se había dejado de pedir.
NOTA_DOMICILIO_BC = ("No se pide. El domicilio del beneficiario ya viene en su "
                     "CSF y el campo no es obligatorio. Decisión de Nea del "
                     "2026-08-12.")


def _sin_acentos(t):
    tabla = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
             "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    return "".join(tabla.get(c, c) for c in (t or ""))


def _clave(t):
    return _sin_acentos((t or "").strip().lower())


def regimen_fiscal(nombre):
    """El nombre largo de la CSF llevado a la opción del dropdown, con clave."""
    if not nombre:
        return None
    hallado = REGIMENES_FISCALES.get(_clave(nombre))
    if hallado:
        return hallado
    # Si la CSF ya trae la clave delante, se respeta tal cual.
    if re.match(r"^\d{3}\s", nombre.strip()):
        return nombre.strip()
    return None


def regimen_capital(nombre):
    if not nombre:
        return None
    return REGIMENES_CAPITAL.get(_clave(nombre))


def fecha(valor):
    """Cualquier fecha del expediente en `aaaa-mm-dd`, o None si no se entiende.

    Se aceptan `aaaa-mm-dd`, `dd/mm/aaaa` y `dd-mm-aaaa`. No se adivina con
    fechas ambiguas de dos dígitos de año: es mejor devolver None y que salga
    FALTA que registrar 2098 en lugar de 1998.
    """
    if not valor:
        return None
    t = str(valor).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
    if m:
        d, mes, a = m.groups()
        return "%s-%02d-%02d" % (a, int(mes), int(d))
    return None


def _nucleo(apellido):
    """El apellido sin partículas, que es lo que la CURP toma en cuenta."""
    piezas = [p for p in re.split(r"\s+", _sin_acentos(apellido or "").upper()) if p]
    utiles = [p for p in piezas if p not in PARTICULAS]
    return " ".join(utiles or piezas)


def _primera_vocal_interna(apellido):
    for c in _nucleo(apellido)[1:]:
        if c in VOCALES:
            return c
    return None


def _iniciales_de_nombre(nombres):
    """Las iniciales que la CURP puede llevar para estos nombres de pila."""
    piezas = [p for p in re.split(r"\s+", _sin_acentos(nombres or "").upper()) if p]
    if not piezas:
        return set()
    validas = {piezas[0][:1]}
    if piezas[0] in NOMBRES_GENERICOS and len(piezas) > 1:
        validas.add(piezas[1][:1])
    return validas


def _cuadra_con_curp(nombres, paterno, materno, curp):
    """Compara la partición contra los cuatro primeros caracteres de la CURP.

    Con apellido materno ausente la CURP lleva 'X' en la tercera posición, que
    es justo la regla del RENAPO y no un caso raro.
    """
    if not curp or len(curp) < 4:
        return None
    c = _sin_acentos(curp[:4]).upper()
    esperado_materno = _nucleo(materno)[:1] if materno else "X"
    return (c[0] == _nucleo(paterno)[:1]
            and c[1] == (_primera_vocal_interna(paterno) or "X")
            and c[2] == esperado_materno
            and c[3] in _iniciales_de_nombre(nombres))


def partir_nombre(completo, curp=None, registral=None):
    """Parte un nombre completo en (nombres, paterno, materno).

    Devuelve además si la partición está **comprobada** contra la CURP o si es
    solo la convención (los dos últimos bloques son los apellidos). El operador
    necesita saber la diferencia: una partición no comprobada la tiene que
    revisar contra la identificación oficial antes de guardar.

    `registral` es el nombre en orden de registro —"PATERNO MATERNO NOMBRES"—,
    que es lo que trae la CSF. Cuando existe, se prueba también esa lectura.
    """
    piezas = [p for p in re.split(r"\s+", (completo or "").strip()) if p]
    if len(piezas) < 2:
        return {"nombres": completo or None, "paterno": None, "materno": None,
                "comprobado": False,
                "nota": "El nombre no tiene apellidos separables; revisar contra la identificación."}

    candidatos = []
    n = len(piezas)
    # Lectura normal: NOMBRES ... PATERNO ... MATERNO
    for i in range(1, n):
        for j in range(i + 1, n + 1):
            candidatos.append((" ".join(piezas[:i]), " ".join(piezas[i:j]),
                               " ".join(piezas[j:]) or None))
    # Lectura registral: PATERNO ... MATERNO ... NOMBRES
    if registral and _clave(registral) != _clave(completo):
        reg = [p for p in re.split(r"\s+", registral.strip()) if p]
        for i in range(1, len(reg)):
            for j in range(i + 1, len(reg) + 1):
                candidatos.append((" ".join(reg[j:]) or None, " ".join(reg[:i]),
                                   " ".join(reg[i:j])))

    for nombres, paterno, materno in candidatos:
        if nombres and _cuadra_con_curp(nombres, paterno, materno, curp):
            return {"nombres": nombres, "paterno": paterno, "materno": materno,
                    "comprobado": True,
                    "nota": "Partición comprobada contra la CURP %s." % curp}

    # Sin CURP que la compruebe queda la convención, marcada como tal. Se lee de
    # atrás hacia adelante absorbiendo partículas, para no dejar "DE LA" del lado
    # de los nombres de pila.
    def _tomar(hasta):
        i = hasta
        while i > 0 and _sin_acentos(piezas[i - 1]).upper() in PARTICULAS:
            i -= 1
        return i

    if len(piezas) == 2:
        conv = {"nombres": piezas[0], "paterno": piezas[1], "materno": None}
    else:
        im = _tomar(len(piezas) - 1)
        ip = _tomar(im - 1)
        if ip <= 0:  # no quedarían nombres de pila: se cae a la lectura simple
            im, ip = len(piezas) - 1, len(piezas) - 2
        conv = {"nombres": " ".join(piezas[:ip]),
                "paterno": " ".join(piezas[ip:im]),
                "materno": " ".join(piezas[im:])}
    conv["comprobado"] = False
    conv["nota"] = ("Partición por convención (los últimos dos bloques como "
                    "apellidos). " +
                    ("No cuadra con la CURP %s: revisar contra la identificación "
                     "oficial antes de guardar." % curp if curp else
                     "Sin CURP para comprobarla: revisar contra la identificación oficial."))
    return conv


def _campo(etiqueta, valor, tipo="texto", nota=None, opcional=False):
    """Un campo del formulario.

    `opcional` distingue el campo que se deja vacío a propósito —porque el dato
    no existe, no porque falte— del que hay que conseguir. Sin esa distinción la
    lista de pendientes se llena de ruido y deja de servir para decidir.
    """
    return {"etiqueta": etiqueta, "valor": valor, "tipo": tipo, "nota": nota,
            "opcional": opcional}


# Nombres legibles para los documentos que no se guardaron con nombre de archivo.
NOMBRES_DOC = {
    "csf_cliente": "Constancia de Situación Fiscal de la empresa",
    "comprobante_domicilio": "Comprobante de domicilio de la empresa",
    "identificacion_rep": "Identificación del representante legal",
    "identificacion_beneficiario": "Identificación del beneficiario controlador",
    "csf_beneficiario": "Constancia de Situación Fiscal del beneficiario",
}


def _doc(exp, tipo, sujeto=None):
    """El documento del expediente que va en un campo de archivo, con su link."""
    for d in reversed(exp.get("documentos") or []):
        if d.get("tipo") != tipo:
            continue
        if sujeto and d.get("sujeto") and _clave(d["sujeto"]) != _clave(sujeto):
            continue
        if d.get("superado_por"):
            continue
        fid = d.get("drive_file_id")
        return {"archivo": d.get("archivo") or NOMBRES_DOC.get(tipo, tipo),
                "url": "https://drive.google.com/file/d/%s/view" % fid if fid else None,
                "tipo": tipo}
    return None


def _archivo(exp, etiqueta, tipos, sujeto=None, nota=None, opcional=False):
    """El campo de archivo, probando los tipos de documento en orden.

    Se prueban varios porque el mismo papel se registra con tipos distintos
    según por dónde entró: la identificación de Diego está como
    `identificacion_rep` y también le sirve como beneficiario controlador. Es la
    misma INE.
    """
    if isinstance(tipos, str):
        tipos = [tipos]
    for t in tipos:
        d = _doc(exp, t, sujeto)
        if d:
            aviso = d["url"] or "Está en el expediente sin link de Drive: buscarlo en la carpeta."
            if d["tipo"] != tipos[0]:
                aviso = "Registrado como %s — es el mismo documento. %s" % (d["tipo"], aviso)
            return _campo(etiqueta, d["archivo"], "archivo", aviso)
    return _campo(etiqueta, None, "archivo",
                  nota or "No hay este documento en el expediente.", opcional)


def _division_firmada(exp, contiene):
    """La división firmada que contiene un documento dado, si ya se firmó."""
    for d in (exp.get("firma") or {}).get("documentos") or []:
        for c in d.get("contiene") or []:
            if _clave(contiene) in _clave(c):
                return d
    return None


# ── las seis secciones ───────────────────────────────────────────────────────

def _seccion_empresa(exp):
    c = (exp.get("cliente") or {}).get("validado") or {}
    perfil = exp.get("_perfil") or {}
    giro = perfil.get("actividad_principal") or c.get("actividad_economica")
    codigo, _ = giros.sugerir(giro or "")

    rf = regimen_fiscal(c.get("regimen_fiscal"))
    rc = regimen_capital(c.get("regimen_capital"))

    os_ = exp.get("obligado_solidario") or {}
    garantizada = bool(os_.get("razon_social") or os_.get("rfc"))
    nota_gar = None
    if garantizada:
        nota_gar = "Obligado solidario: %s (%s)." % (os_.get("razon_social"),
                                                    os_.get("rfc"))
        pf = exp.get("obligado_solidario_pf") or {}
        if pf.get("no_aplica"):
            nota_gar += (" La garantía es solo corporativa: no hay obligado "
                         "solidario persona física.")

    clabe = exp.get("domiciliacion_clabe") or {}
    if isinstance(clabe, str):
        clabe = {"clabe": clabe}

    firmada = (exp.get("firma") or {}).get("estado") == "completada"

    return {"seccion": "Empresa", "titulo": "Add Empresa", "campos": [
        _campo("Nombre comercial", c.get("nombre_comercial")),
        _campo("Razón social", c.get("razon_social")),
        _campo("Fecha de constitución", fecha((exp.get("constitucion") or {}).get("fecha")),
               "fecha"),
        _campo("Rfc", c.get("rfc")),
        _campo("Régimen Fiscal", rf, "lista",
               None if rf else "La CSF dice %r y no está en el catálogo: elegirlo a mano."
               % c.get("regimen_fiscal")),
        _campo("Régimen Capital", rc, "lista",
               None if rc else "La CSF dice %r: elegirlo a mano." % c.get("regimen_capital")),
        _campo("Giro Comercial", giro,
               nota=("Actividad principal declarada al SAT. Nuestro giro interno es %s."
                     % codigo) if codigo else None),
        _archivo(exp, "Cedula de identificacion fiscal", "csf_cliente"),
        _campo("¿Puede operar?", firmada, "checkbox",
               "Contratos firmados el %s." % (exp.get("firma") or {}).get("fecha")
               if firmada else "Sin contratos firmados todavía: no marcar."),
        _campo("CLABE de retiro", clabe.get("clabe"),
               nota=("Cuenta que el cliente autorizó por escrito en la domiciliación (%s). "
                     "Confirmar que el Django la use para retiro y no otra."
                     % clabe.get("banco")) if clabe.get("clabe") else
                    "No hay cuenta autorizada por escrito."),
        _campo("¿Tiene línea garantizada?", garantizada, "checkbox", nota_gar),
        _campo("Logo", None, "archivo",
               "El onboarding no lo pide y no lo tenemos; lo sube quien lo tenga.", True),
        _campo("Clabe stp", SISTEMA, "sistema"),
        _campo("Fecha de pago", SISTEMA, "sistema"),
        _campo("Estado", "Bloqueado", "sistema",
               "En la captura aparece como texto: el Django lo pone en Bloqueado."),
    ]}


def _seccion_direccion(exp):
    d = ((exp.get("cliente") or {}).get("validado") or {}).get("domicilio") or {}
    return {"seccion": "Dirección de la empresa", "titulo": "DIRECCIONES DE EMPRESAS",
            "campos": [
                _campo("Estado", "Activo", "lista", "El del registro, no el geográfico."),
                _campo("Calle", d.get("calle")),
                _campo("Número exterior", d.get("num_ext")),
                _campo("Número interior", d.get("num_int")),
                _campo("Colonia", d.get("colonia")),
                _campo("Municipio", d.get("municipio")),
                _campo("Código postal", d.get("cp")),
                _campo("Ciudad", d.get("ciudad") or d.get("municipio"),
                       nota=None if d.get("ciudad") else
                       "La CSF no trae ciudad aparte; se propone el municipio."),
                _campo("Estado", d.get("estado"), "lista", "El geográfico."),
                _archivo(exp, "Comprobante domicilio", "comprobante_domicilio"),
            ]}


def _seccion_linea(exp):
    a = (exp.get("credito") or {}).get("autorizada") or {}
    linea = a.get("linea")
    return {"seccion": "Línea de crédito", "titulo": "LÍNEAS DE CRÉDITO", "campos": [
        _campo("Estado", "Bloqueado", "lista",
               "Se desbloquea cuando la operación decida activarla, no en el alta."),
        _campo("Línea de crédito", ("%.0f" % linea) if linea is not None else None,
               nota="Autorizada el %s por %s. Score %s, veredicto del modelo %s."
               % (a.get("autorizada_el"), a.get("autorizada_por"), a.get("score"),
                  a.get("veredicto_modelo")) if linea is not None else
               "Sin línea autorizada: no dar de alta todavía."),
    ]}


def _seccion_origen(exp):
    t = exp.get("tracker") or {}
    origen = t.get("origen")
    return {"seccion": "Origen de la empresa", "titulo": "REFERIDO", "campos": [
        _campo("Empresa que refirió", None, "lista",
               "El prospecto vino de %s, que es un canal propio y no un referido de "
               "otra empresa: dejarlo vacío salvo que el catálogo tenga la opción "
               "del canal." % origen if origen else "Sin origen registrado en el tracker.",
               bool(origen)),
        _campo("Entidad que refirió", None, "lista",
               "Ejecutivo que lo trajo: %s. Si el catálogo lista a los ejecutivos, "
               "es el valor." % t.get("ejecutivo") if t.get("ejecutivo")
               else "Sin ejecutivo registrado.", bool(t.get("ejecutivo"))),
    ]}


def _persona(exp, p, prefijo, con_telefono, con_vinculos, archivos, notas_archivo=None):
    curp = p.get("curp")
    n = partir_nombre(p.get("nombre"), curp, p.get("nombre_registral"))
    fnac = fecha(p.get("fecha_nacimiento"))
    campos = [
        _campo("Nombre", n["nombres"], nota=None if n["comprobado"] else n["nota"]),
        _campo("Apellido Paterno", n["paterno"]),
        _campo("Apellido Materno", n["materno"],
               nota=None if n["materno"] else "Sin apellido materno registrado."),
        _campo("Fecha de nacimiento", fnac, "fecha",
               None if fnac else "No se pudo leer %r como fecha." % p.get("fecha_nacimiento")),
        _campo("Código de País", "MX", "lista",
               "México. Es el país de la persona, no la lada del teléfono: en la "
               "sección de beneficiarios este campo existe y el de teléfono no."),
        _campo("Rfc", p.get("rfc")),
        _campo("Curp", curp),
    ]
    if con_telefono:
        campos.append(_campo("Teléfono", p.get("telefono")))
        campos.append(_campo("Correo electrónico", p.get("correo")))
    for etiqueta, tipo in archivos:
        nota, opcional = (notas_archivo or {}).get(etiqueta, (None, False))
        campos.append(_archivo(exp, etiqueta, tipo, p.get("nombre"), nota, opcional))
    if con_vinculos:
        campos.append(_campo("Vínculos de Control o Beneficio",
                             vinculos_de(exp, p), "casillas",
                             p.get("criterio_determinacion")))
    return {"seccion": prefijo, "campos": campos}


def vinculos_de(exp, bc):
    """Los vínculos que se marcan, derivados del criterio ya documentado.

    No se marcan todos los que podrían aplicar: se marcan los que el expediente
    ya sostiene por escrito. Marcar un vínculo que nadie documentó es inventar el
    fundamento de la determinación.
    """
    crit = _clave(bc.get("criterio_determinacion"))
    marcados = []
    if "fraccion i" in crit or "capital social" in crit or (
            bc.get("participacion") or {}).get("porcentaje"):
        marcados.append(VINCULOS[0])
    if "voto" in crit:
        marcados.append(VINCULOS[1])
    org = exp.get("organo_administracion") or {}
    en_organo = any(_clave(v) == _clave(bc.get("nombre"))
                    for k, v in org.items() if isinstance(v, str))
    if "fraccion ii" in crit or "organos de administracion" in crit or en_organo:
        if VINCULOS[2] not in marcados:
            marcados.append(VINCULOS[2])
    if "fraccion iii" in crit or "beneficio economico" in crit:
        marcados.append(VINCULOS[3])
    return marcados


def secciones(exp):
    """Las seis secciones del formulario, en el orden en que se llenan."""
    out = [_seccion_empresa(exp), _seccion_direccion(exp), _seccion_linea(exp),
           _seccion_origen(exp)]

    rl = dict((exp.get("representante_legal") or {}).get("validado") or {})
    rl.setdefault("correo", ((exp.get("representante_legal") or {})
                             .get("propuesto") or {}).get("correo"))
    rl.setdefault("telefono", ((exp.get("cliente") or {}).get("validado") or {})
                  .get("telefono"))
    if not rl.get("telefono"):
        rl["telefono"] = ((exp.get("representante_legal") or {})
                          .get("propuesto") or {}).get("telefono")
    s = _persona(exp, rl, "Representante legal #1", True, False,
                 [("ID Oficial", "identificacion_rep")])
    s["titulo"] = "REPRESENTANTES LEGALES"
    out.append(s)

    for i, bc in enumerate(exp.get("beneficiarios_controladores") or [], 1):
        s = _persona(exp, bc, "Beneficiario controlador #%d" % i, False, True,
                     [("ID Oficial", ["identificacion_beneficiario",
                                      "identificacion_rep"]),
                      ("CSF", ["csf_beneficiario"]),
                      ("Comprobante de Domicilio",
                       ["comprobante_domicilio_beneficiario"])],
                     {"Comprobante de Domicilio": (NOTA_DOMICILIO_BC, True)})
        s["titulo"] = "BENEFICIARIOS CONTROLADORES" if i == 1 else None
        # El formato de identificación del BC es uno solo para toda la empresa y
        # ya va firmado: se sube el mismo archivo en los dos beneficiarios.
        bc = _archivo(exp, "Formato de Identificación del BC",
                      ["formato_bc_firmado", "formato_bc"],
                      nota="El formato de BC no está firmado todavía.")
        if bc["valor"] and bc["nota"]:
            bc["nota"] += (" El mismo archivo para los dos beneficiarios: "
                           "el formato es uno por empresa.")
        s["campos"].insert(-1, bc)
        out.append(s)
    return out


def pendientes(exp):
    """Lo que hay que resolver antes del alta, no lo que falta por llenar.

    Son dos cosas distintas: un campo de archivo vacío se resuelve subiendo el
    archivo; una observación alta abierta se resuelve con el cliente.
    """
    avisos = []
    f = exp.get("firma") or {}
    if f.get("estado") != "completada":
        avisos.append("Los contratos no están firmados (estado: %s). El alta va "
                      "después de la firma." % (f.get("estado") or "sin firma"))
    for o in exp.get("observaciones") or []:
        if o.get("estado") == "abierta" and o.get("severidad") == "alta":
            avisos.append("Observación alta abierta: %s" % o.get("descripcion"))
    for s in secciones(exp):
        for c in s["campos"]:
            if c["tipo"] in ("sistema", "checkbox", "casillas") or c.get("opcional"):
                continue
            if c["valor"] in (None, "", []):
                avisos.append("Sin dato para %s › %s" % (s["seccion"], c["etiqueta"]))
    return avisos


def texto(exp):
    """Todo el alta en texto plano, por si se quiere pegar de un jalón."""
    lineas = []
    for s in secciones(exp):
        lineas.append("")
        lineas.append("=== %s ===" % s["seccion"])
        for c in s["campos"]:
            v = c["valor"]
            if c["tipo"] == "checkbox":
                v = "SÍ (marcar)" if v else "NO (dejar sin marcar)"
            elif c["tipo"] == "casillas":
                v = "; ".join(v) if v else "ninguno"
            elif v in (None, "", []):
                v = "— vacío a propósito —" if c.get("opcional") else FALTA
            lineas.append("%-38s %s" % (c["etiqueta"] + ":", v))
    return "\n".join(lineas).strip()
