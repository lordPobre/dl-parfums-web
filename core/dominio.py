import os

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class DominioCanonicoMiddleware:
    """Evita que las URLs de la plataforma compitan con www.instintoolfativo.cl en Google.

    - Producción en *.vercel.app                 -> 301 al dominio canónico.
    - *.up.railway.app con RAILWAY_REDIRIGIR=1   -> 301 al dominio canónico (actívalo cuando
      el dominio ya apunte a Cloudflare; antes sirve para probar Railway).
    - Previews y *.up.railway.app sin redirigir  -> se sirven con X-Robots-Tag: noindex.
    - Dominio sin www                            -> 301 a www (un solo salto).
    - healthcheck.railway.app no se toca: Railway lo usa para saber si el deploy arrancó.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        es_vercel = host.endswith(".vercel.app")
        es_railway = host.endswith(".up.railway.app")
        vercel_produccion = os.environ.get("VERCEL_ENV") == "production"
        railway_redirigir = os.environ.get("RAILWAY_REDIRIGIR") == "1"

        if (
            (es_vercel and vercel_produccion)
            or (es_railway and railway_redirigir)
            or host == "instintoolfativo.cl"
        ):
            return HttpResponsePermanentRedirect(settings.SITE_URL + request.get_full_path())

        response = self.get_response(request)
        if es_vercel or es_railway:
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
