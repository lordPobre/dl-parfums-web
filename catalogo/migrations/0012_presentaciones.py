import re

import django.db.models.deletion
from django.db import migrations, models

RE_ML = re.compile(r"(\d+)\s*ML", re.I)
RE_DUPE = re.compile(r"Dupe\s+(.+?)\s*\d+\s*ML", re.I)
RE_EDP = re.compile(r"NO\.?\s*\d+\s*[–-]\s*(.+?)\s+EDP", re.I)


def _titulo(texto):
    return texto.title() if texto.isupper() else texto


def crear_presentaciones(apps, schema_editor):
    """Cada perfume actual pasa a tener UNA presentación con su precio y stock de hoy.
    El tamaño se lee del nombre ("25 ML", "100ML"). No se une ni se borra nada."""
    Perfume = apps.get_model("catalogo", "Perfume")
    Presentacion = apps.get_model("catalogo", "Presentacion")
    ItemPedido = apps.get_model("catalogo", "ItemPedido")

    for p in Perfume.objects.all().order_by("id"):
        m = RE_ML.search(p.nombre or "")
        ml = int(m.group(1)) if m else 100
        formato = "decant" if ml <= 10 else "frasco"
        precio = int(p.precio or 0)
        oferta = int(p.precio_oferta) if (p.es_oferta and p.precio_oferta and int(p.precio_oferta) < precio) else None
        Presentacion.objects.create(
            perfume=p, formato=formato, ml=ml,
            sku=f"IO-{p.pk}-{ml}{formato[0].upper()}",
            precio=precio, precio_oferta=oferta, stock=p.stock, activo=True,
        )
        cambios = {"n_presentaciones": 1}
        if re.search(r"\bEDP\b", p.nombre or "", re.I):
            cambios["concentracion"] = "edp"
        if not p.inspirado_en:
            mm = RE_DUPE.search(p.nombre or "") or RE_EDP.search(p.nombre or "")
            if mm:
                cambios["inspirado_en"] = _titulo(mm.group(1).strip())[:200]
        Perfume.objects.filter(pk=p.pk).update(**cambios)

    # Pedidos existentes: cada producto apunta a la presentación de su perfume
    for item in ItemPedido.objects.filter(perfume__isnull=False):
        v = Presentacion.objects.filter(perfume_id=item.perfume_id).first()
        if v:
            ItemPedido.objects.filter(pk=item.pk).update(presentacion=v)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo", "0011_slugs_inspirado_en_meta"),
    ]

    operations = [
        migrations.AddField(
            model_name="perfume",
            name="concentracion",
            field=models.CharField(blank=True, max_length=10, choices=[("", "—"), ("edt", "Eau de Toilette"), ("edp", "Eau de Parfum"), ("parfum", "Parfum"), ("extrait", "Extrait de Parfum")]),
        ),
        migrations.AddField(
            model_name="perfume",
            name="fusionado_en",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fusionados", to="catalogo.perfume", help_text="Si este perfume se unió a otro como presentación, su URL redirige allí."),
        ),
        migrations.AddField(
            model_name="perfume",
            name="n_presentaciones",
            field=models.PositiveSmallIntegerField(default=1, editable=False),
        ),
        migrations.CreateModel(
            name="Presentacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("formato", models.CharField(choices=[("decant", "Decant"), ("frasco", "Frasco")], default="frasco", max_length=10)),
                ("ml", models.PositiveSmallIntegerField(help_text="Contenido en ml (5, 10, 30, 50...).")),
                ("sku", models.CharField(blank=True, help_text="Se genera solo si lo dejas vacío.", max_length=40, unique=True)),
                ("precio", models.PositiveIntegerField(help_text="Precio en CLP.")),
                ("precio_oferta", models.PositiveIntegerField(blank=True, null=True, help_text="Opcional. Debe ser menor que el precio.")),
                ("stock", models.PositiveIntegerField(default=0)),
                ("activo", models.BooleanField(default=True)),
                ("orden", models.PositiveSmallIntegerField(default=0)),
                ("perfume", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="presentaciones", to="catalogo.perfume")),
            ],
            options={
                "verbose_name": "Presentación",
                "verbose_name_plural": "Presentaciones",
                "ordering": ["orden", "ml"],
                "constraints": [
                    models.UniqueConstraint(fields=("perfume", "formato", "ml"), name="presentacion_unica"),
                    models.CheckConstraint(
                        condition=models.Q(precio_oferta__isnull=True) | models.Q(precio_oferta__lt=models.F("precio")),
                        name="oferta_menor_que_precio",
                    ),
                ],
                "indexes": [models.Index(fields=["perfume", "activo"], name="catalogo_pr_perfume_activo_idx")],
            },
        ),
        migrations.CreateModel(
            name="SlugAntiguo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("perfume", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="slugs_antiguos", to="catalogo.perfume")),
            ],
        ),
        migrations.AddField(
            model_name="itempedido",
            name="presentacion",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ventas", to="catalogo.presentacion"),
        ),
        migrations.RunPython(crear_presentaciones, migrations.RunPython.noop),
    ]
