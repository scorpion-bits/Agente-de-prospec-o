"""O admin é a UI do MVP: estes testes percorrem os fluxos reais (login, formulários, inlines)."""

import re

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.urls import reverse

from core.models import (
    ContactPoint,
    FollowUp,
    Interaction,
    Municipality,
    Opportunity,
    Organization,
    ServiceOffering,
    Source,
    Suppression,
    Triage,
)
from core.services.evidence import record_evidence
from tests.conftest import VALID_CNPJ, mask_cnpj

pytestmark = pytest.mark.django_db

CORE_MODELS = sorted(apps.get_app_config("core").get_models(), key=lambda m: m._meta.model_name)


def url(model, action, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}", args=args)


def html_of(response):
    return response.content.decode()


def errors_of(response):
    """Erros do formulário e dos inlines, para mensagens de falha legíveis."""
    errors = {"form": dict(response.context["adminform"].form.errors)}
    for inline in response.context["inline_admin_formsets"]:
        errors[inline.formset.prefix] = [f.errors for f in inline.formset.forms]
    return errors


def management_forms(response, **initial_forms):
    """Campos de controle de todos os inlines da página (sem linhas), prontos para o POST."""
    data = {}
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        data.update(
            {
                f"{prefix}-TOTAL_FORMS": "0",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
            }
        )
    return data


def inline_prefix(response, model):
    return next(
        i.formset.prefix
        for i in response.context["inline_admin_formsets"]
        if i.formset.model is model
    )


ORGANIZATION_FORM = {
    "name": "Escola Admin",
    "kind": "school",
    "size_hint": "unknown",
    "website_status": "unknown",
}


class TestEveryModelIsManageable:
    @pytest.mark.parametrize("model", CORE_MODELS, ids=lambda m: m._meta.model_name)
    def test_changelist_and_add_form_render(self, admin_client, model):
        assert admin_client.get(url(model, "changelist")).status_code == 200
        # "Próximas ações" é uma visão somente leitura: não tem formulário de criação.
        expected_add = 403 if model in (FollowUp, Municipality) else 200
        assert admin_client.get(url(model, "add")).status_code == expected_add

    def test_anonymous_users_are_sent_to_login(self, client):
        response = client.get(url(Opportunity, "changelist"))
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]


class TestOpportunityWithEvidence:
    """Critério da E03: cadastrar oportunidade com 2 evidências (observed e inferred) exibidas
    de forma distinta."""

    def test_register_an_opportunity_with_observed_and_inferred_evidence(self, admin_client):
        add_url = url(Opportunity, "add")
        page = admin_client.get(add_url)
        prefix = inline_prefix(page, apps.get_model("core", "Evidence"))
        data = {
            "title": "Hackathon Exemplo",
            "kind": "hackathon",
            "status": "open",
            "modality": "online",
            "requires_legal_entity": "unknown",
            "effort_estimate": "unknown",
            "official_url": "https://example.org/hackathon",
            "categories": ["games", "education"],
            "benefits": ["prize"],
            "eligible_legal_forms": ["MEI", "ME"],
            "required_cnaes": "62.01-5, 85.99-6/03",
            f"{prefix}-TOTAL_FORMS": "2",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            # 1ª: fato lido na fonte
            f"{prefix}-0-field": "deadline_at",
            f"{prefix}-0-value": '"2026-11-15"',
            f"{prefix}-0-kind": "observed",
            f"{prefix}-0-method": "connector:devpost",
            f"{prefix}-0-source_url": "https://example.org/hackathon",
            f"{prefix}-0-excerpt": "Inscrições até 15/11/2026",
            # 2ª: dedução por regra
            f"{prefix}-1-field": "remote_friendly",
            f"{prefix}-1-value": "true",
            f"{prefix}-1-kind": "inferred",
            f"{prefix}-1-method": "rule:modality_online",
            f"{prefix}-1-confidence": "0.6",
        }
        response = admin_client.post(add_url, data)
        assert response.status_code == 302, errors_of(response)

        opportunity = Opportunity.objects.get(title="Hackathon Exemplo")
        assert opportunity.canonical_key == "url:example.org/hackathon"  # gerada: campo em branco
        assert opportunity.categories == ["games", "education"]
        assert opportunity.eligible_legal_forms == ["MEI", "ME"]
        assert opportunity.required_cnaes == ["62.01-5", "85.99-6/03"]
        stored = {e.field: (e.kind, e.value) for e in opportunity.evidence_items.all()}
        assert stored == {
            "deadline_at": ("observed", "2026-11-15"),
            "remote_friendly": ("inferred", True),
        }

        html = html_of(admin_client.get(url(Opportunity, "change", opportunity.pk)))
        badges = dict(re.findall(r'class="evidence-badge evidence-(\w+)" style="([^"]*)"', html))
        assert set(badges) == {"observed", "inferred"}
        assert "✅ observado" in html
        assert "🔮 inferido" in html
        # distintos em mais de uma dimensão (a cor sozinha não basta)
        assert "dashed" in badges["inferred"] and "solid" in badges["observed"]
        assert badges["inferred"] != badges["observed"]

    def test_canonical_key_is_editable_only_while_creating(self, admin_client, opportunity):
        assert 'name="canonical_key"' in html_of(admin_client.get(url(Opportunity, "add")))
        change = admin_client.get(url(Opportunity, "change", opportunity.pk))
        assert 'name="canonical_key"' not in html_of(change)  # só leitura: é a identidade

    def test_existing_opportunity_can_be_edited(self, admin_client, opportunity):
        change_url = url(Opportunity, "change", opportunity.pk)
        page = admin_client.get(change_url)
        data = {
            "title": "Título corrigido",
            "kind": "game_jam",
            "status": "open",
            "modality": "in_person",
            "requires_legal_entity": "unknown",
            "effort_estimate": "low",
            "official_url": opportunity.official_url,
            **management_forms(page),
        }
        response = admin_client.post(change_url, data)
        assert response.status_code == 302, errors_of(response)
        opportunity.refresh_from_db()
        assert (opportunity.title, opportunity.status) == ("Título corrigido", "open")
        assert opportunity.canonical_key == "url:example.org/jam"  # não muda ao editar

    def test_multi_select_widgets_are_used_for_controlled_vocabularies(self, admin_client):
        html = html_of(admin_client.get(url(Opportunity, "add")))
        for name in ("categories", "benefits", "eligible_legal_forms"):
            assert re.search(rf'<select name="{name}"[^>]*multiple', html), name

    def test_invalid_evidence_is_rejected_by_the_form(self, admin_client):
        add_url = url(Opportunity, "add")
        prefix = inline_prefix(admin_client.get(add_url), apps.get_model("core", "Evidence"))
        data = {
            "title": "X",
            "kind": "other",
            "status": "unknown",
            "modality": "unknown",
            "requires_legal_entity": "unknown",
            "effort_estimate": "unknown",
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-field": "deadline_at",
            f"{prefix}-0-value": '"2026-11-15"',
            f"{prefix}-0-kind": "observed",  # fato observado sem URL da fonte
            f"{prefix}-0-method": "connector:devpost",
        }
        response = admin_client.post(add_url, data)
        assert response.status_code == 200
        assert not Opportunity.objects.filter(title="X").exists()
        assert "source_url" in response.context["inline_admin_formsets"][0].formset.errors[0]


class TestEvidenceListing:
    def test_changelist_shows_origin_badges_and_the_entity(self, admin_client, opportunity):
        record_evidence(
            opportunity,
            "deadline_at",
            "2026-11-15",
            kind="observed",
            method="connector:devpost",
            source_url="https://example.org/jam",
        )
        record_evidence(opportunity, "modality", "online", kind="inferred", method="rule:x")
        html = html_of(admin_client.get(url(apps.get_model("core", "Evidence"), "changelist")))
        assert "✅ observado" in html and "🔮 inferido" in html
        assert "oportunidade: Game Jam Exemplo" in html

    def test_filters_by_kind(self, admin_client, opportunity):
        Evidence = apps.get_model("core", "Evidence")
        record_evidence(opportunity, "modality", "online", kind="inferred", method="rule:x")
        record_evidence(opportunity, "title", "x", kind="manual", method="human")
        html = html_of(admin_client.get(url(Evidence, "changelist"), {"kind__exact": "inferred"}))
        assert "🔮 inferido" in html
        assert "✍️ manual" not in html

    def test_standalone_form_does_not_accept_an_unknown_entity_id(self, admin_client, opportunity):
        Evidence = apps.get_model("core", "Evidence")
        add_url = url(Evidence, "add")
        data = {
            "content_type": ContentType.objects.get_for_model(Opportunity).pk,
            "object_id": 999_999_999,
            "field": "title",
            "value": '"x"',
            "kind": "manual",
            "method": "human",
            "retrieved_at_0": "2026-10-01",
            "retrieved_at_1": "12:00:00",
        }
        response = admin_client.post(add_url, data)
        assert response.status_code == 200
        assert "object_id" in response.context["adminform"].form.errors
        assert Evidence.objects.count() == 0

        response = admin_client.post(add_url, {**data, "object_id": opportunity.pk})
        assert response.status_code == 302
        assert Evidence.objects.get().entity == opportunity


class TestOrganizationAdmin:
    def test_cnpj_with_mask_is_normalized_and_duplicates_are_blocked(self, admin_client):
        add_url = url(Organization, "add")
        form = {
            **ORGANIZATION_FORM,
            "cnpj": mask_cnpj(VALID_CNPJ),
            "similarity_tags": "sistema_s, cultural_publico",
        }
        page = admin_client.get(add_url)
        response = admin_client.post(add_url, {**form, **management_forms(page)})
        assert response.status_code == 302, errors_of(response)
        saved = Organization.objects.get(name="Escola Admin")
        assert saved.cnpj == VALID_CNPJ
        assert saved.similarity_tags == ["sistema_s", "cultural_publico"]

        again = admin_client.post(add_url, {**form, "name": "Outra", **management_forms(page)})
        assert again.status_code == 200
        assert "cnpj" in again.context["adminform"].form.errors
        assert not Organization.objects.filter(name="Outra").exists()

    def test_invalid_cnpj_shows_a_friendly_error(self, admin_client):
        add_url = url(Organization, "add")
        page = admin_client.get(add_url)
        response = admin_client.post(
            add_url, {**ORGANIZATION_FORM, "cnpj": "11222333000182", **management_forms(page)}
        )
        assert response.status_code == 200
        assert "dígitos verificadores" in str(response.context["adminform"].form.errors["cnpj"])

    def test_organizations_without_identifiers_can_be_created_repeatedly(self, admin_client):
        add_url = url(Organization, "add")
        page = admin_client.get(add_url)
        for name in ("Primeira", "Segunda", "Terceira"):
            response = admin_client.post(
                add_url, {**ORGANIZATION_FORM, "name": name, **management_forms(page)}
            )
            assert response.status_code == 302, errors_of(response)
        assert Organization.objects.filter(cnpj__isnull=True).count() == 3

    def test_derived_relationship_fields_are_read_only(self, admin_client, organization):
        html = html_of(admin_client.get(url(Organization, "change", organization.pk)))
        for name in ("relationship_status", "last_interaction_at", "next_action_at"):
            assert f'name="{name}"' not in html

    def test_contact_inline_only_offers_evidence_about_this_organization(
        self, admin_client, organization
    ):
        mine = record_evidence(
            organization, "contact.email", "a@example.org", kind="manual", method="human"
        )
        other = Organization.objects.create(name="Outra")
        record_evidence(other, "contact.email", "b@example.org", kind="manual", method="human")

        change = admin_client.get(url(Organization, "change", organization.pk))
        inline = next(
            i for i in change.context["inline_admin_formsets"] if i.formset.model is ContactPoint
        )
        assert list(inline.formset.empty_form.fields["evidence"].queryset) == [mine]

        add = admin_client.get(url(Organization, "add"))
        inline = next(
            i for i in add.context["inline_admin_formsets"] if i.formset.model is ContactPoint
        )
        assert not inline.formset.empty_form.fields["evidence"].queryset.exists()

    def test_evidence_cannot_be_created_or_deleted_by_popup_from_the_contact_form(
        self, admin_client, organization
    ):
        page = admin_client.get(url(Organization, "change", organization.pk))
        inline = next(
            i for i in page.context["inline_admin_formsets"] if i.formset.model is ContactPoint
        )
        widget = inline.formset.empty_form.fields["evidence"].widget
        assert not widget.can_add_related
        assert not widget.can_change_related
        assert not widget.can_delete_related
        assert not widget.can_view_related

    def test_a_contact_is_added_through_the_inline_using_existing_evidence(
        self, admin_client, organization
    ):
        evidence = record_evidence(
            organization, "contact.email", "SECRETARIA@Example.org", kind="manual", method="human"
        )
        change_url = url(Organization, "change", organization.pk)
        page = admin_client.get(change_url)
        evidence_prefix = inline_prefix(page, type(evidence))
        contact_prefix = inline_prefix(page, ContactPoint)
        interaction_prefix = inline_prefix(page, Interaction)
        data = {
            "name": organization.name,
            "kind": "school",
            "size_hint": "unknown",
            "website_status": "unknown",
            "municipality_name": "Araraquara",
            "uf": "SP",
            f"{interaction_prefix}-TOTAL_FORMS": "0",
            f"{interaction_prefix}-INITIAL_FORMS": "0",
            f"{interaction_prefix}-MIN_NUM_FORMS": "0",
            f"{interaction_prefix}-MAX_NUM_FORMS": "1000",
            # evidência já existente (linha inicial do inline genérico)
            f"{evidence_prefix}-TOTAL_FORMS": "1",
            f"{evidence_prefix}-INITIAL_FORMS": "1",
            f"{evidence_prefix}-MIN_NUM_FORMS": "0",
            f"{evidence_prefix}-MAX_NUM_FORMS": "1000",
            f"{evidence_prefix}-0-id": str(evidence.pk),
            f"{evidence_prefix}-0-field": "contact.email",
            f"{evidence_prefix}-0-value": '"SECRETARIA@Example.org"',
            f"{evidence_prefix}-0-kind": "manual",
            f"{evidence_prefix}-0-method": "human",
            # contato novo apontando para ela
            f"{contact_prefix}-TOTAL_FORMS": "1",
            f"{contact_prefix}-INITIAL_FORMS": "0",
            f"{contact_prefix}-MIN_NUM_FORMS": "0",
            f"{contact_prefix}-MAX_NUM_FORMS": "1000",
            f"{contact_prefix}-0-kind": "email",
            f"{contact_prefix}-0-value": " SECRETARIA@Example.org ",
            f"{contact_prefix}-0-label": "Secretaria",
            f"{contact_prefix}-0-evidence": str(evidence.pk),
            f"{contact_prefix}-0-status": "active",
        }
        response = admin_client.post(change_url, data)
        assert response.status_code == 302, errors_of(response)
        contact = ContactPoint.objects.get(organization=organization)
        assert (contact.value, contact.label, contact.evidence_id) == (
            "secretaria@example.org",
            "Secretaria",
            evidence.pk,
        )

    def test_suppressed_contacts_are_flagged_in_the_organization_page(
        self, admin_client, organization, make_contact
    ):
        make_contact(organization, "email", "secretaria@example.org")
        page_url = url(Organization, "change", organization.pk)
        assert "🚫 suprimido" not in html_of(admin_client.get(page_url))
        Suppression.objects.create(kind="email", value="secretaria@example.org")
        assert "🚫 suprimido" in html_of(admin_client.get(page_url))


class TestServiceCatalogAdmin:
    def test_coverage_and_active_are_editable_directly_in_the_list(self, admin_client):
        call_command("load_services", verbosity=0)
        service = ServiceOffering.objects.get(slug="custom_software")
        response = admin_client.post(
            url(ServiceOffering, "changelist"),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(service.pk),
                "form-0-mei_coverage": "covered",  # sem "form-0-active": desmarcado
                "_save": "Salvar",
            },
        )
        assert response.status_code == 302
        service.refresh_from_db()
        assert (service.mei_coverage, service.active) == ("covered", False)

    def test_a_new_service_can_be_added_without_code(self, admin_client):
        add_url = url(ServiceOffering, "add")
        response = admin_client.post(
            add_url,
            {
                "slug": "audio_design",
                "name": "Áudio para jogos",
                "category": "games",
                "geo_profile": "remote_service",
                "mei_coverage": "verify",
                "keywords": "trilha sonora, efeitos sonoros",
                "target_org_kinds": ["company"],
                "active": "on",
            },
        )
        assert response.status_code == 302
        service = ServiceOffering.objects.get(slug="audio_design")
        assert service.keywords == ["trilha sonora", "efeitos sonoros"]
        assert service.target_org_kinds == ["company"]

    def test_slug_is_read_only_after_creation(self, admin_client):
        call_command("load_services", verbosity=0)
        service = ServiceOffering.objects.get(slug="web_app")
        assert 'name="slug"' in html_of(admin_client.get(url(ServiceOffering, "add")))
        assert 'name="slug"' not in html_of(
            admin_client.get(url(ServiceOffering, "change", service.pk))
        )

    def test_source_slug_is_read_only_after_creation(self, admin_client):
        source = Source.objects.create(slug="devpost", name="Devpost", kind="api")
        assert 'name="slug"' not in html_of(admin_client.get(url(Source, "change", source.pk)))


class TestOtherAdmins:
    def test_suppression_values_are_normalized_and_duplicates_rejected(self, admin_client):
        add_url = url(Suppression, "add")
        response = admin_client.post(
            add_url,
            {"kind": "email", "value": " Pedido@Escola.ORG ", "reason": "Pedido do titular"},
        )
        assert response.status_code == 302
        assert Suppression.objects.get().value == "pedido@escola.org"
        again = admin_client.post(add_url, {"kind": "email", "value": "pedido@escola.org"})
        assert again.status_code == 200
        assert Suppression.objects.count() == 1

    def test_triage_list_shows_the_entity_without_extra_queries_per_row(
        self, admin_client, opportunity, organization, django_assert_max_num_queries
    ):
        for entity in (opportunity, organization):
            Triage.objects.create(
                content_type=ContentType.objects.get_for_model(entity), object_id=entity.pk
            )
        with django_assert_max_num_queries(12):
            html = html_of(admin_client.get(url(Triage, "changelist")))
        assert "oportunidade: Game Jam Exemplo" in html
        assert "organização: Escola Exemplo" in html
