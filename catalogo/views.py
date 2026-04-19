import os
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Perfume,Marca

def home(request):
    perfumes = Perfume.objects.filter(destacado=True, activo=True)
    marca_id = request.GET.get('marca')
    marcas = Marca.objects.all()
    marca_seleccionada = None

    if marca_id:
        marca_seleccionada = get_object_or_404(Marca, id=marca_id)
        perfumes = Perfume.objects.filter(marca=marca_seleccionada, activo=True)
    else:
        perfumes = Perfume.objects.filter(destacado=True, activo=True)[:8]
    
    context = {
        'marcas': marcas,
        'perfumes_destacados': perfumes,
        'marca_seleccionada': marca_seleccionada,
    }
    return render(request, 'home.html', context)

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

def politicas_envio(request):
    return render(request, 'politicas.html')