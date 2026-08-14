# -*- coding: utf-8 -*-
"""
Pruebas de la capa visual: los componentes del sistema de diseño.

Aquí no se prueba que se vea bonito —eso no se prueba con código—. Se prueba lo
que puede salir mal al meter datos reales en HTML:

1. **El escapado.** Las justificaciones de riesgo las escribe una persona y
   pueden traer `<`, `&` o comillas. Sin escapar, el expediente se rompe en
   pantalla o peor: un texto del expediente se ejecuta como marcado.
2. **Que la ausencia de dato no se pinte como algo malo.** Es el principio del
   producto y ahora también es un problema de CSS: "sin datos" no puede caer en
   la clase roja ni dibujarse como una barra en cero.
3. **Los tres estados de un campo**, que en pantalla se ven parecidos y
   significan cosas distintas.

Todos los datos son inventados.

Se corre con:
    python tests/test_tema.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tema

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── LO IMPORTANTE · el CSS tiene que sobrevivir a st.markdown ────────────────
# Streamlit pasa el contenido de st.markdown por un parser de Markdown ANTES de
# insertarlo. Una línea en blanco dentro del <style> se lee como fin de párrafo:
# cierra la etiqueta ahí y el resto del CSS se imprime como texto visible en la
# pantalla. Pasó de verdad: la hoja llegó cortada en 948 de 20,000 caracteres,
# los tokens aplicaron y ninguna clase lo hizo. Una línea indentada tampoco
# sirve: cuatro espacios son un bloque de código.
print("El CSS inyectado sobrevive al parser de Markdown")
hoja = tema.css()
lineas = hoja.split("\n")
check(not [l for l in lineas if not l.strip()],
      "la hoja no lleva ni una linea en blanco: ahi se corta el <style>")
check(not [l for l in lineas if l[:1] in (" ", "\t")],
      "ni una linea indentada: cuatro espacios serian un bloque de codigo")
check(".neaop-metric{" in hoja and ".neaop-obs__just{" in hoja,
      "y llega completa hasta las clases del final")
check("--app-accent:%s" % tema.ACENTO in hoja.replace(" ", ""),
      "el acento de marca queda declarado despues del archivo importado")
check(hoja.rindex("--app-accent:") > hoja.index(".neaop-metric{"),
      "y va al final, para que gane sobre el valor del sistema de diseno")

# ── LO IMPORTANTE · el escapado ──────────────────────────────────────────────
print("Escapado de datos del expediente")
h = tema.observacion({
    "severidad": "intermedia", "estado": "aceptada",
    "descripcion": 'Cuentas <por> pagar & saldo — el cuerpo con "comillas"',
    "justificacion": 'Se acepta porque 5 < 10 & el "riesgo" es acotado',
    "aceptada_por": "Comité <interno>"})
check("<por>" not in h and "&lt;por&gt;" in h,
      "un titulo con < > se escapa en vez de romper el marcado")
check("5 &lt; 10 &amp; el" in h,
      "y la justificacion tambien: la escribe una persona, no el sistema")
check("Comité &lt;interno&gt;" in h, "y la firma de quien la acepto")
check("<div" in h and 'class="neaop-obs' in h,
      "el marcado propio del componente si sale como marcado")

check(tema.esc(None) == "", "un None se escapa a cadena vacia, no al texto 'None'")
check(tema.esc("a\nb") == "a<br>b", "los saltos de linea se conservan como <br>")

# Una razon social con ampersand es de lo mas comun en México.
f = tema.fila_expediente({"folio": "D-01", "razon_social": "GARCIA & ASOCIADOS, S.C.",
                          "etapa": "riesgo", "dias_en_etapa": 2}, "", False)
check("&amp;" in f and "& ASOC" not in f, "una razon social con & se escapa")

# ── veredictos: gris nunca es rojo ───────────────────────────────────────────
print("Veredictos")
check("neaop-badge--aprobado" in tema.badge_veredicto("Aprobado"), "Aprobado")
check("neaop-badge--comite" in tema.badge_veredicto("Comité"), "Comité")
check("neaop-badge--rechazado" in tema.badge_veredicto("Rechazado"), "Rechazado")

sd = tema.badge_veredicto("Sin datos suficientes")
check("neaop-badge--sindatos" in sd, "Sin datos suficientes tiene su propia clase")
check("rechazado" not in sd,
      "y NO cae en la de rechazado: la falta de datos no es una mala nota")

se = tema.badge_veredicto(None)
check("neaop-badge--sinevaluar" in se and "rechazado" not in se,
      "sin veredicto tampoco se pinta como rechazo")

# Cada veredicto lleva glifo propio: en escala de grises o con daltonismo, el
# color solo no alcanza para distinguirlos.
glifos = {tema.GLIFO_VEREDICTO[k] for k in tema.GLIFO_VEREDICTO}
check(len(glifos) == len(tema.GLIFO_VEREDICTO),
      "los glifos de veredicto son todos distintos entre si")

# ── modulos del score: sin datos no es cero ──────────────────────────────────
print("Modulos del score")
m = tema.modulo("Buró de crédito", 0.25, None)
check("neaop-modulo--sindatos" in m, "un modulo sin datos usa su variante")
check("sin datos" in m, "y lo dice con palabras")
check("width:0" not in m and "width: 0" not in m,
      "y NO dibuja una barra en cero: cero es un puntaje malo, no una ausencia")
check("se repartió" in m or "reparti" in m,
      "explica que su peso se repartio entre los demas")

m = tema.modulo("Declaración anual", 0.275, 0.61)
check("neaop-modulo--sindatos" not in m and "width:61" in m.replace(" ", ""),
      "un modulo con datos si dibuja su barra")
check("0.6100" in m, "con el puntaje a cuatro decimales")

# ── los tres estados de un campo ─────────────────────────────────────────────
print("Campo copiable")
c = tema.campo({"etiqueta": "Rfc", "valor": "AAA010101AAA", "tipo": "texto",
                "nota": None, "opcional": False})
check("neaop-field--falta" not in c and "neaop-field--vacio" not in c,
      "un campo con valor no lleva ninguna variante")
check("AAA010101AAA" in c, "y muestra su valor")

c = tema.campo({"etiqueta": "Teléfono", "valor": None, "tipo": "texto",
                "nota": None, "opcional": False})
check("neaop-field--falta" in c and "FALTA" in c, "sin valor y obligatorio: FALTA")

c = tema.campo({"etiqueta": "Logo", "valor": None, "tipo": "archivo",
                "nota": "No se pide.", "opcional": True})
check("neaop-field--vacio" in c, "sin valor pero opcional: vacio a proposito")
check("FALTA" not in c,
      "y NUNCA dice FALTA: es una decision, no trabajo pendiente")
check("No se pide." in c, "con el motivo a la vista, que es lo que lo hace decision")

# ── el score y su salvedad ───────────────────────────────────────────────────
print("Score")
s = tema.score_titular(0.5163, "Comité", 0.0)
check("0.5163" in s, "el score va completo, a cuatro decimales")
check("no propone" in s and "$0.00" not in s,
      "linea propuesta 0 se escribe 'no propone': $0.00 se lee como si propusiera cero")
s = tema.score_titular(0.7420, "Aprobado", 50000.0)
check("$50,000.00" in s, "y una linea real si se escribe con su monto")

sal = tema.salvedad(["modulo_buro"])
check("3 de los 4" in sal and "no es comparable" in sal,
      "la salvedad dice sobre cuantos modulos se calculo y que no es comparable")
check(tema.salvedad([]) == "", "sin modulos faltantes no hay salvedad que mostrar")

# ── etapas ───────────────────────────────────────────────────────────────────
print("Etapas")
e = tema.chip_etapa("riesgo", atorado=True)
check("neaop-etapa--atorado" in e, "una etapa atorada se marca")
check("3/6" in e, "el chip dice en que paso del flujo va")
check("neaop-etapa--atorado" not in tema.chip_etapa("riesgo", atorado=False),
      "y una que no esta atorada, no")

# Las etapas vienen de nea.py, no de una copia. La copia ya se desincronizó una
# vez: un expediente guardado como "firmado" no cuadraba con ninguna etapa y el
# flujo se dibujaba sin marcar nada, sin que nada fallara.
import nea
check(tema.ETAPAS is nea.ETAPAS or tema.ETAPAS == nea.ETAPAS,
      "la lista de etapas es la de nea.py, no una copia")
check(set(tema.ETAPA_NOMBRE) == set(nea.ETAPAS),
      "y cada etapa tiene su nombre para pantalla, sin sobrantes ni faltantes")

# Una etapa que no existe no puede pasar desapercibida.
raro = tema.chip_etapa("firmado")
check("—" in raro, "una etapa fuera del vocabulario se marca como desconocida")
check(tema.flujo_etapas("firmado").count("--current") == 0,
      "y el flujo no inventa cual es la actual")

fl = tema.flujo_etapas("riesgo")
check(fl.count('class="neaop-flow__step') == 6, "el flujo dibuja las seis etapas")
check(fl.count("--done") == 2, "con las dos anteriores marcadas como cumplidas")
check(fl.count("--current") == 1, "y una sola actual")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
