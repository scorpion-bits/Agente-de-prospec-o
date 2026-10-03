"""Recalcula a pontuação de oportunidades (E13) e de leads (E21): gates, fatores, breakdown.

Sem IA, sem rede, determinístico. A saída traz só contagens (logs públicos, ADR-014).
Itens já descartados na triagem não são recalculados (a pontuação antiga fica).
`--dry-run` não grava.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from core.models import Opportunity
from scoring.engine import build_context, is_discarded, save_score, score_opportunity
from scoring.leads import LeadData, lead_profile_for, lead_queryset, score_lead
from scoring.models import Score
from scoring.profiles import LEAD_PROFILES, PROFILE_BY_KIND, SCORING_VERSION


class Command(BaseCommand):
    help = "Calcula o Score de oportunidades e de leads (gates, fatores, confiança, breakdown)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            choices=sorted({*PROFILE_BY_KIND.values(), *LEAD_PROFILES}),
            help="Só este perfil (ex.: opp.edital, lead.sesc); define o alvo sozinho.",
        )
        parser.add_argument(
            "--target",
            choices=("all", "opportunities", "leads"),
            default="all",
            help="O que pontuar (padrão: tudo).",
        )
        parser.add_argument("--limit", type=int, default=0, help="Máximo por alvo (0 = todos).")
        parser.add_argument("--dry-run", action="store_true", help="Não grava.")

    def handle(self, *args, profile, target, limit, dry_run, **options):
        if limit < 0:
            raise CommandError("--limit não pode ser negativo.")
        if profile:  # o perfil escolhido decide o alvo
            target = "leads" if profile in LEAD_PROFILES else "opportunities"
        ctx = build_context()
        if ctx.company is None:
            self.stdout.write("Aviso: perfil da empresa não carregado (rode `make memory`).")
        if not ctx.services:
            self.stdout.write("Aviso: catálogo vazio (rode `make seed`): o fit ficará neutro.")
        if ctx.home is None:
            self.stdout.write("Aviso: municípios não carregados (rode `make seed`): geo neutra.")
        if target in ("all", "opportunities"):
            self._opportunities(ctx, profile, limit, dry_run)
        if target in ("all", "leads"):
            self._leads(ctx, profile, limit, dry_run)

    def _opportunities(self, ctx, profile, limit, dry_run):
        queryset = Opportunity.objects.select_related("organizer", "municipality").order_by("pk")
        if profile:
            kinds = [k for k, p in PROFILE_BY_KIND.items() if p == profile]
            queryset = queryset.filter(kind__in=kinds)
        if limit:
            queryset = queryset[:limit]
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

    def _leads(self, ctx, profile, limit, dry_run):
        orgs = []
        for org in lead_queryset().order_by("pk"):
            org_profile = lead_profile_for(org)
            if org_profile is None or (profile and org_profile != profile):
                continue
            orgs.append((org, org_profile))
            if limit and len(orgs) >= limit:
                break
        data = LeadData([org for org, _ in orgs])
        seen = skipped = 0
        labels: Counter[str] = Counter()
        for org, org_profile in orgs:
            seen += 1
            if is_discarded(org):
                skipped += 1
                continue
            result = score_lead(org, org_profile, ctx, data)
            labels[result.label] += 1
            if not dry_run:
                save_score(org, result, ctx)
        verb = "simulado" if dry_run else "gravado"
        self.stdout.write(
            f"Leads: {seen}; versão {SCORING_VERSION}; {verb}. "
            f"Descartados na triagem (pulados): {skipped}."
        )
        names = dict(Score.Label.choices)
        for label, total in labels.most_common():
            self.stdout.write(f"  {names[label]}: {total}")
