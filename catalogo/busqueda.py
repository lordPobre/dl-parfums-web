"""Búsqueda de perfumes.

En PostgreSQL (producción):
  - ignora tildes y mayúsculas ("citrica" encuentra "Cítrica"),
  - tolera errores de escritura con similitud de trigramas ("sauvaje" encuentra "Sauvage"),
  - busca en nombre, perfume original, casa, familia y notas,
  - ordena por relevancia.
En SQLite (desarrollo local) cae a una búsqueda simple por coincidencia de texto.
"""
from django.db import connection
from django.db.models import CharField, FloatField, Func, Q, Value
from django.db.models.functions import Coalesce, Greatest, Lower

UMBRAL = 0.35        # similitud mínima para contar como resultado
UMBRAL_SUGERIR = 0.15

CAMPOS_TEXTO = ("nombre", "inspirado_en", "marca__nombre", "familia__nombre")
CAMPOS_NOTAS = ("notas_salida", "notas_corazon", "notas_fondo")


class Unaccent(Func):
    function = "UNACCENT"
    output_field = CharField()


def es_postgres():
    return connection.vendor == "postgresql"


def _relevancia(texto):
    from django.contrib.postgres.search import TrigramWordSimilarity

    buscado = Unaccent(Lower(Value(texto)))
    return Greatest(*[
        TrigramWordSimilarity(buscado, Unaccent(Lower(Coalesce(campo, Value("")))))
        for campo in CAMPOS_TEXTO
    ])


def buscar_perfumes(qs, texto):
    """Filtra el queryset por 'texto' y anota 'relevancia' (0 a 1)."""
    texto = (texto or "").strip()
    if not texto:
        return qs
    if not es_postgres():
        cond = Q()
        for campo in CAMPOS_TEXTO + CAMPOS_NOTAS:
            cond |= Q(**{f"{campo}__icontains": texto})
        return qs.filter(cond).annotate(relevancia=Value(1.0, output_field=FloatField()))

    cond = Q(relevancia__gte=UMBRAL)
    for campo in CAMPOS_TEXTO + CAMPOS_NOTAS:
        cond |= Q(**{f"{campo}__unaccent__icontains": texto})
    return qs.annotate(relevancia=_relevancia(texto)).filter(cond)


def sugerir(qs, texto, limite=4):
    """Cuando no hay resultados: los perfumes más parecidos aunque no pasen el umbral."""
    if not es_postgres() or not (texto or "").strip():
        return []
    return list(
        qs.annotate(relevancia=_relevancia(texto))
        .filter(relevancia__gte=UMBRAL_SUGERIR)
        .order_by("-relevancia")[:limite]
    )
