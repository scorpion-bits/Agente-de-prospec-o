"""Entidades núcleo: defaults, unicidade/dedupe, restrições do banco e integridade referencial."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django import forms
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError, RestrictedError

from core.fields import ChoiceArrayField
from core.models import (
    ContactPoint,
    Evidence,
    Match,
    Opportunity,
    Organization,
    ServiceOffering,
    Source,
    Triage,
)
from core.services.evidence import record_evidence
from tests.conftest import VALID_CNPJ, mask_cnpj

pytestmark = pytest.mark.django_db


def make_service(slug="svc", **extra):
    defaults = {"name": slug, "category": "education", "geo_profile": "online"}
    return ServiceOffering.objects.create(slug=slug, **{**defaults, **extra})


class TestSource:
    def test_new_sources_start_disabled_and_unverified(self):
        source = Source.objects.create(slug="devpost", name="Devpost", kind=Source.Kind.API)
        assert source.enabled is False  # coleta educada: só liga depois de conferir termos
        assert source.robots_ok is False
        assert source.schedule == Source.Schedule.MANUAL
        assert source.config == {}

    def test_slug_is_unique(self):
        Source.objects.create(slug="devpost", name="A", kind="api")
        with pytest.raises(IntegrityError), transaction.atomic():
            Source.objects.create(slug="devpost", name="B", kind="api")

    def test_reliability_is_between_1_and_5(self):
        source = Source(slug="x", name="X", kind="api", reliability=6)
        with pytest.raises(ValidationError) as error:
            source.full_clean()
        assert "reliability" in error.value.message_dict


class TestOrganization:
    def test_defaults(self, organization):
        assert organization.relationship_status == Organization.RelationshipStatus.NEVER_CONTACTED
        assert organization.last_interaction_at is None
        assert organization.next_action_at is None
        assert organization.cnpj is None
        assert organization.similarity_tags == []
        assert organization.website_status == Organization.WebsiteStatus.UNKNOWN
        assert str(organization) == "Escola Exemplo"

    def test_blank_identifiers_are_stored_as_null_so_they_do_not_collide(self):
        for name in ("A", "B", "C"):
            Organization.objects.create(name=name, cnpj="", inep_code="", osm_id=" ")
        assert Organization.objects.filter(cnpj__isnull=True).count() == 3
        assert Organization.objects.filter(inep_code__isnull=True).count() == 3
        assert Organization.objects.filter(osm_id__isnull=True).count() == 3

    def test_duplicate_cnpj_is_rejected_even_when_written_with_the_mask(self):
        Organization.objects.create(name="A", cnpj=VALID_CNPJ)
        with pytest.raises(IntegrityError), transaction.atomic():
            Organization.objects.create(name="B", cnpj=mask_cnpj(VALID_CNPJ))

    def test_cnpj_is_stored_without_the_mask(self):
        org = Organization.objects.create(name="A", cnpj=mask_cnpj(VALID_CNPJ))
        org.refresh_from_db()
        assert org.cnpj == VALID_CNPJ

    def test_full_clean_reports_duplicate_cnpj_as_a_field_error(self):
        Organization.objects.create(name="A", cnpj=VALID_CNPJ)
        duplicate = Organization(name="B", cnpj=mask_cnpj(VALID_CNPJ))
        with pytest.raises(ValidationError) as error:
            duplicate.full_clean()
        assert "cnpj" in error.value.message_dict

    def test_full_clean_rejects_invalid_cnpj_and_accepts_alphanumeric(self):
        with pytest.raises(ValidationError) as error:
            Organization(name="A", cnpj="11222333000182").full_clean()
        assert "cnpj" in error.value.message_dict
        Organization(name="B", cnpj="12.ABC.345/01DE-35").full_clean()  # sem erro

    def test_duplicate_inep_code_and_osm_id_are_rejected(self):
        Organization.objects.create(name="A", inep_code="35000001", osm_id="way/1")
        with pytest.raises(IntegrityError), transaction.atomic():
            Organization.objects.create(name="B", inep_code="35000001")
        with pytest.raises(IntegrityError), transaction.atomic():
            Organization.objects.create(name="C", osm_id="way/1")

    def test_inep_code_has_eight_digits(self):
        with pytest.raises(ValidationError) as error:
            Organization(name="A", inep_code="123").full_clean()
        assert "inep_code" in error.value.message_dict

    def test_uf_is_uppercased_on_save_and_must_have_two_letters(self):
        org = Organization.objects.create(name="A", uf=" sp ")
        assert org.uf == "SP"
        with pytest.raises(ValidationError) as error:
            Organization(name="B", uf="SAO").full_clean()
        assert "uf" in error.value.message_dict

    def test_an_organization_cannot_be_its_own_parent(self, organization):
        organization.parent = organization
        with pytest.raises(ValidationError) as error:
            organization.full_clean()
        assert "parent" in error.value.message_dict

    def test_hierarchy_cycles_are_rejected(self):
        a = Organization.objects.create(name="A")
        b = Organization.objects.create(name="B", parent=a)
        c = Organization.objects.create(name="C", parent=b)
        a.parent = c  # A -> C -> B -> A
        with pytest.raises(ValidationError) as error:
            a.full_clean()
        assert "parent" in error.value.message_dict

    def test_network_with_units(self):
        sesc_sp = Organization.objects.create(name="SESC-SP", kind="sesc", network="SESC-SP")
        for city in ("Bauru", "Ribeirão Preto", "São Carlos"):
            Organization.objects.create(
                name=f"SESC {city}",
                kind="sesc",
                network="SESC-SP",
                parent=sesc_sp,
                municipality_name=city,
                uf="SP",
            )
        assert sesc_sp.children.count() == 3
        assert Organization.objects.filter(network="SESC-SP").count() == 4

    def test_a_parent_with_units_cannot_be_deleted_by_accident(self):
        parent = Organization.objects.create(name="Rede")
        Organization.objects.create(name="Unidade", parent=parent)
        with pytest.raises(ProtectedError):
            parent.delete()

    def test_lists_round_trip(self):
        org = Organization.objects.create(
            name="A", similarity_tags=["sistema_s", "cultural_publico"]
        )
        org.refresh_from_db()
        assert org.similarity_tags == ["sistema_s", "cultural_publico"]

    def test_deleting_an_organization_removes_its_evidence_and_triage(self, organization):
        record_evidence(
            organization,
            "offers_high_school",
            True,
            kind="observed",
            method="connector:inep_schools",
            source_url="https://example.org/inep",
        )
        Triage.objects.create(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=organization.pk,
        )
        organization.delete()
        assert Evidence.objects.count() == 0
        assert Triage.objects.count() == 0


class TestOpportunity:
    def test_defaults_mean_unknown_not_assumed(self, opportunity):
        assert opportunity.status == Opportunity.Status.UNKNOWN
        assert opportunity.modality == Opportunity.Modality.UNKNOWN
        assert opportunity.requires_legal_entity == "unknown"
        assert opportunity.exclusive_small_business is None  # desconhecido ≠ "não"
        assert opportunity.eligible_legal_forms == []  # vazio = sem restrição conhecida
        assert opportunity.required_cnaes == []
        assert opportunity.eligible_regions == []
        assert opportunity.min_company_age_months is None

    def test_company_requirement_fields_round_trip(self):
        opp = Opportunity.objects.create(
            title="Edital X",
            official_url="https://example.org/edital-x",
            requires_legal_entity="yes",
            eligible_legal_forms=["MEI", "ME"],
            exclusive_small_business=True,
            min_company_age_months=24,
            required_cnaes=["62.01-5"],
            eligible_regions=["SP", "Araraquara/SP"],
            prize_amount_brl=Decimal("50000.00"),
            categories=["games", "culture"],
            benefits=["money", "visibility"],
            deadline_at=datetime(2026, 11, 15, 23, 59, tzinfo=UTC),
        )
        opp.refresh_from_db()
        assert opp.eligible_legal_forms == ["MEI", "ME"]
        assert opp.exclusive_small_business is True
        assert opp.min_company_age_months == 24
        assert opp.required_cnaes == ["62.01-5"]
        assert opp.prize_amount_brl == Decimal("50000.00")
        assert opp.categories == ["games", "culture"]

    def test_choice_lists_reject_values_outside_the_vocabulary(self):
        opp = Opportunity(title="X", categories=["games", "invented"], eligible_legal_forms=["XYZ"])
        with pytest.raises(ValidationError) as error:
            opp.full_clean()
        assert {"categories", "eligible_legal_forms"} <= set(error.value.message_dict)

    def test_canonical_key_is_generated_from_the_official_url(self):
        opp = Opportunity.objects.create(
            title="Jam", official_url="https://www.example.org/jam/?utm_source=x&id=7#top"
        )
        assert opp.canonical_key == "url:example.org/jam?id=7"

    def test_canonical_key_without_url_uses_organizer_title_and_deadline(self, organization):
        opp = Opportunity.objects.create(
            title="Edital de Cultura",
            organizer=organization,
            deadline_at=datetime(2026, 11, 16, 2, 30, tzinfo=UTC),
        )
        assert opp.canonical_key == "slug:escola-exemplo|edital-de-cultura|2026-11-15"

    def test_an_explicit_canonical_key_is_kept(self):
        opp = Opportunity.objects.create(title="Jam", canonical_key="devpost:12345")
        assert opp.canonical_key == "devpost:12345"

    def test_the_same_opportunity_found_twice_is_a_duplicate(self):
        Opportunity.objects.create(title="Jam", official_url="https://example.org/jam")
        with pytest.raises(IntegrityError), transaction.atomic():
            Opportunity.objects.create(
                title="Jam (cópia)", official_url="http://www.example.org/jam/?utm_medium=email"
            )

    def test_full_clean_reports_the_duplicate_before_hitting_the_database(self):
        Opportunity.objects.create(title="Jam", official_url="https://example.org/jam")
        again = Opportunity(title="Jam", official_url="https://example.org/jam/")
        with pytest.raises(ValidationError) as error:
            again.full_clean()
        assert "canonical_key" in error.value.message_dict

    def test_distinct_opportunities_without_url_do_not_collide(self):
        Opportunity.objects.create(title="Edital A")
        Opportunity.objects.create(title="Edital B")
        assert Opportunity.objects.count() == 2


class TestServiceOffering:
    def test_new_services_default_to_verify_with_the_accountant(self):
        assert make_service().mei_coverage == ServiceOffering.MeiCoverage.VERIFY

    def test_natural_key_is_the_slug(self):
        service = make_service("custom_software")
        assert service.natural_key() == ("custom_software",)
        assert ServiceOffering.objects.get_by_natural_key("custom_software") == service

    def test_ticket_range_cannot_be_inverted(self):
        service = ServiceOffering(
            slug="x",
            name="X",
            category="web",
            geo_profile="remote_service",
            typical_ticket_min_brl=Decimal("5000"),
            typical_ticket_max_brl=Decimal("1000"),
        )
        with pytest.raises(ValidationError):
            service.full_clean()
        with pytest.raises(IntegrityError), transaction.atomic():
            service.save()

    def test_edital_scope_is_not_a_service_geo_profile(self):
        service = ServiceOffering(slug="x", name="X", category="web", geo_profile="edital_scope")
        with pytest.raises(ValidationError) as error:
            service.full_clean()
        assert "geo_profile" in error.value.message_dict


class TestContactPoint:
    def test_duplicates_are_detected_after_normalization(self, organization, make_contact):
        make_contact(organization, "email", "Contato@Example.org ")
        evidence = record_evidence(
            organization,
            "contact.email",
            "outra",
            kind="manual",
            method="human",
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            ContactPoint.objects.create(
                organization=organization,
                kind="email",
                value="contato@example.org",
                evidence=evidence,
            )

    def test_value_is_normalized_by_kind(self, organization, make_contact):
        assert make_contact(organization, "email", "SECRETARIA@Example.org").value == (
            "secretaria@example.org"
        )
        assert make_contact(organization, "phone", "(16) 0000-0000").value == "+551600000000"

    def test_a_contact_cannot_exist_without_evidence(self, organization):
        with pytest.raises(IntegrityError), transaction.atomic():
            ContactPoint.objects.create(organization=organization, kind="email", value="a@b.org")

    def test_evidence_must_be_about_the_same_organization(self, organization, make_contact):
        other = Organization.objects.create(name="Outra")
        foreign = record_evidence(
            other, "contact.email", "x@example.org", kind="manual", method="human"
        )
        contact = ContactPoint(
            organization=organization, kind="email", value="x@example.org", evidence=foreign
        )
        with pytest.raises(ValidationError) as error:
            contact.full_clean()
        assert "evidence" in error.value.message_dict

    def test_evidence_cannot_be_deleted_while_a_contact_depends_on_it(
        self, organization, make_contact
    ):
        contact = make_contact(organization, "email", "a@example.org")
        with pytest.raises(RestrictedError):
            contact.evidence.delete()

    def test_deleting_the_organization_removes_contacts_and_their_evidence(
        self, organization, make_contact
    ):
        make_contact(organization, "email", "a@example.org")
        make_contact(organization, "phone", "(16) 0000-0000")
        organization.delete()
        assert ContactPoint.objects.count() == 0
        assert Evidence.objects.count() == 0


class TestMatch:
    def test_one_match_per_organization_service_and_method(self, organization):
        service = make_service()
        Match.objects.create(organization=organization, service=service, strength=0.7)
        with pytest.raises(IntegrityError), transaction.atomic():
            Match.objects.create(organization=organization, service=service, strength=0.9)
        # outra versão do método convive com a primeira
        Match.objects.create(
            organization=organization, service=service, strength=0.8, method="rules_v2"
        )
        assert Match.objects.count() == 2

    @pytest.mark.parametrize("strength", [-0.1, 1.1])
    def test_strength_is_between_0_and_1(self, organization, strength):
        match = Match(organization=organization, service=make_service(), strength=strength)
        with pytest.raises(ValidationError):
            match.full_clean()
        with pytest.raises(IntegrityError), transaction.atomic():
            match.save()


class TestTriage:
    def triage(self, entity, **extra):
        return Triage(
            content_type=ContentType.objects.get_for_model(entity), object_id=entity.pk, **extra
        )

    def test_one_triage_per_entity(self, opportunity):
        self.triage(opportunity).save()
        with pytest.raises(IntegrityError), transaction.atomic():
            self.triage(opportunity).save()

    def test_discarding_requires_a_reason(self, opportunity):
        triage = self.triage(opportunity, status=Triage.Status.DISCARDED)
        with pytest.raises(ValidationError) as error:
            triage.full_clean()
        assert "discard_reason" in error.value.message_dict
        with pytest.raises(IntegrityError), transaction.atomic():
            triage.save()
        triage.discard_reason = Triage.DiscardReason.TOO_FAR
        triage.full_clean()
        triage.save()
        assert str(triage) == "Game Jam Exemplo — Descartada"

    def test_only_organizations_and_opportunities_can_be_triaged(self):
        source = Source.objects.create(slug="s", name="S", kind="api")
        with pytest.raises(ValidationError) as error:
            self.triage(source).full_clean()
        assert "content_type" in error.value.message_dict

    def test_the_triaged_entity_must_exist(self, opportunity):
        ghost = Triage(
            content_type=ContentType.objects.get_for_model(Opportunity), object_id=999_999_999
        )
        with pytest.raises(ValidationError) as error:
            ghost.full_clean()
        assert "999999999" in str(error.value.message_dict["object_id"])
        self.triage(opportunity).full_clean()  # a existente passa


class TestEvidenceConstraints:
    def evidence(self, entity, **extra):
        values = {
            "content_type": ContentType.objects.get_for_model(entity),
            "object_id": entity.pk,
            "field": "deadline_at",
            "value": "2026-11-15",
            "kind": "observed",
            "method": "connector:devpost",
            "source_url": "https://example.org/jam",
        }
        return Evidence(**{**values, **extra})

    def test_observed_facts_must_have_a_source_url(self, opportunity):
        evidence = self.evidence(opportunity, source_url="")
        with pytest.raises(ValidationError) as error:
            evidence.full_clean()
        assert "source_url" in error.value.message_dict
        with pytest.raises(IntegrityError), transaction.atomic():
            evidence.save()  # a restrição vale também fora do formulário

    @pytest.mark.parametrize("confidence", [-0.01, 1.01])
    def test_confidence_is_between_0_and_1(self, opportunity, confidence):
        evidence = self.evidence(opportunity, confidence=confidence)
        with pytest.raises(ValidationError):
            evidence.full_clean()
        with pytest.raises(IntegrityError), transaction.atomic():
            evidence.save()

    def test_method_vocabulary_and_kind_consistency(self, opportunity):
        with pytest.raises(ValidationError) as error:
            self.evidence(opportunity, method="manual-ish").full_clean()
        assert "method" in error.value.message_dict
        with pytest.raises(ValidationError) as error:
            self.evidence(opportunity, kind="manual", method="rule:x").full_clean()
        assert "method" in error.value.message_dict
        with pytest.raises(ValidationError) as error:
            self.evidence(opportunity, kind="inferred", method="human").full_clean()
        assert "method" in error.value.message_dict

    def test_field_name_vocabulary(self, opportunity):
        for bad in ("Deadline At", "1deadline", "deadline-at"):
            with pytest.raises(ValidationError) as error:
                self.evidence(opportunity, field=bad).full_clean()
            assert "field" in error.value.message_dict
        self.evidence(opportunity, field="contact.email").full_clean()  # sem erro

    def test_a_missing_value_is_not_a_claim(self, opportunity):
        with pytest.raises(ValidationError) as error:
            self.evidence(opportunity, value=None).full_clean()
        assert "value" in error.value.message_dict

    def test_the_entity_must_exist(self, opportunity):
        ghost = self.evidence(opportunity, object_id=999_999_999)
        with pytest.raises(ValidationError) as error:
            ghost.full_clean()
        assert "Não existe oportunidade" in str(error.value.message_dict["object_id"])
        self.evidence(opportunity).full_clean()  # a existente passa

    def test_falsy_values_are_valid_claims(self, opportunity):
        for value in (False, 0, "", [], {}):
            self.evidence(opportunity, value=value).full_clean()  # sem erro


class TestSchema:
    def test_every_core_table_lives_in_the_dedicated_schema_not_public(self, settings):
        tables = {model._meta.db_table for model in apps.get_app_config("core").get_models()}
        assert (
            len(tables) == 15
        )  # 9 (E03) + 3 (E03b) + Municipality (E12) + Deal (E23) + Draft (E24)
        with connection.cursor() as cursor:
            cursor.execute(
                "select table_schema, table_name from information_schema.tables "
                "where table_name = any(%s)",
                [sorted(tables)],
            )
            found = cursor.fetchall()
        assert {name for _, name in found} == tables
        assert {schema for schema, _ in found} == {settings.DB_SCHEMA}


class TestChoiceArrayField:
    def test_form_field_is_a_multiple_choice_with_the_vocabulary(self):
        field = Opportunity._meta.get_field("categories")
        assert isinstance(field, ChoiceArrayField)
        form_field = field.formfield()
        assert isinstance(form_field, forms.MultipleChoiceField)
        assert ("games", "Jogos") in form_field.choices
        assert form_field.required is False  # blank=True
