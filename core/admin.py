"""Admin do núcleo: a UI do MVP (ADR-001, ADR-010).

Regra de interface do ADR-004: fato observado, inferência e informação manual aparecem de forma
visualmente distinta — por cor, ícone **e** texto (a cor sozinha não basta).
"""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html

from core.models import (
    ContactPoint,
    Evidence,
    Match,
    Opportunity,
    Organization,
    ServiceOffering,
    Source,
    Suppression,
    Triage,
)
from core.services.suppression import is_suppressed

# tipo da evidência -> (rótulo, cor do texto e da borda, fundo, estilo da borda)
EVIDENCE_BADGES = {
    "observed": ("✅ observado", "#14532d", "#dcfce7", "solid"),
    "inferred": ("🔮 inferido", "#581c87", "#f3e8ff", "dashed"),
    "manual": ("✍️ manual", "#1e3a8a", "#dbeafe", "solid"),
}


def evidence_badge(kind):
    """Selo do tipo da evidência: fato = borda cheia e ✅; inferência = borda tracejada e 🔮."""
    if kind not in EVIDENCE_BADGES:
        return "—"
    label, color, background, border = EVIDENCE_BADGES[kind]
    return format_html(
        '<span class="evidence-badge evidence-{kind}" style="display:inline-block;'
        "padding:1px 8px;border-radius:10px;border:2px {border} {color};color:{color};"
        'background:{background};font-weight:600;white-space:nowrap">{label}</span>',
        kind=kind,
        border=border,
        color=color,
        background=background,
        label=label,
    )


class EvidenceInlineForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = (
            "field",
            "value",
            "kind",
            "method",
            "source_url",
            "excerpt",
            "confidence",
            "verified",
        )
        widgets = {
            "value": forms.Textarea(attrs={"rows": 2, "cols": 30}),
            "source_url": forms.URLInput(attrs={"size": 50}),
            "excerpt": forms.Textarea(attrs={"rows": 2, "cols": 80}),
        }
        # Cada item repetiria estes textos: no inline fica só a dica do valor (aspas no JSON);
        # as demais continuam na tela própria de Evidências.
        help_texts = {name: "" for name in ("field", "method", "excerpt", "confidence", "verified")}


class EvidenceInline(GenericStackedInline):
    """Evidências da entidade (organização ou oportunidade), com o selo de origem.

    Empilhado, não tabular: são 9 campos por evidência e uma tabela assim estoura a largura.
    """

    model = Evidence
    form = EvidenceInlineForm
    extra = 0
    fields = (
        ("kind_badge", "field", "kind"),
        ("value", "method"),
        ("source_url", "confidence", "verified"),
        "excerpt",
    )
    readonly_fields = ("kind_badge",)
    verbose_name_plural = "evidências (observado × inferido × manual)"

    @admin.display(description="origem")
    def kind_badge(self, obj):
        return evidence_badge(obj.kind)


class ContactPointInline(admin.StackedInline):
    """Contatos institucionais. Só aceita evidências já registradas sobre esta organização."""

    model = ContactPoint
    extra = 0
    fields = (
        ("kind", "value", "status"),
        ("label", "role_hint", "is_personal"),
        ("evidence", "opt_out"),
    )
    readonly_fields = ("opt_out",)

    @admin.display(description="opt-out")
    def opt_out(self, obj):
        if obj.pk and is_suppressed(obj):
            return format_html('<strong style="color:#b91c1c">{}</strong>', "🚫 suprimido")
        return ""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "evidence":
            organization_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = Evidence.objects.none()
            if organization_id:
                kwargs["queryset"] = Evidence.objects.filter(
                    content_type=ContentType.objects.get_for_model(Organization),
                    object_id=organization_id,
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        widget = getattr(formfield, "widget", None)
        if db_field.name == "evidence" and isinstance(widget, RelatedFieldWidgetWrapper):
            # A evidência nasce pelo fluxo que a rastreia (inline de Evidências), não por popup.
            widget.can_add_related = widget.can_change_related = False
            widget.can_delete_related = widget.can_view_related = False
            widget.widget.attrs["style"] = "max-width: 32em"
        return formfield


class EntityLabelMixin:
    """Mostra a entidade de uma `Evidence`/`Triage` (relação genérica), sem consulta por linha."""

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("content_type").prefetch_related("entity")
        )

    @admin.display(description="entidade")
    def entity_label(self, obj):
        return f"{obj.content_type.name}: {obj.entity}"


class SlugLockedMixin:
    """O `slug` é chave estável (importações, regras): depois de criado não se renomeia."""

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "slug") if obj else fields


@admin.register(Source)
class SourceAdmin(SlugLockedMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "kind", "enabled", "robots_ok", "reliability", "schedule")
    list_filter = ("kind", "enabled", "robots_ok", "schedule")
    search_fields = ("slug", "name", "base_url")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "network",
        "municipality_name",
        "uf",
        "relationship_status",
        "website_status",
    )
    list_filter = ("kind", "relationship_status", "uf", "network", "website_status", "size_hint")
    search_fields = ("name", "legal_name", "cnpj", "inep_code", "municipality_name", "website")
    autocomplete_fields = ("parent", "first_seen_source")
    # Derivados das interações (E03b): ninguém digita à mão.
    readonly_fields = (
        "relationship_status",
        "last_interaction_at",
        "next_action_at",
        "created_at",
        "updated_at",
    )
    inlines = (ContactPointInline, EvidenceInline)
    save_on_top = True
    fieldsets = (
        (
            "Identificação",
            {"fields": ("name", "legal_name", "kind", "segment", "size_hint", "cnae_main")},
        ),
        ("Identificadores externos", {"fields": ("cnpj", "inep_code", "osm_id")}),
        ("Localização", {"fields": (("municipality_name", "uf"), "address", ("lat", "lon"))}),
        ("Presença online", {"fields": ("website", "website_status")}),
        ("Rede e similaridade", {"fields": ("network", "parent", "similarity_tags")}),
        (
            "Relacionamento (calculado das interações)",
            {"fields": ("relationship_status", "last_interaction_at", "next_action_at")},
        ),
        (
            "Controle",
            {"fields": ("first_seen_source", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ContactPoint)
class ContactPointAdmin(admin.ModelAdmin):
    list_display = ("value", "kind", "organization", "status", "is_personal", "last_verified_at")
    list_filter = ("kind", "status", "is_personal")
    search_fields = ("value", "label", "organization__name")
    raw_id_fields = ("organization", "evidence")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "kind",
        "status",
        "deadline_at",
        "organizer_label",
        "modality",
        "location",
    )
    list_filter = (
        "kind",
        "status",
        "modality",
        "scope",
        "requires_legal_entity",
        "effort_estimate",
    )
    search_fields = ("title", "organizer_name", "description", "canonical_key")
    date_hierarchy = "deadline_at"
    autocomplete_fields = ("organizer",)
    readonly_fields = ("first_seen_at", "last_seen_at")
    inlines = (EvidenceInline,)
    save_on_top = True
    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "title",
                    "kind",
                    "status",
                    "organizer",
                    "organizer_name",
                    "official_url",
                    "canonical_key",
                )
            },
        ),
        (
            "Descrição e local",
            {
                "fields": (
                    "description",
                    "categories",
                    "modality",
                    "scope",
                    ("municipality_name", "uf"),
                )
            },
        ),
        ("Datas", {"fields": (("opens_at", "deadline_at"), ("starts_at", "ends_at"))}),
        (
            "Elegibilidade (requisitos da empresa)",
            {
                "fields": (
                    "eligibility_text",
                    "requires_legal_entity",
                    "eligible_legal_forms",
                    "exclusive_small_business",
                    "min_company_age_months",
                    "required_cnaes",
                    "eligible_regions",
                )
            },
        ),
        (
            "Valor, benefícios e esforço",
            {
                "fields": (
                    "requirements_text",
                    "prize_text",
                    "prize_amount_brl",
                    "benefits",
                    "participation_cost_text",
                    "effort_estimate",
                )
            },
        ),
        (
            "Controle",
            {
                "fields": ("extraction_version", "first_seen_at", "last_seen_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # A chave de dedupe é a identidade da oportunidade: depois de criada não se edita.
        return (*fields, "canonical_key") if obj else fields

    @admin.display(description="organizador")
    def organizer_label(self, obj):
        return obj.organizer or obj.organizer_name or "—"

    @admin.display(description="local")
    def location(self, obj):
        return "/".join(part for part in (obj.municipality_name, obj.uf) if part) or "—"


@admin.register(Evidence)
class EvidenceAdmin(EntityLabelMixin, admin.ModelAdmin):
    list_display = (
        "field",
        "kind_badge",
        "entity_label",
        "method",
        "verified",
        "confidence",
        "retrieved_at",
    )
    list_filter = ("kind", "verified", "content_type")
    search_fields = ("field", "source_url", "source_name", "excerpt", "method")
    date_hierarchy = "retrieved_at"
    readonly_fields = ("kind_badge",)
    fieldsets = (
        ("Entidade", {"fields": ("content_type", "object_id")}),
        (
            "Afirmação",
            {"fields": ("field", "value", "kind_badge", "kind", "confidence", "verified")},
        ),
        ("Origem", {"fields": ("source_url", "source_name", "retrieved_at", "excerpt", "method")}),
    )

    @admin.display(description="origem", ordering="kind")
    def kind_badge(self, obj):
        return evidence_badge(obj.kind)


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(SlugLockedMixin, admin.ModelAdmin):
    """Catálogo de serviços como dado. `mei_coverage` e `active` editam direto na lista."""

    list_display = ("name", "slug", "category", "mei_coverage", "active", "geo_profile")
    list_editable = ("mei_coverage", "active")
    list_filter = ("category", "mei_coverage", "geo_profile", "active")
    search_fields = ("name", "slug", "description")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("organization", "service", "strength", "method", "created_at")
    list_filter = ("method", "service")
    search_fields = ("organization__name", "service__name")
    autocomplete_fields = ("organization", "service")


@admin.register(Triage)
class TriageAdmin(EntityLabelMixin, admin.ModelAdmin):
    list_display = ("entity_label", "status", "discard_reason", "decided_by", "decided_at")
    list_filter = ("status", "discard_reason", "content_type")
    raw_id_fields = ("decided_by",)


@admin.register(Suppression)
class SuppressionAdmin(admin.ModelAdmin):
    list_display = ("value", "kind", "reason", "created_at")
    list_filter = ("kind",)
    search_fields = ("value", "reason")
