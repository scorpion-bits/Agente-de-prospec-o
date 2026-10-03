"""Encadeia o radar: collect → extract → match → rescore (→ digest), para o GitHub Actions (E16).

Cada etapa roda isolada: se uma falha, as seguintes ainda rodam (com os dados que existirem) e o
comando termina com erro no fim, para o Actions ficar vermelho. A saída traz só contagens e o nome
da etapa (logs do Actions são públicos — ADR-014): erros inesperados mostram só o tipo da exceção;
o detalhe fica em `CollectionRun.error_log` (admin). O digest só roda com `--digest`, e nunca em
`--dry-run` (imprimiria dados privados).
"""

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

STEPS = ("collect", "extract", "match", "rescore", "digest")


class Command(BaseCommand):
    help = (
        "Roda a cadeia collect → extract → match → rescore (→ digest) com falha isolada por etapa."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simula cada etapa; sem digest.")
        parser.add_argument(
            "--digest", action="store_true", help="Inclui o digest semanal ao final."
        )
        parser.add_argument(
            "--email", action="store_true", help="Com --digest, envia à lista DIGEST_EMAIL_TO."
        )
        parser.add_argument(
            "--skip",
            action="append",
            default=[],
            choices=STEPS,
            help="Pula uma etapa (repetível).",
        )
        parser.add_argument(
            "--extract-limit", type=int, default=30, help="Máximo de oportunidades na extração."
        )

    def plan(self, *, dry_run, digest, email, skip, extract_limit):
        """Lista (nome, comando, argumentos) das etapas que vão rodar, na ordem."""
        flag = ["--dry-run"] if dry_run else []
        steps = [
            ("collect", "collect", ["--all", *flag]),
            ("extract", "extract_opportunities", ["--limit", str(extract_limit), *flag]),
            ("match", "match_services", flag),
            ("rescore", "rescore", flag),
        ]
        if digest and not dry_run:
            steps.append(("digest", "digest", ["--email"] if email else []))
        return [s for s in steps if s[0] not in skip]

    def handle(self, *args, dry_run, digest, email, skip, extract_limit, **options):
        if extract_limit < 1:
            raise CommandError("--extract-limit deve ser positivo.")
        if email and not digest:
            raise CommandError("--email só faz sentido com --digest.")
        steps = self.plan(
            dry_run=dry_run, digest=digest, email=email, skip=skip, extract_limit=extract_limit
        )
        if digest and dry_run:
            self.stdout.write("digest: pulado em --dry-run (não imprimimos dados privados).")

        failed = []
        for name, command, args_ in steps:
            self.stdout.write(f"== {name} ==")
            started = time.monotonic()
            try:
                call_command(command, *args_, stdout=self.stdout, stderr=self.stderr)
                outcome = "ok"
            except CommandError as exc:
                outcome = f"falhou ({exc})"
                failed.append(name)
            except Exception as exc:  # noqa: BLE001 - isolamento por etapa; detalhe fora do log público
                outcome = f"falhou ({type(exc).__name__})"
                failed.append(name)
            self.stdout.write(f"{name}: {outcome} em {time.monotonic() - started:.0f}s")

        if failed:
            raise CommandError(f"Etapas com falha: {', '.join(failed)}.")
        self.stdout.write("Pipeline concluído sem falhas.")
