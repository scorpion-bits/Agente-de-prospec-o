"""Admin do núcleo: a UI do MVP (ADR-001, ADR-010).

Regra de interface do ADR-004: fato observado, inferência e informação manual aparecem de forma
visualmente distinta — por cor, ícone **e** texto (a cor sozinha não basta).
"""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from core.models import (
    CompanyProfile,
    ContactPoint,
    Evidence,
    FollowUp,
    Interaction,
    Match,
    Municipality,
    Opportunity,
    Organization,
    PortfolioItem,
    ServiceOffering,
    Source,
    Suppression,
    Triage,
)
from core.services.similarity import SIMILARITY_TAGS
from core.services.suppression import is_suppressed
from core.services.triage import triage_entities
from scoring.display import annotate_scores, breakdown_html, label_badge
from scoring.models import Score

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


class InteractionInline(admin.StackedInline):
    """Memória comercial na própria organização: a interação mais recente aparece primeiro."""

    model = Interaction
    extra = 0
    fields = (
        ("occurred_at", "kind", "channel", "outcome"),
        ("service", "contact_name_role", "data_status"),
        "summary",
        ("next_action", "next_action_at"),
        "attachments_url",
    )
    autocomplete_fields = ("service",)
    ordering = Interaction._meta.ordering
    show_change_link = True


class EntityLabelMixin:
    """Mostra a entidade de uma `Evidence`/`Triage` (relação genérica), sem consulta por linha."""

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("content_type").prefetch_related("entity")
        )

    @admin.display(description="entidade")
    def entity_label(self, obj):
        return f"{obj.content_type.name}: {obj.entity}"


class DiscardForm(forms.Form):
    reason = forms.ChoiceField(label="Motivo", choices=Triage.DiscardReason.choices)
    note = forms.CharField(
        label="Nota (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class TriageStatusFilter(admin.SimpleListFilter):
    """Triagem da lista: «não triadas» = sem decisão ou ainda `Nova` (E14)."""

    title = "triagem"
    parameter_name = "triage"

    def lookups(self, request, model_admin):
        return [("untriaged", "Não triadas"), *Triage.Status.choices[1:]]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "untriaged":
            return queryset.filter(Q(_triage_status__isnull=True) | Q(_triage_status="new"))
        if value:
            return queryset.filter(_triage_status=value)
        return queryset


class TriageActionsMixin:
    """Ações em massa de triagem + coluna da situação. O modelo precisa de `triage_items`."""

    def annotate_triage(self, queryset):
        triage = Triage.objects.filter(
            content_type=ContentType.objects.get_for_model(queryset.model),
            object_id=OuterRef("pk"),
        )
        return queryset.annotate(_triage_status=Subquery(triage.values("status")[:1]))

    @admin.display(description="triagem", ordering="_triage_status")
    def triage(self, obj):
        status = getattr(obj, "_triage_status", None) or Triage.Status.NEW
        return Triage.Status(status).label

    def _apply(self, request, queryset, status, **extra):
        count = triage_entities(queryset, status, request.user, **extra)
        self.message_user(request, f"{count} item(ns) → {Triage.Status(status).label}.")

    @admin.action(description="Triagem: marcar como interessante")
    def mark_interesting(self, request, queryset):
        self._apply(request, queryset, Triage.Status.INTERESTING)

    @admin.action(description="Triagem: marcar como em andamento")
    def mark_acting(self, request, queryset):
        self._apply(request, queryset, Triage.Status.ACTING)

    @admin.action(description="Triagem: marcar como concluído")
    def mark_done(self, request, queryset):
        self._apply(request, queryset, Triage.Status.DONE)

    @admin.action(description="Triagem: voltar para não triado")
    def mark_new(self, request, queryset):
        self._apply(request, queryset, Triage.Status.NEW)

    @admin.action(description="Triagem: descartar (pede o motivo)")
    def discard(self, request, queryset):
        if request.POST.get("apply"):
            form = DiscardForm(request.POST)
            if form.is_valid():
                self._apply(
                    request,
                    queryset,
                    Triage.Status.DISCARDED,
                    reason=form.cleaned_data["reason"],
                    note=form.cleaned_data["note"],
                )
                return None
        else:
            form = DiscardForm()
        return TemplateResponse(
            request,
            "admin/core/discard_reason.html",
            {
                **self.admin_site.each_context(request),
                "title": "Descartar",
                "form": form,
                "count": queryset.count(),
                "selected": list(queryset.values_list("pk", flat=True)),
                "back": request.get_full_path(),
            },
        )


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


class SimilarityFilter(admin.SimpleListFilter):
    """Filtro «parecida com o SESC»: qualquer tag de similaridade, ou uma tag específica (E17b)."""

    title = "parecida com o SESC"
    parameter_name = "similar"

    def lookups(self, request, model_admin):
        return [("any", "Qualquer parecida"), *SIMILARITY_TAGS.items()]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "any":
            return queryset.filter(similarity_tags__len__gt=0)
        if value in SIMILARITY_TAGS:
            return queryset.filter(similarity_tags__contains=[value])
        return queryset


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "network",
        "municipality_name",
        "uf",
        "relationship_status",
        "last_interaction_at",
        "next_action_at",
        "website_status",
        "score",
    )
    list_filter = (
        "kind",
        SimilarityFilter,
        "relationship_status",
        "uf",
        "network",
        "website_status",
        "size_hint",
    )
    search_fields = ("name", "legal_name", "cnpj", "inep_code", "municipality_name", "website")
    autocomplete_fields = ("parent", "first_seen_source", "municipality")
    # Derivados das interações (E03b): ninguém digita à mão.
    readonly_fields = (
        "relationship_status",
        "last_interaction_at",
        "next_action_at",
        "created_at",
        "updated_at",
        "score_breakdown",
    )
    inlines = (InteractionInline, ContactPointInline, EvidenceInline)
    save_on_top = True
    fieldsets = (
        (
            "Identificação",
            {"fields": ("name", "legal_name", "kind", "segment", "size_hint", "cnae_main")},
        ),
        ("Identificadores externos", {"fields": ("cnpj", "inep_code", "osm_id")}),
        (
            "Localização",
            {"fields": (("municipality_name", "uf"), "municipality", "address", ("lat", "lon"))},
        ),
        ("Presença online", {"fields": ("website", "website_status")}),
        ("Rede e similaridade", {"fields": ("network", "parent", "similarity_tags")}),
        (
            "Relacionamento (calculado das interações)",
            {"fields": ("relationship_status", "last_interaction_at", "next_action_at")},
        ),
        ("Pontuação como lead (E21)", {"fields": ("score_breakdown",)}),
        (
            "Controle",
            {"fields": ("first_seen_source", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return annotate_scores(super().get_queryset(request), Organization)

    @admin.display(description="pontuação", ordering="_score_total")
    def score(self, obj):
        return label_badge(getattr(obj, "_score_label", None), getattr(obj, "_score_total", None))

    @admin.display(description="por que essa nota")
    def score_breakdown(self, obj):
        score = (
            Score.objects.filter(
                content_type=ContentType.objects.get_for_model(Organization), object_id=obj.pk
            ).first()
            if obj.pk
            else None
        )
        return breakdown_html(score)


@admin.register(ContactPoint)
class ContactPointAdmin(admin.ModelAdmin):
    list_display = ("value", "kind", "organization", "status", "is_personal", "last_verified_at")
    list_filter = ("kind", "status", "is_personal")
    search_fields = ("value", "label", "organization__name")
    raw_id_fields = ("organization", "evidence")


@admin.register(Opportunity)
class OpportunityAdmin(TriageActionsMixin, admin.ModelAdmin):
    actions = ("mark_interesting", "mark_acting", "mark_done", "discard", "mark_new")
    list_display = (
        "title",
        "kind",
        "status",
        "deadline_at",
        "organizer_label",
        "modality",
        "location",
        "score",
        "triage",
    )
    list_filter = (
        TriageStatusFilter,
        "kind",
        "status",
        "modality",
        "scope",
        "requires_legal_entity",
        "effort_estimate",
    )
    search_fields = ("title", "organizer_name", "description", "canonical_key")
    date_hierarchy = "deadline_at"
    autocomplete_fields = ("organizer", "municipality")
    readonly_fields = ("first_seen_at", "last_seen_at", "score_breakdown")
    inlines = (EvidenceInline,)
    save_on_top = True
    fieldsets = (
        (
            "Pontuação (E13)",
            {"fields": ("score_breakdown",)},
        ),
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
                    "municipality",
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

    def get_queryset(self, request):
        return self.annotate_triage(annotate_scores(super().get_queryset(request), Opportunity))

    @admin.display(description="pontuação", ordering="_score_total")
    def score(self, obj):
        return label_badge(getattr(obj, "_score_label", None), getattr(obj, "_score_total", None))

    @admin.display(description="por que essa nota")
    def score_breakdown(self, obj):
        return breakdown_html(
            Score.objects.filter(
                content_type=ContentType.objects.get_for_model(Opportunity), object_id=obj.pk
            ).first()
            if obj.pk
            else None
        )

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


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    """Histórico comercial completo: "já falamos com eles?"."""

    list_display = (
        "organization",
        "kind",
        "occurred_at",
        "outcome",
        "next_action",
        "next_action_at",
        "data_status",
    )
    list_filter = (
        "kind",
        "outcome",
        "data_status",
        "channel",
        "organization__relationship_status",
        "organization__network",
    )
    search_fields = ("organization__name", "summary", "next_action")
    autocomplete_fields = ("organization", "service")
    raw_id_fields = ("contact_point",)
    date_hierarchy = "occurred_at"
    readonly_fields = ("created_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    """Próximas ações: o que fazer em seguida, a mais urgente primeiro. Somente leitura."""

    list_display = ("name", "next_action_at", "due", "next_action", "relationship_status")
    list_filter = ("relationship_status", "network")
    search_fields = ("name", "network")
    ordering = ("next_action_at", "name")
    list_display_links = ("name",)

    def get_queryset(self, request):
        latest = Interaction.objects.filter(organization=OuterRef("pk")).values("next_action")[:1]
        return (
            super()
            .get_queryset(request)
            .filter(next_action_at__isnull=False)
            .annotate(_next_action=Subquery(latest))
        )

    @admin.display(description="próxima ação", ordering="_next_action")
    def next_action(self, obj):
        return obj._next_action

    @admin.display(description="prazo")
    def due(self, obj):
        today = timezone.localdate()
        if obj.next_action_at < today:
            return format_html('<strong style="color:#b91c1c">{}</strong>', "⏰ vencida")
        if obj.next_action_at == today:
            return format_html('<strong style="color:#b45309">{}</strong>', "📌 hoje")
        return "a vencer"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PortfolioItem)
class PortfolioItemAdmin(SlugLockedMixin, admin.ModelAdmin):
    list_display = ("title", "kind", "year", "public", "status", "public_url")
    list_filter = ("kind", "public", "status", "services")
    search_fields = ("title", "slug", "description")
    filter_horizontal = ("services",)


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    """Perfil da empresa: linha única (MEI, abertura, CNAEs). CNPJ só aqui/.env, nunca no git."""

    save_on_top = True

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        profile = CompanyProfile.get()
        if profile is not None:
            return HttpResponseRedirect(
                reverse("admin:core_companyprofile_change", args=[profile.pk])
            )
        return super().changelist_view(request, extra_context)


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    """Dado de referência do IBGE: consulta e busca (a carga é `load_municipalities`)."""

    list_display = ("name", "uf", "region", "ibge_code", "is_capital")
    list_filter = ("uf", "region", "is_capital")
    search_fields = ("name", "ibge_code")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("organization", "service", "strength", "method", "created_at")
    list_filter = ("method", "service")
    search_fields = ("organization__name", "service__name")
    autocomplete_fields = ("organization", "service")
    filter_horizontal = ("portfolio_refs",)


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
