"""Admin da coleta: execuções e documentos brutos, somente leitura (são registro, não cadastro)."""

from django.contrib import admin

from collection.models import CollectionRun, RawDocument


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CollectionRun)
class CollectionRunAdmin(ReadOnlyAdmin):
    list_display = (
        "source",
        "started_at",
        "status",
        "dry_run",
        "items_seen",
        "items_new",
        "items_updated",
        "items_failed",
    )
    list_filter = ("status", "dry_run", "source")
    date_hierarchy = "started_at"


@admin.register(RawDocument)
class RawDocumentAdmin(ReadOnlyAdmin):
    list_display = ("url", "source", "status_code", "size_bytes", "fetched_at", "expires_at")
    list_filter = ("source", "status_code")
    search_fields = ("url",)
    exclude = ("text_gz",)
