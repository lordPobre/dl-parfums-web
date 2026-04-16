from django.shortcuts import render, get_object_or_404
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
    return render(request, 'contacto.html')

def politicas_envio(request):
    return render(request, 'politicas.html')