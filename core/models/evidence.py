"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models.common import (
    ENTITY_CHOICES,
    EVIDENCE_FIELD_PATTERN,
    EVIDENCE_METHOD_PATTERN,
    UNIT_INTERVAL,
    missing_entity_error,
)


class Evidence(models.Model):
    """Uma afirmação sobre um campo de uma entidade, com sua origem (ADR-004).

    Use `core.services.evidence.record_evidence` para criar: ele aplica as regras do ADR-004.
    """

    class Kind(models.TextChoices):
        OBSERVED = "observed", "Observado"
        INFERRED = "inferred", "Inferido"
        MANUAL = "manual", "Manual"

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo da entidade",
        on_delete=models.CASCADE,
        limit_choices_to=ENTITY_CHOICES,
    )
    object_id = models.PositiveBigIntegerField("ID da entidade")
    entity = GenericForeignKey("content_type", "object_id")

    field = models.CharField(
        "campo",
        max_length=80,
        validators=[
            RegexValidator(
                EVIDENCE_FIELD_PATTERN,
                "Use minúsculas, números e _ (ex.: deadline_at, contact.email).",
            )
        ],
        help_text="Afirmação sobre a entidade. Ex.: deadline_at, offers_high_school.",
    )
    value = models.JSONField(
        "valor",
        encoder=DjangoJSONEncoder,
        blank=True,
        help_text='Em JSON: "2026-11-15" (texto entre aspas), 120, true ou ["a", "b"].',
    )
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    source_url = models.URLField("URL da fonte", max_length=1000, blank=True)
    source_name = models.CharField("nome da fonte", max_length=120, blank=True)
    retrieved_at = models.DateTimeField("coletado em", default=timezone.now)
    excerpt = models.CharField(
        "trecho literal",
        max_length=500,
        blank=True,
        help_text="Trecho copiado da fonte, sem alterações (até 500 caracteres).",
    )
    method = models.CharField(
        "método",
        max_length=120,
        validators=[
            RegexValidator(
                EVIDENCE_METHOD_PATTERN,
                "Use connector:<fonte>, regex:<nome>, rule:<nome>, llm:<modelo>@<prompt> ou human.",
            )
        ],
        help_text="Como o valor foi obtido. Ex.: connector:devpost, rule:cnae_map, human.",
    )
    confidence = models.FloatField(
        "confiança", null=True, blank=True, validators=UNIT_INTERVAL, help_text="De 0 a 1."
    )
    verified = models.BooleanField(
        "citação verificada",
        default=False,
        help_text="O trecho foi encontrado no texto da fonte?",
    )

    class Meta:
        ordering = ["-retrieved_at", "-id"]
        verbose_name = "evidência"
        verbose_name_plural = "evidências"
        indexes = [
            models.Index(fields=["content_type", "object_id", "field"], name="evidence_entity_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1),
                name="evidence_confidence_in_0_1",
            ),
            # ADR-004: todo fato observado tem fonte.
            models.CheckConstraint(
                condition=~Q(kind="observed") | ~Q(source_url=""),
                name="evidence_observed_has_source_url",
            ),
        ]

    def __str__(self):
        reference = self.source_url or self.excerpt[:60] or self.method
        return f"{self.field} · {self.get_kind_display()} · {reference}"

    def clean(self):
        errors = {}
        if self.value is None:
            errors["value"] = "Informe o valor afirmado."
        if self.kind == self.Kind.OBSERVED and not self.source_url:
            errors["source_url"] = "Fato observado exige a URL da fonte (ADR-004)."
        if self.kind == self.Kind.MANUAL and self.method != "human":
            errors["method"] = "Evidência manual usa o método 'human'."
        elif self.kind in (self.Kind.OBSERVED, self.Kind.INFERRED) and self.method == "human":
            errors["method"] = "O método 'human' só vale para evidência manual."
        if missing := missing_entity_error(self.content_type_id, self.object_id):
            errors["object_id"] = missing
        if errors:
            raise ValidationError(errors)


class Triage(models.Model):
    """Decisão humana sobre uma entidade; fonte das métricas de qualidade (E14)."""

    class Status(models.TextChoices):
        NEW = "new", "Nova"
        INTERESTING = "interesting", "Interessante"
        DISCARDED = "discarded", "Descartada"
        ACTING = "acting", "Em andamento"
        DONE = "done", "Concluída"

    class DiscardReason(models.TextChoices):
        NOT_RELEVANT = "not_relevant", "Não relevante"
        TOO_FAR = "too_far", "Longe demais"
        INELIGIBLE = "ineligible", "Inelegível"
        TOO_MUCH_EFFORT = "too_much_effort", "Esforço demais"
        LOW_VALUE = "low_value", "Pouco valor"
        DUPLICATE = "duplicate", "Duplicada"
        BAD_DATA = "bad_data", "Dados ruins"
        OTHER = "other", "Outro"

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo da entidade",
        on_delete=models.CASCADE,
        limit_choices_to=ENTITY_CHOICES,
    )
    object_id = models.PositiveBigIntegerField("ID da entidade")
    entity = GenericForeignKey("content_type", "object_id")

    status = models.CharField("situação", max_length=12, choices=Status.choices, default=Status.NEW)
    discard_reason = models.CharField(
        "motivo do descarte", max_length=20, choices=DiscardReason.choices, blank=True
    )
    note = models.TextField("nota", blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="decidido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField("decidido em", null=True, blank=True)

    class Meta:
        ordering = ["-decided_at", "-id"]
        verbose_name = "triagem"
        verbose_name_plural = "triagens"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"], name="uniq_triage_entity"
            ),
            models.CheckConstraint(
                condition=~Q(status="discarded") | ~Q(discard_reason=""),
                name="triage_discard_needs_reason",
            ),
        ]

    def __str__(self):
        return f"{self.entity} — {self.get_status_display()}"

    def clean(self):
        errors = {}
        if self.status == self.Status.DISCARDED and not self.discard_reason:
            errors["discard_reason"] = "Informe o motivo do descarte."
        if missing := missing_entity_error(self.content_type_id, self.object_id):
            errors["object_id"] = missing
        if errors:
            raise ValidationError(errors)
