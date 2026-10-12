import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from catalogo.fusion import fusionar
from catalogo.models import Perfume, SlugAntiguo, slug_unico

# "Smart Collection No.600 - Dupe Scandal JPG 25 ML"
# "SMART COLLECTION NO.600 – SCANDAL MEN EDP 100 ML"
# "SMART WORLD ASAD 30 ML"
PATRONES = [
    (re.compile(r"^smart collection\s+no\.?\s*(?P<num>\d+)\s*-\s*dupe\s+(?P<insp>.+?)\s*\d+\s*ml\s*$", re.I), "Smart Collection No.{num}"),
    (re.compile(r"^smart collection\s+no\.?\s*(?P<num>\d+)\s*[–-]\s*(?P<insp>.+?)\s+edp\s*\d+\s*ml\s*$", re.I), "Smart Collection No.{num}"),
    (re.compile(r"^smart world\s+(?P<nom>.+?)\s*\d+\s*ml\s*$", re.I), "Smart World {nom}"),
]


def _titulo(texto):
    return texto.title() if texto.isupper() else texto


def proponer(nombre):
    """Devuelve (nombre_limpio, inspirado_en) o (None, '') si el nombre no sigue ningún patrón."""
    for rx, plantilla in PATRONES:
        m = rx.match((nombre or "").strip())
        if m:
            g = m.groupdict()
            limpio = plantilla.format(num=g.get("num") or "", nom=_titulo((g.get("nom") or "").strip()))
            return limpio, _titulo(g["insp"].strip()) if g.get("insp") else ""
    return None, ""


class Command(BaseCommand):
    help = (
        "Quita el tamaño y la palabra 'Dupe' de los nombres, completa 'inspirado en' y propone "
        "qué perfumes unir como tamaños. Sin --aplicar solo muestra lo que haría."
    )

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guarda los nombres limpios.")
        parser.add_argument("--fusionar", action="store_true", dest="unir", help="Con --aplicar, une los grupos sin conflicto.")
        parser.add_argument("--regenerar-slugs", action="store_true", dest="slugs", help="Con --aplicar, crea URLs nuevas desde el nombre limpio (las antiguas redirigen).")

    def handle(self, *args, aplicar, unir, slugs, **opciones):
        grupos = defaultdict(list)
        self.stdout.write(self.style.MIGRATE_HEADING("Nombres"))
        for p in Perfume.objects.filter(activo=True).order_by("id"):
            limpio, insp = proponer(p.nombre)
            if not limpio:
                self.stdout.write(f"  #{p.pk} {p.nombre}  (sin patrón, se deja igual)")
                continue
            self.stdout.write(f"  #{p.pk} {p.nombre}\n      → {limpio}" + (f"  · inspirado en: {insp}" if insp and not p.inspirado_en else ""))
            if limpio.startswith("Smart Collection No."):
                grupos[limpio].append(p)
            if aplicar:
                p.nombre = limpio
                if insp and not p.inspirado_en:
                    p.inspirado_en = insp[:200]
                p.save()

        self.stdout.write(self.style.MIGRATE_HEADING("Perfumes que se pueden unir como tamaños"))
        for nombre, perfumes in grupos.items():
            if len(perfumes) < 2:
                continue
            tamanos = [(v.formato, v.ml) for p in perfumes for v in p.presentaciones.all()]
            detalle = " + ".join(f"#{p.pk}" for p in perfumes)
            if len(tamanos) != len(set(tamanos)):
                self.stdout.write(self.style.WARNING(f"  {nombre}: {detalle} — mismo tamaño repetido, revisar a mano (¿son el mismo perfume?)"))
                continue
            self.stdout.write(f"  {nombre}: {detalle}")
            if aplicar and unir:
                principal, avisos = fusionar(perfumes)
                for a in avisos:
                    self.stdout.write(self.style.WARNING("    " + a))
                self.stdout.write(self.style.SUCCESS(f"    unidos en #{principal.pk}"))

        if aplicar and slugs:
            self.stdout.write(self.style.MIGRATE_HEADING("URLs"))
            for p in Perfume.objects.filter(activo=True).order_by("id"):
                nuevo = slug_unico(Perfume, p.nombre, p.pk, 220)
                if nuevo != p.slug:
                    SlugAntiguo.objects.update_or_create(slug=p.slug, defaults={"perfume": p})
                    Perfume.objects.filter(pk=p.pk).update(slug=nuevo)
                    self.stdout.write(f"  /perfume/{p.slug}/ → /perfume/{nuevo}/")

        if not aplicar:
            self.stdout.write(self.style.NOTICE("\nVista previa. Para guardar: --aplicar  (y opcionalmente --fusionar --regenerar-slugs)"))
