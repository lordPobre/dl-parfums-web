from django.contrib import admin
from .models import Marca, FamiliaOlfativa, Perfume

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(FamiliaOlfativa)
class FamiliaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'precio', 'genero', 'stock','es_oferta', 'precio_oferta', 'activo', 'destacado')
    list_filter = ('marca', 'familia', 'genero','es_oferta', 'activo', 'destacado')
    search_fields = ('nombre', 'marca__nombre')
    list_editable = ('precio', 'stock', 'activo', 'es_oferta', 'precio_oferta', 'destacado') 