from django.apps import AppConfig
from django.conf import settings
from django.db import connections
from django.db.models.signals import pre_migrate


def ensure_schema(sender, using="default", **kwargs):
    """Cria o schema dedicado (ADR-016) antes de qualquer migration.

    Roda também na criação do banco de testes. Idempotente.
    """
    schema = getattr(settings, "DB_SCHEMA", "")
    connection = connections[using]
    if not schema or connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {connection.ops.quote_name(schema)}")


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        pre_migrate.connect(ensure_schema, dispatch_uid="core.ensure_schema")
        from core import signals  # noqa: F401  (registra os receivers)
