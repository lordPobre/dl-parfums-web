"""Aviso por correo a la tienda cuando entra un pedido con los datos del cliente.

Se envía en un hilo aparte para que el cliente no espere a Resend antes de abrir WhatsApp.
Si el envío falla, el pedido queda igual en el admin y el error va a los logs de Railway.
"""
import logging
import os
import threading

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from .templatetags.cloudinary_wm import clp

log = logging.getLogger(__name__)


def buzon_pedidos():
    return os.environ.get("PEDIDOS_EMAIL") or os.environ.get("EMAIL_HOST_USER") or settings.DEFAULT_FROM_EMAIL


def texto_pedido(p):
    lineas = [
        f"Pedido {p.codigo} · {timezone.localtime(p.creado):%d/%m/%Y %H:%M}",
        "",
        "CLIENTE",
        f"Nombre: {p.nombre_completo}",
        f"RUT: {p.rut}",
        f"Teléfono: {p.telefono}",
        f"Email: {p.email}",
        "",
        "ENVÍO",
        f"Dirección: {p.direccion}",
        f"Comuna: {p.comuna}",
        f"Región: {p.region}",
    ]
    if p.notas:
        lineas.append(f"Notas: {p.notas}")
    lineas += ["", "PRODUCTOS"]
    for item in p.items.all():
        lineas.append(f"• {item.cantidad} × {item.nombre} — {clp(item.subtotal)}")
    if p.descuento:
        lineas.append(f"Descuento ({p.detalle_descuento or 'promoción'}): −{clp(p.descuento)}")
    lineas += [
        f"TOTAL: {clp(p.total)}",
        "",
        f"Ver en el admin: {settings.SITE_URL}{reverse('admin:catalogo_pedido_change', args=[p.pk])}",
    ]
    return "\n".join(lineas)


def _enviar(pedido_id):
    from .models import Pedido
    try:
        p = Pedido.objects.prefetch_related("items").get(pk=pedido_id)
        EmailMessage(
            subject=f"Nuevo pedido {p.codigo} · {p.nombre_completo} · {clp(p.total)}",
            body=texto_pedido(p),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[buzon_pedidos()],
            reply_to=[p.email] if p.email else None,  # «Responder» le escribe al cliente
        ).send(fail_silently=False)
    except Exception:
        log.exception("No se pudo enviar el aviso del pedido %s", pedido_id)


def _hilo(pedido_id):
    try:
        _enviar(pedido_id)
    finally:
        connection.close()  # la conexión a la base de este hilo


def enviar_aviso_pedido(pedido_id):
    if getattr(settings, "PEDIDO_CORREO_SINCRONO", False):  # pruebas
        _enviar(pedido_id)
    else:
        threading.Thread(target=_hilo, args=(pedido_id,), daemon=True).start()
