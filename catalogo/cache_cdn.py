from functools import wraps

from django.utils.cache import patch_cache_control

# Parámetros con los que una página sigue siendo pública y cacheable.
# Cualquier otro (?q=, ?resena=, ?familia_txt=...) se sirve siempre fresco desde Django.
PARAMS_CACHEABLES = {"page", "genero", "marca", "familia", "precio", "tamano", "stock", "orden"}


def cache_cdn(segundos=300):
    """Deja que el CDN de Vercel guarde la página `segundos` y la siga sirviendo
    (mientras la renueva en segundo plano) hasta 24 h si Django tarda o falla.

    No se cachea si:
      - no es GET o la respuesta no es 200,
      - la URL trae parámetros fuera de PARAMS_CACHEABLES,
      - el visitante tiene sesión (admin logueado: ve los cambios al instante),
      - la respuesta fija cookies.
    """
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            response = view(request, *args, **kwargs)
            if (
                request.method == "GET"
                and response.status_code == 200
                and set(request.GET.keys()) <= PARAMS_CACHEABLES
                and "sessionid" not in request.COOKIES
                and not response.cookies
            ):
                patch_cache_control(
                    response, public=True, max_age=0,
                    s_maxage=segundos, stale_while_revalidate=86400,
                )
            else:
                patch_cache_control(response, private=True, no_cache=True)
            return response
        return wrapper
    return deco
