import os

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class DominioCanonicoMiddleware:
    """Evita que *.vercel.app compita con www.instintoolfativo.cl en Google.

    - Producción servida en *.vercel.app  -> 301 al dominio canónico.
    - Deploys de preview en *.vercel.app  -> se sirven, pero con X-Robots-Tag: noindex
      (así puedes seguir probando previews sin que se indexen).
    - Dominio sin www                     -> 301 a www (un solo salto).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonico = settings.SITE_URL.split("://", 1)[-1].rstrip("/")

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        es_vercel = host.endswith(".vercel.app")
        es_produccion = os.environ.get("VERCEL_ENV") == "production"

        if (es_vercel and es_produccion) or host == "instintoolfativo.cl":
            return HttpResponsePermanentRedirect(settings.SITE_URL + request.get_full_path())

        response = self.get_response(request)
        if es_vercel:
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
