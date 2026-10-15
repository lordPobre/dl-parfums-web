"""Datos del Inicio del admin (templates/admin/index.html) y contadores del menú."""
from django.db.models import Sum
from django.utils import timezone

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _clp(n):
    return "$" + f"{int(n or 0):,}".replace(",", ".")


def badge_pedidos(request):
    from .models import Pedido
    n = Pedido.objects.filter(estado="pendiente").count()
    return n or None


def badge_resenas(request):
    from .models import Resena
    n = Resena.objects.filter(aprobado=False).count()
    return n or None


def dashboard_callback(request, context):
    from .models import Pedido, Perfume, Promocion

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    fin_ant = inicio_mes - timezone.timedelta(days=1)
    inicio_ant = fin_ant.replace(day=1)
    aprobados = Pedido.objects.filter(estado="aprobado")
    mes = aprobados.filter(creado__date__gte=inicio_mes).aggregate(t=Sum("total"))["t"] or 0
    # Mismo tramo del mes anterior (del 1 al día de hoy), para comparar en igualdad
    tope_ant = min(hoy.day, fin_ant.day)
    ant = aprobados.filter(creado__date__gte=inicio_ant,
                           creado__date__lte=inicio_ant.replace(day=tope_ant)).aggregate(t=Sum("total"))["t"] or 0
    if ant:
        cambio = round((mes - ant) / ant * 100)
        nota_mes = f"{'+' if cambio >= 0 else ''}{cambio}% vs. el mismo tramo de {MESES[inicio_ant.month - 1]}"
    else:
        nota_mes = "Solo ventas aprobadas"

    pendientes = Pedido.objects.filter(estado="pendiente").order_by("creado")
    n_pend = pendientes.count()
    agotados = list(Perfume.objects.filter(activo=True, stock=0).values_list("nombre", flat=True)[:4])
    n_agot = Perfume.objects.filter(activo=True, stock=0).count()
    vigentes = list(Promocion.vigentes().order_by("fecha_fin", "orden")[:4])

    recientes = []
    for p in Pedido.objects.prefetch_related("items").order_by("-creado")[:6]:
        items = [f"{i.nombre} ×{i.cantidad}" if i.cantidad > 1 else i.nombre for i in p.items.all()]
        recientes.append({
            "pedido": p, "items": " · ".join(items) or "—", "total": _clp(p.total),
            "fecha": timezone.localtime(p.creado),
        })

    context.update({
        "saludo_fecha": f"{DIAS[hoy.weekday()].capitalize()} {hoy.day} de {MESES[hoy.month - 1]}",
        "kpis": [
            {"titulo": f"Ventas de {MESES[hoy.month - 1]}", "icono": "payments", "valor": _clp(mes),
             "nota": nota_mes, "url": "admin:panel_ventas"},
            {"titulo": "Pedidos por confirmar", "icono": "shopping_bag", "valor": n_pend,
             "nota": (f"El más antiguo: {timezone.localtime(pendientes[0].creado):%d/%m %H:%M}" if n_pend else "Todo al día"),
             "url": "admin:catalogo_pedido_changelist", "query": "?estado__exact=pendiente", "alerta": n_pend > 0},
            {"titulo": "Perfumes agotados", "icono": "inventory_2", "valor": n_agot,
             "nota": ", ".join(agotados) + ("…" if n_agot > len(agotados) else "") if n_agot else "Ninguno",
             "url": "admin:catalogo_perfume_changelist", "query": "?activo__exact=1&stock=0"},
            {"titulo": "Promociones vigentes", "icono": "percent", "valor": len(vigentes),
             "nota": (f"«{vigentes[0].titulo}» vence el {vigentes[0].fecha_fin:%d/%m}"
                      if vigentes and vigentes[0].fecha_fin else "Sin fecha de término"),
             "url": "admin:catalogo_promocion_changelist"},
        ],
        "recientes": recientes,
        "promos_vigentes": vigentes,
        "hoy": hoy,
    })
    return context
