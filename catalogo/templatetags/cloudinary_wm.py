from django import template

register = template.Library()

# Marca de agua aplicada vía transformación de URL de Cloudinary.
# Ajusta el texto, opacidad (o_), posición (g_) y márgenes (x_,y_) a tu gusto.
# Para usar un LOGO en vez de texto: sube tu logo a Cloudinary y reemplaza WM por,
# por ejemplo: "l_dl_logo,o_45,g_center,w_0.5,fl_relative"
WM = "l_text:Arial_45_bold:Instinto%20Olfativo,co_white,o_35,g_south_east,x_20,y_20"


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
    t = f"f_auto,q_auto,c_limit,w_{int(ancho)}"
    if con_marca:
        t += f"/{WM}"
    return url.replace("/upload/", f"/upload/{t}/", 1)


@register.filter
def cl(url, ancho=800):
    """Imagen de producto optimizada (AVIF/WebP automático, ancho máximo) + marca de agua.
    Uso: {{ perfume.imagen.url|cl:480 }}"""
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
