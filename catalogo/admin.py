from django.contrib import admin
from django.urls import reverse
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
    extra = 3              
    fields = ('imagen', 'orden')


class ResenaInline(admin.TabularInline):
    model = Resena
    extra = 0
    fields = ('nombre', 'calificacion', 'comentario', 'aprobado', 'fecha')
    readonly_fields = ('fecha',)

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

class PrevNextAdminMixin:
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            obj = self.model.objects.get(pk=object_id)
            qs = self.get_queryset(request)
            ordering = self.get_ordering(request) or self.model._meta.ordering or ['pk']
            qs = qs.order_by(*ordering)
            ids = list(qs.values_list('pk', flat=True))
            if obj.pk in ids:
                i = ids.index(obj.pk)
                info = (self.model._meta.app_label, self.model._meta.model_name)
                if i > 0:
                    extra_context['prev_object_url'] = reverse('admin:%s_%s_change' % info, args=[ids[i - 1]])
                if i < len(ids) - 1:
                    extra_context['next_object_url'] = reverse('admin:%s_%s_change' % info, args=[ids[i + 1]])
        except Exception:
            pass
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

@admin.register(Perfume)
class PerfumeAdmin(PrevNextAdminMixin, admin.ModelAdmin):
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
