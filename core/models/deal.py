"""Pipeline leve (E23, ADR-045): negócio = organização + serviço + estágio + valor."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models.catalog import ServiceOffering
from core.models.opportunity import Opportunity
from core.models.organization import Organization

# Ordem do funil; `lost` fica fora: perdido guarda o estágio mais alto alcançado em `peak_stage`.
FUNNEL = ("interesting", "contacted", "responded", "meeting", "proposal", "negotiation", "won")
OPEN_STAGES = FUNNEL[:-1]


class Deal(models.Model):
    """Organização + serviço + estágio + valor estimado. Sem outros campos de CRM (ADR-045).

    O estágio é decisão humana (admin); as `Interaction`s ligadas ao negócio dão o histórico e o
    ritmo de follow-up (`core.services.pipeline`). `peak_stage` e as datas saem do `save()`.
    """

    class Stage(models.TextChoices):
        INTERESTING = "interesting", "Interessante"
        CONTACTED = "contacted", "Contato"
        RESPONDED = "responded", "Respondeu"
        MEETING = "meeting", "Reunião"
        PROPOSAL = "proposal", "Proposta"
        NEGOTIATION = "negotiation", "Negociação"
        WON = "won", "Fechado (ganho)"
        LOST = "lost", "Perdido"

    class LostReason(models.TextChoices):
        NO_RESPONSE = "no_response", "Sem resposta"
        NO_BUDGET = "no_budget", "Sem orçamento"
        CHOSE_OTHER = "chose_other", "Escolheram outro"
        NOT_NOW = "not_now", "Não é o momento"
        OPT_OUT = "opt_out", "Pediu para não ser contatado"
        OTHER = "other", "Outro"

    organization = models.ForeignKey(
        Organization, verbose_name="organização", on_delete=models.CASCADE, related_name="deals"
    )
    service = models.ForeignKey(
        ServiceOffering,
        verbose_name="serviço",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deals",
    )
    opportunity = models.ForeignKey(
        Opportunity,
        verbose_name="oportunidade de origem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deals",
    )
    stage = models.CharField(
        "estágio", max_length=12, choices=Stage.choices, default=Stage.INTERESTING
    )
    peak_stage = models.CharField(
        "estágio mais alto alcançado", max_length=12, choices=Stage.choices, editable=False
    )
    estimated_value = models.DecimalField(
        "valor estimado (R$)", max_digits=12, decimal_places=2, null=True, blank=True
    )
    lost_reason = models.CharField(
        "motivo da perda", max_length=12, choices=LostReason.choices, blank=True
    )
    notes = models.CharField("observação", max_length=255, blank=True)
    stage_changed_at = models.DateTimeField("estágio mudou em", editable=False)
    closed_at = models.DateTimeField("fechado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "negócio"
        verbose_name_plural = "negócios (pipeline)"
        indexes = [models.Index(fields=["stage"], name="deal_stage_idx")]

    def __str__(self):
        service = f" · {self.service}" if self.service_id else ""
        return f"{self.organization}{service} ({self.get_stage_display()})"

    def save(self, *args, **kwargs):
        now = timezone.now()
        previous = (
            type(self).objects.filter(pk=self.pk).values_list("stage", flat=True).first()
            if self.pk
            else None
        )
        if previous != self.stage:
            self.stage_changed_at = now
            self.closed_at = None if self.is_open else now
        self.stage_changed_at = self.stage_changed_at or now
        if self.stage in FUNNEL:
            reached = self.peak_stage if self.peak_stage in FUNNEL else self.stage
            self.peak_stage = max(reached, self.stage, key=FUNNEL.index)
        elif not self.peak_stage:
            self.peak_stage = self.Stage.INTERESTING  # perdido sem histórico: só entrou no funil
        if self.stage != self.Stage.LOST:
            self.lost_reason = ""
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.stage in OPEN_STAGES

    def clean(self):
        if self.stage == self.Stage.LOST and not self.lost_reason:
            raise ValidationError({"lost_reason": "Diga por que o negócio foi perdido."})
        if self.stage != self.Stage.LOST and self.lost_reason:
            raise ValidationError({"lost_reason": "Motivo só vale para negócio perdido."})
