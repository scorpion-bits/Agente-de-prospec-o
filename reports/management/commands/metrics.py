"""Exibe as métricas M1–M9 (E14). Só leitura; a saída traz contagens, sem dados pessoais."""

from django.core.management.base import BaseCommand

from reports.metrics import compute, render, triage_backlog


class Command(BaseCommand):
    help = "Mostra as métricas do MVP (docs/product/metrics.md) com os dados atuais."

    def handle(self, *args, **options):
        self.stdout.write(render(compute(), triage_backlog()))
