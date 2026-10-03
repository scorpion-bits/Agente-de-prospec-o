"""Gera o digest semanal (E15) em `data/digests/AAAA-Www.html` e `.md`. Só leitura do banco."""

from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from reports import digest


class Command(BaseCommand):
    help = "Gera o digest semanal (HTML e Markdown). E-mail opcional só para a equipe."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(settings.DIGEST_DIR), help="Pasta de saída.")
        parser.add_argument(
            "--since", help="Novidades desde AAAA-MM-DD (padrão: último digest ou 7 dias)."
        )
        parser.add_argument(
            "--email", action="store_true", help="Envia para a lista DIGEST_EMAIL_TO do .env."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Imprime o Markdown; não grava nem envia."
        )

    def handle(self, *args, **options):
        out = options["out"]
        since = None
        if options["since"]:
            try:
                since = timezone.make_aware(datetime.strptime(options["since"], "%Y-%m-%d"))
            except ValueError as exc:
                raise CommandError("--since deve ser AAAA-MM-DD.") from exc
        else:
            since = digest.read_state(out)
        if options["email"]:
            try:
                digest.team_recipients()  # falha cedo, antes de gerar
            except digest.EmailNotAllowed as exc:
                raise CommandError(str(exc)) from exc
        result = digest.build(since=since)
        if options["dry_run"]:
            self.stdout.write(digest.render_markdown(result))
            return
        html_path, md_path = digest.write_files(result, out)
        self.stdout.write(f"Digest {result.week}: {html_path} e {md_path.name}")
        self.stdout.write(
            f"{len(result.top)} no topo, {len(result.deadlines)} prazos, "
            f"{result.new['total']} novidades, {result.blocked['total']} bloqueadas por requisito, "
            f"{result.follow_ups['total']} follow-ups."
        )
        if options["email"]:
            try:
                sent = digest.send_email(result)
            except digest.EmailNotAllowed as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"E-mail enviado para {len(sent)} endereço(s) da equipe.")
