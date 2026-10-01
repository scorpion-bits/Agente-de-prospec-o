"""Descobre o site oficial de organizações sem `website` (E18).

Busca (cache permanente, teto por execução) → baixa até 3 candidatos com o `PoliteFetcher` → valida
nome e município na página. Só marca `found` quando exatamente um domínio confere; dúvida vira
`ambiguous`. A saída traz só contagens (logs públicos, ADR-014). `--dry-run` não grava site nem
evidência (a busca e as páginas continuam em cache, então repetir não custa nada).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from collection.fetcher import PoliteFetcher
from collection.search import SearchBudgetExceeded, SearchError, get_provider
from collection.website_finder import STATUS, apply_decision, find_website, known_domains
from core.models import Organization
from core.services.normalize import normalize_domain
from extraction.website import MAX_CANDIDATES


class Command(BaseCommand):
    help = "Encontra e valida o site oficial de organizações sem site (busca web com cache)."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=Organization.Kind.values, help="Só este tipo.")
        parser.add_argument("--limit", type=int, default=20, help="Máximo de organizações.")
        parser.add_argument(
            "--retry",
            action="store_true",
            help="Inclui as já pesquisadas (não encontrado/ambíguo); busca em cache é grátis.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Não grava site nem evidência.")
        parser.add_argument("--provider", help="serper | brave (padrão: SEARCH_PROVIDER).")

    def handle(self, *args, kind, limit, retry, dry_run, provider, **options):
        if limit < 1:
            raise CommandError("--limit deve ser positivo.")
        statuses = [STATUS.UNKNOWN] + ([STATUS.NOT_FOUND, STATUS.AMBIGUOUS] if retry else [])
        queryset = Organization.objects.filter(website="", website_status__in=statuses)
        if kind:
            queryset = queryset.filter(kind=kind)
        no_city = queryset.filter(municipality_name="").count()
        organizations = list(queryset.exclude(municipality_name="").order_by("pk")[:limit])

        try:
            search = get_provider(provider, max_calls=settings.SEARCH_MAX_CALLS_PER_RUN)
        except SearchError as exc:
            raise CommandError(str(exc)) from exc
        fetcher = PoliteFetcher(max_requests=len(organizations) * MAX_CANDIDATES)
        taken = known_domains()
        counts = {STATUS.FOUND: 0, STATUS.AMBIGUOUS: 0, STATUS.NOT_FOUND: 0}
        stop = ""
        try:
            for organization in organizations:
                try:
                    decision = find_website(organization, search, fetcher, taken=taken)
                except SearchBudgetExceeded as exc:
                    stop = str(exc)
                    break
                except SearchError as exc:
                    stop = f"busca falhou: {exc}"
                    break
                counts[decision.status] += 1
                if not dry_run:
                    apply_decision(organization, decision, provider_name=search.name)
                    if decision.url:
                        taken.setdefault(normalize_domain(decision.url), organization.pk)
        finally:
            fetcher.close()
            search.close()

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}find_websites: {sum(counts.values())} de {len(organizations)} processadas — "
            f"{counts[STATUS.FOUND]} encontradas, {counts[STATUS.AMBIGUOUS]} ambíguas, "
            f"{counts[STATUS.NOT_FOUND]} não encontradas; {search.calls} buscas pagas, "
            f"{search.cache_hits} em cache; {no_city} sem município (ignoradas)."
        )
        if stop:
            raise CommandError(f"Interrompido: {stop} As restantes ficam para a próxima execução.")
