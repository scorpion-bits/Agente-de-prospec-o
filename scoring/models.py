"""`Score`: nota explicável de uma entidade (E13, ADR-006, docs/architecture/scoring.md)."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models.common import ENTITY_CHOICES, UNIT_INTERVAL


class Score(models.Model):
    """Resultado do cálculo para uma entidade: total, rótulo, confiança e o detalhamento.

    Uma linha por entidade (ADR-017: relação genérica); recalcular substitui a linha e grava a
    `scoring_version` usada. `total` é nulo quando a entidade foi barrada por um gate.
    """

    class Label(models.TextChoices):
        PRIORITIZE = "prioritize", "Priorizar"
        EVALUATE = "evaluate", "Avaliar"
        LOW = "low", "Baixa"
        IGNORE = "ignore", "Ignorar"
        GATED = "gated", "Bloqueada"
        ONGOING = "ongoing", "Em andamento"

    class GateKind(models.TextChoices):
        EXPIRED = "expired", "Prazo vencido ou já ocorreu"
        TERRITORY = "territory", "Território inelegível"
        COMPANY_REQUIREMENT = "company_requirement", "Requisito da empresa não atendido"
        DO_NOT_CONTACT = "do_not_contact", "Não contatar (opt-out)"

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo da entidade",
        on_delete=models.CASCADE,
        limit_choices_to=ENTITY_CHOICES,
    )
    object_id = models.PositiveBigIntegerField("ID da entidade")
    entity = GenericForeignKey("content_type", "object_id")

    profile = models.CharField("perfil", max_length=40, help_text="Ex.: opp.edital.")
    scoring_version = models.CharField("versão da pontuação", max_length=20)
    total = models.PositiveSmallIntegerField(
        "pontos",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="De 0 a 100. Vazio quando a entidade foi barrada por um gate.",
    )
    label = models.CharField("rótulo", max_length=10, choices=Label.choices)
    confidence = models.FloatField("confiança (K)", null=True, blank=True, validators=UNIT_INTERVAL)
    gated = models.BooleanField("barrada por gate", default=False)
    gate_kind = models.CharField(
        "tipo do gate", max_length=20, choices=GateKind.choices, blank=True
    )
    gate_reason = models.CharField("motivo do gate", max_length=300, blank=True)
    breakdown = models.JSONField(
        "detalhamento",
        default=list,
        blank=True,
        help_text='Lista de {"factor", "label", "raw", "weight", "points", "explanation", '
        '"evidence_ids", "support"}.',
    )
    alerts = models.JSONField("alertas", default=list, blank=True)
    raw_sum = models.FloatField("soma ponderada", null=True, blank=True)
    computed_at = models.DateTimeField("calculado em", default=timezone.now)

    class Meta:
        ordering = [models.F("total").desc(nulls_last=True), "-computed_at"]
        verbose_name = "pontuação"
        verbose_name_plural = "pontuações"
        indexes = [models.Index(fields=["content_type", "object_id"], name="score_entity_idx")]
        constraints = [
            models.UniqueConstraint(fields=["content_type", "object_id"], name="uniq_score_entity"),
            models.CheckConstraint(
                condition=Q(total__isnull=True) | Q(total__gte=0, total__lte=100),
                name="score_total_in_0_100",
            ),
            models.CheckConstraint(
                condition=Q(gated=False, total__isnull=False) | Q(gated=True, total__isnull=True),
                name="score_gated_iff_no_total",
            ),
        ]

    def __str__(self):
        shown = "bloqueada" if self.total is None else f"{self.total}/100"
        return f"{self.entity} — {shown} ({self.get_label_display()})"
