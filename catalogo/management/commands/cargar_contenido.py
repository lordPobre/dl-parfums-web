import json
from pathlib import Path

from django.core.management.base import BaseCommand

from catalogo.models import FamiliaOlfativa, Perfume

ARCHIVO_POR_DEFECTO = Path(__file__).resolve().parents[2] / "data" / "contenido_top20.json"
CAMPOS = ("descripcion", "inspirado_en", "meta_descripcion", "notas_salida", "notas_corazon", "notas_fondo")


class Command(BaseCommand):
    help = (
        "Carga descripciones, 'inspirado en', familia, notas y meta descripción desde un JSON. "
        "Sin --aplicar solo muestra lo que cambiaría."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", nargs="?", default=str(ARCHIVO_POR_DEFECTO))
        parser.add_argument("--aplicar", action="store_true", help="Guarda los cambios en la base de datos.")

    def handle(self, *args, archivo, aplicar, **opciones):
        datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
        total = 0
        for d in datos:
            p = Perfume.objects.filter(pk=d["pk"]).select_related("fusionado_en").first()
            if not p:
                self.stdout.write(self.style.WARNING(f"#{d['pk']}: no existe, se omite."))
                continue
            if not p.activo and p.fusionado_en:
                p = p.fusionado_en

            cambios = {c: d[c] for c in CAMPOS if d.get(c) and getattr(p, c) != d[c]}
            if d.get("familia"):
                fam = FamiliaOlfativa.objects.filter(nombre__iexact=d["familia"]).first()
                if not fam:
                    self.stdout.write(self.style.WARNING(f"#{p.pk}: la familia «{d['familia']}» no existe en el admin."))
                elif p.familia_id != fam.id:
                    cambios["familia"] = fam

            resumen = ", ".join(cambios) or "sin cambios"
            self.stdout.write(f"#{p.pk} {p.nombre}: {resumen}")
            if aplicar and cambios:
                for campo, valor in cambios.items():
                    setattr(p, campo, valor)
                p.save()
                total += 1

        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"{total} perfume(s) actualizados."))
        else:
            self.stdout.write(self.style.NOTICE("Vista previa. Ejecuta de nuevo con --aplicar para guardar."))
