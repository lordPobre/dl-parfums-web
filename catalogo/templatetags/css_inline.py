"""{% css_inline 'css/app.css' %} incrusta el CSS compilado dentro de <style>.
Evita una petición que bloquea el primer pintado (PageSpeed: "Solicitudes de bloqueo de renderización").
Si el archivo no se encuentra o es muy grande, vuelve a un <link> normal."""
from functools import lru_cache

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()

LIMITE = 60_000  # bytes sin comprimir


def _leer(ruta):
    archivo = finders.find(ruta)
    if not archivo:
        return None
    with open(archivo, encoding="utf-8") as f:
        return f.read()


_leer_cache = lru_cache(maxsize=8)(_leer)


@register.simple_tag
def css_inline(ruta):
    css = _leer(ruta) if settings.DEBUG else _leer_cache(ruta)
    if not css or len(css) > LIMITE:
        return mark_safe(f'<link rel="stylesheet" href="{static(ruta)}">')
    return mark_safe(f"<style>{css}</style>")
