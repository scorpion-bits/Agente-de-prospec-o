"""E30: calibração de pesos (amostra, AUC, proposta, simulação, comando)."""

import itertools

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.utils import timezone

from core.models import Opportunity, Triage
from reports import calibration as cal
from scoring.models import Score
from scoring.profiles import FACTORS, WEIGHTS

pytestmark = pytest.mark.django_db
PROFILE = "opp.hackathon_jam"
_ids = itertools.count()


def add(status, raws, *, reason="", gated=False, profile=PROFILE):
    opp = Opportunity.objects.create(title=f"Jam {next(_ids)}", kind=Opportunity.Kind.GAME_JAM)
    ct = ContentType.objects.get_for_model(Opportunity)
    Triage.objects.create(
        content_type=ct,
        object_id=opp.pk,
        status=status,
        discard_reason=reason,
        decided_at=timezone.now(),
    )
    breakdown = [{"factor": f, "raw": raws.get(f, 0.5), "support": 1} for f in FACTORS]
    Score.objects.create(
        content_type=ct,
        object_id=opp.pk,
        profile=profile,
        scoring_version="v1",
        total=None if gated else 50,
        label="gated" if gated else "evaluate",
        gated=gated,
        gate_kind="expired" if gated else "",
        gate_reason="x" if gated else "",
        breakdown=[] if gated else breakdown,
    )
    return opp


def fill(pos=12, neg=12):
    """Fit (F) separa bem; Valor (V) não separa nada."""
    for i in range(pos):
        add(Triage.Status.INTERESTING, {"F": 0.9, "V": 0.2 + 0.05 * (i % 4)})
    for i in range(neg):
        add(Triage.Status.DISCARDED, {"F": 0.2, "V": 0.2 + 0.05 * (i % 4)}, reason="not_relevant")


def test_auc_basics():
    assert cal.auc([1, 2], [0, 0]) == 1.0
    assert cal.auc([0], [1]) == 0.0
    assert cal.auc([1], [1]) == 0.5
    assert cal.auc([], [1]) is None


def test_empty_database_is_not_ready():
    c = cal.build()
    assert (c.sample, c.ready) == (0, False) and c.profiles == []
    text = cal.render_markdown(c, timezone.now())
    assert "Pronto para calibrar: não" in text and "nada a comparar" in text


def test_sample_ignores_gated_duplicates_and_undecided():
    add(Triage.Status.INTERESTING, {}, gated=True)
    add(Triage.Status.DISCARDED, {}, reason="duplicate")
    add(Triage.Status.DISCARDED, {}, reason="bad_data")
    add(Triage.Status.NEW, {})
    add(Triage.Status.ACTING, {})
    c = cal.build()
    assert (c.sample, c.positives, c.negatives) == (1, 1, 0)


def test_small_profile_gets_no_proposal():
    fill(3, 3)
    r = cal.build().profiles[0]
    assert not r.enough and r.new_weights == {}
    assert "sem proposta" in cal.render_markdown(cal.build(), timezone.now())


def test_proposal_raises_separating_factor_and_sums_to_one():
    fill(26, 26)
    c = cal.build()
    assert c.ready
    r = c.profiles[0]
    stats = {s.factor: s for s in r.stats}
    assert stats["F"].auc == 1.0 and stats["V"].auc == 0.5
    assert r.new_weights["F"] > WEIGHTS[PROFILE]["F"]
    assert abs(sum(r.new_weights.values()) - 1) < 0.01
    # limite de ±25% relativo (antes de normalizar): nenhum peso dobra
    assert all(r.new_weights[f] <= WEIGHTS[PROFILE][f] * 1.4 for f in FACTORS)
    assert r.after["auc"] >= r.before["auc"]


def test_total_with_matches_engine_formula():
    fill(1, 1)
    item = cal.collect()[PROFILE][0]
    # raw 0,5 em tudo (F=0,9) com suporte total: K=1
    expected = round(100 * sum(item.raw[f] * WEIGHTS[PROFILE][f] for f in FACTORS))
    assert cal.total_with(WEIGHTS[PROFILE], item) == expected


def test_command_writes_file_and_dry_run_does_not(tmp_path, capsys):
    fill()
    call_command("calibrate", "--dry-run", "--out", str(tmp_path))
    assert "Calibração de pesos" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())
    call_command("calibrate", "--out", str(tmp_path))
    (f,) = tmp_path.iterdir()
    assert "Perfil `opp.hackathon_jam`" in f.read_text(encoding="utf-8")
