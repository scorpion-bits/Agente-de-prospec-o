"""E22: relatório de go/no-go (prontidão, sugestão por regras, comando)."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.utils import timezone

from core.models import Opportunity, Triage
from reports import evaluation as ev

pytestmark = pytest.mark.django_db


def triaged(n, status, days_ago=0, prefix="Jam"):
    ct = ContentType.objects.get_for_model(Opportunity)
    for i in range(n):
        opp = Opportunity.objects.create(
            title=f"{prefix} {status} {i}", kind=Opportunity.Kind.GAME_JAM
        )
        Triage.objects.update_or_create(
            content_type=ct,
            object_id=opp.pk,
            defaults={
                "status": status,
                "decided_at": timezone.now() - timedelta(days=days_ago),
                **({"discard_reason": "irrelevant"} if status == Triage.Status.DISCARDED else {}),
            },
        )


def m(code, ok, value=1):
    from reports.metrics import Metric

    return Metric(code, code, value, "meta", ok=ok)


class TestReadiness:
    def test_empty_database_is_not_ready(self):
        r = ev.readiness(timezone.now())
        assert (r.ready, r.days, r.decided) == (False, None, 0)
        assert any("nenhum uso real" in x for x in r.reasons)

    def test_short_period_is_not_ready(self):
        triaged(25, Triage.Status.INTERESTING, days_ago=10)
        r = ev.readiness(timezone.now())
        assert not r.ready and r.days == 10 and any("mínimo 28" in x for x in r.reasons)

    def test_few_triages_is_not_ready(self):
        triaged(5, Triage.Status.INTERESTING, days_ago=40)
        r = ev.readiness(timezone.now())
        assert not r.ready and any("5 triagens" in x for x in r.reasons)

    def test_enough_use_is_ready(self):
        triaged(25, Triage.Status.INTERESTING, days_ago=40)
        assert ev.readiness(timezone.now()).ready


class TestSuggest:
    ready = ev.Readiness(40, 30, True, [])

    def test_not_ready_extends_whatever_the_metrics(self):
        r = ev.Readiness(3, 1, False, ["pouco uso"])
        decision, why = ev.suggest(r, [m("M1", True), m("M2", True), m("M4", True)])
        assert decision == ev.EXTEND and why

    def test_all_core_ok_continues(self):
        metrics = [m("M1", True), m("M2", True), m("M4", True), m("M5", None), m("M9", True)]
        assert ev.suggest(self.ready, metrics)[0] == ev.CONTINUE

    def test_secondary_failure_adjusts(self):
        metrics = [m("M1", True), m("M2", True), m("M4", True), m("M7", False, 30)]
        decision, why = ev.suggest(self.ready, metrics)
        assert decision == ev.ADJUST and "M7" in why[0]

    def test_all_core_failing_stops(self):
        metrics = [m("M1", False), m("M2", False), m("M4", False)]
        assert ev.suggest(self.ready, metrics)[0] == ev.STOP

    def test_core_without_data_extends(self):
        metrics = [m("M1", True), m("M2", None), m("M4", True)]
        decision, why = ev.suggest(self.ready, metrics)
        assert decision == ev.EXTEND and "M2" in why[0]

    def test_one_core_failing_adjusts(self):
        metrics = [m("M1", True), m("M2", False), m("M4", True)]
        assert ev.suggest(self.ready, metrics)[0] == ev.ADJUST


class TestManualInputs:
    def test_m3_and_m6_set_value_and_verdict(self):
        metrics = ev.apply_manual([m("M3", None, None), m("M6", None, None)], 6, 45)
        by = {x.code: x for x in metrics}
        assert (by["M3"].value, by["M3"].ok) == (6, True)
        assert (by["M6"].value, by["M6"].ok) == (45, False)

    def test_without_inputs_nothing_changes(self):
        metrics = ev.apply_manual([m("M3", None, None), m("M6", None, None)])
        assert all(x.ok is None and x.value is None for x in metrics)


class TestBuildAndCommand:
    def test_empty_database_suggests_extending(self):
        result = ev.build()
        assert result.suggestion == ev.EXTEND
        assert "Estender o período" in ev.render_markdown(result)

    def test_command_writes_report_without_contact_data(self, tmp_path):
        triaged(25, Triage.Status.INTERESTING, days_ago=40)
        call_command("evaluate", "--out", str(tmp_path), "--m3", "6", "--m6", "20")
        (path,) = list(tmp_path.glob("*.md"))
        text = path.read_text(encoding="utf-8")
        assert "## Prontidão" in text and "M3" in text and "@" not in text

    def test_dry_run_prints_and_writes_nothing(self, tmp_path, capsys):
        call_command("evaluate", "--out", str(tmp_path), "--dry-run")
        assert "Avaliação do MVP" in capsys.readouterr().out
        assert not list(tmp_path.iterdir())
