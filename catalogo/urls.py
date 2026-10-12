from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/pedido/', views.crear_pedido, name='crear_pedido'),
    path('api/csrf/', views.csrf_api, name='csrf_api'),

    # Catálogo y landings
    path('perfumes/', views.catalogo, name='catalogo'),
    path('perfumes/<str:genero>/', views.catalogo_genero, name='catalogo_genero'),
    path('familia/<slug:slug>/', views.catalogo_familia, name='catalogo_familia'),
    path('casa/<slug:slug>/', views.catalogo_casa, name='catalogo_casa'),

    # Ficha: la URL antigua con id redirige (301) a la nueva con slug
    path('perfume/<int:pk>/', views.redirigir_perfume_id),
    path('perfume/<slug:slug>/', views.perfume_detalle, name='perfume_detalle'),

    # URL antigua del catálogo (conserva los filtros ?genero=, ?marca=, ?familia=)
    path('catalogo/', RedirectView.as_view(pattern_name='catalogo', permanent=True, query_string=True)),

    path('contacto/', views.contacto, name='contacto'),
    path('politicas-de-envio/', views.politicas_envio, name='politicas'),
    path('nosotros/', views.nosotros, name='nosotros'),
]
