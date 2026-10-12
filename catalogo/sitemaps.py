from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from .models import FamiliaOlfativa, Marca, Perfume
from .views import GENEROS_URL


class EstaticoSitemap(Sitemap):
    changefreq = "monthly"
    _priority = {"home": 1.0, "catalogo": 0.9}

    def items(self):
        return ["home", "catalogo", "nosotros", "contacto", "politicas"]

    def priority(self, item):
        return self._priority.get(item, 0.5)

    def location(self, item):
        return reverse(item)


class GeneroSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return list(GENEROS_URL.keys())

    def location(self, item):
        return reverse("catalogo_genero", args=[item])


class FamiliaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return FamiliaOlfativa.objects.filter(perfume__activo=True).annotate(
            ultima=Max("perfume__actualizado")
        ).distinct().order_by("nombre")

    def lastmod(self, obj):
        return obj.ultima


class CasaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Marca.objects.filter(productos__activo=True).annotate(
            ultima=Max("productos__actualizado")
        ).distinct().order_by("nombre")

    def lastmod(self, obj):
        return obj.ultima


class PerfumeSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Perfume.objects.filter(activo=True).order_by("-id")

    def lastmod(self, obj):
        return obj.actualizado
