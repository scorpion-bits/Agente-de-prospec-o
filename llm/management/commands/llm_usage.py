"""Uso e custo da camada de IA no mês corrente (E10). Só contagens e US$: sem conteúdo (ADR-014)."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from llm import budget
from llm.models import LLMCall


class Command(BaseCommand):
    help = "Mostra chamadas, cache e custo do mês por cobrança, tarefa e estratégia."

    def handle(self, *args, **options):
        since = budget.month_start()
        calls = LLMCall.objects.filter(created_at__gte=since)
        self.stdout.write(f"Mês a partir de {since:%d/%m/%Y}: {calls.count()} registros")

        for billing, label in (("money", "dinheiro novo"), ("credits", "créditos AI Pro")):
            spent, cap = budget.month_spent(billing), budget.monthly_cap(billing)
            self.stdout.write(
                f"  {label}: US$ {spent:.4f} de US$ {cap:.2f} (resta {cap - spent:.4f})"
            )
        free = calls.filter(billing="free", status__in=["ok", "invalid"]).count()
        self.stdout.write(f"  free tier / local: {free} chamadas (custo 0)")
        cached = calls.filter(status=LLMCall.Status.CACHED).count()
        live = calls.exclude(status=LLMCall.Status.CACHED).count()
        self.stdout.write(f"  cache: {cached} acertos para {live} chamadas ao provedor")

        rows = (
            calls.values("task", "strategy", "status")
            .annotate(
                n=Count("id"),
                usd=Sum("cost_usd"),
                tin=Sum("input_tokens"),
                tout=Sum("output_tokens"),
            )
            .order_by("task", "strategy", "status")
        )
        for row in rows:
            usd = row["usd"] or Decimal("0")
            self.stdout.write(
                f"  {row['task']} · {row['strategy']} · {row['status']}: {row['n']}x, "
                f"{row['tin']}+{row['tout']} tokens, US$ {usd:.4f}"
            )
