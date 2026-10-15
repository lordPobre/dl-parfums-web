from django.conf import settings


def sitio(request):
    """Expone SITE_URL a todas las plantillas (canónicas, og:url, JSON-LD)."""
    return {
        "SITE_URL": settings.SITE_URL,
        "META_PIXEL_ID": getattr(settings, "META_PIXEL_ID", ""),
        "TIKTOK_PIXEL_ID": getattr(settings, "TIKTOK_PIXEL_ID", ""),
    }
