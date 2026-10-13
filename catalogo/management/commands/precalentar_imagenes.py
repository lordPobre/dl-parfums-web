"""Pide una vez a Cloudinary cada variante de imagen que usa el sitio, para que la
genere y la deje en caché antes de que llegue un visitante.

Uso (con las variables de producción cargadas, igual que para migrate):
    python manage.py precalentar_imagenes
    python manage.py precalentar_imagenes --hilos 4

Ejecútalo después de cada despliegue que cambie anchos o la marca de agua,
y después de subir perfumes nuevos.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.core.management.base import BaseCommand

from catalogo.models import ImagenPerfume, ImagenPortada, Marca, Perfume, Promocion
from catalogo.templatetags.cloudinary_wm import _transformar

# (ancho, con marca de agua) que usan las plantillas
PERFUME = [(120, True), (160, True), (320, True), (480, True), (720, True),
           (600, True), (900, True), (1200, True)]
OFERTA = [(800, True), (1600, True)]
GALERIA = [(160, True), (900, True)]
PORTADA = [(1600, False)]
LOGO = [(300, False), (400, False)]
PROMO = [(160, True), (720, True)]

# f_auto entrega un formato distinto según el navegador: se calientan los dos principales
NAVEGADORES = {
    "avif": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "webp": "image/webp,image/*,*/*;q=0.8",
}


def _url(campo):
    try:
        return campo.url if campo else None
    except Exception:
        return None


class Command(BaseCommand):
    help = "Genera por adelantado en Cloudinary todas las variantes de imagen del sitio."

    def add_arguments(self, parser):
        parser.add_argument("--hilos", type=int, default=6)

    def handle(self, *args, **opts):
        urls = set()

        def agregar(campo, variantes):
            base = _url(campo)
            if base:
                for ancho, marca in variantes:
                    urls.add(_transformar(base, ancho, marca))

        for p in Perfume.objects.filter(activo=True, fusionado_en__isnull=True).only("imagen", "es_oferta"):
            agregar(p.imagen, PERFUME + (OFERTA if p.es_oferta else []))
        for g in ImagenPerfume.objects.filter(perfume__activo=True).only("imagen"):
            agregar(g.imagen, GALERIA)
        for i in ImagenPortada.objects.filter(activo=True).only("imagen"):
            agregar(i.imagen, PORTADA)
        for m in Marca.objects.exclude(logo="").exclude(logo__isnull=True).only("logo"):
            agregar(m.logo, LOGO)
        for pr in Promocion.objects.filter(activo=True).only("imagen"):
            agregar(pr.imagen, PROMO)

        tareas = [(u, a) for u in urls for a in NAVEGADORES.values()]
        self.stdout.write(f"{len(urls)} variantes · {len(tareas)} peticiones…")

        sesion = requests.Session()

        def pedir(url, accept):
            try:
                r = sesion.get(url, headers={"Accept": accept}, timeout=60)
                return r.status_code
            except requests.RequestException:
                return 0

        ok = fallos = 0
        with ThreadPoolExecutor(max_workers=opts["hilos"]) as pool:
            futuros = {pool.submit(pedir, u, a): u for u, a in tareas}
            for n, f in enumerate(as_completed(futuros), 1):
                if f.result() == 200:
                    ok += 1
                else:
                    fallos += 1
                    self.stderr.write(f"  ✗ {futuros[f]}")
                if n % 100 == 0:
                    self.stdout.write(f"  {n}/{len(tareas)}")

        self.stdout.write(self.style.SUCCESS(f"Listo: {ok} correctas, {fallos} con error."))
