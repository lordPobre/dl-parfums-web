"""Healthcheck de Railway (/salud/): 200 solo si la base responde y no faltan migraciones.
Si falla, Railway no activa el deploy nuevo y el anterior sigue atendiendo."""
import logging

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

log = logging.getLogger(__name__)


@never_cache
def salud(request):
    try:
        connection.ensure_connection()
        ejecutor = MigrationExecutor(connection)
        pendientes = ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
    except Exception:
        log.exception("Healthcheck: la base no responde")
        return JsonResponse({"ok": False, "motivo": "base"}, status=503)
    if pendientes:
        log.error("Healthcheck: faltan %s migraciones", len(pendientes))
        return JsonResponse({"ok": False, "motivo": "migraciones", "pendientes": len(pendientes)}, status=503)
    return JsonResponse({"ok": True})
