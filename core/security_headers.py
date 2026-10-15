# 'unsafe-eval' y cdn.tailwindcss.com ya no son necesarios en el sitio: Tailwind se compila a static/css/app.css.
# 'unsafe-inline' se mantiene por los scripts inline del sitio y de los píxeles de Facebook/TikTok.
from django.urls import reverse

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://connect.facebook.net https://analytics.tiktok.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://res.cloudinary.com https://www.facebook.com https://analytics.tiktok.com; "
    "connect-src 'self' https://connect.facebook.net https://www.facebook.com https://analytics.tiktok.com https://analytics-ipv6.tiktokw.us https://*.tiktokw.us https://*.tiktok.com; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-src https://www.google.com https://maps.google.com; "
    "object-src 'none'; "
    "upgrade-insecure-requests"
)

# El admin (Unfold) usa Alpine.js, que necesita 'unsafe-eval'. Sin él, el buscador,
# los filtros y los menús quedan abiertos encima de la página y no se pueden cerrar.
# Solo se permite dentro del admin; el sitio público sigue sin 'unsafe-eval'.
CSP_ADMIN = CSP.replace("script-src 'self' 'unsafe-inline'", "script-src 'self' 'unsafe-inline' 'unsafe-eval'", 1)

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
        response = self.get_response(request)
        csp = CSP_ADMIN if request.path.startswith(self.ruta_admin()) else CSP
        response.setdefault("Content-Security-Policy", csp)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response
