"""Detecta sinais de necessidade web nos sites das organizações (E26).

Lê **só a página inicial** com o `PoliteFetcher` (robots, rate limit) e grava `Evidence` por sinal
(`web.signal.*`): sem site, só rede social, site fora do ar, sem HTTPS, sem viewport, © antigo,
tecnologia obsoleta. Sinal é fator de Fit, não verdade. Respeita `Suppression`. A saída traz só
contagens (logs públicos, ADR-014). `--dry-run` não grava.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from collection.fetcher import PageBudgetExceeded, PoliteFetcher
from collection.web_signal_finder import (
    apply_scan,
    mark_checked,
    pending_organizations,
    scan_organization,
)
from core.models import Organization
from core.services.suppression import SuppressionIndex


class Command(BaseCommand):
    help = "Acha sinais determinísticos de que a organização precisa de site novo ou melhor."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=Organization.Kind.values, help="Só este tipo.")
        parser.add_argument("--limit", type=int, default=20, help="Máximo de organizações.")
        parser.add_argument(
            "--refresh", action="store_true", help="Inclui as checadas há menos de 30 dias."
        )
        parser.add_argument("--dry-run", action="store_true", help="Não grava evidência.")

    def handle(self, *args, kind, limit, refresh, dry_run, **options):
        if limit < 1:
            raise CommandError("--limit deve ser positivo.")
        organizations = list(pending_organizations(refresh=refresh, kind=kind)[:limit])
        fetcher = PoliteFetcher(max_requests=len(organizations))
        index = SuppressionIndex.load()
        statuses: Counter = Counter()
        found: Counter = Counter()
        stop = ""
        try:
            for organization in organizations:
                try:
                    scan = scan_organization(organization, fetcher, index)
                except PageBudgetExceeded as exc:
                    stop = str(exc)
                    break
                statuses[scan.status] += 1
                found.update(s.code for s in scan.signals)
                if dry_run:
                    continue
                if scan.status in ("ok", "unreadable"):
                    apply_scan(organization, scan)
                else:  # sem acesso permitido ou em opt-out: não reler a cada execução
                    mark_checked(organization)
        finally:
            fetcher.close()

        prefix = "[dry-run] " if dry_run else ""
        signals = ", ".join(f"{n} {c}" for c, n in sorted(found.items())) or "nenhum"
        self.stdout.write(
            f"{prefix}web_signals: {sum(statuses.values())} de {len(organizations)} organizações — "
            f"{statuses['ok']} lidas, {statuses['unreadable']} com site fora do ar, "
            f"{statuses['skipped']} sem permissão (robots/bloqueio), {statuses['suppressed']} em "
            f"opt-out; sinais: {signals}."
        )
        if stop:
            raise CommandError(f"Interrompido: {stop} As restantes ficam para a próxima execução.")
