"""Memória comercial (ADR-012): o que já fizemos com cada organização."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models.catalog import ServiceOffering
from core.models.contact import ContactPoint
from core.models.organization import Organization


class Interaction(models.Model):
    """Um contato, proposta, reunião ou entrega com uma organização.

    Responde "já falamos com eles? quando? sobre o quê? resultado? próximo passo?". Ao salvar ou
    apagar, o status de relacionamento da organização é recalculado
    (`core.services.relationship`). `occurred_at` pode ficar em branco: histórico que o titular
    ainda não confirmou entra sem data inventada (`data_status=pending`).

    Contém dados pessoais (cargo do contato): fica só no banco, nunca no git (ADR-014).
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "E-mail"
        PHONE = "phone", "Telefone"
        WHATSAPP = "whatsapp", "WhatsApp"
        IN_PERSON = "in_person", "Presencial"
        FORM = "form", "Formulário do site"
        OTHER = "other", "Outro"

    class Kind(models.TextChoices):
        PROPOSAL_SENT = "proposal_sent", "Proposta enviada"
        MEETING = "meeting", "Reunião"
        MESSAGE = "message", "Mensagem"
        CALL = "call", "Ligação"
        VISIT = "visit", "Visita"
        COURSE_DELIVERED = "course_delivered", "Curso/oficina realizado"
        EVENT_PARTICIPATION = "event_participation", "Participação em evento"
        RESPONSE_RECEIVED = "response_received", "Resposta recebida"
        OTHER = "other", "Outro"

    class Outcome(models.TextChoices):
        PENDING = "pending", "Pendente"
        POSITIVE = "positive", "Positivo"
        NEGATIVE = "negative", "Negativo"
        NO_RESPONSE = "no_response", "Sem resposta"
        WON = "won", "Fechado (ganho)"
        LOST = "lost", "Perdido"

    class DataStatus(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        PENDING = "pending", "Pendente de confirmação"

    organization = models.ForeignKey(
        Organization,
        verbose_name="organização",
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    occurred_at = models.DateField(
        "data", null=True, blank=True, help_text="Em branco se ainda não confirmada."
    )
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    channel = models.CharField("canal", max_length=10, choices=Channel.choices, blank=True)
    service = models.ForeignKey(
        ServiceOffering,
        verbose_name="serviço",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interactions",
    )
    deal = models.ForeignKey(
        "core.Deal",
        verbose_name="negócio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interactions",
        help_text="Pipeline (E23): agrupa as interações de um mesmo negócio.",
    )
    contact_point = models.ForeignKey(
        ContactPoint,
        verbose_name="contato",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interactions",
    )
    contact_name_role = models.CharField(
        "cargo/papel do contato",
        max_length=120,
        blank=True,
        help_text="Dado pessoal: prefira o cargo ao nome e registre só o necessário.",
    )
    summary = models.TextField("resumo", blank=True)
    outcome = models.CharField(
        "resultado", max_length=12, choices=Outcome.choices, default=Outcome.PENDING
    )
    next_action = models.CharField("próxima ação", max_length=255, blank=True)
    next_action_at = models.DateField("próxima ação em", null=True, blank=True)
    attachments_url = models.URLField(
        "link dos anexos",
        max_length=500,
        blank=True,
        help_text="Ex.: proposta no Drive da empresa. Nunca anexe arquivos aqui.",
    )
    data_status = models.CharField(
        "situação do registro",
        max_length=10,
        choices=DataStatus.choices,
        default=DataStatus.CONFIRMED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = [models.F("occurred_at").desc(nulls_first=True), "-created_at"]
        verbose_name = "interação"
        verbose_name_plural = "interações"
        indexes = [models.Index(fields=["next_action_at"], name="interaction_next_action_idx")]

    def __str__(self):
        when = self.occurred_at.strftime("%d/%m/%Y") if self.occurred_at else "data pendente"
        return f"{self.organization} · {self.get_kind_display()} ({when})"

    def clean(self):
        errors = {}
        if self.contact_point_id and self.organization_id:
            if self.contact_point.organization_id != self.organization_id:
                errors["contact_point"] = "O contato pertence a outra organização."
        if (
            self.deal_id
            and self.organization_id
            and self.deal.organization_id != self.organization_id
        ):
            errors["deal"] = "O negócio pertence a outra organização."
        if self.next_action_at and not self.next_action:
            errors["next_action"] = "Descreva a próxima ação que tem data."
        if errors:
            raise ValidationError(errors)


class FollowUp(Organization):
    """Visão "próximas ações": organizações com lembrete marcado (sem tabela própria)."""

    class Meta:
        proxy = True
        verbose_name = "próxima ação"
        verbose_name_plural = "próximas ações"
