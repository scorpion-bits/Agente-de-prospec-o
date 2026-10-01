"""Roda os conectores: `collect <slug>` ou `collect --all` (fontes habilitadas).

A saída traz só contagens (logs do GitHub Actions são públicos — ADR-014); os erros ficam em
`CollectionRun.error_log`, visíveis no admin. Termina com erro se alguma fonte falhou por completo.
"""

from django.core.management.base import BaseCommand, CommandError

from collection import registry, runner
from collection.models import CollectionRun
from core.models import Source


class Command(BaseCommand):
    help = "Executa conectores de coleta (fetch → normalize → upsert → evidências)."

    def add_arguments(self, parser):
        parser.add_argument("slug", nargs="?", help="Slug da fonte (Source).")
        parser.add_argument("--all", action="store_true", help="Todas as fontes habilitadas.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Roda o conector sem gravar os itens."
        )
        parser.add_argument("--limit", type=int, help="Máximo de itens por fonte.")

    def handle(self, *args, slug, all, dry_run, limit, **options):
        if bool(slug) == bool(all):
            raise CommandError("Informe uma fonte (`collect <slug>`) ou use --all.")
        if limit is not None and limit < 1:
            raise CommandError("--limit deve ser positivo.")

        if all:
            sources = list(Source.objects.filter(enabled=True))
        else:
            source = Source.objects.filter(slug=slug).first()
            if source is None:
                raise CommandError(f"Fonte {slug!r} não existe (crie em Admin → Fontes).")
            if problem := runner.runnable_problem(source, dry_run=dry_run):
                raise CommandError(f"{slug}: {problem}")
            sources = [source]

        prefix = "[dry-run] " if dry_run else ""
        failures = 0
        for source in sources:
            if all and (problem := runner.runnable_problem(source, dry_run=dry_run)):
                self.stdout.write(f"{prefix}{source.slug}: ignorada — {problem}")
                continue
            try:
                run = runner.run_source(source, limit=limit, dry_run=dry_run)
            except registry.NoConnector as exc:  # pragma: no cover - coberto via runner
                self.stdout.write(f"{prefix}{source.slug}: {exc}")
                failures += 1
                continue
            self.stdout.write(
                f"{prefix}{source.slug}: {run.get_status_display().lower()} — {run.items_seen} "
                f"vistos, {run.items_new} novos, {run.items_updated} atualizados, "
                f"{run.items_failed} com falha"
            )
            failures += run.status == CollectionRun.Status.ERROR
        if failures:
            raise CommandError(f"{failures} fonte(s) falharam; veja Admin → Execuções de coleta.")
