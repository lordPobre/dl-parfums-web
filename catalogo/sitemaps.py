from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Perfume

class PerfumeSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Perfume.objects.filter(activo=True)

    def lastmod(self, obj):
        return obj.id 

class VistasEstaticasSitemap(Sitemap):
    priority = 1.0
    changefreq = "monthly"

    def items(self):
        return ['home', 'catalogo', 'nosotros']

    def location(self, item):
        return reverse(item)