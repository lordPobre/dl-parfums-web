from django.db import migrations, models
from django.utils.text import slugify


def poblar_slugs(apps, schema_editor):
    for nombre_modelo, largo in (("Marca", 120), ("FamiliaOlfativa", 120), ("Perfume", 220)):
        Modelo = apps.get_model("catalogo", nombre_modelo)
        usados = set()
        for obj in Modelo.objects.all().order_by("id"):
            base = (slugify(obj.nombre) or "item")[: largo - 4]
            slug, n = base, 2
            while slug in usados:
                slug = f"{base}-{n}"
                n += 1
            usados.add(slug)
            Modelo.objects.filter(pk=obj.pk).update(slug=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo", "0010_perfume_actualizado_marca_protect"),
    ]

    operations = [
        # 1) Campos nuevos, todavía sin restricción de unicidad
        migrations.AddField("marca", "slug", models.SlugField(max_length=120, blank=True, default="", db_index=False), preserve_default=False),
        migrations.AddField("familiaolfativa", "slug", models.SlugField(max_length=120, blank=True, default="", db_index=False), preserve_default=False),
        migrations.AddField("perfume", "slug", models.SlugField(max_length=220, blank=True, default="", db_index=False), preserve_default=False),
        migrations.AddField("perfume", "inspirado_en", models.CharField(max_length=200, blank=True, default="", help_text="Perfume original de referencia, ej: 'Sauvage de Dior'. Se muestra bajo el nombre y se usa en la búsqueda."), preserve_default=False),
        migrations.AddField("perfume", "meta_titulo", models.CharField(max_length=70, blank=True, default="", help_text="Opcional. Título para Google (máx. 60–70 caracteres). Si lo dejas vacío se genera solo."), preserve_default=False),
        migrations.AddField("perfume", "meta_descripcion", models.CharField(max_length=160, blank=True, default="", help_text="Opcional. Descripción para Google (140–155 caracteres). Si la dejas vacía se genera sola."), preserve_default=False),

        # 2) Genera los slugs de lo que ya existe
        migrations.RunPython(poblar_slugs, migrations.RunPython.noop),

        # 3) Ahora sí: únicos
        migrations.AlterField("marca", "slug", models.SlugField(max_length=120, unique=True, blank=True, help_text="Parte de la URL: /casa/<slug>/. Se genera solo si lo dejas vacío.")),
        migrations.AlterField("familiaolfativa", "slug", models.SlugField(max_length=120, unique=True, blank=True, help_text="Parte de la URL: /familia/<slug>/. Se genera solo si lo dejas vacío.")),
        migrations.AlterField("perfume", "slug", models.SlugField(max_length=220, unique=True, blank=True, help_text="Parte de la URL: /perfume/<slug>/. Se genera solo si lo dejas vacío. Cambiarlo rompe enlaces existentes.")),
        migrations.AlterField("familiaolfativa", "descripcion", models.TextField(blank=True, help_text="Se muestra como introducción en /familia/<slug>/ (ideal 80–150 palabras).")),
        migrations.AlterField("marca", "descripcion", models.TextField(blank=True, verbose_name="Historia de la marca", help_text="Se muestra como introducción en /casa/<slug>/.")),
    ]
