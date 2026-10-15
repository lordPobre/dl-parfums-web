from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0016_limitesolicitud'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocion',
            name='unidades',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Unidades disponibles. Si no hay fecha de término, es obligatorio: la tarjeta muestra «Hasta agotar N unidades».',
            ),
        ),
    ]
