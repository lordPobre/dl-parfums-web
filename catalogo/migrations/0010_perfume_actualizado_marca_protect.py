import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0009_pedido_itempedido'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfume',
            name='actualizado',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='perfume',
            name='marca',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='productos', to='catalogo.marca'),
        ),
    ]
