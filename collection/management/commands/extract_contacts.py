"""Extrai contatos públicos institucionais do site oficial das organizações (E19).

Lê até 5 páginas por site com o `PoliteFetcher` (robots, rate limit) e grava `ContactPoint` só com
evidência (URL + trecho). Respeita `Suppression`. A saída traz só contagens (logs públicos,
ADR-014). `--dry-run` não grava contato nem evidência (as páginas ficam em cache).
"""

from django.core.management.base import BaseCommand, CommandError

from collection.contact_finder import REACHABLE_KINDS, apply_scan, mark_checked, scan_organization
from collection.fetcher import PageBudgetExceeded, PoliteFetcher
from core.models import ContactPoint, Organization
from core.services.suppression import SuppressionIndex
from extraction.contacts import MAX_PAGES


class Command(BaseCommand):
    help = "Extrai e-mails, telefones, WhatsApp, formulário e redes publicados no site oficial."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=Organization.Kind.values, help="Só este tipo.")
        parser.add_argument("--limit", type=int, default=20, help="Máximo de organizações.")
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Inclui as já verificadas (páginas em cache custam pouco).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Não grava contato nem evidência."
        )

    def handle(self, *args, kind, limit, refresh, dry_run, **options):
        if limit < 1:
            raise CommandError("--limit deve ser positivo.")
        queryset = Organization.objects.exclude(website="")
        if not refresh:
            queryset = queryset.filter(contacts_checked_at__isnull=True)
        if kind:
            queryset = queryset.filter(kind=kind)
        organizations = list(queryset.order_by("pk")[:limit])

        fetcher = PoliteFetcher(max_requests=len(organizations) * MAX_PAGES)
        index = SuppressionIndex.load()
        totals = {"ok": 0, "unreachable": 0, "suppressed": 0}
        pages = skipped = dropped = personal = no_contact = 0
        created: dict[str, int] = {}
        stop = ""
        try:
            for organization in organizations:
                try:
                    scan = scan_organization(organization, fetcher, index)
                except PageBudgetExceeded as exc:
                    stop = str(exc)
                    break
                totals[scan.status] += 1
                pages += scan.pages
                skipped += scan.skipped_suppressed
                dropped += scan.dropped_social_kinds
                personal += sum(1 for s in scan.contacts if s.contact.is_personal)
                no_contact += scan.status == "ok" and not scan.contacts
                if dry_run:
                    for item in scan.contacts:
                        created[item.contact.kind] = created.get(item.contact.kind, 0) + 1
                elif scan.status == "ok":
                    for name, count in apply_scan(organization, scan).items():
                        created[name] = created.get(name, 0) + count
                else:  # inacessível ou suprimida: não reler a cada execução
                    mark_checked(organization)
        finally:
            fetcher.close()

        prefix = "[dry-run] " if dry_run else ""
        kinds = ", ".join(f"{n} {k}" for k, n in sorted(created.items())) or "nenhum"
        self.stdout.write(
            f"{prefix}extract_contacts: {sum(totals.values())} de {len(organizations)} "
            f"organizações — {totals['ok']} lidas, {totals['unreachable']} sem acesso ao site, "
            f"{totals['suppressed']} em opt-out; {pages} páginas; contatos "
            f"{'achados' if dry_run else 'novos'}: {kinds}; {personal} marcados como pessoais, "
            f"{skipped} descartados por opt-out, {dropped} redes ambíguas descartadas; "
            f"{no_contact} sites sem nenhum contato."
        )
        if not dry_run:
            self.stdout.write(self.coverage_line())
        if stop:
            raise CommandError(f"Interrompido: {stop} As restantes ficam para a próxima execução.")

    @staticmethod
    def coverage_line() -> str:
        """% de organizações com site que têm ≥ 1 contato institucional utilizável (métrica E19)."""
        with_site = Organization.objects.exclude(website="")
        total = with_site.count()
        reachable = (
            ContactPoint.objects.usable()
            .filter(kind__in=REACHABLE_KINDS, is_personal=False, organization__in=with_site)
            .values("organization")
            .distinct()
            .count()
        )
        pct = f"{100 * reachable / total:.0f}%" if total else "—"
        return (
            f"Cobertura: {reachable} de {total} organizações com site têm "
            f"≥ 1 contato institucional ({pct})."
        )
