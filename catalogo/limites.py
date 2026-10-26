"""Límite de envíos por IP (pedidos, reseñas, contacto), guardado en la base.

Antes se contaba en la caché en memoria, que en Vercel es distinta en cada instancia y se
reinicia seguido, así que el límite casi nunca se cumplía. Ahora el conteo es compartido.
La IP no se guarda: solo un hash con SECRET_KEY, y cada registro se borra a las 24 h.
"""
import hashlib
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def ip_cliente(request):
    # En Vercel, x-real-ip y el primer valor de x-forwarded-for los fija la plataforma.
    ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return ip or request.META.get("REMOTE_ADDR") or "anon"


def _clave(accion, ip):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{accion}:{ip}".encode()).hexdigest()[:40]


def excede_limite(request, accion, maximo, segundos):
    """True si esta IP ya hizo `maximo` envíos de `accion` en los últimos `segundos`."""
    from .models import LimiteSolicitud

    ahora = timezone.now()
    clave = _clave(accion, ip_cliente(request))
    LimiteSolicitud.objects.filter(creado__lt=ahora - timedelta(days=1)).delete()
    recientes = LimiteSolicitud.objects.filter(clave=clave, creado__gte=ahora - timedelta(seconds=segundos))
    # Primero se registra y después se cuenta: así varios envíos simultáneos no pasan todos.
    # Los intentos rechazados también cuentan, de modo que insistir no acorta la espera.
    LimiteSolicitud.objects.create(clave=clave)
    return recientes.count() > maximo
