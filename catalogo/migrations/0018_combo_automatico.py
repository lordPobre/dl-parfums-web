from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0017_promocion_unidades'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocion',
            name='combo_cantidad',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name='Cantidad del combo',
                help_text='Combo automático: cuántos perfumes forman el combo (ej. 2). Si lo llenas, el precio '
                          'de la promoción se aplica solo en la selección y en el pedido cuando el cliente junta '
                          'esa cantidad de perfumes que califican.',
            ),
        ),
        migrations.AddField(
            model_name='promocion',
            name='combo_ml',
            field=models.CharField(
                max_length=40, blank=True, verbose_name='Tamaños que califican (ml)',
                help_text='Separados por coma, ej: 25,30. Vacío = cualquier tamaño.',
            ),
        ),
        migrations.AddField(
            model_name='promocion',
            name='combo_nombre',
            field=models.CharField(
                max_length=80, blank=True, verbose_name='Nombre empieza con',
                help_text='Ej: Smart Collection. Vacío = cualquier perfume.',
            ),
        ),
        migrations.AddField(
            model_name='promocion',
            name='combo_solo_incluidos',
            field=models.BooleanField(
                default=False, verbose_name='Solo los perfumes incluidos',
                help_text='Si lo marcas, solo califican los perfumes elegidos en «Perfumes».',
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='descuento',
            field=models.PositiveIntegerField(
                default=0, help_text='Descuento por combos automáticos (CLP). Ya está restado del total.',
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='detalle_descuento',
            field=models.CharField(max_length=255, blank=True, verbose_name='Detalle del descuento'),
        ),
    ]
