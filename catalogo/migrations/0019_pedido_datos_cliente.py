from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0018_combo_automatico'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedido',
            name='cliente',
            field=models.CharField(max_length=120, blank=True, verbose_name='Nombre'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='apellido',
            field=models.CharField(max_length=60, blank=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='rut',
            field=models.CharField(max_length=14, blank=True, verbose_name='RUT'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='email',
            field=models.EmailField(max_length=120, blank=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='region',
            field=models.CharField(max_length=60, blank=True, verbose_name='Región'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='comuna',
            field=models.CharField(max_length=60, blank=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='direccion',
            field=models.CharField(max_length=160, blank=True, verbose_name='Dirección'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='notas',
            field=models.TextField(blank=True, help_text='Indicaciones del cliente para el envío.'),
        ),
    ]
