"""Segundo factor (TOTP) para el admin. Punto A4 de la auditoría de seguridad.

Después de la contraseña, todo usuario staff debe ingresar un código de su app
autenticadora (Google Authenticator, Microsoft Authenticator, 1Password, etc.).
La primera vez se le pide escanear un QR y recibe 10 códigos de respaldo.
"""
import base64
import io
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login
from django_otp import match_token, user_has_device
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

CODIGOS_RESPALDO = 10


class Admin2FAMiddleware:
    """Va después de OTPMiddleware. Solo actúa dentro del admin y con usuarios staff."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._rutas = None

    def rutas(self):
        if self._rutas is None:
            libres = {reverse(n) for n in ("admin:login", "admin:logout", "admin:jsi18n",
                                           "admin2fa_verificar", "admin2fa_configurar")}
            self._rutas = (reverse("admin:index"), libres)
        return self._rutas

    def __call__(self, request):
        if getattr(settings, "ADMIN_2FA_OBLIGATORIO", True):
            prefijo, libres = self.rutas()
            usuario = request.user
            if (request.path.startswith(prefijo) and request.path not in libres
                    and usuario.is_authenticated and usuario.is_staff and not usuario.is_verified()):
                destino = "admin2fa_verificar" if user_has_device(usuario) else "admin2fa_configurar"
                return redirect(f"{reverse(destino)}?next={quote(request.get_full_path())}")
        return self.get_response(request)


def _siguiente(request):
    url = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return reverse("admin:index")


def _contexto(request, **extra):
    return {**admin.site.each_context(request), "next": _siguiente(request), **extra}


def _codigo(request):
    return "".join(request.POST.get("codigo", "").split()).lower()


@never_cache
@staff_member_required
def verificar(request):
    if not user_has_device(request.user):
        return redirect("admin2fa_configurar")
    if request.user.is_verified():
        return redirect(_siguiente(request))
    error = ""
    if request.method == "POST":
        dispositivo = match_token(request.user, _codigo(request)) if _codigo(request) else None
        if dispositivo:
            otp_login(request, dispositivo)
            return redirect(_siguiente(request))
        error = "Código incorrecto o vencido. Si fallas varias veces, espera unos segundos antes de reintentar."
    return render(request, "admin/2fa_verificar.html", _contexto(request, title="Verificación en dos pasos", error=error))


@never_cache
@staff_member_required
def configurar(request):
    # Quien ya tiene un dispositivo debe verificarse antes; para cambiar de teléfono,
    # un superusuario borra su dispositivo en el admin (OTP_TOTP › TOTP devices).
    if user_has_device(request.user):
        return redirect("admin2fa_verificar" if not request.user.is_verified() else _siguiente(request))

    dispositivo = (TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
                   or TOTPDevice.objects.create(user=request.user, name="App autenticadora", confirmed=False))
    error = ""
    if request.method == "POST":
        if dispositivo.verify_token(_codigo(request)):
            dispositivo.confirmed = True
            dispositivo.save(update_fields=["confirmed"])
            otp_login(request, dispositivo)
            return render(request, "admin/2fa_respaldo.html",
                          _contexto(request, title="Códigos de respaldo", codigos=_crear_codigos_respaldo(request.user)))
        error = "El código no coincide. Revisa que la hora del teléfono sea automática y prueba con el código siguiente."

    svg = io.BytesIO()
    qrcode.make(dispositivo.config_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2).save(svg)
    secreto = base64.b32encode(dispositivo.bin_key).decode()
    return render(request, "admin/2fa_configurar.html", _contexto(
        request, title="Activa la verificación en dos pasos", error=error,
        qr="data:image/svg+xml;base64," + base64.b64encode(svg.getvalue()).decode(),
        secreto=" ".join(secreto[i:i + 4] for i in range(0, len(secreto), 4)),
    ))


def _crear_codigos_respaldo(usuario):
    dispositivo, _ = StaticDevice.objects.get_or_create(user=usuario, name="Códigos de respaldo", defaults={"confirmed": True})
    dispositivo.token_set.all().delete()
    codigos = [StaticToken.random_token() for _ in range(CODIGOS_RESPALDO)]
    StaticToken.objects.bulk_create(StaticToken(device=dispositivo, token=c) for c in codigos)
    return codigos


urlpatterns = [
    path("", verificar, name="admin2fa_verificar"),
    path("configurar/", configurar, name="admin2fa_configurar"),
]
