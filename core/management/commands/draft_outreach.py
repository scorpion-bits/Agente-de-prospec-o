"""Gera rascunhos de abordagem (E24, ADR-046) ou resume a avaliação humana deles.

Nada é enviado: o rascunho vai para o admin («Rascunhos de abordagem») para o humano editar. A saída
traz só contagens e ids (logs públicos, ADR-014). `--compare` roda cada estratégia sozinha (A/B).
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from core.models import Organization, OutreachDraft, ServiceOffering
from core.services.outreach import (
    TASK,
    OutreachBlocked,
    OutreachError,
    generate_draft,
)


class Command(BaseCommand):
    help = "Gera rascunhos de abordagem por organização (--org) ou resume as avaliações (--report)."

    def add_arguments(self, parser):
        parser.add_argument("--org", type=int, nargs="+", help="IDs das organizações.")
        parser.add_argument("--service", help="Slug do serviço (padrão: melhor match).")
        parser.add_argument(
            "--channel", choices=OutreachDraft.Channel.values, default=OutreachDraft.Channel.EMAIL
        )
        parser.add_argument(
            "--compare",
            action="store_true",
            help="A/B: uma estratégia por vez, sem fallback (gera um rascunho por estratégia).",
        )
        parser.add_argument("--report", action="store_true", help="Resume as avaliações humanas.")

    def handle(self, *args, org, service, channel, compare, report, **options):
        if report:
            return self.report()
        if not org:
            raise CommandError("Informe --org ID [ID…] (ou --report).")
        svc = None
        if service:
            svc = ServiceOffering.objects.filter(slug=service).first()
            if svc is None:
                raise CommandError(f"Serviço «{service}» não existe (`make seed`).")
        made = 0
        for organization in Organization.objects.filter(pk__in=org):
            runs = [[s] for s in TASK.configured_strategies()] if compare else [None]
            for strategies in runs:
                try:
                    draft = generate_draft(
                        organization,
                        service=svc,
                        channel=channel,
                        strategies=strategies,
                        fallback=not compare,
                    )
                except (OutreachBlocked, OutreachError) as exc:
                    self.stdout.write(f"org {organization.pk}: {exc}")
                    continue
                made += 1
                self.stdout.write(
                    f"org {organization.pk}: rascunho {draft.pk} ({draft.strategy}, "
                    f"{draft.get_status_display()}, US$ {draft.cost_usd:.4f})"
                )
        self.stdout.write(
            f"{made} rascunho(s) gerado(s). Avalie no admin (Rascunhos de abordagem)."
        )

    def report(self):
        drafts = OutreachDraft.objects.all()
        if not drafts.exists():
            self.stdout.write("Sem rascunhos ainda.")
            return
        stats = defaultdict(lambda: {"n": 0, "valid": 0, "rated": 0, "usable": 0, "cost": 0.0})
        for d in drafts:
            row = stats[d.strategy or "—"]
            row["n"] += 1
            row["valid"] += d.status == OutreachDraft.Status.VALID
            row["rated"] += bool(d.rating)
            row["usable"] += d.rating == OutreachDraft.Rating.USABLE
            row["cost"] += float(d.cost_usd)
        self.stdout.write(
            "estratégia · rascunhos · válidos · avaliados · usáveis · custo médio (US$)"
        )
        for name, r in sorted(stats.items()):
            self.stdout.write(
                f"{name} · {r['n']} · {r['valid']} · {r['rated']} · {r['usable']} · "
                f"{r['cost'] / r['n']:.4f}"
            )
        self.stdout.write("Meta da E24: ≥ 7 usáveis em 10 avaliados, toda afirmação com fato.")
