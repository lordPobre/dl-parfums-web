import re

import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify

# Separa "Bergamota, limón y pimienta rosa / cardamomo" en notas sueltas
SEPARADORES = re.compile(r"\s*(?:,|;|/|\+|\s[-–]\s|\s+y\s+|\s+e\s+|\s+&\s+)\s*", re.IGNORECASE)
CAMPOS = (("salida", "notas_salida"), ("corazon", "notas_corazon"), ("fondo", "notas_fondo"))


def _limpiar(texto):
    texto = re.sub(r"\s+", " ", (texto or "").strip(" .·-–—\t"))
    return texto[:1].upper() + texto[1:].lower() if texto else ""


def crear_notas(apps, schema_editor):
    """Convierte el texto de las 3 columnas de notas en registros Nota + PerfumeNota."""
    Perfume = apps.get_model("catalogo", "Perfume")
    Nota = apps.get_model("catalogo", "Nota")
    PerfumeNota = apps.get_model("catalogo", "PerfumeNota")
    por_slug = {}
    for perfume in Perfume.objects.all():
        for nivel, campo in CAMPOS:
            vistos = set()
            for orden, trozo in enumerate(SEPARADORES.split(getattr(perfume, campo) or "")):
                nombre = _limpiar(trozo)
                slug = slugify(nombre)[:100]
                if not slug or len(nombre) > 80 or slug in vistos:
                    continue
                vistos.add(slug)
                nota = por_slug.get(slug)
                if nota is None:
                    nota = Nota.objects.filter(slug=slug).first() or Nota.objects.create(nombre=nombre, slug=slug)
                    por_slug[slug] = nota
                PerfumeNota.objects.get_or_create(perfume=perfume, nota=nota, nivel=nivel, defaults={"orden": orden})


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo", "0013_extensiones_busqueda"),
    ]

    operations = [
        migrations.CreateModel(
            name="Nota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, help_text="Parte de la URL: /nota/<slug>/. Se genera solo si lo dejas vacío.", max_length=100, unique=True)),
                ("descripcion", models.TextField(blank=True, help_text="Introducción de /nota/<slug>/ (ideal 60–120 palabras): cómo huele, en qué perfumes destaca.")),
            ],
            options={"verbose_name": "Nota olfativa", "verbose_name_plural": "Notas olfativas", "ordering": ["nombre"]},
        ),
        migrations.CreateModel(
            name="PerfumeNota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nivel", models.CharField(choices=[("salida", "Salida"), ("corazon", "Corazón"), ("fondo", "Fondo")], default="corazon", max_length=8)),
                ("orden", models.PositiveSmallIntegerField(default=0)),
                ("nota", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="en_perfumes", to="catalogo.nota")),
                ("perfume", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notas_perfume", to="catalogo.perfume")),
            ],
            options={"verbose_name": "Nota del perfume", "verbose_name_plural": "Notas olfativas (pirámide)", "ordering": ["orden", "id"]},
        ),
        migrations.AddConstraint(
            model_name="perfumenota",
            constraint=models.UniqueConstraint(fields=("perfume", "nota", "nivel"), name="nota_unica_por_nivel"),
        ),
        migrations.AddIndex(
            model_name="perfumenota",
            index=models.Index(fields=["nota", "perfume"], name="catalogo_pn_nota_perfume_idx"),
        ),
        migrations.AddField(
            model_name="perfume",
            name="notas",
            field=models.ManyToManyField(blank=True, related_name="perfumes", through="catalogo.PerfumeNota", to="catalogo.nota"),
        ),
        migrations.RunPython(crear_notas, migrations.RunPython.noop),
    ]
