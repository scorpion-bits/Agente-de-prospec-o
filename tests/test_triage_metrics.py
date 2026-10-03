"""E14: triagem em massa no admin e métricas M1–M9."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from collection.models import CollectionRun
from core.models import Opportunity, Organization, Source, Triage
from core.services.triage import triage_entities
from llm.models import LLMCall
from reports import metrics
from scoring.models import Score

pytestmark = pytest.mark.django_db

CT = lambda: ContentType.objects.get_for_model(Opportunity)  # noqa: E731


def make_opps(n, prefix="Jam"):
    return [
        Opportunity.objects.create(title=f"{prefix} {i}", kind=Opportunity.Kind.GAME_JAM)
        for i in range(n)
    ]


def triage_of(opp):
    return Triage.objects.get(content_type=CT(), object_id=opp.pk)


def changelist():
    return reverse("admin:core_opportunity_changelist")


class TestService:
    def test_records_author_and_date(self, admin_user):
        (opp,) = make_opps(1)
        triage_entities([opp], Triage.Status.INTERESTING, admin_user)
        t = triage_of(opp)
        assert (t.status, t.decided_by, t.decided_at is not None) == (
            "interesting",
            admin_user,
            True,
        )

    def test_discard_requires_reason(self, admin_user):
        (opp,) = make_opps(1)
        with pytest.raises(ValueError):
            triage_entities([opp], Triage.Status.DISCARDED, admin_user)

    def test_reason_is_cleared_when_reopened_and_new_resets_decision(self, admin_user):
        (opp,) = make_opps(1)
        triage_entities([opp], Triage.Status.DISCARDED, admin_user, reason="too_far", note="longe")
        triage_entities([opp], Triage.Status.INTERESTING, admin_user)
        t = triage_of(opp)
        assert (t.discard_reason, t.note) == ("", "longe")
        triage_entities([opp], Triage.Status.NEW, admin_user)
        t.refresh_from_db()
        assert (t.status, t.decided_by, t.decided_at) == ("new", None, None)


class TestAdmin:
    def post_action(self, client, action, opps, **extra):
        return client.post(
            changelist(),
            {"action": action, "_selected_action": [o.pk for o in opps], **extra},
            follow=True,
        )

    def test_bulk_actions_change_status(self, admin_client, admin_user):
        opps = make_opps(3)
        self.post_action(admin_client, "mark_interesting", opps[:2])
        self.post_action(admin_client, "mark_acting", opps[2:])
        assert [triage_of(o).status for o in opps] == ["interesting", "interesting", "acting"]
        assert triage_of(opps[0]).decided_by == admin_user

    def test_discard_asks_for_reason_then_saves(self, admin_client):
        opps = make_opps(2)
        response = self.post_action(admin_client, "discard", opps)
        assert "Motivo" in response.content.decode()
        assert not Triage.objects.exists()
        self.post_action(admin_client, "discard", opps, apply="1", reason="too_far", note="")
        assert {triage_of(o).discard_reason for o in opps} == {"too_far"}

    def test_discard_without_valid_reason_does_nothing(self, admin_client):
        opps = make_opps(1)
        self.post_action(admin_client, "discard", opps, apply="1", reason="")
        assert not Triage.objects.exists()

    def test_untriaged_filter_and_column(self, admin_client, admin_user):
        a, b, c = make_opps(3)
        triage_entities([a], Triage.Status.INTERESTING, admin_user)
        Triage.objects.create(content_type=CT(), object_id=b.pk)  # nova = não triada
        html = admin_client.get(changelist(), {"triage": "untriaged"}).content.decode()
        assert "Jam 1" in html and "Jam 2" in html and "Jam 0" not in html
        html = admin_client.get(changelist(), {"triage": "interesting"}).content.decode()
        assert "Jam 0" in html and "Jam 1" not in html
        assert "Interessante" in html

    def test_changelist_query_count_is_flat(self, admin_client, django_assert_max_num_queries):
        make_opps(15)
        with django_assert_max_num_queries(20):
            admin_client.get(changelist())


class TestMetrics:
    def score(self, opp, total, gated=False):
        Score.objects.create(
            content_type=CT(),
            object_id=opp.pk,
            profile="opp.jam",
            scoring_version="v1",
            total=None if gated else total,
            label="gated" if gated else "evaluate",
            gated=gated,
            gate_kind="expired" if gated else "",
            gate_reason="x" if gated else "",
        )

    def by_code(self):
        return {m.code: m for m in metrics.compute()}

    def test_everything_empty_is_no_data(self):
        m = self.by_code()
        assert m["M1"].value is None and m["M2"].value is None and m["M7"].value is None
        assert m["M9"].value == 0 and m["M9"].ok is True
        assert "sem dados" in metrics.render(metrics.compute(), metrics.triage_backlog())

    def test_m1_m4_count_decisions_in_window(self, admin_user):
        opps = make_opps(4)
        triage_entities(opps[:3], Triage.Status.INTERESTING, admin_user)
        triage_entities(opps[3:], Triage.Status.ACTING, admin_user)
        old = triage_of(opps[0])
        old.decided_at = timezone.now() - timedelta(days=60)
        old.save()
        m = self.by_code()
        assert (
            m["M1"].value == 0.8 and "3 nos" in m["M1"].detail
        )  # 3 aceitas (2 + 1 em andamento) em 4 semanas
        assert m["M4"].value == 1

    def test_m2_precision_among_triaged_top(self, admin_user):
        opps = make_opps(4)
        for i, o in enumerate(opps):
            self.score(o, 90 - i)
        gated = make_opps(1, prefix="Bloq")[0]
        self.score(gated, 0, gated=True)
        triage_entities(opps[:1], Triage.Status.INTERESTING, admin_user)
        triage_entities(opps[1:2], Triage.Status.DISCARDED, admin_user, reason="not_relevant")
        precision, top, decided = metrics.top_precision()
        assert (precision, top, decided) == (0.5, 4, 2)
        assert self.by_code()["M2"].ok is True

    def test_m5_counts_only_paid_calls(self, admin_user):
        (opp,) = make_opps(1)
        triage_entities([opp], Triage.Status.INTERESTING, admin_user)
        for billing, cost in (("money", "0.30"), ("free", "5")):
            LLMCall.objects.create(
                task="t",
                strategy="s",
                provider="p",
                model="m",
                billing=billing,
                data_class="public",
                status="ok",
                cost_usd=Decimal(cost),
            )
        assert self.by_code()["M5"].value == Decimal("0.30")

    def test_m7_ignores_dry_runs(self):
        source = Source.objects.create(slug="s1", name="S1", kind="opportunity")
        for status, dry in (("ok", False), ("error", False), ("error", True)):
            CollectionRun.objects.create(source=source, status=status, dry_run=dry)
        m = self.by_code()["M7"]
        assert m.value == 50 and m.ok is False and "s1 1/2" in m.detail

    def test_m8_distribution_and_m9_overdue(self, admin_user):
        opps = make_opps(3)
        triage_entities(opps[:2], Triage.Status.DISCARDED, admin_user, reason="too_far")
        triage_entities(opps[2:], Triage.Status.DISCARDED, admin_user, reason="low_value")
        assert metrics.discard_reasons()[0] == ("Longe demais", 2)
        today = timezone.localdate()
        Organization.objects.create(name="A", next_action_at=today - timedelta(days=10))
        Organization.objects.create(name="B", next_action_at=today - timedelta(days=3))
        assert metrics.overdue_follow_ups(today) == 1

    def test_command_prints_report(self, capsys):
        make_opps(2)
        call_command("metrics")
        out = capsys.readouterr().out
        assert "2 não triadas" in out and "M9" in out
