from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0015_promocion_tema'),
    ]

    operations = [
        migrations.CreateModel(
            name='LimiteSolicitud',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(max_length=40)),
                ('creado', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'límite de solicitudes',
                'verbose_name_plural': 'límites de solicitudes',
                'indexes': [models.Index(fields=['clave', 'creado'], name='limite_clave_creado_idx')],
            },
        ),
    ]
