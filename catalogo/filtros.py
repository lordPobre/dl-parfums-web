"""Construcción de URLs del catálogo a partir del estado de los filtros.

Una sola regla para todos los enlaces de filtros:
  - parte del estado actual (incluido el filtro que viene de una landing),
  - aplica los cambios (un valor igual al actual lo quita: los chips se encienden y apagan),
  - si queda UN solo filtro de género, familia o casa, devuelve la URL limpia de su landing
    (/perfumes/mujer/, /familia/<slug>/, /casa/<slug>/), que es la que conviene para Google.
"""
from urllib.parse import urlencode

from django.urls import reverse

GENERO_A_SLUG = {"F": "mujer", "M": "hombre", "U": "unisex"}
ORDEN_PARAMS = ("q", "genero", "marca", "familia", "tamano", "precio", "stock", "orden")


def url_filtros(estado, slugs, alternar=True, **cambios):
    datos = {k: str(v) for k, v in (estado or {}).items() if v not in (None, "", False)}
    for clave, valor in cambios.items():
        valor = "" if valor is None else str(valor)
        if not valor or (alternar and datos.get(clave) == valor):
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    datos.pop("page", None)

    claves = set(datos)
    if claves == {"genero"} and datos["genero"] in GENERO_A_SLUG:
        return reverse("catalogo_genero", args=[GENERO_A_SLUG[datos["genero"]]])
    if claves == {"familia"} and datos["familia"] in slugs.get("familia", {}):
        return reverse("catalogo_familia", args=[slugs["familia"][datos["familia"]]])
    if claves == {"marca"} and datos["marca"] in slugs.get("marca", {}):
        return reverse("catalogo_casa", args=[slugs["marca"][datos["marca"]]])

    pares = [(k, datos[k]) for k in ORDEN_PARAMS if k in datos]
    return reverse("catalogo") + ("?" + urlencode(pares) if pares else "")
