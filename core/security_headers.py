# CSP estricta para el sitio público:
# - default-src 'none': todo lo que no se declara queda bloqueado.
# - script-src con nonce por request + 'strict-dynamic': sin 'unsafe-inline'.
#   Los píxeles de Meta/TikTok cargan porque su snippet lleva el nonce y crea sus scripts dinámicamente.
# - style-src con nonce para <style>; los atributos style="" quedan en style-src-attr (ver README).
# El admin (Unfold/Alpine) mantiene su política propia: no lo escanea Observatory y necesita 'unsafe-eval'.
import secrets

from django.urls import reverse

TERCEROS_SCRIPT = "https://connect.facebook.net https://analytics.tiktok.com"

CSP_SITIO = (
    "default-src 'none'; "
    "script-src 'self' 'nonce-{n}' 'strict-dynamic' " + TERCEROS_SCRIPT + "; "
    "style-src 'self' 'nonce-{n}' https://fonts.googleapis.com; "
    "style-src-attr 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://res.cloudinary.com https://www.facebook.com https://analytics.tiktok.com; "
    "connect-src 'self' https://connect.facebook.net https://www.facebook.com https://analytics.tiktok.com https://*.tiktokw.us https://*.tiktok.com; "
    "frame-src https://www.google.com https://maps.google.com; "
    "manifest-src 'self'; "
    "form-action 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "upgrade-insecure-requests"
)

CSP_ADMIN = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://res.cloudinary.com; "
    "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"
)

PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=(), autoplay=(self), "
    "fullscreen=(self), interest-cohort=()"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._admin = None

    def ruta_admin(self):
        if self._admin is None:
            self._admin = reverse("admin:index")
        return self._admin

    def __call__(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        response = self.get_response(request)
        if request.path.startswith(self.ruta_admin()):
            csp = CSP_ADMIN
        else:
            csp = CSP_SITIO.replace("{n}", nonce)
        response.setdefault("Content-Security-Policy", csp)
        response.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response
