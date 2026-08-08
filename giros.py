# -*- coding: utf-8 -*-
"""
giros.py — La tabla de Giro del modelo de riesgo
=================================================
Seis códigos ordenados por **ciclo de conversión de efectivo**: cuánto tarda el
negocio en volver dinero una venta. Es lo que importa para una línea revolvente
que se paga cada semana: un transportista cobra al entregar, una constructora
cobra a estimaciones, y los dos pueden ser igual de sólidos y aun así tener una
capacidad de pago semanal muy distinta.

La proveeduría a gobierno se dejó **fuera** a propósito. El ciclo largo de
cobro a gobierno aplica en cualquier giro: un transportista que le factura a
una dependencia cobra tan lento como una constructora. Meterlo como código
contaminaría la clasificación, así que va como variable aparte.

El SAT no nos da el código SCIAN, solo el nombre oficial de la actividad. Por
eso esto **sugiere** un código a partir de palabras clave y el operador
confirma: la clasificación es un juicio de negocio, y una coincidencia de texto
no lo sustituye. Lo que sí hace es que el operador confirme en vez de inventar.
"""

CODIGOS = {
    "Codigo 1": (1.00, "Cobra al momento de vender",
                 "No genera cuenta por cobrar: el dinero entra el mismo día."),
    "Codigo 2": (0.80, "Cobra contra entrega o dentro de 15 días",
                 "Hay cuenta por cobrar pero rota rápido."),
    "Codigo 3": (0.65, "Crédito comercial de 30 días",
                 "El plazo estándar entre empresas."),
    "Codigo 4": (0.50, "45 a 60 días, o con inventario que financiar",
                 "El dinero se queda en inventario o en cadenas que pagan tarde."),
    "Codigo 5": (0.30, "Cobra por avance de obra o por proyecto, 90 días o más",
                 "El cobro depende de que alguien autorice un avance."),
    "Codigo 6": (0.15, "Cobro contingente o estacional",
                 "Puede pasar un ciclo entero sin ingreso."),
}

# Se evalúan en orden: la primera regla que coincide gana. El orden está pensado
# para que la naturaleza del servicio le gane al sector al que le vende —un
# veterinario que atiende ganaderías cobra como servicio profesional, no como
# ganadería—.
REGLAS = [
    # "transporte de" y no "transporte" a secas: así entra "transporte de
    # materiales para la construcción" —que cobra al entregar, aunque su
    # cliente sea una obra— y no entra "fabricación de equipo de transporte",
    # que es manufactura.
    ("Codigo 2", ["autotransporte", "transporte de", "mensajer", "paqueter",
                  "mudanza", "almacenamiento"]),
    ("Codigo 1", ["comercio al por menor", "restaurante", "preparación de alimentos",
                  "preparacion de alimentos", "alojamiento temporal", "hotel",
                  "gasolina", "farmacia", "autoservicio", "salones", "estética",
                  "estetica", "gimnasio", "estacionamiento", "lavander"]),
    ("Codigo 5", ["construcción", "construccion", "edificación", "edificacion",
                  "obra civil", "obras de ingenier", "instalaciones en construcciones",
                  "montaje de estructuras", "trabajos especializados para la construcción"]),
    ("Codigo 6", ["inmobiliari", "fraccionamiento", "minería", "mineria",
                  "extracción de petróleo", "extraccion de petroleo",
                  "agricultura", "cultivo", "cría y explotación", "cria y explotacion",
                  "pesca", "aprovechamiento forestal", "espectáculo", "espectaculo",
                  "artístico", "artistico", "deportivo", "casino", "juegos de azar"]),
    ("Codigo 4", ["fabricación", "fabricacion", "manufactura", "industria",
                  "elaboración", "elaboracion", "confección", "confeccion",
                  "textil", "impresión", "impresion", "ensamble"]),
    ("Codigo 3", ["comercio al por mayor", "servicios profesionales", "consultor",
                  "contabilidad", "jurídic", "juridic", "publicidad", "arquitectura",
                  "ingeniería", "ingenieria", "apoyo a los negocios", "limpieza",
                  "seguridad", "laboratorio", "veterinari", "reparación",
                  "reparacion", "mantenimiento", "alquiler", "arrendamiento",
                  "intermediari", "comisionista", "software", "informátic",
                  "informatic", "telecomunicaciones", "educativ", "salud"]),
]


def _sin_acentos(t):
    tabla = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    return "".join(tabla.get(c, c) for c in (t or "").lower())


def sugerir(actividad):
    """(codigo, palabra_que_coincidio) para el nombre oficial de una actividad."""
    texto = _sin_acentos(actividad)
    for codigo, claves in REGLAS:
        for clave in claves:
            if _sin_acentos(clave) in texto:
                return codigo, clave
    return None, None


def sugerir_de_actividades(actividades):
    """Sugiere el giro a partir de la lista de actividades del SAT.

    `actividades` son los dicts de `summary.economicActivities`, con `name` y
    `percentage`. Manda la actividad de mayor porcentaje: es la que el propio
    contribuyente declaró como principal. Se devuelve también el desglose para
    que el operador vea si el negocio está partido entre giros distintos, que
    es en sí una señal.
    """
    desglose = []
    for a in actividades or []:
        nombre = a.get("name") if isinstance(a, dict) else a
        pct = (a.get("percentage") if isinstance(a, dict) else None) or 0
        codigo, clave = sugerir(nombre)
        desglose.append({"actividad": nombre, "porcentaje": pct,
                         "codigo": codigo, "coincidencia": clave})

    con_codigo = [d for d in desglose if d["codigo"]]
    if not con_codigo:
        return None, desglose
    principal = max(con_codigo, key=lambda d: d["porcentaje"])
    return principal["codigo"], desglose


def peso(codigo):
    return CODIGOS.get(codigo, (None,))[0]
