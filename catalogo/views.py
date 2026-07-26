import os
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg
from .models import Perfume, Marca, FamiliaOlfativa, ImagenPortada, Promocion, Resena, PaginaNosotros


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
    import json
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

    return render(request, 'catalogo.html', {
        'perfumes': perfumes,
        'marcas': Marca.objects.all(),
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

    # Relacionados: misma familia; si no alcanza, se completa con la misma marca.
    relacionados = Perfume.objects.filter(activo=True).exclude(id=perfume.id).select_related('marca')
    if perfume.familia_id:
        relacionados = relacionados.filter(familia_id=perfume.familia_id)[:4]
    else:
        relacionados = relacionados.filter(marca_id=perfume.marca_id)[:4]

    # Fallback: si no hay suficientes, mostrar otras fragancias de la misma marca
    if relacionados.count() < 4:
        relacionados = Perfume.objects.filter(
            activo=True, marca_id=perfume.marca_id
        ).exclude(id=perfume.id).select_related('marca')[:4]

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


def lista_perfumes(request):
    perfumes = Perfume.objects.all()
    filtro_genero = request.GET.get('genero')
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)

    contexto = {
        'perfumes': perfumes,
        'genero_actual': filtro_genero,
    }
    return render(request, 'index.html', contexto)


def politicas_envio(request):
    return render(request, 'politicas.html')


def nosotros(request):
    nosotros = PaginaNosotros.cargar()
    return render(request, 'nosotros.html', {'nosotros': nosotros})
