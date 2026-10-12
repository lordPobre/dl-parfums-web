from django.conf import settings


def sitio(request):
    """Expone SITE_URL a todas las plantillas (canónicas, og:url, JSON-LD)."""
    return {"SITE_URL": settings.SITE_URL}
