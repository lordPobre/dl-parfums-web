from django.db import transaction

from .models import ImagenPerfume, Perfume


@transaction.atomic
def fusionar(perfumes):
    """Une varios perfumes en uno solo, con sus tamaños como presentaciones.

    - El de menor id queda como principal (conserva su URL, reseñas y contenido).
    - Las presentaciones de los demás pasan al principal; si el principal ya tiene
      ese mismo tamaño, esa presentación no se mueve y se informa.
    - La imagen principal y la galería de los demás pasan a la galería del principal.
    - Las reseñas se trasladan.
    - Los demás quedan inactivos y su URL redirige (301) al principal.
    Devuelve (principal, avisos)."""
    perfumes = sorted(perfumes, key=lambda p: p.pk)
    principal, otros = perfumes[0], perfumes[1:]
    avisos = []
    existentes = {(v.formato, v.ml) for v in principal.presentaciones.all()}

    for otro in otros:
        for v in otro.presentaciones.all():
            if (v.formato, v.ml) in existentes:
                avisos.append(f"«{otro.nombre}»: el principal ya tiene {v.etiqueta}; esa presentación no se movió.")
                continue
            v.perfume = principal
            v.sku = ""  # se regenera con el id del principal
            v.save()
            existentes.add((v.formato, v.ml))

        if otro.imagen:
            ImagenPerfume.objects.create(perfume=principal, imagen=otro.imagen.name, orden=50)
        otro.galeria.update(perfume=principal)
        otro.resenas.update(perfume=principal)

        for campo in ("inspirado_en", "notas_salida", "notas_corazon", "notas_fondo", "concentracion", "meta_descripcion"):
            if not getattr(principal, campo) and getattr(otro, campo):
                setattr(principal, campo, getattr(otro, campo))
        if not principal.familia_id and otro.familia_id:
            principal.familia_id = otro.familia_id
        if len(otro.descripcion or "") > len(principal.descripcion or ""):
            principal.descripcion = otro.descripcion
        principal.destacado = principal.destacado or otro.destacado

        Perfume.objects.filter(pk=otro.pk).update(activo=False, destacado=False, fusionado_en=principal)
        # Si a "otro" ya se le habían unido perfumes antes, ahora apuntan al principal
        Perfume.objects.filter(fusionado_en=otro).update(fusionado_en=principal)

    principal.save()
    principal.actualizar_resumen()
    return principal, avisos
