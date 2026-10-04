"""Exibe as métricas M1–M9 (E14) e o funil do pipeline (E23). Só leitura, sem dados pessoais."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.services.pipeline import deals_needing_follow_up, funnel
from reports.metrics import compute, render, render_funnel, triage_backlog


class Command(BaseCommand):
    help = "Mostra as métricas do MVP (docs/product/metrics.md) com os dados atuais."

    def handle(self, *args, **options):
        self.stdout.write(render(compute(), triage_backlog()))
        self.stdout.write(
            "\n" + render_funnel(funnel(), len(deals_needing_follow_up(timezone.localdate())))
        )
