from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Activa en PostgreSQL las extensiones que usa la búsqueda:
    pg_trgm (tolerancia a errores de escritura) y unaccent (ignorar tildes).
    En SQLite no hace nada."""

    dependencies = [
        ("catalogo", "0012_presentaciones"),
    ]

    operations = [
        TrigramExtension(),
        UnaccentExtension(),
    ]
