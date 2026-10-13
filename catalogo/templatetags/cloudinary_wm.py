import os

from django import template

register = template.Library()

# Marca de agua aplicada vía transformación de URL de Cloudinary.
# Por defecto es texto. Para usar tu LOGO (se genera mucho más rápido que el texto):
#   1. Sube el logo en PNG blanco con fondo transparente a Cloudinary.
#   2. En Vercel crea la variable CLOUDINARY_WM_LOGO con su public_id
#      (si está en una carpeta, cambia "/" por ":", ej. "marca:logo-blanco").
WM_LOGO = os.environ.get("CLOUDINARY_WM_LOGO", "").strip()
if WM_LOGO:
    WM = f"l_{WM_LOGO},o_35,g_south_east,x_20,y_20,w_0.25,fl_relative"
else:
    WM = "l_text:Arial_45_bold:Instinto%20Olfativo,co_white,o_35,g_south_east,x_20,y_20"

# Bajo este ancho no se pone marca de agua (miniaturas del carrito, buscador y galería):
# ahí no se lee y es la parte más lenta de generar.
ANCHO_MIN_MARCA = 300


@register.filter
def watermark(url):
    """Inserta la marca de agua en una URL de Cloudinary.
    Si la URL no es de Cloudinary (no tiene /upload/), la devuelve intacta."""
    if url and "/upload/" in url:
        return url.replace("/upload/", f"/upload/{WM}/", 1)
    return url


def _transformar(url, ancho, con_marca):
    if not url or "/upload/" not in url:
        return url
    ancho = int(ancho)
    t = f"f_auto,q_auto,c_limit,w_{ancho}"
    if con_marca and ancho >= ANCHO_MIN_MARCA:
        t += f"/{WM}"
    return url.replace("/upload/", f"/upload/{t}/", 1)


@register.filter
def cl(url, ancho=800):
    """Imagen de producto optimizada (AVIF/WebP automático, ancho máximo) + marca de agua
    desde 300 px. Uso: {{ perfume.imagen.url|cl:480 }}"""
    return _transformar(url, ancho, True)


@register.filter
def clsin(url, ancho=1600):
    """Igual que |cl pero SIN marca de agua (portadas del hero, logos de casas)."""
    return _transformar(url, ancho, False)


@register.filter
def clp(valor):
    """Formato de precio chileno: 15000 -> $15.000"""
    try:
        return "$" + f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor
