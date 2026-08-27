# -*- coding: utf-8 -*-
"""
precio_comparado.py — ¿El monedero cobra más caro que la compra directa?
=============================================================================
La comisión que factura un monedero (`comisiones_monedero.py`) es solo una
forma de cobrar; la otra es meter el margen en el precio por litro. Este
módulo compara las dos, en la misma estación y el mismo día exacto, entre un
cliente que carga vía monedero y uno que compra directo.

**El único cruce posible hoy es angosto, y hay que decirlo así.** De todo el
portafolio, un solo RFC de estación (`SFS920210NY3`, Servicio Fácil del
Sureste) tiene carga de ambos lados con fecha en común: MERQ vía monedero
(Pluxee) y JL Machinery comprando directo. Son 8 días. El otro cliente de
compra directa, Grupo Constructor Hyclam, compró en 2023 — dos años antes de
que exista carga de monedero ahí — y no cruza con nada.

**El resultado, con esa muestra chica, invierte la hipótesis.** El precio del
monedero fue MÁS BARATO que el de compra directa los 8 días, entre 4% y 11%.
No se puede generalizar de un solo par y ocho días, pero contradice la idea
de que el margen se esconde en el precio: aquí el cliente de monedero paga
menos por litro, no más.

**Por qué se compara por RFC de estación y no por (RFC, clave) o permiso
CRE.** El complemento de monedero solo trae la clave interna del monedero
("0" en el 73% de los casos); la compra directa solo trae el permiso CRE.
No comparten ningún identificador de sucursal — el único que tienen en común
es el RFC del emisor. Es una comparación más gruesa de lo ideal, pero es la
única que los datos permiten hoy.

Uso: se llama desde `discovery_estaciones.py` con la bandera `--precio`
(requiere `--directo`). No es un script de línea de comandos por sí solo.
"""

from collections import defaultdict


def _promedio_precio(litros, importe):
    return (importe / litros) if litros else None


def comparar(cargos_monedero, cargos_directo):
    """Cruza cargas de monedero y de compra directa por (rfc_estacion, fecha).

    Cada entrada de `cargos_monedero` y `cargos_directo` es un dict con
    rfc_cliente, razon_social, rfc_estacion, fecha (AAAA-MM-DD), litros,
    importe — una carga o concepto individual, sin agregar.

    Devuelve los días donde HUBO carga de ambos lados en la misma estación
    (`dias`), y el agregado por estación sobre esos días (`estaciones`). Un
    día o estación sin la contraparte del otro lado simplemente no aparece:
    no hay nada que comparar todavía."""
    por_dia_mon = defaultdict(list)
    por_dia_dir = defaultdict(list)
    for c in cargos_monedero:
        if c.get("rfc_estacion") and c.get("fecha"):
            por_dia_mon[(c["rfc_estacion"], c["fecha"])].append(c)
    for c in cargos_directo:
        if c.get("rfc_estacion") and c.get("fecha"):
            por_dia_dir[(c["rfc_estacion"], c["fecha"])].append(c)

    claves_comunes = sorted(set(por_dia_mon) & set(por_dia_dir))

    dias = []
    por_estacion = defaultdict(lambda: {
        "litros_monedero": 0.0, "importe_monedero": 0.0,
        "litros_directo": 0.0, "importe_directo": 0.0,
        "dias_set": set(), "clientes_monedero": set(), "clientes_directo": set(),
    })

    for rfc_estacion, fecha in claves_comunes:
        mon = por_dia_mon[(rfc_estacion, fecha)]
        dir_ = por_dia_dir[(rfc_estacion, fecha)]
        litros_mon = sum(c["litros"] or 0 for c in mon)
        importe_mon = sum(c["importe"] or 0 for c in mon)
        litros_dir = sum(c["litros"] or 0 for c in dir_)
        importe_dir = sum(c["importe"] or 0 for c in dir_)
        if not litros_mon or not litros_dir:
            continue

        precio_mon = importe_mon / litros_mon
        precio_dir = importe_dir / litros_dir
        dias.append({
            "rfc_estacion": rfc_estacion,
            "fecha": fecha,
            "precio_monedero": round(precio_mon, 4),
            "precio_directo": round(precio_dir, 4),
            "diferencia_pct": (precio_mon - precio_dir) / precio_dir,
            "clientes_monedero": sorted({c.get("razon_social") or c["rfc_cliente"]
                                         for c in mon}),
            "clientes_directo": sorted({c.get("razon_social") or c["rfc_cliente"]
                                        for c in dir_}),
        })

        e = por_estacion[rfc_estacion]
        e["litros_monedero"] += litros_mon
        e["importe_monedero"] += importe_mon
        e["litros_directo"] += litros_dir
        e["importe_directo"] += importe_dir
        e["dias_set"].add(fecha)
        e["clientes_monedero"].update(c.get("razon_social") or c["rfc_cliente"] for c in mon)
        e["clientes_directo"].update(c.get("razon_social") or c["rfc_cliente"] for c in dir_)

    filas_estaciones = []
    for rfc_estacion, e in por_estacion.items():
        precio_mon = _promedio_precio(e["litros_monedero"], e["importe_monedero"])
        precio_dir = _promedio_precio(e["litros_directo"], e["importe_directo"])
        filas_estaciones.append({
            "rfc_estacion": rfc_estacion,
            "dias_comparados": len(e["dias_set"]),
            "precio_monedero": round(precio_mon, 4) if precio_mon else None,
            "precio_directo": round(precio_dir, 4) if precio_dir else None,
            "diferencia_pct": ((precio_mon - precio_dir) / precio_dir
                               if precio_mon and precio_dir else None),
            "clientes_monedero": sorted(e["clientes_monedero"]),
            "clientes_directo": sorted(e["clientes_directo"]),
        })
    filas_estaciones.sort(key=lambda f: -f["dias_comparados"])

    return {"dias": dias, "estaciones": filas_estaciones}
