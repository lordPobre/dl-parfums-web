from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.urls import reverse, path
from .models import Marca, FamiliaOlfativa, Perfume, ImagenPortada, Promocion, ImagenPerfume, Resena,PaginaNosotros,Pedido, ItemPedido, Presentacion
from .fusion import fusionar
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
    list_display = ('nombre', 'slug')
    search_fields = ('nombre',)
    prepopulated_fields = {'slug': ('nombre',)}

@admin.register(FamiliaOlfativa)
class FamiliaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}

class FamiliaOlfativaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'total_perfumes')
    search_fields = ('nombre',)
    ordering = ('nombre',)

    def total_perfumes(self, obj):
        return obj.perfume_set.count()
    total_perfumes.short_description = "N.º de perfumes"

class PresentacionInline(admin.TabularInline):
    model = Presentacion
    extra = 1
    fields = ('formato', 'ml', 'precio', 'precio_oferta', 'stock', 'activo', 'orden', 'sku')
    readonly_fields = ('sku',)
    verbose_name = "Presentación (tamaño)"
    verbose_name_plural = "Presentaciones (tamaños, precios y stock)"


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
    list_display = ('nombre', 'inspirado_en', 'marca', 'precio', 'stock', 'n_presentaciones', 'genero', 'es_oferta', 'activo', 'destacado')
    list_filter = ('marca', 'familia', 'genero','es_oferta', 'activo', 'destacado')
    search_fields = ('nombre', 'marca__nombre', 'inspirado_en')
    prepopulated_fields = {'slug': ('nombre',)}
    list_editable = ('activo', 'destacado')
    # Precio, stock y oferta se calculan desde las presentaciones (se editan abajo, en la ficha)
    readonly_fields = ('precio', 'precio_oferta', 'es_oferta', 'stock', 'n_presentaciones', 'fusionado_en')
    inlines = [PresentacionInline, ImagenPerfumeInline, ResenaInline]
    actions = ['marcar_destacado', 'quitar_destacado', 'marcar_activo', 'quitar_activo', 'unir_como_presentaciones']

    @admin.action(description="Unir en un solo perfume (como tamaños)")
    def unir_como_presentaciones(self, request, queryset):
        if queryset.count() < 2:
            messages.error(request, "Selecciona al menos dos perfumes para unirlos.")
            return
        principal, avisos = fusionar(list(queryset))
        for aviso in avisos:
            messages.warning(request, aviso)
        messages.success(request, f"Unidos en «{principal.nombre}». Las URLs de los demás redirigen a este.")

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
    fields = ('perfume', 'presentacion', 'nombre', 'precio', 'cantidad', 'subtotal')
    readonly_fields = ('subtotal',)

    def subtotal(self, obj):
        return f"${obj.subtotal}" if obj.pk else "—"


def _resolver_presentaciones(pedido):
    """Pedidos creados antes de las presentaciones: asigna la presentación de su perfume."""
    for item in pedido.items.filter(presentacion__isnull=True, perfume__isnull=False).select_related('perfume'):
        destino = item.perfume.fusionado_en or item.perfume
        v = destino.presentaciones.filter(activo=True).order_by('precio').first()
        if v:
            item.presentacion = v
            item.save(update_fields=['presentacion'])


def _cantidades(pedido):
    necesita = {}
    for item in pedido.items.all():
        if item.presentacion_id:
            necesita[item.presentacion_id] = necesita.get(item.presentacion_id, 0) + item.cantidad
    return necesita


def descontar_stock(pedido_id):
    """Aprueba el pedido y descuenta stock por presentación en UNA transacción.
    - select_for_update bloquea el pedido (no se aprueba dos veces) y las presentaciones
      en orden de id (evita interbloqueos).
    - La resta se hace en la base de datos con F().
    Devuelve (ok, faltantes)."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.stock_descontado:
            if pedido.estado != 'aprobado':
                Pedido.objects.filter(pk=pedido.pk).update(estado='aprobado')
            return True, []
        _resolver_presentaciones(pedido)
        necesita = _cantidades(pedido)
        pres = {
            v.id: v for v in Presentacion.objects.select_for_update(of=('self',))
            .select_related('perfume').filter(id__in=necesita).order_by('id')
        }
        faltan = [
            f"{v.perfume.nombre} {v.etiqueta} (stock {v.stock}, pedido {necesita[vid]})"
            for vid, v in pres.items() if v.stock < necesita[vid]
        ]
        if faltan:
            return False, faltan
        for vid in pres:
            Presentacion.objects.filter(pk=vid).update(stock=F('stock') - necesita[vid])
        Pedido.objects.filter(pk=pedido.pk).update(stock_descontado=True, estado='aprobado')
        for perfume in {v.perfume for v in pres.values()}:
            perfume.actualizar_resumen()
        return True, []


def devolver_stock(pedido_id):
    """Rechaza el pedido; si ya se había descontado stock, lo repone (una sola vez)."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.stock_descontado:
            necesita = _cantidades(pedido)
            for vid in sorted(necesita):
                Presentacion.objects.filter(pk=vid).update(stock=F('stock') + necesita[vid])
            for perfume in Perfume.objects.filter(presentaciones__id__in=necesita).distinct():
                perfume.actualizar_resumen()
        Pedido.objects.filter(pk=pedido.pk).update(stock_descontado=False, estado='rechazado')


@admin.action(description="Aprobar venta y descontar stock")
def aprobar_pedidos(modeladmin, request, queryset):
    aprobados = 0
    for pid in queryset.values_list('pk', flat=True):
        ok, faltan = descontar_stock(pid)
        if ok:
            aprobados += 1
        else:
            messages.error(request, f"Pedido IO-{pid:06d}: no hay stock suficiente para " + "; ".join(faltan))
    if aprobados:
        messages.success(request, f"{aprobados} venta(s) aprobada(s) y stock descontado.")


@admin.action(description="Rechazar venta (repone el stock si ya se había descontado)")
def rechazar_pedidos(modeladmin, request, queryset):
    n = 0
    for pid in queryset.values_list('pk', flat=True):
        devolver_stock(pid)
        n += 1
    messages.success(request, f"{n} venta(s) rechazada(s).")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente', 'telefono', 'estado', 'total', 'stock_descontado', 'creado')
    list_filter = ('estado', 'creado')
    search_fields = ('id', 'cliente', 'telefono')
    readonly_fields = ('codigo', 'total', 'stock_descontado', 'creado', 'actualizado')
    inlines = [ItemPedidoInline]
    actions = [aprobar_pedidos, rechazar_pedidos]

    @admin.display(description="Código", ordering='id')
    def codigo(self, obj):
        return obj.codigo

    def save_model(self, request, obj, form, change):
        # Aprobar o rechazar mueve stock: se aplica DESPUÉS de guardar los productos
        # (save_related), con las funciones transaccionales. Mientras tanto se
        # conserva el estado anterior para no dejar un "aprobado" sin descuento.
        anterior = form.initial.get('estado', 'pendiente') if change else 'pendiente'
        obj._estado_pedido = obj.estado if obj.estado != anterior else None
        if obj._estado_pedido in ('aprobado', 'rechazado'):
            obj.estado = anterior
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        obj.recalcular_total()
        obj.save(update_fields=['total'])
        nuevo = getattr(obj, '_estado_pedido', None)
        if nuevo == 'aprobado':
            ok, faltan = descontar_stock(obj.pk)
            if ok:
                messages.success(request, f"{obj.codigo} aprobado y stock descontado.")
            else:
                messages.error(request, f"{obj.codigo} sigue pendiente: no hay stock suficiente para " + "; ".join(faltan))
        elif nuevo == 'rechazado':
            devolver_stock(obj.pk)
            messages.success(request, f"{obj.codigo} rechazado.")


registrar_panel_ventas(admin.site)
