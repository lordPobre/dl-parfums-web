"""Purga de Cloudflare al cambiar precio, stock o contenido (E3 de la auditoría).

Sin esto, una ficha podía mostrar «Agregar» o un precio anterior hasta 1 hora (s-maxage) y hasta
24 h si Django fallaba (stale-while-revalidate). Se purgan la ficha, el home y /perfumes/; las
landings y las combinaciones de filtros se renuevan solas al vencer su hora.

Variables en Railway: CF_ZONA_ID y CF_TOKEN_PURGA (token con un solo permiso: Zone → Cache Purge).
Sin ellas solo se borra la caché de los filtros del catálogo (desarrollo, CI).
"""
import logging
import os
import threading

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.urls import reverse

log = logging.getLogger(__name__)

CLAVE_FACETAS = "catalogo:facetas"   # listas de filtros del catálogo (views._facetas)
FIJAS = ("/", "/perfumes/")
MAX_URLS = 30    # máximo de URLs por solicitud en el plan gratis; con más se purga todo
ESPERA = 1.0     # segundos para juntar los cambios de un mismo guardado del admin

_lock = threading.Lock()
_rutas = set()
_timer = None


def configurado():
    return bool(os.environ.get("CF_ZONA_ID") and os.environ.get("CF_TOKEN_PURGA"))


def _enviar(rutas):
    urls = sorted({settings.SITE_URL + r for r in (*rutas, *FIJAS)})
    cuerpo = {"files": urls} if len(urls) <= MAX_URLS else {"purge_everything": True}
    try:
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{os.environ['CF_ZONA_ID']}/purge_cache",
            headers={"Authorization": f"Bearer {os.environ['CF_TOKEN_PURGA']}"},
            json=cuerpo, timeout=5,
        )
        if r.status_code != 200 or not r.json().get("success"):
            log.warning("Cloudflare no purgó (%s): %s", r.status_code, r.text[:300])
    except Exception:
        log.exception("No se pudo purgar Cloudflare")


def _vaciar():
    global _timer
    with _lock:
        rutas = set(_rutas)
        _rutas.clear()
        _timer = None
    _enviar(rutas)


def _agrupar(rutas):
    cache.delete(CLAVE_FACETAS)
    if not configurado():
        return
    if getattr(settings, "PURGA_SINCRONA", False):  # pruebas
        _enviar(rutas)
        return
    global _timer
    with _lock:
        _rutas.update(rutas)
        if _timer is None:
            _timer = threading.Timer(ESPERA, _vaciar)
            _timer.daemon = True
            _timer.start()


def purgar_al_confirmar(*rutas):
    """Purga estas rutas (y el home y /perfumes/) cuando se confirme la transacción en curso.
    Si la transacción se revierte, no se purga nada."""
    rutas = [r for r in rutas if r]
    transaction.on_commit(lambda: _agrupar(rutas))


def _ruta_perfume(perfume_id):
    from .models import Perfume
    slug = Perfume.objects.filter(pk=perfume_id).values_list("slug", flat=True).first()
    return reverse("perfume_detalle", args=[slug]) if slug else None


def _perfume(sender, instance, **kwargs):
    purgar_al_confirmar(instance.get_absolute_url() if instance.slug else None)


def _de_un_perfume(sender, instance, **kwargs):
    purgar_al_confirmar(_ruta_perfume(instance.perfume_id))


def _general(sender, instance, **kwargs):
    purgar_al_confirmar()


def conectar():
    """Lo llama models.py al cargarse. El stock y el precio se purgan desde Perfume.actualizar_resumen."""
    pares = [
        ("catalogo.Perfume", _perfume),
        ("catalogo.Resena", _de_un_perfume),
        ("catalogo.ImagenPerfume", _de_un_perfume),
        ("catalogo.Promocion", _general),
        ("catalogo.ImagenPortada", _general),
        ("catalogo.Marca", _general),
        ("catalogo.FamiliaOlfativa", _general),
        ("catalogo.Nota", _general),
    ]
    for modelo, funcion in pares:
        for senal, nombre in ((post_save, "save"), (post_delete, "delete")):
            senal.connect(funcion, sender=modelo, dispatch_uid=f"purga-{modelo}-{nombre}")
