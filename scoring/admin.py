"""Admin das pontuações (E13): lista ordenada pela nota e o breakdown linha a linha."""

from django.contrib import admin

from scoring.display import breakdown_html, label_badge
from scoring.models import Score


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = (
        "entity_label",
        "total_label",
        "profile",
        "confidence",
        "gate_reason",
        "computed_at",
    )
    list_filter = ("label", "gated", "gate_kind", "profile", "scoring_version")
    search_fields = ("gate_reason",)
    readonly_fields = ("entity_label", "breakdown_view", "computed_at")
    fields = (
        "entity_label",
        "breakdown_view",
        ("profile", "scoring_version"),
        ("total", "label", "confidence", "raw_sum"),
        ("gated", "gate_kind", "gate_reason"),
        "alerts",
        "breakdown",
        "computed_at",
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("content_type").prefetch_related("entity")
        )

    def has_add_permission(self, request):
        return False  # só `rescore` cria: a nota é calculada, nunca digitada

    def get_readonly_fields(self, request, obj=None):
        # Tudo é calculado; o admin só mostra.
        return (*self.readonly_fields, *(f.name for f in Score._meta.fields if f.name != "id"))

    @admin.display(description="entidade")
    def entity_label(self, obj):
        return f"{obj.content_type.name}: {obj.entity}"

    @admin.display(description="pontos", ordering="total")
    def total_label(self, obj):
        return label_badge(obj.label, obj.total)

    @admin.display(description="por que essa nota")
    def breakdown_view(self, obj):
        return breakdown_html(obj)
