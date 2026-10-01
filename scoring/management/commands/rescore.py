"""Recalcula a pontuação das oportunidades (E13): gates, fatores, confiança, breakdown.

Sem IA, sem rede, determinístico. A saída traz só contagens (logs públicos, ADR-014).
Oportunidades já descartadas na triagem não são recalculadas (a pontuação antiga fica).
`--dry-run` não grava.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from core.models import Opportunity
from scoring.engine import build_context, is_discarded, save_score, score_opportunity
from scoring.models import Score
from scoring.profiles import PROFILE_BY_KIND, SCORING_VERSION


class Command(BaseCommand):
    help = "Calcula o Score de cada oportunidade (gates, fatores, confiança, breakdown)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            choices=sorted(set(PROFILE_BY_KIND.values())),
            help="Só oportunidades deste perfil (ex.: opp.edital).",
        )
        parser.add_argument("--limit", type=int, default=0, help="Máximo (0 = todas).")
        parser.add_argument("--dry-run", action="store_true", help="Não grava.")

    def handle(self, *args, profile, limit, dry_run, **options):
        if limit < 0:
            raise CommandError("--limit não pode ser negativo.")
        queryset = Opportunity.objects.select_related("organizer", "municipality").order_by("pk")
        if profile:
            kinds = [k for k, p in PROFILE_BY_KIND.items() if p == profile]
            queryset = queryset.filter(kind__in=kinds)
        if limit:
            queryset = queryset[:limit]
        ctx = build_context()
        if ctx.company is None:
            self.stdout.write("Aviso: perfil da empresa não carregado (rode `make memory`).")
        if not ctx.services:
            self.stdout.write("Aviso: catálogo vazio (rode `make seed`): o fit ficará neutro.")
        if ctx.home is None:
            self.stdout.write("Aviso: municípios não carregados (rode `make seed`): geo neutra.")

        seen = skipped = 0
        labels: Counter[str] = Counter()
        gates: Counter[str] = Counter()
        for opp in queryset:
            seen += 1
            if is_discarded(opp):
                skipped += 1
                continue
            result = score_opportunity(opp, ctx)
            labels[result.label] += 1
            if result.gated:
                gates[result.gate_kind] += 1
            if not dry_run:
                save_score(opp, result, ctx)
        verb = "simulado" if dry_run else "gravado"
        self.stdout.write(
            f"Oportunidades: {seen}; versão {SCORING_VERSION}; {verb}. "
            f"Descartadas na triagem (puladas): {skipped}."
        )
        names = dict(Score.Label.choices)
        for label, total in labels.most_common():
            self.stdout.write(f"  {names[label]}: {total}")
        kinds = dict(Score.GateKind.choices)
        for kind, total in gates.most_common():
            self.stdout.write(f"    bloqueio · {kinds[kind]}: {total}")
