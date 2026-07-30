from django.contrib import admin, messages
from django.urls import reverse, path
from .models import Marca, FamiliaOlfativa, Perfume, ImagenPortada, Promocion, ImagenPerfume, Resena,PaginaNosotros,Pedido, ItemPedido
from django.utils.html import format_html
from datetime import date, timedelta
from django.template.response import TemplateResponse
from django.db.models import Sum
from django.db.models.functions import TruncDate
from .admin_ventas import registrar_panel_ventas


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
    actions = ['marcar_destacado', 'quitar_destacado', 'marcar_activo', 'quitar_activo']

    @admin.action(description="Marcar como DESTACADO")
    def marcar_destacado(self, request, queryset):
        queryset.update(destacado=True)

    @admin.action(description="Quitar DESTACADO")
    def quitar_destacado(self, request, queryset):
        queryset.update(destacado=False)

    @admin.action(description="Marcar como ACTIVO")
    def marcar_activo(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Marcar como INACTIVO")
    def quitar_activo(self, request, queryset):
        queryset.update(activo=False)
    
    
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

@admin.register(PaginaNosotros)
class PaginaNosotrosAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'titulo', 'actualizado')

    def has_add_permission(self, request):
        # Solo un registro: si ya existe, oculta el botón "Agregar"
        return not PaginaNosotros.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False  # no permitir borrar el contenido

class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    fields = ('perfume', 'nombre', 'precio', 'cantidad', 'subtotal')
    readonly_fields = ('subtotal',)

    def subtotal(self, obj):
        return f"${obj.subtotal}" if obj.pk else "—"


def _descontar_stock(pedido, request):
    """Descuenta el stock de cada item una sola vez. Devuelve True si se aplicó."""
    if pedido.stock_descontado:
        return False
    faltantes = []
    for item in pedido.items.select_related('perfume'):
        p = item.perfume
        if not p:
            continue
        if p.stock is None:
            continue
        if p.stock < item.cantidad:
            faltantes.append(f"{p.nombre} (stock {p.stock}, pedido {item.cantidad})")
    if faltantes:
        messages.error(request, "No hay stock suficiente para: " + "; ".join(faltantes))
        return False
    for item in pedido.items.select_related('perfume'):
        p = item.perfume
        if p and p.stock is not None:
            p.stock = max(0, p.stock - item.cantidad)
            p.save(update_fields=['stock'])
    pedido.stock_descontado = True
    pedido.save(update_fields=['stock_descontado'])
    return True


@admin.action(description="Aprobar venta y descontar stock")
def aprobar_pedidos(modeladmin, request, queryset):
    aprobados = 0
    for pedido in queryset:
        if _descontar_stock(pedido, request):
            pedido.estado = 'aprobado'
            pedido.save(update_fields=['estado'])
            aprobados += 1
    if aprobados:
        messages.success(request, f"{aprobados} venta(s) aprobada(s) y stock descontado.")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'total', 'stock_descontado', 'creado')
    list_filter = ('estado', 'creado')
    search_fields = ('cliente', 'telefono')
    readonly_fields = ('total', 'stock_descontado', 'creado', 'actualizado')
    inlines = [ItemPedidoInline]
    actions = [aprobar_pedidos]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        obj.recalcular_total()
        obj.save(update_fields=['total'])
        # Si se cambia el estado a "aprobado" desde el formulario, descontar stock.
        if obj.estado == 'aprobado' and not obj.stock_descontado:
            _descontar_stock(obj, request)
            if obj.stock_descontado:
                messages.success(request, "Stock descontado para esta venta.")


registrar_panel_ventas(admin.site)
