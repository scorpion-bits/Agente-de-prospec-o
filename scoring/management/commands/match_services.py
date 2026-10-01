"""Gera hipóteses «organização → serviço, porque…, prova: trabalho» por regras (E20).

Sem IA, sem rede. Reexecutável: atualiza os matches `rules_v1` e remove os que deixaram de valer.
A saída traz só contagens (logs públicos, ADR-014). `--dry-run` não grava.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from core.models import Organization, ServiceOffering
from scoring.matching import load_portfolio, match_organization, save_matches


class Command(BaseCommand):
    help = "Cria/atualiza os Match (serviço × organização × portfólio) pelas regras v1."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=Organization.Kind.values, help="Só este tipo.")
        parser.add_argument(
            "--limit", type=int, default=0, help="Máximo de organizações (0 = todas)."
        )
        parser.add_argument("--dry-run", action="store_true", help="Não grava.")

    def handle(self, *args, kind, limit, dry_run, **options):
        if limit < 0:
            raise CommandError("--limit não pode ser negativo.")
        services = {s.slug: s for s in ServiceOffering.objects.filter(active=True)}
        if not services:
            raise CommandError("Catálogo vazio: rode `make seed` (load_services).")
        portfolio = load_portfolio()
        queryset = Organization.objects.order_by("pk")
        if kind:
            queryset = queryset.filter(kind=kind)
        if limit:
            queryset = queryset[:limit]

        orgs = with_match = no_proof = 0
        created = updated = removed = 0
        per_service: Counter[str] = Counter()
        for organization in queryset:
            orgs += 1
            candidates = match_organization(organization, services, portfolio)
            with_match += bool(candidates)
            no_proof += sum(1 for c in candidates if not c.proof)
            per_service.update(c.service.slug for c in candidates)
            if not dry_run:
                c_, u_, r_ = save_matches(organization, candidates)
                created, updated, removed = created + c_, updated + u_, removed + r_
        verb = "simulado" if dry_run else "gravado"
        self.stdout.write(f"Organizações analisadas: {orgs}; com ≥ 1 match: {with_match}.")
        for slug, total in per_service.most_common():
            self.stdout.write(f"  {slug}: {total}")
        self.stdout.write(f"Sem item de portfólio como prova: {no_proof} match(es).")
        if not dry_run:
            self.stdout.write(
                f"{verb}: {created} criado(s), {updated} atualizado(s), {removed} removido(s)."
            )
        if not portfolio:
            self.stdout.write("Aviso: nenhum item público de portfólio (rode `make memory`).")
