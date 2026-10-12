from django import template

from catalogo.filtros import url_filtros

register = template.Library()


@register.simple_tag(takes_context=True)
def filtro_url(context, alternar=True, **cambios):
    """{% filtro_url genero='F' %} -> URL del catálogo con ese filtro activado (o desactivado
    si ya estaba). {% filtro_url orden='precio-asc' alternar=False %} para valores fijos."""
    return url_filtros(
        context.get("estado_filtros", {}),
        context.get("slugs_filtros", {}),
        alternar=alternar,
        **cambios,
    )
