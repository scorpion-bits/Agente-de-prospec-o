"""`record_evidence`: as regras do ADR-004 (fato observado × inferência × manual)."""

from datetime import UTC, datetime, timedelta

import pytest

from core.models import Evidence, Opportunity, Organization, Source
from core.services.evidence import EXCERPT_MAX_CHARS, EvidenceError, quote_in_text, record_evidence

pytestmark = pytest.mark.django_db

URL = "https://example.org/jam"
LLM = "llm:gemini-2.5-flash-lite@prompt_v3"


def observed(entity, **extra):
    values = {
        "field": "deadline_at",
        "value": "2026-11-15",
        "kind": "observed",
        "method": "connector:devpost",
        "source_url": URL,
    }
    values.update(extra)
    return record_evidence(entity, values.pop("field"), values.pop("value"), **values)


class TestRecording:
    def test_stores_the_claim_with_its_origin(self, opportunity):
        evidence = observed(
            opportunity,
            source_name="Exemplo",
            excerpt="Inscrições até 15/11/2026",
            confidence=0.9,
        )
        evidence.refresh_from_db()
        assert evidence.entity == opportunity
        assert (evidence.field, evidence.value, evidence.kind) == (
            "deadline_at",
            "2026-11-15",
            "observed",
        )
        assert evidence.source_url == URL
        assert evidence.method == "connector:devpost"
        assert evidence.excerpt == "Inscrições até 15/11/2026"
        assert evidence.confidence == 0.9
        assert evidence.verified is False  # ninguém conferiu a citação contra o texto
        assert list(opportunity.evidence_items.all()) == [evidence]

    def test_works_for_organizations_too(self, organization):
        evidence = observed(organization, field="offers_high_school", value=True)
        assert list(organization.evidence_items.all()) == [evidence]

    def test_structured_values_and_datetimes_are_stored_as_json(self, opportunity):
        when = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
        evidence = observed(opportunity, value=when)
        evidence.refresh_from_db()
        assert evidence.value == "2026-11-15T23:59:00Z"
        listed = observed(opportunity, field="eligible_legal_forms", value=["MEI", "ME"])
        listed.refresh_from_db()
        assert listed.value == ["MEI", "ME"]

    def test_falsy_values_are_valid_claims(self, opportunity):
        assert observed(opportunity, field="requires_legal_entity", value=False).value is False
        assert observed(opportunity, field="min_company_age_months", value=0).value == 0

    def test_manual_evidence_needs_no_url(self, opportunity):
        evidence = record_evidence(
            opportunity, "deadline_at", "2026-11-15", kind="manual", method="human"
        )
        assert evidence.kind == "manual"
        assert evidence.source_url == ""

    def test_inferred_evidence_needs_no_url(self, organization):
        evidence = record_evidence(
            organization, "likely_buys_courses", True, kind="inferred", method="rule:school_rules"
        )
        assert evidence.kind == "inferred"


class TestRules:
    def test_observed_requires_a_source_url(self, opportunity):
        with pytest.raises(EvidenceError, match="source_url"):
            observed(opportunity, source_url="")

    @pytest.mark.parametrize(
        "bad",
        [
            {"field": "Deadline At"},
            {"field": ""},
            {"method": "whatever"},
            {"method": "connector:"},
            {"kind": "guess"},
            {"confidence": 1.5},
            {"confidence": -0.2},
            {"value": None},
            {"source_url": "not a url"},
            {"kind": "manual", "method": "rule:x", "source_url": ""},
            {"kind": "inferred", "method": "human", "source_url": ""},
        ],
    )
    def test_invalid_requests_are_rejected_and_nothing_is_written(self, opportunity, bad):
        with pytest.raises(EvidenceError):
            observed(opportunity, **bad)
        assert Evidence.objects.count() == 0

    def test_unsaved_entities_are_rejected(self):
        with pytest.raises(EvidenceError, match="Salve"):
            observed(Organization(name="Ainda não salva"))

    def test_only_organizations_and_opportunities_take_evidence(self):
        source = Source.objects.create(slug="s", name="S", kind="api")
        with pytest.raises(EvidenceError, match="não se aplica"):
            observed(source)


class TestExcerpt:
    def test_whitespace_is_normalized(self, opportunity):
        evidence = observed(opportunity, excerpt="  Inscrições\n\n até   15/11/2026\t ")
        assert evidence.excerpt == "Inscrições até 15/11/2026"

    def test_excerpt_is_clipped_to_500_chars_keeping_a_literal_prefix(self, opportunity):
        text = "palavra " * 200
        evidence = observed(opportunity, excerpt=text)
        assert len(evidence.excerpt) == EXCERPT_MAX_CHARS
        assert text.startswith(evidence.excerpt)


class TestIdempotency:
    def test_recording_the_same_claim_again_refreshes_instead_of_duplicating(self, opportunity):
        first = observed(opportunity, retrieved_at=datetime(2026, 10, 1, tzinfo=UTC))
        second = observed(opportunity, retrieved_at=datetime(2026, 10, 8, tzinfo=UTC))
        assert second.pk == first.pk
        assert Evidence.objects.count() == 1
        first.refresh_from_db()
        assert first.retrieved_at == datetime(2026, 10, 8, tzinfo=UTC)

    def test_same_datetime_value_is_recognized_as_the_same_claim(self, opportunity):
        when = datetime(2026, 11, 15, 23, 59, tzinfo=UTC)
        assert observed(opportunity, value=when).pk == observed(opportunity, value=when).pk

    def test_refresh_keeps_the_excerpt_when_the_new_call_has_none(self, opportunity):
        observed(opportunity, excerpt="Inscrições até 15/11/2026", confidence=0.8)
        again = observed(opportunity)  # sem trecho nem confiança
        again.refresh_from_db()
        assert again.excerpt == "Inscrições até 15/11/2026"
        assert again.confidence == 0.8

    def test_refresh_takes_the_new_excerpt_and_verification_together(self, opportunity):
        observed(opportunity, excerpt="prazo antigo na página")
        again = observed(
            opportunity,
            excerpt="Inscrições até 15/11/2026",
            source_text="... Inscrições até 15/11/2026 ...",
        )
        again.refresh_from_db()
        assert again.excerpt == "Inscrições até 15/11/2026"
        assert again.verified is True
        assert Evidence.objects.count() == 1

    def test_a_changed_value_keeps_the_history(self, opportunity):
        old = observed(opportunity, value="2026-11-15")
        new = observed(opportunity, value="2026-11-30")
        assert old.pk != new.pk
        assert Evidence.objects.filter(field="deadline_at").count() == 2

    def test_different_methods_or_sources_are_different_claims(self, opportunity):
        observed(opportunity)
        observed(opportunity, method="regex:deadline")
        observed(opportunity, source_url="https://example.org/outra-pagina")
        assert Evidence.objects.count() == 3

    def test_kind_is_part_of_the_claim(self, opportunity):
        observed(opportunity)
        record_evidence(
            opportunity,
            "deadline_at",
            "2026-11-15",
            kind="inferred",
            method="connector:devpost",
            source_url=URL,
        )
        assert Evidence.objects.count() == 2

    def test_same_pk_on_different_entity_types_does_not_clash(self):
        org = Organization.objects.create(id=990001, name="Org")
        opp = Opportunity.objects.create(id=990001, title="Opp")
        observed(org, field="website", value="x")
        observed(opp, field="website", value="x")
        assert Evidence.objects.count() == 2


class TestVerification:
    """ADR-004: saídas de LLM só contam como observadas se a citação estiver no texto-fonte."""

    TEXT = "O prazo final para inscrições é 15 de novembro de 2026, às 23h59."

    def test_quote_found_in_source_text_is_verified(self, opportunity):
        evidence = observed(
            opportunity,
            excerpt="prazo final para inscrições é 15 de novembro",
            source_text=self.TEXT,
        )
        assert evidence.verified is True

    def test_matching_ignores_case_spacing_and_typographic_quotes(self):
        assert quote_in_text("PRAZO  final\npara inscrições", self.TEXT)
        assert quote_in_text("o “prazo” — final", 'O "prazo" - final do edital')

    def test_quote_not_in_source_text_is_not_verified(self, opportunity):
        evidence = observed(
            opportunity, excerpt="inscrições até 30 de dezembro", source_text=self.TEXT
        )
        assert evidence.verified is False

    def test_very_short_quotes_prove_nothing(self):
        assert not quote_in_text("sim", "sim, claro")

    def test_empty_quote_is_never_verified(self):
        assert not quote_in_text("", self.TEXT)

    def test_computed_verification_overrides_what_the_caller_claims(self, opportunity):
        evidence = observed(
            opportunity, excerpt="texto que não está na fonte", source_text=self.TEXT, verified=True
        )
        assert evidence.verified is False

    def test_llm_claim_with_a_found_quote_stays_observed(self, opportunity):
        evidence = observed(
            opportunity,
            method=LLM,
            excerpt="prazo final para inscrições é 15 de novembro",
            source_text=self.TEXT,
        )
        assert (evidence.kind, evidence.verified) == ("observed", True)

    def test_llm_claim_with_a_quote_not_found_is_downgraded_to_inferred(self, opportunity):
        evidence = observed(
            opportunity,
            method=LLM,
            excerpt="inscrições até 30 de dezembro",
            source_text=self.TEXT,
        )
        assert (evidence.kind, evidence.verified) == ("inferred", False)
        assert evidence.value == "2026-11-15"  # o dado não se perde, só deixa de valer como fato

    def test_llm_claim_without_source_text_cannot_be_observed(self, opportunity):
        evidence = observed(opportunity, method=LLM, excerpt="prazo final para inscrições")
        assert (evidence.kind, evidence.verified) == ("inferred", False)

    def test_the_caller_cannot_force_verified_for_an_llm_claim(self, opportunity):
        evidence = observed(opportunity, method=LLM, verified=True)
        assert evidence.verified is False

    def test_llm_inference_needs_no_url(self, opportunity):
        evidence = record_evidence(
            opportunity, "modality", "online", kind="inferred", method=LLM, confidence=0.6
        )
        assert evidence.kind == "inferred"

    def test_deterministic_methods_keep_the_callers_verification(self, opportunity):
        evidence = observed(opportunity, method="regex:deadline", verified=True)
        assert evidence.verified is True


def test_retrieved_at_defaults_to_now(opportunity):
    before = datetime.now(UTC) - timedelta(seconds=5)
    evidence = observed(opportunity)
    assert evidence.retrieved_at >= before
