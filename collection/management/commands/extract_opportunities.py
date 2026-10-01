"""Extrai campos estruturados das oportunidades candidatas (E11).

Candidata = `Opportunity` com URL oficial e `extraction_version` vazia. Baixa a página com o
`PoliteFetcher` (robots, rate limit, cache), manda só **texto público** à tarefa
`extract_opportunity` (Gemini free → Haiku → regras) e grava campos + evidências. A saída traz só
contagens (logs públicos, ADR-014). `--dry-run` não grava nada além do cache de páginas e do log
de custo da IA.
"""

from django.core.management.base import BaseCommand, CommandError

from collection.fetcher import FetchError, PageBudgetExceeded, PoliteFetcher, UnsupportedContent
from core.models import Opportunity
from extraction.opportunity import EXTRACTION_VERSION, apply_extraction, extract_opportunity
from extraction.text import MIN_TEXT_CHARS, page_text
from llm.router import AIService
from llm.types import BudgetExceeded, LLMError

NO_TEXT = "sem-texto"  # PDF ou página só-JS: não tentar de novo a cada execução (use --force)


class Command(BaseCommand):
    help = "Extrai prazo, requisitos de empresa, prêmio e resumo das oportunidades candidatas."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Máximo de oportunidades.")
        parser.add_argument("--kind", choices=Opportunity.Kind.values, help="Só este tipo.")
        parser.add_argument(
            "--force", action="store_true", help="Inclui as já extraídas ou marcadas sem texto."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Não grava campos nem evidências."
        )

    def handle(self, *args, limit, kind, force, dry_run, **options):
        if limit < 1:
            raise CommandError("--limit deve ser positivo.")
        queryset = Opportunity.objects.exclude(official_url="")
        if not force:
            queryset = queryset.filter(extraction_version="")
        if kind:
            queryset = queryset.filter(kind=kind)
        opportunities = list(queryset.order_by("pk")[:limit])

        fetcher = PoliteFetcher(max_requests=len(opportunities) + 1)
        service = AIService()
        by_strategy: dict[str, int] = {}
        done = no_text = failed = observed = inferred = unverified = columns = cached = 0
        stop = ""
        try:
            for opp in opportunities:
                try:
                    fetched = fetcher.fetch(opp.official_url)
                except PageBudgetExceeded as exc:
                    stop = str(exc)
                    break
                except UnsupportedContent:
                    no_text += 1
                    self._mark(opp, dry_run)
                    continue
                except FetchError:
                    failed += 1
                    continue
                title, text = page_text(fetched.text, fetched.content_type)
                if len(text) < MIN_TEXT_CHARS:
                    no_text += 1
                    self._mark(opp, dry_run)
                    continue
                try:
                    extraction = extract_opportunity(opp, text, service, title=title)
                except BudgetExceeded as exc:
                    stop = str(exc)
                    break
                except LLMError:
                    failed += 1  # as razões ficam no `LLMCall`, sem o conteúdo
                    continue
                counts = apply_extraction(opp, extraction, text, dry_run=dry_run)
                done += 1
                cached += extraction.cached
                columns += counts["columns"]
                observed += counts["observed"]
                inferred += counts["inferred"]
                unverified += len(extraction.unverified)
                by_strategy[extraction.strategy] = by_strategy.get(extraction.strategy, 0) + 1
        finally:
            fetcher.close()

        prefix = "[dry-run] " if dry_run else ""
        strategies = ", ".join(f"{n} {s}" for s, n in sorted(by_strategy.items())) or "nenhuma"
        self.stdout.write(
            f"{prefix}extract_opportunities ({EXTRACTION_VERSION}): {done} de "
            f"{len(opportunities)} extraídas ({strategies}; {cached} do cache), "
            f"{no_text} sem texto aproveitável (PDF ou só JS), {failed} com falha; "
            f"{columns} colunas preenchidas, "
            f"{observed} campos observados, {inferred} inferidos (citação não confirmada: "
            f"{unverified}); custo da execução US$ {service.run_spent:.4f}."
        )
        if stop:
            raise CommandError(f"Interrompido: {stop} As restantes ficam para a próxima execução.")

    @staticmethod
    def _mark(opp: Opportunity, dry_run: bool) -> None:
        if not dry_run:
            opp.extraction_version = NO_TEXT
            opp.save(update_fields=["extraction_version"])
