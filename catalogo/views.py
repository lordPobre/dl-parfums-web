import os
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Case, When, IntegerField
from django.db import transaction
from django.core.cache import cache
from .models import Perfume, Marca, FamiliaOlfativa, ImagenPortada, Promocion, Resena, PaginaNosotros, Pedido, ItemPedido


def home(request):
    ofertas = Perfume.objects.filter(es_oferta=True, activo=True)[:4]
    destacados = Perfume.objects.filter(destacado=True, activo=True, es_oferta=False)[:8]
    marcas = Marca.objects.all()
    # Solo familias que tengan al menos un perfume activo (evita tarjetas vacías)
    familias = FamiliaOlfativa.objects.filter(perfume__activo=True).distinct()
    # Diapositivas del carrusel de portada (gestionadas desde el admin)
    portadas = ImagenPortada.objects.filter(activo=True)
    # Promociones / combos activos (gestionados desde el admin)
    promociones = Promocion.objects.filter(activo=True).prefetch_related('perfumes')
    # Familias en JSON para el test olfativo (id + nombre) — cubre todas las del admin
    familias_data = json.dumps(
        [{'id': f.id, 'nombre': f.nombre} for f in familias],
        ensure_ascii=False,
    )

    context = {
        'ofertas': ofertas,
        'destacados': destacados,
        'marcas': marcas,
        'familias': familias,
        'familias_data': familias_data,
        'portadas': portadas,
        'promociones': promociones,
    }
    return render(request, 'home.html', context)


def catalogo(request):
    perfumes = Perfume.objects.filter(activo=True).select_related('marca', 'familia')
    filtro_genero = request.GET.get('genero')
    marca_id = request.GET.get('marca')
    familia_id = request.GET.get('familia')
    familia_txt = request.GET.get('familia_txt')  # clave del test olfativo (ej: 'oriental')
    buscar = (request.GET.get('q') or '').strip()

    if buscar:
        from django.db.models import Q
        cond = Q(nombre__icontains=buscar) | Q(marca__nombre__icontains=buscar)
        # Incluye 'inspirado_en' solo si el campo existe en el modelo
        if any(f.name == 'inspirado_en' for f in Perfume._meta.get_fields()):
            cond |= Q(inspirado_en__icontains=buscar)
        perfumes = perfumes.filter(cond)

    if marca_id:
        perfumes = perfumes.filter(marca_id=marca_id)
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)
    if familia_id:
        perfumes = perfumes.filter(familia_id=familia_id)
    elif familia_txt:
        # El test olfativo manda una palabra clave; se busca la familia cuyo nombre
        # la contenga, ignorando acentos y mayúsculas (ej: 'citrica' -> 'Cítrica').
        import unicodedata

        def _norm(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', (s or '').lower())
                if unicodedata.category(c) != 'Mn'
            )

        clave = _norm(familia_txt)
        fam = None
        for f in FamiliaOlfativa.objects.all():
            if clave in _norm(f.nombre):
                fam = f
                break
        if fam:
            perfumes = perfumes.filter(familia_id=fam.id)
            familia_id = str(fam.id)

    # Ordenar: primero con stock, agotados al final; luego por id
    from django.db.models import Case, When, IntegerField
    perfumes = perfumes.annotate(
        sin_stock=Case(When(stock__lte=0, then=1), default=0, output_field=IntegerField())
    ).order_by('sin_stock', '-id')

    return render(request, 'catalogo.html', {
        'perfumes': perfumes,
        'buscar': buscar,
        'marcas': Marca.objects.filter(productos__activo=True).distinct(),
        'familias': FamiliaOlfativa.objects.filter(perfume__activo=True).distinct().order_by('nombre'),
        'genero_actual': filtro_genero,
        'marca_seleccionada_id': int(marca_id) if marca_id else None,
        'familia_actual': int(familia_id) if familia_id else None,
    })


def perfume_detalle(request, perfume_id):
    perfume = get_object_or_404(
        Perfume.objects.prefetch_related('galeria', 'resenas'),
        id=perfume_id, activo=True
    )

    # Envío de una nueva reseña (queda pendiente de aprobación en el admin)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        comentario = request.POST.get('comentario', '').strip()
        try:
            calificacion = int(request.POST.get('calificacion', 5))
        except (TypeError, ValueError):
            calificacion = 5
        calificacion = min(5, max(1, calificacion))
        if nombre and comentario:
            Resena.objects.create(
                perfume=perfume, nombre=nombre,
                calificacion=calificacion, comentario=comentario,
                aprobado=False,
            )
            messages.success(request, 'Tu reseña fue enviada y será publicada tras ser revisada.')
        else:
            messages.error(request, 'Completa tu nombre y comentario para enviar la reseña.')
        return redirect('perfume_detalle', perfume_id=perfume.id)

    # Galería: imagen principal + imágenes secundarias (para el visor multi-imagen)
    galeria = list(perfume.galeria.all())
    # Reseñas aprobadas + promedio de calificación
    resenas = perfume.resenas.filter(aprobado=True)
    promedio = resenas.aggregate(prom=Avg('calificacion'))['prom']

    # Relacionados: primero la misma familia; si faltan, se completa con la misma marca.
    base_rel = Perfume.objects.filter(activo=True).exclude(id=perfume.id).select_related('marca')
    relacionados = list(base_rel.filter(familia_id=perfume.familia_id)[:4]) if perfume.familia_id else []
    if len(relacionados) < 4:
        ya = [p.id for p in relacionados]
        relacionados += list(
            base_rel.filter(marca_id=perfume.marca_id).exclude(id__in=ya)[: 4 - len(relacionados)]
        )

    context = {
        'perfume': perfume,
        'relacionados': relacionados,
        'galeria': galeria,
        'resenas': resenas,
        'promedio': promedio,
        'total_resenas': resenas.count(),
    }
    return render(request, 'detalle.html', context)


def contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email_cliente = request.POST.get('email')
        mensaje = request.POST.get('mensaje')

        asunto = f'Nuevo mensaje de contacto en Instinto Olfativo de: {nombre}'
        cuerpo = f'Nombre: {nombre}\nCorreo de contacto: {email_cliente}\n\nMensaje:\n{mensaje}'
        mi_correo = os.environ.get('EMAIL_HOST_USER')

        try:
            send_mail(asunto, cuerpo, mi_correo, [mi_correo], fail_silently=False)
            messages.success(request, 'Tu mensaje ha sido enviado. Te contactaremos pronto.')
            return redirect('contacto')
        except Exception:
            messages.error(request, 'Hubo un problema al enviar el mensaje. Intenta nuevamente.')

    return render(request, 'contacto.html')


def politicas_envio(request):
    return render(request, 'politicas.html')


def nosotros(request):
    nosotros = PaginaNosotros.cargar()
    return render(request, 'nosotros.html', {'nosotros': nosotros})

MAX_QTY = 10      # unidades máximas por línea
MAX_ITEMS = 30    # líneas máximas por pedido
MAX_PEDIDOS = 5   # pedidos por IP cada 10 minutos


def _ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")) or "anon"


@require_POST
def crear_pedido(request):
    """Recibe el carrito (JSON) y crea un Pedido 'pendiente'.
    Los precios se leen SIEMPRE de la base de datos; los del navegador se ignoran.
    No descuenta stock: eso ocurre cuando el admin aprueba."""
    clave = f"pedido:{_ip(request)}"
    intentos = cache.get(clave, 0)
    if intentos >= MAX_PEDIDOS:
        return JsonResponse({"ok": False, "error": "Demasiados pedidos seguidos. Intenta en unos minutos."}, status=429)
    cache.set(clave, intentos + 1, 600)

    try:
        data = json.loads(request.body.decode("utf-8"))
        items = data.get("items") or []
        if not isinstance(items, list):
            raise ValueError
    except (ValueError, UnicodeDecodeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Datos inválidos"}, status=400)

    # Normaliza las líneas: (tipo, id, cantidad)
    pedidas = []
    for it in items[:MAX_ITEMS]:
        if not isinstance(it, dict):
            continue
        try:
            qty = max(1, min(MAX_QTY, int(it.get("qty") or 1)))
        except (TypeError, ValueError):
            continue
        pid = str(it.get("id") or "")
        if pid.isdigit():
            pedidas.append(("perfume", int(pid), qty))
        elif pid.startswith("promo-") and pid[6:].isdigit():
            pedidas.append(("promo", int(pid[6:]), qty))

    perfumes = Perfume.objects.filter(activo=True, stock__gt=0).in_bulk(
        [i for t, i, _ in pedidas if t == "perfume"]
    )
    promos = Promocion.objects.filter(activo=True).in_bulk(
        [i for t, i, _ in pedidas if t == "promo"]
    )

    lineas = []
    for tipo, obj_id, qty in pedidas:
        if tipo == "perfume" and obj_id in perfumes:
            p = perfumes[obj_id]
            precio = p.precio_oferta if (p.es_oferta and p.precio_oferta) else p.precio
            lineas.append(ItemPedido(perfume=p, nombre=p.nombre[:200], precio=int(precio), cantidad=qty))
        elif tipo == "promo" and obj_id in promos:
            pr = promos[obj_id]
            lineas.append(ItemPedido(perfume=None, nombre=f"Promoción: {pr.titulo}"[:200], precio=int(pr.precio), cantidad=qty))

    if not lineas:
        return JsonResponse({"ok": False, "error": "El carrito no tiene productos disponibles"}, status=400)

    with transaction.atomic():
        pedido = Pedido.objects.create(
            cliente=str(data.get("cliente") or "")[:120],
            telefono=str(data.get("telefono") or "")[:40],
            estado="pendiente",
        )
        for l in lineas:
            l.pedido = pedido
        ItemPedido.objects.bulk_create(lineas)
        pedido.recalcular_total()
        pedido.save(update_fields=["total"])

    return JsonResponse({
        "ok": True,
        "pedido_id": pedido.id,
        "codigo": f"IO-{pedido.id:06d}",
        "total": pedido.total,
    })
