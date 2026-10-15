"""{% css_inline 'css/app.css' %} incrusta el CSS compilado dentro de <style>.
Evita una petición que bloquea el primer pintado (PageSpeed: "Solicitudes de bloqueo de renderización").
Si el archivo no se encuentra o es muy grande, vuelve a un <link> normal.
El <style> lleva el nonce de la request: sin él, la CSP estricta lo bloquea."""
from functools import lru_cache

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import escape
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


@register.simple_tag(takes_context=True)
def css_inline(context, ruta):
    request = context.get("request")
    nonce = escape(getattr(request, "csp_nonce", ""))
    attr = f' nonce="{nonce}"' if nonce else ""
    css = _leer(ruta) if settings.DEBUG else _leer_cache(ruta)
    if not css or len(css) > LIMITE:
        return mark_safe(f'<link rel="stylesheet" href="{static(ruta)}">')
    return mark_safe(f"<style{attr}>{css}</style>")
