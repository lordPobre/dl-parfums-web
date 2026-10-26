import os
import json
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q, Exists, OuterRef
from django.db.models.functions import Coalesce
from django.utils.cache import patch_cache_control
from urllib.parse import urlencode
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Case, When, IntegerField, Count
from django.db import transaction
from django.core.cache import cache
from .models import Perfume, Marca, FamiliaOlfativa, ImagenPortada, Promocion, Resena, PaginaNosotros, Pedido, ItemPedido, Presentacion, SlugAntiguo, Nota, PerfumeNota
from .cache_cdn import cache_cdn
from .forms import ContactoForm
from .models import ENCABEZADO_TEMA
from .busqueda import buscar_perfumes, sugerir
from .filtros import url_filtros
from .templatetags.cloudinary_wm import cl, clp


# Límite por IP compartido entre instancias de Vercel (catalogo/limites.py)
from .limites import excede_limite as _excede_limite, ip_cliente as _ip  # noqa: E402


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
    # (solo las vigentes por fecha). Si todas comparten tema, el encabezado también lo usa.
    promociones = list(Promocion.vigentes().prefetch_related('perfumes'))
    temas = {p.tema for p in promociones}
    tema_promos = temas.pop() if len(temas) == 1 else 'especial'
    # Familias en JSON para el test olfativo (id + nombre) — cubre todas las del admin
    familias_data = [{'id': f.id, 'nombre': f.nombre} for f in familias]  # la plantilla lo escapa con json_script

    context = {
        'ofertas': ofertas,
        'destacados': destacados,
        'marcas': marcas,
        'familias': familias,
        'familias_data': familias_data,
        'portadas': portadas,
        'promociones': promociones,
        'tema_promos': tema_promos,
        'encabezado_promos': ENCABEZADO_TEMA[tema_promos],
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


PRECIOS = [
    # (clave, etiqueta, mínimo exclusivo, máximo inclusivo)
    ('hasta-10000', 'Hasta $10.000', None, 10000),
    ('10000-20000', '$10.001 – $20.000', 10000, 20000),
    ('desde-20000', 'Más de $20.000', 20000, None),
]
ORDENES = [
    ('', 'Novedades'),
    ('relevancia', 'Más relevantes'),
    ('precio-asc', 'Precio: menor a mayor'),
    ('precio-desc', 'Precio: mayor a menor'),
    ('nombre', 'Nombre A–Z'),
]
GENEROS_TXT = {'F': 'Mujer', 'M': 'Hombre', 'U': 'Unisex'}
FORMATOS_TXT = dict(Presentacion.FORMATOS)
INTENSIDADES = [
    # (clave, etiqueta, concentraciones)
    ('ligera', 'Ligera (EDT)', ('edt',)),
    ('intensa', 'Intensa (EDP)', ('edp',)),
    ('muy-intensa', 'Muy intensa (Parfum)', ('parfum', 'extrait')),
]
MIN_PERFUMES_NOTA = 3   # bajo esto, /nota/<slug>/ lleva noindex y no va al sitemap
MAX_NOTAS_FILTRO = 24


def _catalogo(request, landing=None):
    """Catálogo con búsqueda, filtros combinables y orden. 'landing' fija un filtro desde
    la URL (/perfumes/mujer/, /familia/<slug>/, /casa/<slug>/) y aporta título e introducción."""
    landing = landing or {}
    perfumes = Perfume.objects.filter(activo=True).select_related('marca', 'familia')

    genero = landing.get('genero') or request.GET.get('genero')
    if genero not in GENEROS_TXT:
        genero = None
    marca_id = landing.get('marca_id') or _entero(request.GET.get('marca'))
    familia_id = landing.get('familia_id') or _entero(request.GET.get('familia'))
    familia_txt = request.GET.get('familia_txt')  # clave del test olfativo (ej: 'oriental')
    precio = request.GET.get('precio')
    precio = precio if precio in {p[0] for p in PRECIOS} else None
    tamano = _entero(request.GET.get('tamano'))
    formato = request.GET.get('formato')
    formato = formato if formato in FORMATOS_TXT else None
    intensidad = request.GET.get('intensidad')
    intensidad = intensidad if intensidad in {i[0] for i in INTENSIDADES} else None
    nota_id = landing.get('nota_id') or _entero(request.GET.get('nota'))
    solo_stock = request.GET.get('stock') == '1'
    buscar = (request.GET.get('q') or '').strip()[:80]
    orden_pedido = request.GET.get('orden') or ''
    orden_pedido = orden_pedido if orden_pedido in dict(ORDENES) else ''
    orden = orden_pedido or ('relevancia' if buscar else '')

    if marca_id:
        perfumes = perfumes.filter(marca_id=marca_id)
    if genero:
        perfumes = perfumes.filter(genero=genero)
    if familia_id:
        perfumes = perfumes.filter(familia_id=familia_id)
    elif familia_txt and slugify(familia_txt):
        fam = FamiliaOlfativa.objects.filter(slug__icontains=slugify(familia_txt)).first()
        if fam:
            perfumes = perfumes.filter(familia_id=fam.id)
            familia_id = fam.id

    # Precio, tamaño y formato se filtran por presentación: UNA misma presentación
    # debe cumplirlos todos (ej. "decant de hasta $10.000").
    if precio or tamano or formato:
        pres = Presentacion.objects.filter(perfume=OuterRef('pk'), activo=True)
        if precio:
            _, _, minimo, maximo = next(p for p in PRECIOS if p[0] == precio)
            pres = pres.annotate(pv=Coalesce('precio_oferta', 'precio'))
            if minimo:
                pres = pres.filter(pv__gt=minimo)
            if maximo:
                pres = pres.filter(pv__lte=maximo)
        if tamano:
            pres = pres.filter(ml=tamano)
        if formato:
            pres = pres.filter(formato=formato)
        perfumes = perfumes.filter(Exists(pres))
    if intensidad:
        perfumes = perfumes.filter(concentracion__in=next(i[2] for i in INTENSIDADES if i[0] == intensidad))
    if nota_id:
        perfumes = perfumes.filter(Exists(PerfumeNota.objects.filter(perfume=OuterRef('pk'), nota_id=nota_id)))
    if solo_stock:
        perfumes = perfumes.filter(stock__gt=0)
    if buscar:
        perfumes = buscar_perfumes(perfumes, buscar)

    perfumes = perfumes.annotate(
        sin_stock=Case(When(stock__lte=0, then=1), default=0, output_field=IntegerField())
    )
    criterios = {
        '': ('sin_stock', '-id'),
        'relevancia': ('sin_stock', '-relevancia', '-id') if buscar else ('sin_stock', '-id'),
        'precio-asc': ('sin_stock', 'precio', '-id'),
        'precio-desc': ('sin_stock', '-precio', '-id'),
        'nombre': ('nombre',),
    }
    perfumes = perfumes.order_by(*criterios[orden])

    paginator = Paginator(perfumes, POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Datos para los filtros
    marcas = list(Marca.objects.filter(productos__activo=True).distinct().order_by('nombre'))
    familias = list(FamiliaOlfativa.objects.filter(perfume__activo=True).distinct().order_by('nombre'))
    tamanos = list(
        Presentacion.objects.filter(activo=True, perfume__activo=True)
        .values_list('ml', flat=True).distinct().order_by('ml')
    )
    formatos = [
        (f, FORMATOS_TXT[f]) for f in FORMATOS_TXT
        if Presentacion.objects.filter(activo=True, perfume__activo=True, formato=f).exists()
    ]
    concentraciones = set(
        Perfume.objects.filter(activo=True).exclude(concentracion='').values_list('concentracion', flat=True)
    )
    intensidades = [(c, e) for c, e, codigos in INTENSIDADES if concentraciones & set(codigos)]
    notas_filtro = list(
        Nota.objects.annotate(n=Count('en_perfumes__perfume', filter=Q(en_perfumes__perfume__activo=True), distinct=True))
        .filter(n__gte=2).order_by('-n', 'nombre')[:MAX_NOTAS_FILTRO]
    )
    if nota_id and nota_id not in {n.id for n in notas_filtro}:
        notas_filtro += list(Nota.objects.filter(pk=nota_id))
    notas_filtro.sort(key=lambda n: n.nombre)

    estado = {
        'q': buscar, 'genero': genero, 'marca': marca_id, 'familia': familia_id, 'nota': nota_id,
        'tamano': tamano, 'formato': formato, 'precio': precio, 'intensidad': intensidad,
        'stock': '1' if solo_stock else None, 'orden': orden_pedido,
    }
    estado = {k: v for k, v in estado.items() if v not in (None, '')}
    slugs = {
        'familia': {str(f.id): f.slug for f in familias},
        'marca': {str(m.id): m.slug for m in marcas},
        'nota': {str(n.id): n.slug for n in notas_filtro},
    }

    # Chips de "filtros activos", cada uno con su enlace para quitarlo
    nombres_familia = {f.id: f.nombre for f in familias}
    nombres_marca = {m.id: m.nombre for m in marcas}
    etiquetas = {
        'genero': GENEROS_TXT.get(genero),
        'familia': nombres_familia.get(familia_id),
        'marca': nombres_marca.get(marca_id),
        'nota': next((f"Nota: {n.nombre}" for n in notas_filtro if n.id == nota_id), None),
        'tamano': f"{tamano} ml" if tamano else None,
        'formato': FORMATOS_TXT.get(formato),
        'intensidad': dict((i[0], i[1]) for i in INTENSIDADES).get(intensidad),
        'precio': dict((p[0], p[1]) for p in PRECIOS).get(precio),
        'stock': 'Solo disponibles' if solo_stock else None,
    }
    activos = [
        {'etiqueta': texto, 'url': url_filtros(estado, slugs, **{clave: None})}
        for clave, texto in etiquetas.items() if texto
    ]

    return render(request, 'catalogo.html', {
        'perfumes': page_obj,
        'page_obj': page_obj,
        'rango_paginas': paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1),
        'landing': landing,
        'buscar': buscar,
        'sugerencias': sugerir(Perfume.objects.filter(activo=True), buscar) if buscar and not paginator.count else [],
        'marcas': marcas,
        'familias': familias,
        'tamanos': tamanos,
        'formatos': formatos,
        'intensidades': intensidades,
        'notas_filtro': notas_filtro,
        'precios': PRECIOS,
        'ordenes': [o for o in ORDENES if o[0] != 'relevancia' or buscar],
        'genero_actual': genero,
        'marca_seleccionada_id': marca_id,
        'familia_actual': familia_id,
        'tamano_actual': tamano,
        'formato_actual': formato,
        'intensidad_actual': intensidad,
        'nota_actual': nota_id,
        'precio_actual': precio,
        'solo_stock': solo_stock,
        'orden_actual': orden,
        'estado_filtros': estado,
        'estado_sin_q': [(k, v) for k, v in estado.items() if k != 'q'],
        'slugs_filtros': slugs,
        'filtros_activos': activos,
        'n_filtros': len(activos),
        'n_mas_filtros': sum(bool(x) for x in (tamano, formato, precio, intensidad, nota_id, solo_stock, orden_pedido)),
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


@cache_cdn()
def catalogo_nota(request, slug):
    nota = get_object_or_404(Nota, slug=slug)
    n = nota.en_perfumes.filter(perfume__activo=True).values('perfume').distinct().count()
    return _catalogo(request, {
        'nota_id': nota.id,
        'titulo': f"Perfumes con notas de {nota.nombre.lower()}",
        'intro': nota.descripcion,
        'noindex': n < MIN_PERFUMES_NOTA,
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
        .prefetch_related('galeria', 'resenas', 'presentaciones', 'notas_perfume__nota')
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
    form = ContactoForm(request.POST or None)
    if request.method == 'POST':
        if request.POST.get('sitio_web'):          # campo trampa: se finge éxito y no se envía nada
            messages.success(request, 'Tu mensaje ha sido enviado. Te contactaremos pronto.')
            return redirect('contacto')
        if _excede_limite(request, 'contacto', 3, 600):
            messages.error(request, 'Recibimos varios mensajes seguidos desde tu conexión. '
                                    'Intenta en unos minutos o escríbenos por WhatsApp.')
        elif form.is_valid():
            datos = form.cleaned_data
            buzon = os.environ.get('EMAIL_HOST_USER') or settings.DEFAULT_FROM_EMAIL
            correo = EmailMessage(
                subject=f"Nuevo mensaje de contacto en Instinto Olfativo de: {datos['nombre']}",
                body=f"Nombre: {datos['nombre']}\nCorreo de contacto: {datos['email']}\n\nMensaje:\n{datos['mensaje']}",
                from_email=buzon,
                to=[buzon],
                reply_to=[datos['email']],   # «Responder» en Gmail le contesta al cliente
            )
            try:
                correo.send(fail_silently=False)
                messages.success(request, 'Tu mensaje ha sido enviado. Te contactaremos pronto.')
                return redirect('contacto')
            except Exception:
                messages.error(request, 'Hubo un problema al enviar el mensaje. Intenta nuevamente.')
        else:
            messages.error(request, 'Revisa los campos marcados.')

    return render(request, 'contacto.html', {'form': form})


@cache_cdn(3600)
def politicas_envio(request):
    return render(request, 'politicas.html')


@cache_cdn(3600)
def terminos(request):
    return render(request, 'terminos.html')


@cache_cdn(3600)
def privacidad(request):
    return render(request, 'privacidad.html')


@cache_cdn(3600)
def nosotros(request):
    nosotros = PaginaNosotros.cargar()
    return render(request, 'nosotros.html', {'nosotros': nosotros})

MAX_QTY = 10      # unidades máximas por línea
MAX_ITEMS = 30    # líneas máximas por pedido
MAX_PEDIDOS = 5   # pedidos por IP cada 10 minutos


def api_buscar(request):
    """Resultados instantáneos para el buscador del encabezado (máx. 6)."""
    texto = (request.GET.get('q') or '').strip()[:80]
    resultados = []
    if len(texto) >= 2:
        qs = buscar_perfumes(Perfume.objects.filter(activo=True).select_related('marca'), texto)
        qs = qs.annotate(
            sin_stock=Case(When(stock__lte=0, then=1), default=0, output_field=IntegerField())
        ).order_by('sin_stock', '-relevancia', '-id')[:6]
        for p in qs:
            resultados.append({
                'nombre': p.nombre,
                'inspirado_en': p.inspirado_en,
                'casa': p.marca.nombre if p.marca_id else '',
                'url': p.get_absolute_url(),
                'img': cl(p.imagen.url, 120) if p.imagen else '',
                'precio': clp(p.precio_vigente),
                'desde': p.n_presentaciones > 1,
                'agotado': p.stock <= 0,
            })
    resp = JsonResponse({
        'resultados': resultados,
        'ver_todos': reverse('catalogo') + '?' + urlencode({'q': texto}),
    })
    patch_cache_control(resp, public=True, max_age=300, s_maxage=3600, stale_while_revalidate=86400)
    return resp


@never_cache
def csrf_api(request):
    """Entrega el token CSRF (y fija la cookie) para formularios en páginas cacheadas."""
    return JsonResponse({"token": get_token(request)})


from . import combos  # noqa: E402


def _normalizar(items):
    """Líneas del carrito -> [(id_carrito, tipo, id, cantidad)]
      "v-12"    -> presentación 12 (ficha con selector de tamaño)
      "8"       -> perfume 8 (tarjeta con un solo tamaño, o carrito guardado antes del cambio)
      "promo-3" -> promoción 3"""
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
            pedidas.append((pid, "presentacion", int(pid[2:]), qty))
        elif pid.isdigit():
            pedidas.append((pid, "perfume", int(pid), qty))
        elif pid.startswith("promo-") and pid[6:].isdigit():
            pedidas.append((pid, "promo", int(pid[6:]), qty))
    return pedidas


def _nombre_linea(pres):
    nombre = f"{pres.perfume.nombre} · {pres.etiqueta}"
    if pres.perfume.inspirado_en:
        nombre += f" (inspirado en {pres.perfume.inspirado_en})"
    return nombre[:200]


def _lineas(pedidas):
    """[(id_carrito, ItemPedido)] con los precios de la base de datos; lo no disponible se omite.
    Las promociones con combo automático no se piden como línea: se descuentan solas (combos.py)."""
    def ids(tipo):
        return [i for _c, t, i, _q in pedidas if t == tipo]

    disponibles = Presentacion.objects.filter(activo=True, stock__gt=0, perfume__activo=True).select_related("perfume")
    por_id = disponibles.in_bulk(ids("presentacion"))
    # Perfume -> su presentación disponible más barata (siguiendo fusiones)
    destino = {p.pk: (p.fusionado_en_id or p.pk) for p in Perfume.objects.filter(pk__in=ids("perfume"))}
    mas_barata = {}
    for pres in disponibles.filter(perfume_id__in=set(destino.values())).order_by("precio"):
        mas_barata.setdefault(pres.perfume_id, pres)
    promos = Promocion.vigentes().filter(combo_cantidad__isnull=True).in_bulk(ids("promo"))

    lineas = []
    for cid, tipo, obj_id, qty in pedidas:
        if tipo == "promo":
            pr = promos.get(obj_id)
            if pr:
                lineas.append((cid, ItemPedido(perfume=None, nombre=f"Promoción: {pr.titulo}"[:200], precio=int(pr.precio), cantidad=qty)))
            continue
        pres = por_id.get(obj_id) if tipo == "presentacion" else mas_barata.get(destino.get(obj_id))
        if pres:
            lineas.append((cid, ItemPedido(
                perfume=pres.perfume, presentacion=pres, nombre=_nombre_linea(pres),
                precio=int(pres.precio_vigente), cantidad=qty,
            )))
    return lineas


def api_cotizar(request):
    """Vista previa del carrito: precios vigentes, «inspirado en» y descuentos de combos.
    Solo lectura (no crea nada). Formato: ?i=v-12:2,v-15:1"""
    items = []
    for parte in (request.GET.get("i") or "").split(",")[:MAX_ITEMS]:
        pid, _, qty = parte.partition(":")
        items.append({"id": pid.strip(), "qty": qty})
    lineas = _lineas(_normalizar(items))
    descuento, detalle = combos.calcular([l for _, l in lineas])
    subtotal = sum(l.subtotal for _, l in lineas)
    resp = JsonResponse({
        "lineas": [
            {"id": cid, "precio": l.precio, "insp": l.perfume.inspirado_en if l.perfume_id else ""}
            for cid, l in lineas
        ],
        "subtotal": subtotal,
        "descuento": descuento,
        "detalle": detalle,
        "total": max(0, subtotal - descuento),
    })
    patch_cache_control(resp, public=True, max_age=0, s_maxage=300)
    return resp


@require_POST
def crear_pedido(request):
    """Recibe el carrito (JSON) y crea un Pedido 'pendiente'.
    Los precios se leen SIEMPRE de la base de datos; los del navegador se ignoran.
    Los combos automáticos (catalogo/combos.py) se restan del total.
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

    lineas = [l for _, l in _lineas(_normalizar(items))]
    if not lineas:
        return JsonResponse({"ok": False, "error": "El carrito no tiene productos disponibles"}, status=400)
    descuento, detalle = combos.calcular(lineas)

    with transaction.atomic():
        pedido = Pedido.objects.create(
            cliente=str(data.get("cliente") or "")[:120],
            telefono=str(data.get("telefono") or "")[:40],
            estado="pendiente",
            descuento=descuento,
            detalle_descuento=combos.texto(detalle),
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
        "lineas": [{"nombre": l.nombre, "cantidad": l.cantidad, "precio": l.precio} for l in lineas],
        "descuento": descuento,
        "detalle": detalle,
    })
