# -*- coding: utf-8 -*-
"""
Pruebas del cruce de proveedores contra el padrón de monederos de gasolina.

`monederos.py` no llama a Syntage ni a Supabase en estas pruebas: lo único que
se prueba aquí es la lógica de cruce, con datos inventados con la misma forma
que devuelve `supplier-concentration`. La llamada real ya se probó a mano
contra Syntage (LA FICTICIA SUPPLIER) para confirmar el formato del insight;
aquí se fija ese contrato para que no se rompa en silencio.

Se corre con:
    python tests/test_monederos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monederos

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── el padrón en sí ──────────────────────────────────────────────────────────
rfcs = [m["rfc"] for m in monederos.PADRON]
check(len(rfcs) == len(set(rfcs)), "el padrón no tiene RFC repetido")
check(all(m.get("nombre_comercial") for m in monederos.PADRON),
      "todo monedero del padrón trae nombre comercial")
check(("TFM191231NA7", "NEA CONTROL") in
      [(m["rfc"], m["nombre_comercial"]) for m in monederos.PADRON],
      "NEA CONTROL (Grit Mobility) está en el padrón: el cruce también detecta clientes propios")


# ── detectar_monederos(): forma de supplier-concentration ───────────────────
PROVEEDORES_LA_FICTICIA = [
    {"rfc": "BBB180313XX2", "name": "COMERCIALIZADORA FICTICIA", "total": 1000000.00, "share": 60.0},
    {"rfc": "AAA980429XX1", "name": "INSUMOS AGROPECUARIOS DEL BAJIO", "total": 500000.00, "share": 30.0},
]
hallazgos = monederos.detectar_monederos(PROVEEDORES_LA_FICTICIA)
check(hallazgos == [], "un cliente sin proveedores del padrón no produce hallazgos")

PROVEEDORES_CON_MONEDERO = PROVEEDORES_LA_FICTICIA + [
    {"rfc": "cco230329kc2".upper(), "name": "CLIC CONNECT", "total": 500000.0, "share": 4.2},
]
hallazgos = monederos.detectar_monederos(PROVEEDORES_CON_MONEDERO)
check(len(hallazgos) == 1, "un proveedor del padrón sí produce un hallazgo")
h = hallazgos[0] if hallazgos else {}
check(h.get("rfc_monedero") == "CCO230329KC2", "el RFC coincide sin importar mayúsculas/minúsculas")
check(h.get("nombre_comercial") == "MAS BENEFITS COMBUSTIBLE",
      "el hallazgo trae el nombre comercial del monedero, no la razón social del proveedor")
check(h.get("monto") == 500000.0, "el hallazgo conserva el monto facturado por Syntage")
check(h.get("porcentaje_gasto") == 4.2, "el hallazgo conserva el % de participación de Syntage")

check(monederos.detectar_monederos([]) == [], "una lista de proveedores vacía no truena")
check(monederos.detectar_monederos([{"rfc": None, "name": "X"}]) == [],
      "un proveedor sin RFC no truena")


# ── _rfc_de_expediente(): mismo shape que expedientes/*.json ────────────────
EXPEDIENTE = {"cliente": {"validado": {"rfc": "LSU230906KB9"}}}
check(monederos._rfc_de_expediente(EXPEDIENTE) == "LSU230906KB9",
      "se extrae el RFC validado del expediente")
check(monederos._rfc_de_expediente({"cliente": {}}) is None,
      "un expediente sin cliente validado no truena")
check(monederos._rfc_de_expediente({}) is None,
      "un expediente vacío no truena")


# ── analizar_cliente(): un cliente en Supabase sin entidad en Syntage ───────
# Se descubrió corriendo el barrido real: DEMO-03 está en Supabase pero nunca
# se dio de alta en Syntage, y syntage.id_entidad() truena con LookupError.
# Ese cliente no debe tumbar el barrido de los demás.
class _SyntageSinEntidad(object):
    @staticmethod
    def extraccion_completa(rfc):
        return True, []

    @staticmethod
    def id_entidad(rfc, crear=False):
        raise LookupError("El RFC %s no existe como entidad en Syntage." % rfc)


_original_syntage = monederos.syntage
monederos.syntage = _SyntageSinEntidad
hallazgos, estado = monederos.analizar_cliente("SNA790717GU5")
monederos.syntage = _original_syntage
check(hallazgos == [], "un cliente sin entidad en Syntage no produce hallazgos falsos")
check("Syntage" in estado, "el estado explica que el cliente no está dado de alta en Syntage: %r" % estado)


# ── _rfc_de_entidad_syntage(): forma real de /entities ──────────────────────
ENTIDAD_SYNTAGE = {"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "name": "COMERCIALIZADORA FICTICIA SA DE CV",
                    "taxpayer": {"id": "BBB180313XX2"}}
check(monederos._rfc_de_entidad_syntage(ENTIDAD_SYNTAGE) == "BBB180313XX2",
      "se extrae el RFC de una entidad de Syntage")
check(monederos._rfc_de_entidad_syntage({"taxpayer": {}}) is None,
      "una entidad sin RFC de contribuyente no truena")


# ── _proveedores_completos(): supplier-concentration pagina en 100 ──────────
# Se descubrió corriendo el barrido real: LOGISTICA FICTICIA DE MEXICO tiene 1,381
# proveedores y Efecticard le pesa 0.05% del gasto — aparece hasta la página 2.
# Sin paginar, el default de Syntage (10 filas) lo deja fuera en silencio.
PAGINA_1 = [{"rfc": "AAA%06d" % i, "name": "PROVEEDOR %d" % i, "total": 1000.0, "share": 1.0}
            for i in range(100)]
PAGINA_2 = [{"rfc": "EFE8908015L3", "name": "EFECTIVALE", "total": 500.0, "share": 0.04}]


class _SyntagePaginado(object):
    ErrorSyntage = monederos.syntage.ErrorSyntage
    llamadas = []

    @staticmethod
    def insight(eid, nombre, **params):
        _SyntagePaginado.llamadas.append(params)
        offset = params.get("options[offset]", 0)
        return {"data": PAGINA_1 if offset == 0 else (PAGINA_2 if offset == 100 else [])}


_original_syntage = monederos.syntage
monederos.syntage = _SyntagePaginado
proveedores = monederos._proveedores_completos("cualquier-id")
monederos.syntage = _original_syntage
check(len(proveedores) == 101, "se acumulan las páginas completas: %d proveedores" % len(proveedores))
check(len(_SyntagePaginado.llamadas) == 2,
      "se pide una página más tras una llena, y se para en la que no llega a 100: %d llamada(s)"
      % len(_SyntagePaginado.llamadas))

hallazgos = monederos.detectar_monederos(proveedores)
check(len(hallazgos) == 1 and hallazgos[0]["rfc_monedero"] == "EFE8908015L3",
      "el proveedor de la segunda página sí se detecta")


# ── barrer_entidades_syntage(): una entidad no debe tumbar el barrido ───────
# Se descubrió corriendo el barrido real: un IncompleteRead a media página 40
# tiró TODO el trabajo ya hecho porque nada en el barrido atrapaba la falla.
# Mismo principio que ya usa syntage.extraer_todo(): lo que falle se anota y
# se sigue, nunca tumba el barrido completo.
ENTIDADES_DE_PRUEBA = [
    {"id": "e1", "taxpayer": {"id": "AAA010101AAA", "name": "PRIMERA"}},
    {"id": "e2", "taxpayer": {"id": "BBB020202BBB", "name": "SEGUNDA (truena)"}},
    {"id": "e3", "taxpayer": {"id": "CCC030303CCC", "name": "TERCERA"}},
]


class _SyntageEntidadesConFalla(object):
    ErrorSyntage = monederos.syntage.ErrorSyntage

    @staticmethod
    def entidades():
        return iter(ENTIDADES_DE_PRUEBA)

    @staticmethod
    def extraccion_completa(rfc):
        if rfc == "BBB020202BBB":
            raise monederos.syntage.ErrorSyntage(0, "respuesta incompleta: simulada", "/extractions")
        return True, []

    @staticmethod
    def id_entidad(rfc, crear=False):
        return {"AAA010101AAA": "e1", "CCC030303CCC": "e3"}[rfc]

    @staticmethod
    def insight(eid, nombre, **params):
        return {"data": []}


_original_syntage = monederos.syntage
monederos.syntage = _SyntageEntidadesConFalla
resultados = monederos.barrer_entidades_syntage()
monederos.syntage = _original_syntage

check(len(resultados) == 3,
      "las 3 entidades quedan en el resultado aunque la de en medio truene: %d" % len(resultados))
check(resultados[0]["estado"] == "ok" and resultados[2]["estado"] == "ok",
      "la primera y la tercera sí se cruzan bien")
check(resultados[1]["estado"] != "ok" and "incompleta" in resultados[1]["estado"],
      "la que truena queda marcada con su error, no detiene a las demás: %r" % resultados[1]["estado"])
check(resultados[0]["entidad_id"] == "e1" and resultados[2]["entidad_id"] == "e3",
      "cada resultado trae su entidad_id de Syntage, no solo el RFC")


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
