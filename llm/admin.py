"""Admin das chamadas de IA: somente leitura (é registro, não cadastro)."""

from django.contrib import admin

from llm.models import LLMCall


@admin.register(LLMCall)
class LLMCallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "task", "strategy", "status", "cost_usd", "input_tokens")
    list_filter = ("status", "billing", "data_class", "task")
    date_hierarchy = "created_at"
    exclude = ("response_text",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
