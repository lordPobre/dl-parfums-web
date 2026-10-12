from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import HttpResponse
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from catalogo.sitemaps import EstaticoSitemap, GeneroSitemap, FamiliaSitemap, CasaSitemap, PerfumeSitemap

sitemaps_dict = {
    "estaticas": EstaticoSitemap,
    "generos": GeneroSitemap,
    "familias": FamiliaSitemap,
    "casas": CasaSitemap,
    "perfumes": PerfumeSitemap,
}


def robots_txt(request):
    lineas = [
        "User-Agent: *",
        "Allow: /",
        "Disallow: /api/",
        # Combinaciones de filtros sin valor propio para Google (las landings sí se indexan)
        "Disallow: /*?*orden=",
        "Disallow: /*?*precio=",
        "Disallow: /*?*tamano=",
        "Disallow: /*?*stock=",
        "Disallow: /*?*q=",
        "",
        "Sitemap: https://www.instintoolfativo.cl/sitemap.xml",
    ]
    return HttpResponse("\n".join(lineas), content_type="text/plain")


urlpatterns = [
    path('perseus-access-x12/', admin.site.urls),
    path('', include('catalogo.urls')),
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
