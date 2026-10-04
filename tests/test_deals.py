"""E23 — pipeline leve: negócios, estágios, ritmo de follow-up, funil e opt-out."""

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from core.models import Deal, Interaction, Organization, Suppression
from core.services.pipeline import (
    FOLLOW_UP_INTERVAL_DAYS,
    advance_stage,
    deals_needing_follow_up,
    follow_up_state,
    funnel,
)
from core.services.suppression import register_opt_out
from reports.metrics import render_funnel

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 20)
K = Interaction.Kind
S = Deal.Stage


def touch(deal, kind=K.MESSAGE, days_ago=0, **extra):
    return Interaction.objects.create(
        organization=deal.organization,
        deal=deal,
        kind=kind,
        occurred_at=TODAY - timedelta(days=days_ago),
        **extra,
    )


@pytest.fixture
def deal(organization):
    return Deal.objects.create(organization=organization, stage=S.CONTACTED)


class TestStages:
    def test_walks_the_whole_funnel(self, deal):
        seen = [deal.stage]
        while (nxt := advance_stage(deal)) is not None:
            deal.stage = nxt
            deal.save()
            seen.append(deal.stage)
        assert seen == [
            "contacted", "responded", "meeting", "proposal", "negotiation", "won"
        ]  # fmt: skip
        assert deal.closed_at is not None and not deal.is_open
        assert advance_stage(deal) is None

    def test_peak_stage_survives_loss_and_never_goes_back(self, deal):
        deal.stage = S.PROPOSAL
        deal.save()
        deal.stage = S.RESPONDED  # voltar atrás não apaga o que já foi alcançado
        deal.save()
        assert deal.peak_stage == S.PROPOSAL
        deal.stage, deal.lost_reason = S.LOST, Deal.LostReason.NO_BUDGET
        deal.save()
        assert deal.peak_stage == S.PROPOSAL and deal.closed_at is not None

    def test_lost_needs_a_reason_and_reason_clears_on_reopen(self, deal):
        deal.stage = S.LOST
        with pytest.raises(ValidationError):
            deal.full_clean()
        deal.lost_reason = Deal.LostReason.NOT_NOW
        deal.save()
        deal.stage = S.CONTACTED
        deal.save()
        assert deal.lost_reason == "" and deal.closed_at is None

    def test_interaction_must_belong_to_the_same_organization(self, deal):
        other = Organization.objects.create(name="Outra Escola", kind="school")
        item = Interaction(organization=other, deal=deal, kind=K.MESSAGE)
        with pytest.raises(ValidationError) as err:
            item.full_clean()
        assert "deal" in err.value.message_dict


class TestFollowUpRhythm:
    def test_no_contact_yet(self, deal):
        assert follow_up_state(deal, TODAY).state == "no_contact"

    def test_waits_until_the_interval_passes(self, deal):
        touch(deal, days_ago=FOLLOW_UP_INTERVAL_DAYS - 1)
        st = follow_up_state(deal, TODAY)
        assert st.state == "wait" and not st.needs_attention
        assert st.next_at == TODAY + timedelta(days=1)

    def test_first_follow_up_becomes_due(self, deal):
        touch(deal, days_ago=FOLLOW_UP_INTERVAL_DAYS + 2)
        st = follow_up_state(deal, TODAY)
        assert st.state == "due" and st.follow_ups == 0
        assert "follow-up 1 devido há 2 dia(s)" in st.message

    def test_limit_after_two_follow_ups_without_answer(self, deal):
        for ago in (20, 13, 7):  # contato + 2 follow-ups
            touch(deal, days_ago=ago)
        st = follow_up_state(deal, TODAY)
        assert st.state == "limit" and st.follow_ups == 2 and st.needs_attention

    def test_second_follow_up_still_allowed(self, deal):
        for ago in (14, 8):
            touch(deal, days_ago=ago)
        st = follow_up_state(deal, TODAY)
        assert st.state == "due" and st.follow_ups == 1

    def test_an_answer_resets_the_count(self, deal):
        for ago in (30, 23, 16):
            touch(deal, days_ago=ago)
        touch(deal, K.RESPONSE_RECEIVED, days_ago=10)
        assert follow_up_state(deal, TODAY).state == "replied"
        touch(deal, days_ago=9)  # nova tentativa depois da resposta: conta do zero
        st = follow_up_state(deal, TODAY)
        assert st.state == "due" and st.attempts == 1 and st.follow_ups == 0

    def test_undated_interactions_are_ignored(self, deal):
        Interaction.objects.create(
            organization=deal.organization, deal=deal, kind=K.MESSAGE, occurred_at=None
        )
        assert follow_up_state(deal, TODAY).state == "no_contact"

    def test_closed_deal_has_no_rhythm(self, deal):
        touch(deal, days_ago=30)
        deal.stage = S.WON
        deal.save()
        assert follow_up_state(deal, TODAY).state == "closed"
        assert deals_needing_follow_up(TODAY) == []

    def test_listing_orders_most_overdue_first(self, deal, db):
        other = Deal.objects.create(
            organization=Organization.objects.create(name="Escola B", kind="school"),
            stage=S.CONTACTED,
        )
        touch(deal, days_ago=9)
        touch(other, days_ago=20)
        assert [d for d, _ in deals_needing_follow_up(TODAY)] == [other, deal]


class TestFunnelAndMetrics:
    def test_empty(self):
        assert funnel()["total"] == 0
        assert "sem negócios" in render_funnel(funnel())

    def test_reached_counts_lost_up_to_their_peak(self, organization):
        def make(stage, **kw):
            return Deal.objects.create(organization=organization, stage=stage, **kw)

        make(S.INTERESTING)
        make(S.MEETING, estimated_value=1000)
        won = make(S.PROPOSAL, estimated_value=3000)
        won.stage = S.WON
        won.save()
        lost = make(S.PROPOSAL)
        lost.stage, lost.lost_reason = S.LOST, Deal.LostReason.NO_RESPONSE
        lost.save()
        data = funnel()
        assert data["total"] == 4
        assert data["reached"]["interesting"] == 4
        assert data["reached"]["meeting"] == 3  # reunião, ganho (passou), perdido na proposta
        assert data["reached"]["proposal"] == 2
        assert data["reached"]["won"] == 1
        assert data["current"]["lost"] == 1 and data["open_value"] == 1000
        assert data["won_value"] == 3000
        text = render_funnel(data, due=2)
        assert "alcançaram 3" in text and "devidos ou no limite: 2" in text

    def test_metrics_command_prints_funnel(self, deal):
        out = StringIO()
        call_command("metrics", stdout=out)
        assert "Funil: 1 negócios" in out.getvalue()

    def test_pipeline_does_not_enter_go_no_go_metrics(self, deal):
        from reports import metrics

        assert [m.code for m in metrics.compute()] == [f"M{i}" for i in range(1, 10)]


class TestOptOut:
    def test_registers_suppression_and_closes_open_deals(self, organization, deal):
        won = Deal.objects.create(organization=organization, stage=S.WON)
        register_opt_out(organization, "pediu por e-mail")
        register_opt_out(organization)  # idempotente
        organization.refresh_from_db()
        assert organization.relationship_status == "do_not_contact"
        assert Suppression.objects.filter(kind="organization").count() == 1
        deal.refresh_from_db()
        assert deal.stage == S.LOST and deal.lost_reason == Deal.LostReason.OPT_OUT
        won.refresh_from_db()
        assert won.stage == S.WON

    def test_opt_out_survives_a_new_interaction(self, organization):
        register_opt_out(organization)
        Interaction.objects.create(organization=organization, kind=K.MESSAGE)
        organization.refresh_from_db()
        assert organization.relationship_status == "do_not_contact"


class TestAdmin:
    @pytest.fixture
    def client_admin(self, client, django_user_model):
        user = django_user_model.objects.create_superuser("adm", "a@example.org", "x")
        client.force_login(user)
        return client

    def test_changelist_filters_and_actions(self, client_admin, deal):
        Interaction.objects.create(
            organization=deal.organization,
            deal=deal,
            kind=K.MESSAGE,
            occurred_at=timezone.localdate() - timedelta(days=10),
        )
        url = reverse("admin:core_deal_changelist")
        for query in ("", "?ritmo=attention", "?ritmo=open", "?ritmo=closed", "?stage=won"):
            assert client_admin.get(url + query).status_code == 200
        page = client_admin.get(url + "?ritmo=attention").content.decode()
        assert "follow-up 1 devido" in page
        client_admin.post(url, {"action": "advance", "_selected_action": [deal.pk]})
        deal.refresh_from_db()
        assert deal.stage == S.RESPONDED
        client_admin.post(url, {"action": "win", "_selected_action": [deal.pk]})
        deal.refresh_from_db()
        assert deal.stage == S.WON

    def test_organization_opt_out_action(self, client_admin, organization, deal):
        url = reverse("admin:core_organization_changelist")
        client_admin.post(url, {"action": "opt_out", "_selected_action": [organization.pk]})
        assert Suppression.objects.filter(kind="organization").exists()
        deal.refresh_from_db()
        assert deal.stage == S.LOST
