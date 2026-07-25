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
