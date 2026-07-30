# Panel de Ventas en el admin: ganancias día/mes/año + gráfico de línea
# ----------------------------------------------------------------------
# Requiere que ya tengas los modelos Pedido / ItemPedido (VENTAS_PEDIDOS.md).
# El panel considera SOLO pedidos en estado 'aprobado' (ventas confirmadas).
#
# Instalación:
# 1) Copia este archivo como  catalogo/admin_ventas.py
# 2) En catalogo/admin.py agrega al final:
#        from .admin_ventas import registrar_panel_ventas
#        registrar_panel_ventas(admin.site)
# 3) La sección aparece en:  /perseus-access-x12/ventas/  (link también en el índice del admin)

from datetime import date, timedelta
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncYear


def _panel_ventas_view(admin_site):
    def vista(request):
        from .models import Pedido

        aprobados = Pedido.objects.filter(estado='aprobado')
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)
        inicio_anio = hoy.replace(month=1, day=1)

        def suma(qs):
            return qs.aggregate(t=Sum('total'))['t'] or 0

        total_dia = suma(aprobados.filter(creado__date=hoy))
        total_mes = suma(aprobados.filter(creado__date__gte=inicio_mes))
        total_anio = suma(aprobados.filter(creado__date__gte=inicio_anio))
        total_hist = suma(aprobados)
        num_ventas = aprobados.count()

        # Cantidad de productos vendidos (suma de cantidades en pedidos aprobados)
        from .models import ItemPedido
        productos_vendidos = ItemPedido.objects.filter(
            pedido__estado='aprobado'
        ).aggregate(t=Sum('cantidad'))['t'] or 0

        # --- Serie DÍA: últimos 30 días ---
        hace_30 = hoy - timedelta(days=29)
        por_dia = dict(
            aprobados.filter(creado__date__gte=hace_30)
            .annotate(d=TruncDate('creado')).values('d')
            .annotate(t=Sum('total')).values_list('d', 't')
        )
        labels_dia, valores_dia = [], []
        for i in range(30):
            d = hace_30 + timedelta(days=i)
            labels_dia.append(d.strftime('%d/%m'))
            valores_dia.append(int(por_dia.get(d, 0)))

        # --- Serie MES: últimos 12 meses ---
        por_mes = dict(
            aprobados.annotate(m=TruncMonth('creado')).values('m')
            .annotate(t=Sum('total')).values_list('m', 't')
        )
        por_mes = {(k.year, k.month): int(v) for k, v in por_mes.items()}
        meses_txt = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        labels_mes, valores_mes = [], []
        y, m = hoy.year, hoy.month
        seq = []
        for _ in range(12):
            seq.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        for (yy, mm) in reversed(seq):
            labels_mes.append(f"{meses_txt[mm-1]} {str(yy)[2:]}")
            valores_mes.append(por_mes.get((yy, mm), 0))

        # --- Serie AÑO: últimos 5 años ---
        por_anio = dict(
            aprobados.annotate(a=TruncYear('creado')).values('a')
            .annotate(t=Sum('total')).values_list('a', 't')
        )
        por_anio = {k.year: int(v) for k, v in por_anio.items()}
        labels_anio, valores_anio = [], []
        for yy in range(hoy.year - 4, hoy.year + 1):
            labels_anio.append(str(yy))
            valores_anio.append(por_anio.get(yy, 0))

        ctx = {
            **admin_site.each_context(request),
            'title': 'Panel de Ventas',
            'total_dia': total_dia,
            'total_mes': total_mes,
            'total_anio': total_anio,
            'total_hist': total_hist,
            'num_ventas': num_ventas,
            'productos_vendidos': productos_vendidos,
            'labels_dia': labels_dia, 'valores_dia': valores_dia,
            'labels_mes': labels_mes, 'valores_mes': valores_mes,
            'labels_anio': labels_anio, 'valores_anio': valores_anio,
        }
        return TemplateResponse(request, 'admin/panel_ventas.html', ctx)
    return vista


def registrar_panel_ventas(admin_site):
    """Inyecta la URL /ventas/ en el admin y un acceso desde el índice."""
    _orig_get_urls = admin_site.get_urls

    def get_urls():
        urls = _orig_get_urls()
        extra = [path('ventas/', admin_site.admin_view(_panel_ventas_view(admin_site)), name='panel_ventas')]
        return extra + urls
    admin_site.get_urls = get_urls
