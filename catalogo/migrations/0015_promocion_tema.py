from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0014_notas'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocion',
            name='tema',
            field=models.CharField(
                choices=[
                    ('especial', 'Oferta especial'),
                    ('navidad', 'Navidad'),
                    ('valentin', 'San Valentín'),
                    ('madre', 'Día de la Madre'),
                    ('padre', 'Día del Padre'),
                    ('patrias', 'Fiestas Patrias'),
                    ('black', 'Black Friday'),
                ],
                default='especial',
                help_text='Estilo de la tarjeta en el home (colores, adorno y etiqueta).',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='promocion',
            name='precio_normal',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Opcional. Precio sin la promoción; muestra el precio tachado, el % y el ahorro.',
            ),
        ),
        migrations.AddField(
            model_name='promocion',
            name='fecha_inicio',
            field=models.DateField(blank=True, null=True, help_text='Opcional. Desde este día aparece en el home.'),
        ),
        migrations.AddField(
            model_name='promocion',
            name='fecha_fin',
            field=models.DateField(blank=True, null=True, help_text='Opcional. Último día visible; la tarjeta muestra «Hasta el …».'),
        ),
    ]
