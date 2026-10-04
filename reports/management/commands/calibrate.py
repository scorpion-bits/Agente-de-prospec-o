"""Calibração de pesos do score (E30). Só leitura; a mudança de pesos é humana (ADR-044)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports import calibration


class Command(BaseCommand):
    help = "Gera data/calibrations/AAAA-MM-DD.md: fatores × triagem e proposta de pesos."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "data" / "calibrations"))
        parser.add_argument("--dry-run", action="store_true", help="Imprime; não grava.")

    def handle(self, *args, **options):
        now = timezone.localtime()
        text = calibration.render_markdown(calibration.build(), now)
        if options["dry_run"]:
            self.stdout.write(text)
            return
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{now:%Y-%m-%d}.md"
        path.write_text(text, encoding="utf-8")
        self.stdout.write(f"Relatório: {path}")
