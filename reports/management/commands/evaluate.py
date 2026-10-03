"""Relatório de go/no-go do MVP (E22). Só leitura; a decisão final é humana (ADR-040)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from reports import evaluation


class Command(BaseCommand):
    help = "Gera data/evaluations/AAAA-MM-DD.md com M1–M9, prontidão e sugestão de decisão."

    def add_arguments(self, parser):
        parser.add_argument("--m3", type=int, help="M3: interessantes fora do baseline manual.")
        parser.add_argument("--m6", type=int, help="M6: minutos de triagem por semana (média).")
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "data" / "evaluations"))
        parser.add_argument("--dry-run", action="store_true", help="Imprime; não grava.")

    def handle(self, *args, **options):
        ev = evaluation.build(new_vs_manual=options["m3"], triage_minutes=options["m6"])
        text = evaluation.render_markdown(ev)
        if options["dry_run"]:
            self.stdout.write(text)
            return
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{ev.generated_at:%Y-%m-%d}.md"
        path.write_text(text, encoding="utf-8")
        self.stdout.write(f"Relatório: {path}")
        self.stdout.write(f"Sugestão: {evaluation.LABELS[ev.suggestion]}")
