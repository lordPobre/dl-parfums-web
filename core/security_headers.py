# Cabeceras de seguridad para DL Parfums
# ---------------------------------------
# 1) Guarda este archivo como  core/security_headers.py  (junto a settings.py).
# 2) En settings.py, agrega la ruta al MIDDLEWARE (al final de la lista):
#
#       MIDDLEWARE = [
#           ...
#           "core.security_headers.SecurityHeadersMiddleware",
#       ]
#
# Ajustado a las fuentes que usa el sitio:
#   - Tailwind CDN (cdn.tailwindcss.com)
#   - Google Fonts (fonts.googleapis.com / fonts.gstatic.com)
#   - Cloudinary (res.cloudinary.com)
#   - WhatsApp (wa.me) en enlaces
#
# NOTA: Tailwind CDN y los estilos inline requieren 'unsafe-inline' / 'unsafe-eval'
# en style/script. Es lo normal usando el CDN. Si algún día compilas Tailwind a un
# .css estático, puedes endurecer la política quitando esos 'unsafe-*'.

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://res.cloudinary.com; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "upgrade-insecure-requests"
)

PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=(), autoplay=(self), "
    "fullscreen=(self), interest-cohort=()"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        # Cabeceras extra recomendadas
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response
