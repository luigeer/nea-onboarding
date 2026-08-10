# -*- coding: utf-8 -*-
"""
Pruebas del puente entre Supabase y el modelo.

Aquí es donde un error no se ve: el modelo corre, devuelve un número, y nadie
nota que el número se calculó sobre la cuenta equivocada o sobre el buró del
garante. Por eso se prueba con un cliente falso de Supabase en vez de con la
base real.

Todos los datos son inventados.

Se corre con:
    python tests/test_insumos_riesgo.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import insumos_riesgo

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── un Supabase de mentiras ──────────────────────────────────────────────────
class _Consulta(object):
    def __init__(self, filas):
        self.filas = list(filas)

    def select(self, *a, **k):
        return self

    def eq(self, campo, valor):
        self.filas = [f for f in self.filas if f.get(campo) == valor]
        return self

    def order(self, campo, desc=False):
        self.filas.sort(key=lambda f: (f.get(campo) is None, f.get(campo)),
                        reverse=desc)
        return self

    def execute(self):
        return type("R", (), {"data": self.filas})()


class FakeSB(object):
    def __init__(self, tablas):
        self.tablas = tablas

    def table(self, nombre):
        return _Consulta(self.tablas.get(nombre, []))


BURO = [
    {"folio": "T-01", "sujeto": "EJEMPLO, S.A. de C.V.", "fecha_consulta": "2026-08-01",
     "resultado": "sin_historial", "folio_consulta": "111", "score_pyme": None,
     "ocurrencias_mora": None},
    {"folio": "T-01", "sujeto": "GARANTE, S.A. de C.V. (obligado solidario)",
     "fecha_consulta": "2026-08-02", "resultado": "con_historial",
     "folio_consulta": "222", "score_pyme": 192, "ocurrencias_mora": 0},
]

EDOS = [
    {"folio": "T-01", "banco": "BBVA", "cuenta": "0001", "fecha_final": "2026-05-31",
     "numero_depositos": 2, "numero_depositos_operativo": 0,
     "numero_retiros": 8, "numero_retiros_operativo": 5,
     "monto_depositos": 200000.0, "monto_depositos_operativo": 0.0,
     "monto_retiros": 197861.45, "monto_retiros_operativo": 193816.58,
     "saldo_inicial": 9062.38, "saldo_final": 11200.93,
     "saldo_promedio": 13741.18, "saldo_minimo": 2506.44, "saldo_maximo": 170773.44},
    {"folio": "T-01", "banco": "BBVA", "cuenta": "0001", "fecha_final": "2026-06-30",
     "numero_depositos": 4, "numero_depositos_operativo": 0,
     "numero_retiros": 8, "numero_retiros_operativo": 5,
     "monto_depositos": 90000.0, "monto_depositos_operativo": 0.0,
     "monto_retiros": 69334.68, "monto_retiros_operativo": 61842.75,
     "saldo_inicial": 11200.93, "saldo_final": 31866.25,
     "saldo_promedio": 13387.11, "saldo_minimo": 3709.0, "saldo_maximo": 46201.76},
    {"folio": "T-01", "banco": "Santander", "cuenta": "0002", "fecha_final": "2026-06-30",
     "numero_depositos": 11, "numero_retiros": 9,
     "numero_depositos_operativo": None, "numero_retiros_operativo": None,
     "monto_depositos_operativo": None, "monto_retiros_operativo": None,
     "monto_depositos": 44000.0, "monto_retiros": 40000.0,
     "saldo_inicial": 5000.0, "saldo_final": 9000.0,
     "saldo_promedio": 7000.0, "saldo_minimo": 1000.0, "saldo_maximo": 20000.0},
]

FISCAL = [
    {"folio": "T-01", "ejercicio": 2023, "ingresos_totales": 4000000.0,
     "utilidad_operacion": 300000.0, "activo_corto_plazo": 900000.0,
     "pasivo_corto_plazo": 400000.0, "capital_contable": 500000.0},
    {"folio": "T-01", "ejercicio": 2024, "ingresos_totales": None,
     "utilidad_operacion": 0.0, "activo_corto_plazo": None,
     "pasivo_corto_plazo": None, "capital_contable": None},
    {"folio": "T-01", "ejercicio": 2025, "ingresos_totales": None,
     "utilidad_operacion": 0.0, "activo_corto_plazo": None,
     "pasivo_corto_plazo": None, "capital_contable": None},
]

sb = FakeSB({"buro": BURO, "estados_cuenta": EDOS, "info_fiscal": FISCAL})


# ── el buró que entra al modelo es el del acreditado ─────────────────────────
print("Buró")
b = insumos_riesgo.buro("T-01", sb=sb)
check(b["folio_consulta"] == "111",
      "toma el buró del acreditado aunque el del garante sea más reciente")
check(b["score_pyme"] is None,
      "y no hereda el score del garante")
check(b["resultado"] == "sin_historial",
      "conserva el resultado de la consulta, que no es lo mismo que no consultar")


# ── las cuentas ──────────────────────────────────────────────────────────────
print("Estados de cuenta")
cs = insumos_riesgo.cuentas("T-01", sb=sb)
check(len(cs) == 2, "agrupa por banco y número de cuenta")

bbva = [c for c in cs if len(c) == 2][0]
check(bbva[0]["_corte"] > bbva[1]["_corte"],
      "ordena los periodos del más reciente al más antiguo, como los lee el modelo")
check(bbva[0]["saldo_final"] == 31866.25 and bbva[1]["saldo_inicial"] == 9062.38,
      "el saldo final sale del periodo reciente y el inicial del más antiguo")

# LO IMPORTANTE: los conteos son de movimientos totales, no de operativos.
check([p["num_depositos"] for p in bbva] == [4, 2],
      "los conteos de movimientos NO usan la columna operativa")
check(bbva[0]["monto_depositos"] == 0.0,
      "pero los montos sí prefieren la cifra reconciliada")

santander = [c for c in cs if len(c) == 1][0]
check(santander[0]["monto_depositos"] == 44000.0,
      "y cuando no hay reconciliación caen a la cifra declarada")
check(santander[0]["saldo_min"] == 1000.0 and santander[0]["saldo_max"] == 20000.0,
      "saldo_minimo y saldo_maximo se renombran a lo que el modelo pide")


# ── la declaración ───────────────────────────────────────────────────────────
print("Declaración anual")
d, ejercicio = insumos_riesgo.declaracion("T-01", sb=sb)
check(ejercicio == 2023,
      "toma el ejercicio más reciente CON datos, no el más reciente a secas")
check(d["ingresos_totales"] == 4000000.0, "y trae sus cifras")

# Una empresa que se constituyó y nunca operó: las tres declaraciones existen,
# se extrajeron bien de Syntage, y no dicen nada.
vacios = FakeSB({"info_fiscal": [
    dict({c: None for c in insumos_riesgo.CAMPOS_FISCAL},
         folio="T-01", ejercicio=a, utilidad_operacion=0.0)
    for a in (2023, 2024, 2025)]})
d, ejercicio = insumos_riesgo.declaracion("T-01", sb=vacios)
check(d == {} and ejercicio is None,
      "tres declaraciones vacías se reportan como módulo ausente, no como ceros")

# LO IMPORTANTE: declarado en ceros SÍ es el ejercicio a usar. Es el caso de la
# empresa que se constituyó, presentó sus tres declaraciones y no facturó.
en_ceros = FakeSB({"info_fiscal": [
    dict({c: 0.0 for c in insumos_riesgo.CAMPOS_FISCAL},
         folio="T-01", ejercicio=a, declarado=True, capital_contable=100000.0,
         activo_corto_plazo=100000.0, dictaminados=None)
    for a in (2023, 2024, 2025)]})
d, ejercicio = insumos_riesgo.declaracion("T-01", sb=en_ceros)
check(ejercicio == 2025 and d["ingresos_totales"] == 0.0,
      "un ejercicio declarado en ceros sí se usa: no facturar es información")

# Y uno declarado gana sobre uno más reciente sin declarar.
mixto = FakeSB({"info_fiscal": [
    dict({c: None for c in insumos_riesgo.CAMPOS_FISCAL},
         folio="T-01", ejercicio=2026, declarado=None),
    dict({c: 0.0 for c in insumos_riesgo.CAMPOS_FISCAL},
         folio="T-01", ejercicio=2025, declarado=True, ingresos_totales=800000.0),
]})
d, ejercicio = insumos_riesgo.declaracion("T-01", sb=mixto)
check(ejercicio == 2025,
      "y un ejercicio sin declarar no le gana al último declarado por ser más reciente")


# ── el perfil ────────────────────────────────────────────────────────────────
print("Perfil")
exp = {"credito": {"solicitada": {"linea": 50000.0}},
       "cliente": {"validado": {"fecha_constitucion": "2023-09-06"}},
       "perfil_empresa": {"giro": "Codigo 2"}}
p = insumos_riesgo.perfil(exp)
check(p["monto_solicitado"] == 50000.0,
      "el monto sale del expediente, no del perfil capturado")
check(p["fecha_constitucion"] == date(2023, 9, 6),
      "y la fecha de constitución se cae al dato de la CSF si el perfil no la trae")
check(p["giro"] == "Codigo 2", "lo capturado en el perfil se respeta")

p = insumos_riesgo.perfil({"credito": {"solicitada": {}}, "cliente": {"validado": {}}})
check(p["monto_solicitado"] is None and p["fecha_constitucion"] is None,
      "un perfil vacío no inventa datos")


# ── el efecto en el modelo ───────────────────────────────────────────────────
print("Efecto en el score")
import modelo_riesgo

r = modelo_riesgo.evaluar(insumos_riesgo.perfil(exp), b,
                          insumos_riesgo.declaracion("T-01", sb=sb)[0], cs)
check("buro" in r["modulos_sin_datos"],
      "un buró sin historial deja el módulo ausente en vez de calificarlo con ceros")
check(r["score"] is not None,
      "y el score se calcula renormalizando los módulos que sí tienen datos")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")


# ── presencia digital: buscar y no encontrar no es lo mismo que no tener ──────
print("Presencia digital")
import perfil_empresa

nota, _ = perfil_empresa.nota_presencia_digital({"sin_presencia": True, "redes": []})
check(nota == 0.0,
      "verificar que no tiene sitio ni redes es un dato y califica cero")

# El dominio del correo con el que firma el representante legal: el dato mas
# duro de este bloque, porque no depende de una busqueda ni de un juicio.
check(perfil_empresa.es_dominio_propio("diego.ramirez@la-llosa.com") is True,
      "un correo con dominio de la empresa cuenta como dominio propio")
check(perfil_empresa.es_dominio_propio("diego.ramirez@gmail.com") is False,
      "y uno de proveedor gratuito no")
check(perfil_empresa.es_dominio_propio("") is None,
      "sin correo no se afirma ni se niega")

sin_dominio, des = perfil_empresa.nota_presencia_digital(
    {"correo_dominio": "alguien@hotmail.com", "redes": []})
check(sin_dominio == 0.0 and des["tiene_dominio_propio"] is False,
      "firmar desde un correo gratuito califica cero, no ausente")

con_dominio, des = perfil_empresa.nota_presencia_digital(
    {"correo_dominio": "alguien@empresa.mx", "sitio_web": "https://empresa.mx",
     "redes": []})
check(con_dominio > sin_dominio,
      "dominio propio mas sitio activo pesa mas que un correo gratuito: %.2f vs %.2f"
      % (con_dominio, sin_dominio))

nota, des = perfil_empresa.nota_presencia_digital({"no_encontrado": True, "redes": []})
check(nota is None and des.get("no_encontrado"),
      "pero una busqueda sin resultados deja la variable ausente, no en cero")

nota, des = perfil_empresa.nota_presencia_digital({
    "sitio_web": "https://ejemplo.mx",
    "redes": [{"red": "Instagram", "seguidores": 3200,
               "ultima_publicacion": "2026-08-01"},
              {"red": "Facebook", "seguidores": 800,
               "ultima_publicacion": "2024-01-01"}]})
check(des["num_redes_activas"] == 1,
      "una red sin publicar en tres meses no cuenta como activa")
check(des["seguidores_totales"] == 4000,
      "pero sus seguidores si suman: el publico sigue ahi")
check(0.6 < nota <= 1.0, "sitio mas una red activa mas 4,000 seguidores: %.2f" % nota)

check(perfil_empresa.nota_presencia_digital(None)[0] is None,
      "y sin capturar nada la variable no existe")

# LO IMPORTANTE: no saber el dominio no puede valer lo mismo que saber que es
# gratuito. Este es el defecto que el proyecto lleva corrigiendo en todos lados
# y que se colo aqui: se atrapo con esta prueba.
sin_correo, d1 = perfil_empresa.nota_presencia_digital(
    {"sitio_web": "https://empresa.mx", "redes": []})
con_gratuito, d2 = perfil_empresa.nota_presencia_digital(
    {"sitio_web": "https://empresa.mx", "correo_dominio": "x@gmail.com", "redes": []})
check(sin_correo > con_gratuito,
      "no saber el dominio puntua mejor que saber que es gratuito: %.2f vs %.2f"
      % (sin_correo, con_gratuito))
check(d1["peso_evaluado"] < d2["peso_evaluado"],
      "y se ve en el peso evaluado: sin correo se promedia sobre menos")

# Un mayorista B2B con dominio y sitio vivo, sin redes verificadas, no se
# castiga por unas redes que nadie reviso.
nota, des = perfil_empresa.nota_presencia_digital(
    {"correo_dominio": "d@la-empresa.com", "sitio_web": "https://la-empresa.com",
     "redes": [], "redes_no_encontradas": True})
check(des["redes_sin_verificar"] and nota == 1.0,
      "redes no verificadas salen del promedio en vez de contar como cero")
