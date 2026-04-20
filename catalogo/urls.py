from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('perfume/<int:perfume_id>/', views.perfume_detalle, name='perfume_detalle'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('contacto/', views.contacto, name='contacto'),
    path('politicas-de-envio/', views.politicas_envio, name='politicas'),
    path('nosotros/', views.nosotros, name='nosotros'),
]