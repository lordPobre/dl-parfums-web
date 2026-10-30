from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo", "0019_pedido_datos_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="clave",
            field=models.UUIDField(
                blank=True, editable=False, null=True, unique=True,
                help_text="Identificador del envío desde el carrito: evita pedidos duplicados.",
            ),
        ),
    ]
