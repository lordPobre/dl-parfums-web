from django import template

from .cloudinary_wm import clp

register = template.Library()

MARCA = "Instinto Olfativo"
MAX_TITULO = 60  # Google corta cerca de 60 caracteres


@register.filter
def titulo_seo(p):
    """<title> de la ficha: usa meta_titulo si existe; si no, quita la marca cuando el título se pasa de 60."""
    if getattr(p, "meta_titulo", ""):
        return p.meta_titulo
    insp = getattr(p, "inspirado_en", "") or ""
    if insp:
        t = f"{p.nombre} – Inspirado en {insp} | {MARCA}"
        return t if len(t) <= MAX_TITULO else f"{p.nombre} – Inspirado en {insp}"
    return f"{p.nombre} | {MARCA}"


@register.filter
def descripcion_seo(p):
    if getattr(p, "meta_descripcion", ""):
        return p.meta_descripcion
    t = p.nombre
    familia = getattr(p, "familia", None)
    if familia:
        t += f", fragancia {familia.nombre.lower()}"
    insp = getattr(p, "inspirado_en", "") or ""
    if insp:
        t += f" inspirada en {insp}"
    t += f". Desde {clp(getattr(p, 'precio_vigente', p.precio))}. Asesoría por WhatsApp y envío a todo Chile."
    return t[:160]
