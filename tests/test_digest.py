"""E15: digest semanal."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from collection.models import CollectionRun
from core.models import Interaction, Opportunity, Organization, Source, Triage
from core.services.triage import triage_entities
from llm.models import LLMCall
from reports import digest
from scoring.models import Score

pytestmark = pytest.mark.django_db

CT = lambda: ContentType.objects.get_for_model(Opportunity)  # noqa: E731


def opp(title, total=80, *, label="prioritize", deadline_days=None, **kw):
    o = Opportunity.objects.create(
        title=title,
        deadline_at=timezone.now() + timedelta(days=deadline_days) if deadline_days else None,
        **kw,
    )
    Score.objects.create(
        content_type=CT(),
        object_id=o.pk,
        profile="opp.edital",
        scoring_version="t",
        total=total,
        label=label,
        confidence=0.9,
        breakdown=[
            {"factor": "F1", "label": "Prazo", "points": 20, "explanation": "tem tempo"},
            {"factor": "F2", "label": "Local", "points": 30, "explanation": "perto"},
            {"factor": "F3", "label": "Valor", "points": 5, "explanation": "baixo"},
        ],
        alerts=["exige ME"] if total == 55 else [],
    )
    return o


def gated(title, kind="company_requirement", amount=None):
    o = Opportunity.objects.create(title=title, prize_amount_brl=amount)
    Score.objects.create(
        content_type=CT(),
        object_id=o.pk,
        profile="opp.edital",
        scoring_version="t",
        label="gated",
        gated=True,
        gate_kind=kind,
        gate_reason="exige 2 anos de CNPJ",
    )
    return o


def titles(rows):
    return [r["title"] for r in rows]


class TestSections:
    def test_top_orders_by_score_and_hides_gated_discarded_done(self, admin_user):
        a, b = opp("A", 90), opp("B", 70)
        gone, finished = opp("Descartada", 99), opp("Concluida", 98)
        gated("Bloqueada")
        triage_entities([gone], Triage.Status.DISCARDED, admin_user, reason="not_relevant")
        triage_entities([finished], Triage.Status.DONE, admin_user)
        d = digest.build()
        assert titles(d.top) == ["A", "B"]
        assert a and b

    def test_top_limited_and_why_line(self):
        for i in range(15):
            opp(f"O{i}", 60 + i)
        top = digest.build().top
        assert len(top) == digest.TOP_N
        assert top[0]["why"].startswith("Local: perto · Prazo: tem tempo")
        assert top[0]["admin_url"].endswith("/change/")

    def test_alert_in_why(self):
        opp("Com alerta", 55)
        assert "⚠ exige ME" in digest.build().top[0]["why"]

    def test_deadlines_window_and_exclusions(self, admin_user):
        opp("Perto", deadline_days=5)
        opp("Longe", deadline_days=40)
        opp("Sem prazo")
        gone = opp("Descartada", deadline_days=3)
        triage_entities([gone], Triage.Status.DISCARDED, admin_user, reason="not_relevant")
        opp("Passado", deadline_days=-2)
        assert titles(digest.build().deadlines) == ["Perto"]

    def test_new_since_last_digest(self):
        old = opp("Velha")
        Opportunity.objects.filter(pk=old.pk).update(
            first_seen_at=timezone.now() - timedelta(days=10)
        )
        opp("Nova")
        gated("Bloqueada nova")
        d = digest.build(since=timezone.now() - timedelta(days=3))
        assert titles(d.new["rows"]) == ["Nova"] and d.new["total"] == 1

    def test_blocked_by_requirement_sums_value(self, admin_user):
        gated("Grande", amount=Decimal("50000"))
        gated("Pequena", amount=Decimal("10000.50"))
        gated("Sem valor")
        gated("Território", kind="territory", amount=Decimal("999"))
        gone = gated("Descartada", amount=Decimal("1"))
        triage_entities([gone], Triage.Status.DISCARDED, admin_user, reason="not_relevant")
        b = digest.build().blocked
        assert (b["total"], b["amount"], b["with_value"]) == (3, Decimal("60000.50"), 2)
        assert titles(b["rows"]) == ["Grande", "Pequena", "Sem valor"]

    def test_follow_ups(self):
        today = timezone.localdate()
        late = Organization.objects.create(
            name="Atrasada", next_action_at=today - timedelta(days=9)
        )
        Organization.objects.create(name="Em breve", next_action_at=today + timedelta(days=3))
        Organization.objects.create(name="Longe", next_action_at=today + timedelta(days=30))
        Organization.objects.create(name="Sem ação")
        Interaction.objects.create(
            organization=late,
            kind=Interaction.Kind.PROPOSAL_SENT,
            occurred_at=today - timedelta(days=20),
            summary="x" * 500,
        )
        Organization.objects.filter(pk=late.pk).update(next_action_at=today - timedelta(days=9))
        f = digest.build().follow_ups
        assert [r["name"] for r in f["rows"]] == ["Atrasada", "Em breve"]
        assert f["rows"][0]["overdue_days"] == 9
        assert len(f["rows"][0]["summary"]) == digest.SUMMARY_CHARS

    def test_sources_errors_and_stale(self):
        now = timezone.now()
        ok = Source.objects.create(slug="ok", name="ok", kind="api", enabled=True)
        bad = Source.objects.create(slug="bad", name="bad", kind="api", enabled=True)
        old = Source.objects.create(slug="old", name="old", kind="api", enabled=True)
        Source.objects.create(slug="off", name="off", kind="api", enabled=False)
        CollectionRun.objects.create(source=ok, status="ok")
        CollectionRun.objects.create(source=bad, status="error")
        CollectionRun.objects.create(source=old, status="ok", started_at=now - timedelta(days=12))
        s = digest.build(now=now).sources
        assert [p[0] for p in s["problems"]] == ["bad"]
        assert s["stale"] == [("old", "última coleta há 12 dias")]

    def test_costs_this_month_only(self):
        kw = dict(
            task="t", strategy="p:m", provider="p", model="m", data_class="public", status="ok"
        )
        LLMCall.objects.create(billing="money", cost_usd="0.30", **kw)
        LLMCall.objects.create(billing="credits", cost_usd="1.20", **kw)
        old = LLMCall.objects.create(billing="money", cost_usd="9", **kw)
        LLMCall.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=45))
        c = digest.build().costs
        assert (c["money"], c["credits"], c["calls"]) == (Decimal("0.30"), Decimal("1.20"), 2)

    def test_empty_database_renders(self):
        d = digest.build()
        assert "Nenhum follow-up" in digest.render_markdown(d)
        assert "Nenhuma oportunidade pontuada" in digest.render_html(d)


class TestOutput:
    def test_html_escapes_and_links(self):
        opp("<script>x</script>", official_url="https://exemplo.org/edital")
        html = digest.render_html(digest.build())
        assert "<script>x" not in html and "&lt;script&gt;" in html
        assert 'href="https://exemplo.org/edital"' in html and "/admin/core/opportunity/" in html

    def test_command_writes_files_and_state(self, tmp_path, capsys):
        opp("A")
        call_command("digest", out=str(tmp_path))
        week = digest.week_label(timezone.now())
        assert (tmp_path / f"{week}.html").exists() and (tmp_path / f"{week}.md").exists()
        assert digest.read_state(tmp_path) is not None

    def test_dry_run_writes_nothing(self, tmp_path, capsys):
        opp("A")
        call_command("digest", out=str(tmp_path), dry_run=True)
        assert list(tmp_path.iterdir()) == []
        assert "# Digest semanal" in capsys.readouterr().out

    def test_second_run_only_news_since_first(self, tmp_path):
        opp("A")
        call_command("digest", out=str(tmp_path))
        since = digest.read_state(tmp_path)
        assert digest.build(since=since).new["total"] == 0


class TestEmail:
    def test_requires_recipient_list(self, settings):
        settings.DIGEST_EMAIL_TO = []
        with pytest.raises(digest.EmailNotAllowed):
            digest.team_recipients()

    def test_command_refuses_before_generating(self, settings, tmp_path):
        settings.DIGEST_EMAIL_TO = []
        with pytest.raises(CommandError, match="DIGEST_EMAIL_TO"):
            call_command("digest", out=str(tmp_path), email=True)
        assert list(tmp_path.iterdir()) == []

    def test_sends_to_configured_list(self, settings, tmp_path):
        settings.DIGEST_EMAIL_TO = ["equipe@example.org", "membro@example.net"]
        settings.DIGEST_EMAIL_FROM = "radar@example.org"
        opp("A")
        call_command("digest", out=str(tmp_path), email=True)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["equipe@example.org", "membro@example.net"]
        assert mail.outbox[0].alternatives

    def test_sender_falls_back_to_smtp_user(self, settings):
        settings.DIGEST_EMAIL_TO = ["equipe@example.org"]
        settings.DIGEST_EMAIL_FROM = ""
        settings.EMAIL_HOST_USER = "conta@example.org"
        digest.send_email(digest.build())
        assert mail.outbox[0].from_email == "conta@example.org"

    def test_requires_sender(self, settings):
        settings.DIGEST_EMAIL_TO = ["equipe@example.org"]
        settings.DIGEST_EMAIL_FROM = ""
        settings.EMAIL_HOST_USER = ""
        with pytest.raises(digest.EmailNotAllowed):
            digest.send_email(digest.build())
