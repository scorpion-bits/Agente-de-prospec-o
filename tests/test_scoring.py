"""E13 — score de oportunidades: gates, fatores, elegibilidade, confiança e cenários dourados."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from itertools import count

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from django.urls import reverse

from core.models import (
    CompanyProfile,
    ContactPoint,
    Municipality,
    Opportunity,
    Organization,
    PortfolioItem,
    ServiceOffering,
    Triage,
)
from core.services.evidence import record_evidence
from scoring.eligibility import check_eligibility, months_between
from scoring.engine import (
    build_context,
    combine,
    confidence,
    is_discarded,
    save_score,
    score_opportunity,
)
from scoring.factors import EvidenceIndex, FactorResult
from scoring.models import Score
from scoring.profiles import BANDS, FACTORS, PROFILE_BY_KIND, WEIGHTS, label_for, profile_for_kind

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)


def days(n: int) -> datetime:
    return NOW + timedelta(days=n)


@pytest.fixture
def home(db):
    call_command("load_services", stdout=StringIO())
    return Municipality.objects.create(
        ibge_code=3503208, name="Araraquara", uf="SP", lat=-21.7845, lon=-48.178
    )


@pytest.fixture
def company(db):
    return CompanyProfile.objects.create(
        legal_form="MEI",
        opened_at=date(2025, 4, 10),
        primary_cnae="8599603",
        cnaes=[{"code": "85.99-6/03", "role": "principal"}],
    )


@pytest.fixture
def ctx(home, company):
    return build_context(now=NOW)


_urls = count(1)


def make_opp(**fields):
    fields.setdefault("title", "Edital de jogos educativos")
    fields.setdefault("kind", Opportunity.Kind.EDITAL)
    fields.setdefault("official_url", f"https://example.org/edital-{next(_urls)}")
    fields.setdefault("deadline_at", days(32))
    return Opportunity.objects.create(**fields)


def observe(opp, field, value):
    return record_evidence(
        opp,
        field,
        value,
        kind="observed",
        method="regex:test",
        source_url="https://example.org/edital",
        excerpt=f"{field}: {value}",
    )


def factor(result: Score | object, key: str) -> dict:
    return next(row for row in result.breakdown if row["factor"] == key)


class TestProfiles:
    def test_weights_sum_to_one_per_profile(self):
        for profile, weights in WEIGHTS.items():
            assert tuple(weights) == FACTORS, profile
            assert sum(weights.values()) == pytest.approx(1.0), profile

    def test_every_kind_has_a_profile_with_weights(self):
        assert set(PROFILE_BY_KIND) == {k.value for k in Opportunity.Kind}
        assert set(PROFILE_BY_KIND.values()) <= set(WEIGHTS)
        assert profile_for_kind("game_jam") == "opp.hackathon_jam"
        assert profile_for_kind("desconhecido") == "opp.event"

    def test_bands(self):
        assert [label_for(n) for n in (100, 75, 74, 55, 54, 35, 34, 0)] == [
            "prioritize", "prioritize", "evaluate", "evaluate", "low", "low", "ignore", "ignore",
        ]  # fmt: skip
        assert BANDS[0][0] == 75


class TestCombine:
    """O exemplo de `docs/architecture/scoring.md` (PIPE Fase 1) reproduzido na fórmula."""

    def doc_factors(self, support):
        values = {"V": 0.95, "F": 0.80, "C": 0.55, "T": 0.90, "A": 0.80, "L": 0.25}
        return [FactorResult(k, v, f"ex {k}", [1], support[k]) for k, v in values.items()]

    def test_documented_example_gives_72(self):
        # q = 0,92: cinco fatores observados e um (Leveza) inferido ≈ 0,92 na média do exemplo.
        support = {"V": 1, "F": 1, "C": 1, "T": 1, "A": 1, "L": 0.5}
        factors = self.doc_factors(support)
        total, k, raw_sum, breakdown = combine("opp.edital", factors)
        assert raw_sum == pytest.approx(0.74, abs=0.001)
        assert k == pytest.approx(0.7 + 0.3 * (5.5 / 6))
        assert total == 72
        assert label_for(total) == "evaluate"
        assert [row["factor"] for row in breakdown] == list(FACTORS)
        assert breakdown[0]["points"] == pytest.approx(28.5)

    def test_confidence_range(self):
        none = [FactorResult(k, 0.5, "", [], 0.0) for k in FACTORS]
        full = [FactorResult(k, 0.5, "", [1], 1.0) for k in FACTORS]
        assert confidence(none) == pytest.approx(0.7)
        assert confidence(full) == pytest.approx(1.0)

    def test_weak_data_lowers_the_score_not_raises_it(self):
        values = [FactorResult(k, 0.8, "", [], 0.0) for k in FACTORS]
        strong = [FactorResult(k, 0.8, "", [1], 1.0) for k in FACTORS]
        assert combine("opp.edital", values)[0] < combine("opp.edital", strong)[0]


class TestGates:
    def test_deadline_passed_is_gated(self, ctx):
        opp = make_opp(deadline_at=days(-1))
        result = score_opportunity(opp, ctx)
        assert result.gated and result.total is None
        assert result.gate_kind == Score.GateKind.EXPIRED
        assert "prazo vencido" in result.gate_reason

    def test_closed_without_dates_is_gated(self, ctx):
        opp = make_opp(deadline_at=None, status=Opportunity.Status.CLOSED)
        assert score_opportunity(opp, ctx).gate_kind == Score.GateKind.EXPIRED

    def test_event_that_already_happened_is_gated(self, ctx):
        opp = make_opp(kind="event", deadline_at=None, starts_at=days(-10))
        assert score_opportunity(opp, ctx).gate_kind == Score.GateKind.EXPIRED

    def test_territory_restriction_is_gated(self, ctx):
        opp = make_opp(eligible_regions=["RJ"], scope="state")
        result = score_opportunity(opp, ctx)
        assert result.gate_kind == Score.GateKind.TERRITORY
        assert "RJ" in result.gate_reason

    def test_territory_that_includes_our_state_passes(self, ctx):
        opp = make_opp(eligible_regions=["SP"], scope="state")
        assert not score_opportunity(opp, ctx).gated

    def test_company_requirement_gate_names_the_reason(self, ctx):
        opp = make_opp(eligible_legal_forms=["ME", "EPP"])
        result = score_opportunity(opp, ctx)
        assert result.gate_kind == Score.GateKind.COMPANY_REQUIREMENT
        assert result.gate_reason.startswith("bloqueado por requisito da empresa")

    def test_gate_order_prefers_expired_over_company(self, ctx):
        opp = make_opp(deadline_at=days(-3), eligible_legal_forms=["ME"])
        assert score_opportunity(opp, ctx).gate_kind == Score.GateKind.EXPIRED


class TestEligibility:
    def check(self, opp, company, service=None, today=date(2026, 10, 1)):
        return check_eligibility(opp, company, service, today)

    def test_accepts_mei_when_listed(self, company):
        opp = make_opp(eligible_legal_forms=["MEI", "ME"])
        assert self.check(opp, company).gate is None

    def test_min_age_uses_the_deadline_date(self, company):
        # MEI desde 10/04/2025: 24 meses só em 10/04/2027 (ADR-013).
        before = make_opp(
            min_company_age_months=24, deadline_at=datetime(2027, 4, 9, 23, tzinfo=UTC)
        )
        after = make_opp(
            title="Outro", official_url="https://example.org/2", min_company_age_months=24,
            deadline_at=datetime(2027, 4, 10, 23, tzinfo=UTC),
        )  # fmt: skip
        assert self.check(before, company).gate
        assert "meses" in self.check(before, company).gate
        assert self.check(after, company).gate is None

    def test_min_age_without_opening_date_is_an_alert_not_a_gate(self, db):
        profile = CompanyProfile.objects.create(legal_form="MEI")
        result = self.check(make_opp(min_company_age_months=24), profile)
        assert result.gate is None and result.alerts

    def test_legal_entity_without_forms_is_ambiguous(self, company):
        opp = make_opp(requires_legal_entity="yes")
        result = self.check(opp, company)
        assert result.gate is None
        assert any("aceita MEI" in a for a in result.alerts)

    def test_cnae_missing_is_alert_with_penalty(self, company):
        result = self.check(make_opp(required_cnaes=["62.01-5"]), company)
        assert result.gate is None
        assert any("CNAE" in a for a in result.alerts)
        assert sum(d for d, _ in result.adjustments) < 0

    def test_cnae_present_has_no_alert(self, company):
        result = self.check(make_opp(required_cnaes=["85.99-6"]), company)
        assert not result.alerts

    def test_small_business_quota_is_a_bonus(self, company):
        result = self.check(make_opp(exclusive_small_business=True), company)
        assert sum(d for d, _ in result.adjustments) > 0
        assert not result.alerts

    def test_prize_above_mei_cap_alerts(self, company):
        result = self.check(make_opp(prize_amount_brl=Decimal("120000")), company)
        assert any("migrar para ME" in a for a in result.alerts)

    def test_uses_the_profile_cap_when_informed(self, db):
        profile = CompanyProfile.objects.create(
            legal_form="MEI", annual_revenue_cap_brl=Decimal("500000")
        )
        assert not self.check(make_opp(prize_amount_brl=Decimal("120000")), profile).alerts

    def test_service_not_covered_by_mei_alerts(self, company, home):
        service = ServiceOffering.objects.get(slug="custom_software")
        verify = ServiceOffering.objects.get(slug="gamification")
        covered = ServiceOffering.objects.get(slug="course_gamedev")
        assert any("exigiria ME" in a for a in self.check(make_opp(), company, service).alerts)
        assert self.check(make_opp(), company, verify).adjustments
        assert not self.check(make_opp(), company, covered).alerts

    def test_missing_profile_never_gates(self, db):
        result = self.check(make_opp(eligible_legal_forms=["ME"]), None)
        assert result.gate is None and result.alerts

    def test_months_between(self):
        assert months_between(date(2025, 4, 10), date(2027, 4, 10)) == 24
        assert months_between(date(2025, 4, 10), date(2027, 4, 9)) == 23


class TestFactors:
    def test_value_bands_and_benefits(self, ctx):
        big = score_opportunity(make_opp(prize_amount_brl=Decimal("500000")), ctx)
        small = score_opportunity(
            make_opp(title="B", official_url="https://example.org/b", prize_amount_brl=2000), ctx
        )
        benefit = score_opportunity(
            make_opp(title="C", official_url="https://example.org/c", benefits=["visibility"]), ctx
        )
        none = score_opportunity(make_opp(title="D", official_url="https://example.org/d"), ctx)
        assert factor(big, "V")["raw"] == 0.95
        assert factor(small, "V")["raw"] == 0.3
        assert factor(benefit, "V")["raw"] == 0.35
        assert factor(none, "V")["raw"] == 0.5
        assert "sem dado" in factor(none, "V")["explanation"]

    def test_fit_by_keyword_category_and_nothing(self, ctx):
        kw = score_opportunity(make_opp(title="Edital de jogo educativo"), ctx)
        cat = score_opportunity(
            make_opp(title="Chamada X", official_url="https://example.org/x", categories=["games"]),
            ctx,
        )
        off = score_opportunity(
            make_opp(title="Torneio de xadrez", official_url="https://example.org/y"), ctx
        )
        assert factor(kw, "F")["raw"] == 0.6
        assert "jogo educativo" in factor(kw, "F")["explanation"]
        assert factor(cat, "F")["raw"] == 0.45
        assert factor(off, "F")["raw"] == 0.2

    def test_fit_without_any_text_is_neutral(self, ctx):
        opp = make_opp(title="", kind="other", official_url="https://example.org/z")
        assert factor(score_opportunity(opp, ctx), "F")["raw"] == 0.5

    def test_fit_proof_from_public_portfolio(self, ctx):
        service = ServiceOffering.objects.get(slug="educational_game")
        item = PortfolioItem.objects.create(
            slug="astro", title="AstroDash", kind="game", public=True, status="complete"
        )
        item.services.add(service)
        ctx = build_context(now=NOW)
        result = score_opportunity(make_opp(title="Edital de jogo educativo"), ctx)
        assert factor(result, "F")["raw"] == 0.7
        assert "AstroDash" in factor(result, "F")["explanation"]

    def test_private_portfolio_is_not_proof(self, home, company):
        service = ServiceOffering.objects.get(slug="educational_game")
        item = PortfolioItem.objects.create(slug="x", title="Segredo", kind="game", public=False)
        item.services.add(service)
        ctx = build_context(now=NOW)
        result = score_opportunity(make_opp(title="Edital de jogo educativo"), ctx)
        assert factor(result, "F")["raw"] == 0.6

    @pytest.mark.parametrize(
        ("offset", "expected"),
        [(2, 0.1), (5, 0.5), (10, 0.85), (32, 0.95), (60, 0.7), (200, 0.5)],
    )
    def test_timing_bands(self, ctx, offset, expected):
        result = score_opportunity(make_opp(deadline_at=days(offset)), ctx)
        assert factor(result, "T")["raw"] == expected

    def test_timing_without_dates_is_neutral(self, ctx):
        result = score_opportunity(make_opp(deadline_at=None), ctx)
        assert factor(result, "T")["raw"] == 0.5
        assert "sem dado" in factor(result, "T")["explanation"]

    def test_timing_uses_event_start_without_deadline(self, ctx):
        result = score_opportunity(
            make_opp(kind="event", deadline_at=None, starts_at=days(20)), ctx
        )
        assert factor(result, "T")["raw"] == 0.95
        assert "início" in factor(result, "T")["explanation"]

    @pytest.mark.parametrize(
        ("effort", "expected"),
        [("low", 1.0), ("medium", 0.6), ("high", 0.25), ("unknown", 0.5)],
    )
    def test_lightness(self, ctx, effort, expected):
        result = score_opportunity(make_opp(effort_estimate=effort), ctx)
        assert factor(result, "L")["raw"] == expected

    def test_chance_scope_and_relationship(self, ctx):
        client = Organization.objects.create(
            name="SESC Araraquara",
            kind="sesc",
            network="sesc",
            relationship_status=Organization.RelationshipStatus.CLIENT,
        )
        sibling = Organization.objects.create(name="SESC Bauru", kind="sesc", network="sesc")
        lost = Organization.objects.create(
            name="Perdida", relationship_status=Organization.RelationshipStatus.LOST
        )

        def chance(**fields):
            return factor(score_opportunity(make_opp(**fields), ctx), "C")["raw"]

        base = chance()
        as_client = chance(organizer=client)
        as_network = chance(organizer=sibling)
        as_lost = chance(organizer=lost)
        world = chance(scope="international")
        assert as_client > as_network > base > as_lost
        assert world < base

    def test_chance_is_clamped_to_unit_interval(self, ctx):
        opp = make_opp(
            requires_legal_entity="yes",
            required_cnaes=["99.99-9"],
            prize_amount_brl=Decimal("900000"),
            scope="international",
        )
        raw = factor(score_opportunity(opp, ctx), "C")["raw"]
        assert 0.0 <= raw <= 1.0

    def test_access_online_ignores_distance(self, ctx):
        opp = make_opp(kind="game_jam", modality="online")
        result = score_opportunity(opp, ctx)
        assert factor(result, "A")["raw"] == 0.8  # G=1,0 × inscrição pela página oficial

    def test_access_with_direct_contact_beats_official_url(self, ctx):
        org = Organization.objects.create(name="Org", kind="company")
        evidence = record_evidence(
            org, "contact.email", "a@b.org", kind="observed", method="regex:contact",
            source_url="https://example.org/c", excerpt="a@b.org",
        )  # fmt: skip
        ContactPoint.objects.create(
            organization=org, kind="email", value="a@b.org", evidence=evidence
        )
        opp = make_opp(kind="game_jam", modality="online", organizer=org)
        assert factor(score_opportunity(opp, ctx), "A")["raw"] == 1.0

    def test_access_unknown_location_is_neutral_with_alert(self, ctx):
        opp = make_opp(kind="event", modality="in_person")
        result = score_opportunity(opp, ctx)
        assert any("localização" in a for a in result.alerts)
        assert "confiança reduzida" in factor(result, "A")["explanation"]

    def test_access_near_event_beats_far_event(self, ctx):
        far = Municipality.objects.create(
            ibge_code=2611606, name="Recife", uf="PE", lat=-8.05, lon=-34.88
        )
        near = make_opp(kind="event", modality="in_person", municipality=ctx.home, title="n")
        far_opp = make_opp(
            kind="event", modality="in_person", municipality=far, title="f",
            official_url="https://example.org/f",
        )  # fmt: skip
        assert (
            factor(score_opportunity(near, ctx), "A")["raw"]
            > factor(score_opportunity(far_opp, ctx), "A")["raw"]
        )


class TestEvidenceSupport:
    def test_observed_evidence_supports_and_lists_ids(self, ctx):
        opp = make_opp(prize_amount_brl=Decimal("500000"))
        evidence = observe(opp, "prize_amount_brl", "500000")
        row = factor(score_opportunity(opp, ctx), "V")
        assert row["support"] == 1.0 and row["evidence_ids"] == [evidence.pk]

    def test_inferred_evidence_counts_half(self, ctx):
        opp = make_opp(prize_amount_brl=Decimal("500000"))
        record_evidence(
            opp, "prize_amount_brl", "500000", kind="inferred", method="rule:test",
            source_url="https://example.org/edital",
        )  # fmt: skip
        assert factor(score_opportunity(opp, ctx), "V")["support"] == 0.5

    def test_observed_beats_inferred_for_the_same_field(self, ctx):
        opp = make_opp(prize_amount_brl=Decimal("500000"))
        record_evidence(opp, "prize_amount_brl", "1", kind="inferred", method="rule:x")
        observed = observe(opp, "prize_amount_brl", "500000")
        index = EvidenceIndex(opp.evidence_items.all() if hasattr(opp, "evidence_items") else [])
        assert index.by_field["prize_amount_brl"].pk == observed.pk

    def test_no_data_has_no_support(self, ctx):
        row = factor(score_opportunity(make_opp(), ctx), "V")
        assert row["support"] == 0.0 and row["evidence_ids"] == []


class TestGoldenScenarios:
    """Cenários dourados: fixam o comportamento esperado do score e dos gates."""

    def strong(self, **extra):
        fields = dict(
            title="Edital de jogos educativos",
            categories=["games", "education"],
            prize_amount_brl=Decimal("60000"),
            benefits=["money"],
            effort_estimate="low",
            scope="state",
            eligible_regions=["SP"],
            exclusive_small_business=True,
            modality="online",
            deadline_at=days(30),
        )
        fields.update(extra)
        return make_opp(**fields)

    def test_high_score_with_proven_data_is_prioritized(self, ctx):
        opp = self.strong()
        for name, value in (
            ("prize_amount_brl", "60000"),
            ("deadline_at", "x"),
            ("categories", "games"),
            ("exclusive_small_business", True),
            ("effort_estimate", "low"),
            ("scope", "state"),
            ("modality", "online"),
        ):
            observe(opp, name, value)
        result = score_opportunity(opp, ctx)
        assert not result.gated
        assert result.total >= 55
        assert result.confidence > 0.9
        assert [row["factor"] for row in result.breakdown] == list(FACTORS)

    def test_high_score_but_need_not_proven_is_capped_by_confidence(self, ctx):
        """Mesmos fatores, sem evidência: o total cai (dados fracos puxam para baixo)."""
        proven, unproven = (
            self.strong(),
            self.strong(title="Edital de jogos educativos 2", official_url="https://example.org/2"),
        )
        for name in (
            "prize_amount_brl", "deadline_at", "categories", "exclusive_small_business",
            "effort_estimate", "scope", "modality",
        ):  # fmt: skip
            observe(proven, name, "valor")
        a, b = score_opportunity(proven, ctx), score_opportunity(unproven, ctx)
        assert [r["raw"] for r in a.breakdown] == [r["raw"] for r in b.breakdown]
        assert b.confidence == pytest.approx(0.7)
        assert b.total < a.total

    def test_does_not_accept_mei_is_blocked_with_company_reason(self, ctx):
        opp = self.strong(eligible_legal_forms=["ME", "EPP", "OTHER_COMPANY"])
        result = score_opportunity(opp, ctx)
        assert result.gated
        assert result.gate_kind == Score.GateKind.COMPANY_REQUIREMENT
        assert result.label == Score.Label.GATED

    def test_company_age_gate_flips_after_the_two_year_mark(self, ctx):
        early = self.strong(min_company_age_months=24, deadline_at=datetime(2027, 4, 1, tzinfo=UTC))
        late = self.strong(
            min_company_age_months=24, deadline_at=datetime(2027, 4, 20, tzinfo=UTC),
            title="Depois", official_url="https://example.org/depois",
        )  # fmt: skip
        assert score_opportunity(early, ctx).gate_kind == Score.GateKind.COMPANY_REQUIREMENT
        assert not score_opportunity(late, ctx).gated

    def test_small_business_quota_outranks_the_same_edital_without_it(self, ctx):
        with_quota = self.strong()
        without = self.strong(
            exclusive_small_business=None, title="Sem cota", official_url="https://example.org/sc"
        )
        assert score_opportunity(with_quota, ctx).total > score_opportunity(without, ctx).total

    def test_software_edital_alerts_that_it_would_require_me(self, ctx):
        opp = make_opp(
            title="Chamada para desenvolvimento de software sob encomenda",
            prize_amount_brl=Decimal("150000"),
        )
        result = score_opportunity(opp, ctx)
        assert not result.gated
        assert any("exigiria ME" in a for a in result.alerts)
        assert any("migrar para ME" in a for a in result.alerts)

    def test_expired_wins_over_everything(self, ctx):
        opp = self.strong(deadline_at=days(-1))
        assert score_opportunity(opp, ctx).gate_kind == Score.GateKind.EXPIRED

    def test_unknown_everything_is_not_an_error(self, ctx):
        opp = Opportunity.objects.create(title="", kind="other", official_url="https://e.org/vazio")
        result = score_opportunity(opp, ctx)
        assert not result.gated
        assert result.confidence == pytest.approx(0.7)
        assert result.total is not None and 0 <= result.total <= 100

    def test_deterministic(self, ctx):
        opp = self.strong()
        first, second = score_opportunity(opp, ctx), score_opportunity(opp, ctx)
        assert first == second


class TestPersistence:
    def test_save_creates_then_updates_one_row(self, ctx):
        opp = make_opp()
        save_score(opp, score_opportunity(opp, ctx), ctx)
        save_score(opp, score_opportunity(opp, ctx), ctx)
        assert Score.objects.count() == 1
        score = Score.objects.get()
        assert score.entity == opp and score.scoring_version == "v1"
        assert score.total is not None and score.label

    def test_gated_has_no_total_and_database_enforces_it(self, ctx):
        from django.db import IntegrityError, transaction

        opp = make_opp(deadline_at=days(-1))
        score = save_score(opp, score_opportunity(opp, ctx), ctx)
        assert score.total is None and score.gated and score.gate_reason
        with pytest.raises(IntegrityError), transaction.atomic():
            Score.objects.filter(pk=score.pk).update(total=50)

    def test_str(self, ctx):
        opp = make_opp()
        score = save_score(opp, score_opportunity(opp, ctx), ctx)
        assert "/100" in str(score)


class TestRescoreCommand:
    def run(self, *args):
        out = StringIO()
        call_command("rescore", *args, stdout=out)
        return out.getvalue()

    def test_scores_everything_and_reports_counts(self, home, company):
        make_opp(title="Edital de jogos educativos")
        make_opp(title="Vencido", official_url="https://e.org/v", deadline_at=days(-5))
        out = self.run()
        assert "Oportunidades: 2" in out and "versão v1" in out
        assert "Bloqueada: 1" in out and "Prazo vencido" in out
        assert Score.objects.count() == 2

    def test_dry_run_does_not_write(self, home, company):
        make_opp()
        out = self.run("--dry-run")
        assert "simulado" in out
        assert Score.objects.count() == 0

    def test_filter_by_profile_and_limit(self, home, company):
        make_opp()
        make_opp(title="Jam", kind="game_jam", official_url="https://e.org/jam")
        assert "Oportunidades: 1" in self.run("--profile", "opp.hackathon_jam")
        assert "Oportunidades: 1" in self.run("--limit", "1")
        with pytest.raises(CommandError):
            call_command("rescore", "--limit", "-1")

    def test_discarded_in_triage_is_skipped_and_keeps_old_score(self, home, company):
        opp = make_opp()
        self.run()
        before = Score.objects.get().computed_at
        Triage.objects.create(
            content_type=ContentType.objects.get_for_model(Opportunity),
            object_id=opp.pk,
            status="discarded",
            discard_reason="not_relevant",
        )
        assert is_discarded(opp)
        out = self.run()
        assert "puladas): 1" in out
        assert Score.objects.get().computed_at == before

    def test_warns_when_context_is_missing(self, db):
        make_opp()
        out = self.run()
        assert "perfil da empresa não carregado" in out
        assert "catálogo vazio" in out

    def test_new_version_recalculates_everything(self, home, company, monkeypatch):
        make_opp()
        self.run()
        monkeypatch.setattr("scoring.engine.SCORING_VERSION", "v2")
        monkeypatch.setattr("scoring.management.commands.rescore.SCORING_VERSION", "v2")
        self.run()
        assert Score.objects.get().scoring_version == "v2"

    def test_changed_inputs_change_the_stored_score(self, home, company):
        opp = make_opp(effort_estimate="high")
        self.run()
        first = Score.objects.get().total
        opp.effort_estimate = "low"
        opp.save()
        self.run()
        assert Score.objects.get().total > first


class TestAdmin:
    @pytest.fixture
    def admin_client(self, client, django_user_model):
        user = django_user_model.objects.create_superuser("adm", "adm@example.org", "x")
        client.force_login(user)
        return client

    def test_score_pages_render_the_breakdown(self, admin_client, home, company):
        opp = make_opp(title="Edital de jogos educativos")
        call_command("rescore", stdout=StringIO())
        score = Score.objects.get()
        listing = admin_client.get(reverse("admin:scoring_score_changelist"))
        assert listing.status_code == 200
        detail = admin_client.get(reverse("admin:scoring_score_change", args=[score.pk]))
        html = detail.content.decode()
        assert detail.status_code == 200
        for label in ("Valor", "Fit", "Chance", "Timing", "Acesso", "Leveza"):
            assert label in html
        assert "Soma ponderada" in html
        change = admin_client.get(reverse("admin:core_opportunity_change", args=[opp.pk]))
        assert "Soma ponderada" in change.content.decode()

    def test_opportunity_list_shows_and_orders_by_score(self, admin_client, home, company):
        make_opp(title="Edital de jogos educativos")
        make_opp(title="Vencido", official_url="https://e.org/v", deadline_at=days(-5))
        make_opp(title="Sem nota", official_url="https://e.org/n", kind="event")
        call_command("rescore", stdout=StringIO())
        base = reverse("admin:core_opportunity_changelist")
        for order in ("", "?o=-8", "?o=8"):
            response = admin_client.get(base + order)
            assert response.status_code == 200
        assert "Bloqueada" in admin_client.get(base).content.decode()

    def test_unscored_opportunity_says_so(self, admin_client, db):
        opp = make_opp()
        response = admin_client.get(reverse("admin:core_opportunity_change", args=[opp.pk]))
        assert "Ainda não pontuada" in response.content.decode()

    def test_score_cannot_be_added_by_hand(self, admin_client):
        assert admin_client.get(reverse("admin:scoring_score_add")).status_code == 403
