import os
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Perfume, Marca, FamiliaOlfativa, ImagenPortada


def home(request):
    ofertas = Perfume.objects.filter(es_oferta=True, activo=True)[:4]
    destacados = Perfume.objects.filter(destacado=True, activo=True, es_oferta=False)[:8]
    marcas = Marca.objects.all()
    # Solo familias que tengan al menos un perfume activo (evita tarjetas vacías)
    familias = FamiliaOlfativa.objects.filter(perfume__activo=True).distinct()
    # Diapositivas del carrusel de portada (gestionadas desde el admin)
    portadas = ImagenPortada.objects.filter(activo=True)

    context = {
        'ofertas': ofertas,
        'destacados': destacados,
        'marcas': marcas,
        'familias': familias,
        'portadas': portadas,
    }
    return render(request, 'home.html', context)


def catalogo(request):
    perfumes = Perfume.objects.filter(activo=True).select_related('marca', 'familia')

    filtro_genero = request.GET.get('genero')
    marca_id = request.GET.get('marca')
    familia_id = request.GET.get('familia')

    if marca_id:
        perfumes = perfumes.filter(marca_id=marca_id)
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)
    if familia_id:
        perfumes = perfumes.filter(familia_id=familia_id)

    return render(request, 'catalogo.html', {
        'perfumes': perfumes,
        'marcas': Marca.objects.all(),
        'familias': FamiliaOlfativa.objects.filter(perfume__activo=True).distinct(),
        'genero_actual': filtro_genero,
        'marca_seleccionada_id': int(marca_id) if marca_id else None,
        'familia_actual': int(familia_id) if familia_id else None,
    })


def perfume_detalle(request, perfume_id):
    perfume = get_object_or_404(Perfume, id=perfume_id, activo=True)

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
    }
    return render(request, 'detalle.html', context)


def contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email_cliente = request.POST.get('email')
        mensaje = request.POST.get('mensaje')

        asunto = f'Nuevo mensaje de contacto en DL Parfums de: {nombre}'
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
    return render(request, 'nosotros.html')
