"""E16: run_pipeline, workflows e scripts de backup."""

import re
import subprocess
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def calls(monkeypatch):
    """Substitui call_command do pipeline; `fail` mapeia comando → exceção a lançar."""
    made, fail = [], {}

    def fake(command, *args, **kwargs):
        made.append((command, list(args)))
        if command in fail:
            raise fail[command]

    monkeypatch.setattr("radar.management.commands.run_pipeline.call_command", fake)
    return made, fail


def run(*args):
    out = StringIO()
    try:
        call_command("run_pipeline", *args, stdout=out)
    except CommandError as exc:
        return out.getvalue(), exc
    return out.getvalue(), None


def test_runs_steps_in_order_without_digest(calls):
    made, _ = calls
    out, err = run()
    assert err is None
    assert [c for c, _ in made] == ["collect", "extract_opportunities", "match_services", "rescore"]
    assert made[0][1] == ["--all"]
    assert "Pipeline concluído" in out


def test_failure_is_isolated_and_reported_at_the_end(calls):
    made, fail = calls
    fail["collect"] = CommandError("fonte x falhou")
    out, err = run()
    assert [c for c, _ in made][-1] == "rescore"  # as etapas seguintes ainda rodam
    assert "Etapas com falha: collect" in str(err)
    assert "collect: falhou (fonte x falhou)" in out


def test_unexpected_error_logs_only_exception_type(calls):
    made, fail = calls
    fail["extract_opportunities"] = RuntimeError("postgres://user:senha@host/db")
    out, err = run()
    assert err is not None
    assert "RuntimeError" in out
    assert "senha" not in out and "senha" not in str(err)


def test_dry_run_skips_digest_and_passes_flag(calls):
    made, _ = calls
    out, err = run("--dry-run", "--digest")
    assert err is None
    assert "digest" not in [c for c, _ in made]
    assert all("--dry-run" in a for _, a in made)
    assert "digest: pulado" in out


def test_digest_with_email_and_skip(calls):
    made, _ = calls
    run("--digest", "--email", "--skip", "collect", "--skip", "extract")
    assert [c for c, _ in made] == ["match_services", "rescore", "digest"]
    assert made[-1][1] == ["--email"]


def test_email_requires_digest_and_limit_positive(calls):
    assert "--digest" in str(run("--email")[1])
    assert "positivo" in str(run("--extract-limit", "0")[1])


def test_workflows_are_safe_for_a_public_repo():
    for name in ("pipeline.yml", "backup.yml"):
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "schedule:" in text and "workflow_dispatch:" in text
        assert not re.search(
            r"(?i)(password|key|token|url)\s*:\s*[\"']?[A-Za-z0-9]{8,}",
            text.replace("secrets.", ""),
        )
    pipeline = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "upload-artifact" not in pipeline  # digest/dados nunca viram artefato público
    assert "run_pipeline" in pipeline
    backup = (ROOT / ".github/workflows/backup.yml").read_text(encoding="utf-8")
    assert ".dump.age" in backup and "backups/*.dump" not in backup.replace(".dump.age", "")


@pytest.mark.parametrize("script", ["backup.sh", "restore_backup.sh"])
def test_scripts_have_valid_bash_syntax(script):
    subprocess.run(["bash", "-n", str(ROOT / "scripts" / script)], check=True)


def test_restore_requires_confirmation(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/restore_backup.sh"), "a", "b", "postgres://x"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode != 0
    assert "RESTORE_CONFIRM=sim" in result.stderr
