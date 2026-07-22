from django.contrib import admin
from .models import Marca, FamiliaOlfativa, Perfume, ImagenPortada, Promocion, ImagenPerfume, Resena
from django.utils.html import format_html

@admin.register(ImagenPortada)
class ImagenPortadaAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'titulo', 'orden', 'activo')
    list_display_links = ('miniatura', 'titulo')
    list_editable = ('orden', 'activo')
    list_filter = ('activo',)
    ordering = ('orden', 'id')

    def miniatura(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" style="height:44px;width:78px;object-fit:cover;border-radius:4px;" />',
                obj.imagen.url
            )
        return "—"
    miniatura.short_description = "Vista previa"

class ImagenPerfumeInline(admin.TabularInline):
    model = ImagenPerfume
    extra = 3               # 3 casillas vacías para subir imágenes de una vez
    fields = ('imagen', 'orden')


class ResenaInline(admin.TabularInline):
    model = Resena
    extra = 0
    fields = ('nombre', 'calificacion', 'comentario', 'aprobado', 'fecha')
    readonly_fields = ('fecha',)


# --- OPCIÓN A (recomendada): añade los inlines a tu PerfumeAdmin existente ---
# Si ya tienes un @admin.register(Perfume) class PerfumeAdmin, solo agrégale:
#     inlines = [ImagenPerfumeInline, ResenaInline]
#
# --- OPCIÓN B: si NO tienes PerfumeAdmin propio, descomenta este bloque ---
# admin.site.unregister(Perfume)  # solo si ya estaba registrado sin inlines
# @admin.register(Perfume)
# class PerfumeAdmin(admin.ModelAdmin):
#     list_display = ('nombre', 'marca', 'familia', 'precio', 'es_oferta', 'stock', 'activo')
#     list_filter = ('marca', 'familia', 'genero', 'es_oferta', 'activo')
#     search_fields = ('nombre', 'marca__nombre')
#     inlines = [ImagenPerfumeInline, ResenaInline]


# También puedes moderar todas las reseñas en su propia sección:
@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'perfume', 'calificacion', 'aprobado', 'fecha')
    list_editable = ('aprobado',)
    list_filter = ('aprobado', 'calificacion')
    search_fields = ('nombre', 'perfume__nombre', 'comentario')

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(FamiliaOlfativa)
class FamiliaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

class FamiliaOlfativaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'total_perfumes')
    search_fields = ('nombre',)
    ordering = ('nombre',)

    def total_perfumes(self, obj):
        return obj.perfume_set.count()
    total_perfumes.short_description = "N.º de perfumes"

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'precio', 'genero', 'stock','es_oferta', 'precio_oferta', 'activo', 'destacado')
    list_filter = ('marca', 'familia', 'genero','es_oferta', 'activo', 'destacado')
    search_fields = ('nombre', 'marca__nombre')
    list_editable = ('precio', 'stock', 'activo', 'es_oferta', 'precio_oferta', 'destacado') 
    inlines = [ImagenPerfumeInline, ResenaInline]


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'titulo', 'precio', 'etiqueta', 'orden', 'activo')
    list_display_links = ('miniatura', 'titulo')
    list_editable = ('precio', 'orden', 'activo')
    list_filter = ('activo',)
    filter_horizontal = ('perfumes',)
    ordering = ('orden', 'id')

    def miniatura(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" style="height:44px;width:78px;object-fit:cover;border-radius:4px;" />',
                obj.imagen.url
            )
        return "—"
    miniatura.short_description = "Vista previa"


# --- Opcional pero recomendado ---
# Para asignar la familia (y las notas) al crear/editar cada perfume desde el admin,
# asegúrate de que tu PerfumeAdmin incluya 'familia' en los campos. Ejemplo:
#
# @admin.register(Perfume)
# class PerfumeAdmin(admin.ModelAdmin):
#     list_display = ('nombre', 'marca', 'familia', 'precio', 'es_oferta', 'stock', 'activo')
#     list_filter = ('marca', 'familia', 'genero', 'es_oferta', 'activo')
#     list_editable = ('precio', 'es_oferta', 'activo')
#     search_fields = ('nombre', 'marca__nombre')