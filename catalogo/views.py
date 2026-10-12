import os
import json
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Case, When, IntegerField
from django.db import transaction
from django.core.cache import cache
from .models import Perfume, Marca, FamiliaOlfativa, ImagenPortada, Promocion, Resena, PaginaNosotros, Pedido, ItemPedido, Presentacion, SlugAntiguo
from .cache_cdn import cache_cdn


def _ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")) or "anon"


def _excede_limite(request, accion, maximo, segundos):
    """Límite simple por IP usando la caché de Django (Redis si está configurado)."""
    clave = f"lim:{accion}:{_ip(request)}"
    n = cache.get(clave, 0)
    if n >= maximo:
        return True
    cache.set(clave, n + 1, segundos)
    return False


@cache_cdn()
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


GENEROS_URL = {
    'mujer': ('F', 'Perfumes para mujer'),
    'hombre': ('M', 'Perfumes para hombre'),
    'unisex': ('U', 'Perfumes unisex'),
}
POR_PAGINA = 24


def _entero(valor):
    try:
        return int(valor) if valor not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _catalogo(request, landing=None):
    """Catálogo con filtros combinables. 'landing' fija un filtro desde la URL
    (/perfumes/mujer/, /familia/<slug>/, /casa/<slug>/) y aporta título e introducción."""
    landing = landing or {}
    perfumes = Perfume.objects.filter(activo=True).select_related('marca', 'familia')

    filtro_genero = landing.get('genero') or request.GET.get('genero')
    if filtro_genero not in ('F', 'M', 'U'):
        filtro_genero = None
    marca_id = landing.get('marca_id') or _entero(request.GET.get('marca'))
    familia_id = landing.get('familia_id') or _entero(request.GET.get('familia'))
    familia_txt = request.GET.get('familia_txt')  # clave del test olfativo (ej: 'oriental')
    buscar = (request.GET.get('q') or '').strip()[:80]

    if buscar:
        perfumes = perfumes.filter(
            Q(nombre__icontains=buscar) | Q(marca__nombre__icontains=buscar) | Q(inspirado_en__icontains=buscar)
        )
    if marca_id:
        perfumes = perfumes.filter(marca_id=marca_id)
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)
    if familia_id:
        perfumes = perfumes.filter(familia_id=familia_id)
    elif familia_txt:
        # 'citrica' encuentra el slug 'citrica' de "Cítrica" (el slug ya no tiene tildes)
        fam = FamiliaOlfativa.objects.filter(slug__icontains=slugify(familia_txt)).first()
        if fam:
            perfumes = perfumes.filter(familia_id=fam.id)
            familia_id = fam.id

    # Primero con stock, agotados al final; luego los más nuevos
    perfumes = perfumes.annotate(
        sin_stock=Case(When(stock__lte=0, then=1), default=0, output_field=IntegerField())
    ).order_by('sin_stock', '-id')

    paginator = Paginator(perfumes, POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'catalogo.html', {
        'perfumes': page_obj,
        'page_obj': page_obj,
        'rango_paginas': paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1),
        'landing': landing,
        'buscar': buscar,
        'marcas': Marca.objects.filter(productos__activo=True).distinct().order_by('nombre'),
        'familias': FamiliaOlfativa.objects.filter(perfume__activo=True).distinct().order_by('nombre'),
        'genero_actual': filtro_genero,
        'marca_seleccionada_id': marca_id,
        'familia_actual': familia_id,
    })


@cache_cdn()
def catalogo(request):
    return _catalogo(request)


@cache_cdn()
def catalogo_genero(request, genero):
    if genero not in GENEROS_URL:
        raise Http404
    codigo, titulo = GENEROS_URL[genero]
    return _catalogo(request, {'genero': codigo, 'titulo': titulo, 'intro': ''})


@cache_cdn()
def catalogo_familia(request, slug):
    fam = get_object_or_404(FamiliaOlfativa, slug=slug)
    return _catalogo(request, {
        'familia_id': fam.id,
        'titulo': f"Perfumes de familia {fam.nombre.lower()}",
        'intro': fam.descripcion,
    })


@cache_cdn()
def catalogo_casa(request, slug):
    marca = get_object_or_404(Marca, slug=slug)
    return _catalogo(request, {
        'marca_id': marca.id,
        'titulo': f"Perfumes {marca.nombre}",
        'intro': marca.descripcion,
    })


def redirigir_perfume_id(request, pk):
    """301 desde las URLs antiguas /perfume/<id>/ a /perfume/<slug>/."""
    perfume = Perfume.objects.filter(pk=pk).first()
    if perfume and perfume.slug != str(pk):
        return redirect(perfume.fusionado_en or perfume, permanent=True)
    # Caso raro: un perfume cuyo slug es solo números (ej. "212")
    if Perfume.objects.filter(slug=str(pk)).exists():
        return perfume_detalle(request, slug=str(pk))
    raise Http404


@cache_cdn()
def perfume_detalle(request, slug):
    perfume = (
        Perfume.objects.select_related('marca', 'familia', 'fusionado_en')
        .prefetch_related('galeria', 'resenas', 'presentaciones')
        .filter(slug=slug).first()
    )
    if perfume is None:
        antiguo = SlugAntiguo.objects.select_related('perfume').filter(slug=slug).first()
        if antiguo:
            return redirect(antiguo.perfume, permanent=True)
        raise Http404
    if not perfume.activo:
        # Perfume unido a otro como tamaño: su URL redirige al perfume principal
        if perfume.fusionado_en and perfume.fusionado_en.activo:
            return redirect(perfume.fusionado_en, permanent=True)
        raise Http404

    # Envío de una nueva reseña (queda pendiente de aprobación en el admin).
    # El resultado se informa con ?resena=... (esas URLs no se cachean en el CDN).
    if request.method == 'POST':
        destino = perfume.get_absolute_url()
        if request.POST.get('sitio_web'):          # campo trampa: solo lo llenan los bots
            return redirect(f"{destino}?resena=enviada#resenas")
        if _excede_limite(request, 'resena', 3, 600):
            return redirect(f"{destino}?resena=limite#resenas")
        nombre = request.POST.get('nombre', '').strip()[:80]
        comentario = request.POST.get('comentario', '').strip()[:2000]
        try:
            calificacion = int(request.POST.get('calificacion', 5))
        except (TypeError, ValueError):
            calificacion = 5
        calificacion = min(5, max(1, calificacion))
        if not (nombre and comentario):
            return redirect(f"{destino}?resena=incompleta#resenas")
        Resena.objects.create(
            perfume=perfume, nombre=nombre,
            calificacion=calificacion, comentario=comentario,
            aprobado=False,
        )
        return redirect(f"{destino}?resena=enviada#resenas")

    # Galería: imagen principal + imágenes secundarias (para el visor multi-imagen)
    galeria = list(perfume.galeria.all())
    # Reseñas aprobadas + promedio de calificación
    resenas = perfume.resenas.filter(aprobado=True)
    from django.db.models import Count
    agg = resenas.aggregate(prom=Avg('calificacion'), n=Count('id'))
    promedio = agg['prom']

    # Presentaciones (tamaños): por defecto la primera con stock
    presentaciones = [p for p in perfume.presentaciones.all() if p.activo]
    seleccion = next((p for p in presentaciones if p.stock > 0), presentaciones[0] if presentaciones else None)
    ml_pedido = _entero(request.GET.get('ml'))
    if ml_pedido:
        seleccion = next((p for p in presentaciones if p.ml == ml_pedido and p.stock > 0), seleccion)

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
        'presentaciones': presentaciones,
        'seleccion': seleccion,
        'resenas': resenas,
        'promedio': promedio,
        'total_resenas': agg['n'],
        'estado_resena': request.GET.get('resena'),
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


@cache_cdn(3600)
def politicas_envio(request):
    return render(request, 'politicas.html')


@cache_cdn(3600)
def nosotros(request):
    nosotros = PaginaNosotros.cargar()
    return render(request, 'nosotros.html', {'nosotros': nosotros})

MAX_QTY = 10      # unidades máximas por línea
MAX_ITEMS = 30    # líneas máximas por pedido
MAX_PEDIDOS = 5   # pedidos por IP cada 10 minutos


@never_cache
def csrf_api(request):
    """Entrega el token CSRF (y fija la cookie) para formularios en páginas cacheadas."""
    return JsonResponse({"token": get_token(request)})


@require_POST
def crear_pedido(request):
    """Recibe el carrito (JSON) y crea un Pedido 'pendiente'.
    Los precios se leen SIEMPRE de la base de datos; los del navegador se ignoran.
    No descuenta stock: eso ocurre cuando el admin aprueba."""
    if _excede_limite(request, 'pedido', MAX_PEDIDOS, 600):
        return JsonResponse({"ok": False, "error": "Demasiados pedidos seguidos. Intenta en unos minutos."}, status=429)

    try:
        data = json.loads(request.body.decode("utf-8"))
        items = data.get("items") or []
        if not isinstance(items, list):
            raise ValueError
    except (ValueError, UnicodeDecodeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Datos inválidos"}, status=400)

    # Normaliza las líneas: (tipo, id, cantidad)
    #   "v-12"    -> presentación 12 (ficha con selector de tamaño)
    #   "8"       -> perfume 8 (tarjeta con un solo tamaño, o carrito guardado antes del cambio)
    #   "promo-3" -> promoción 3
    pedidas = []
    for it in items[:MAX_ITEMS]:
        if not isinstance(it, dict):
            continue
        try:
            qty = max(1, min(MAX_QTY, int(it.get("qty") or 1)))
        except (TypeError, ValueError):
            continue
        pid = str(it.get("id") or "")
        if pid.startswith("v-") and pid[2:].isdigit():
            pedidas.append(("presentacion", int(pid[2:]), qty))
        elif pid.isdigit():
            pedidas.append(("perfume", int(pid), qty))
        elif pid.startswith("promo-") and pid[6:].isdigit():
            pedidas.append(("promo", int(pid[6:]), qty))

    disponibles = Presentacion.objects.filter(activo=True, stock__gt=0, perfume__activo=True).select_related("perfume")
    por_id = disponibles.in_bulk([i for t, i, _ in pedidas if t == "presentacion"])
    # Perfume -> su presentación disponible más barata (siguiendo fusiones)
    destino = {
        p.pk: (p.fusionado_en_id or p.pk)
        for p in Perfume.objects.filter(pk__in=[i for t, i, _ in pedidas if t == "perfume"])
    }
    mas_barata = {}
    for pres in disponibles.filter(perfume_id__in=set(destino.values())).order_by("precio"):
        mas_barata.setdefault(pres.perfume_id, pres)
    promos = Promocion.objects.filter(activo=True).in_bulk([i for t, i, _ in pedidas if t == "promo"])

    lineas = []
    for tipo, obj_id, qty in pedidas:
        if tipo == "promo":
            if obj_id in promos:
                pr = promos[obj_id]
                lineas.append(ItemPedido(perfume=None, nombre=f"Promoción: {pr.titulo}"[:200], precio=int(pr.precio), cantidad=qty))
            continue
        pres = por_id.get(obj_id) if tipo == "presentacion" else mas_barata.get(destino.get(obj_id))
        if pres:
            lineas.append(ItemPedido(
                perfume=pres.perfume, presentacion=pres,
                nombre=f"{pres.perfume.nombre} · {pres.etiqueta}"[:200],
                precio=int(pres.precio_vigente), cantidad=qty,
            ))

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
        "codigo": pedido.codigo,
        "total": pedido.total,
    })
