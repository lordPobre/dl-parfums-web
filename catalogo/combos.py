"""Combos automáticos: una promoción con «Cantidad del combo» se aplica sola cuando el
carrito junta esa cantidad de perfumes que califican (ej. 2 Smart Collection de 25 o 30 ml
por $10.000). Lo usan crear_pedido (precio final) y api_cotizar (vista previa del carrito)."""
from .models import Promocion
from .templatetags.cloudinary_wm import clp


def promos_combo():
    return list(Promocion.vigentes().filter(combo_cantidad__gte=2).prefetch_related("perfumes"))


def calcular(lineas, promos=None):
    """lineas: ItemPedido sin guardar, con presentación. Devuelve (descuento, detalle).
    Cada unidad cuenta en un solo combo. Los combos se arman con las unidades más caras
    primero (mayor ahorro para el cliente) y solo se aplican si de verdad bajan el precio."""
    unidades = [
        {"pres": l.presentacion, "precio": l.precio, "libre": True}
        for l in lineas if l.presentacion_id for _ in range(l.cantidad)
    ]
    if not unidades:
        return 0, []
    total, detalle = 0, []
    for pr in (promos_combo() if promos is None else promos):
        n = pr.combo_cantidad
        elegibles = sorted(
            (u for u in unidades if u["libre"] and pr.califica(u["pres"])),
            key=lambda u: -u["precio"],
        )
        combos = ahorro = 0
        for k in range(0, len(elegibles) - n + 1, n):
            grupo = elegibles[k:k + n]
            a = sum(u["precio"] for u in grupo) - pr.precio
            if a <= 0:
                break
            for u in grupo:
                u["libre"] = False
            combos += 1
            ahorro += a
        if combos:
            total += ahorro
            detalle.append({"titulo": pr.titulo, "combos": combos, "ahorro": ahorro})
    return total, detalle


def texto(detalle):
    """Resumen para el admin: «2 Smart Collection por $10.000 x1: -$2.000»."""
    return "; ".join(f"{d['titulo']} x{d['combos']}: -{clp(d['ahorro'])}" for d in detalle)[:255]
