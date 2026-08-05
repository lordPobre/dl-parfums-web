from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Perfume


class EstaticoSitemap(Sitemap):
    changefreq = "monthly"

    # Prioridad por vista
    _priority = {"home": 1.0, "catalogo": 0.9}

    def items(self):
        return ["home", "catalogo", "nosotros", "contacto", "politicas"]

    def priority(self, item):
        return self._priority.get(item, 0.7)

    def location(self, item):
        return reverse(item)


class PerfumeSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return Perfume.objects.filter(activo=True)

    def lastmod(self, obj):
        return getattr(obj, "actualizado", None)

    def location(self, obj):
        return reverse("perfume_detalle", args=[obj.id])