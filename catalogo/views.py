import os
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Perfume,Marca

def home(request):
    ofertas = Perfume.objects.filter(es_oferta=True, activo=True)[:4]
    destacados = Perfume.objects.filter(destacado=True, activo=True, es_oferta=False)[:8]
    marcas = Marca.objects.all()

    context = {
        'ofertas': ofertas,
        'destacados': destacados,
        'marcas': marcas,
    }
    return render(request, 'home.html', context)

def catalogo(request):
    perfumes = Perfume.objects.filter(activo=True)
    
    filtro_genero = request.GET.get('genero')
    marca_id = request.GET.get('marca')
    
    if marca_id:
        perfumes = perfumes.filter(marca_id=marca_id)
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)

    return render(request, 'catalogo.html', {
        'perfumes': perfumes,
        'marcas': Marca.objects.all(),
        'genero_actual': filtro_genero,
        'marca_seleccionada_id': int(marca_id) if marca_id else None
    })

def perfume_detalle(request, perfume_id):
    perfume = get_object_or_404(Perfume, id=perfume_id, activo=True)
    
    context = {
        'perfume': perfume,
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
            send_mail(
                asunto,
                cuerpo,
                mi_correo, 
                [mi_correo],
                fail_silently=False,
            )

            messages.success(request, 'Tu mensaje ha sido enviado. Te contactaremos pronto.')
            return redirect('contacto') 
            
        except Exception as e:
            messages.error(request, 'Hubo un problema al enviar el mensaje. Intenta nuevamente.')
            
    return render(request, 'contacto.html')

def lista_perfumes(request):
    # 1. Traemos TODOS los perfumes por defecto
    perfumes = Perfume.objects.all()
    
    # 2. Capturamos si la URL trae un filtro (ej: ?genero=H)
    filtro_genero = request.GET.get('genero')
    
    # 3. Si hay un filtro en la URL, aplicamos el filtro a la base de datos
    if filtro_genero:
        perfumes = perfumes.filter(genero=filtro_genero)

    # 4. Enviamos los perfumes y el filtro actual al HTML
    contexto = {
        'perfumes': perfumes,
        'genero_actual': filtro_genero,
    }
    return render(request, 'index.html', contexto)

def politicas_envio(request):
    return render(request, 'politicas.html')

def nosotros(request):
    return render(request, 'nosotros.html')