"""Rascunho de abordagem (E24, ADR-046): o humano edita e envia por conta própria."""

from django.conf import settings
from django.db import models

from core.models.catalog import ServiceOffering
from core.models.organization import Organization


class OutreachDraft(models.Model):
    """Texto curto gerado a partir de fatos com origem; nunca é enviado pelo sistema (ADR-005).

    `claims` liga cada afirmação aos fatos que a sustentam; `validation_issues` lista o que o
    validador achou de errado (rascunho `rejected` fica guardado para o A/B, mas não é para usar).
    `facts` guarda a lista de fatos enviada ao modelo, para auditar de onde saiu cada frase.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Mode(models.TextChoices):
        FIRST_CONTACT = "first_contact", "Primeiro contato"
        FOLLOW_UP = "follow_up", "Retomada"

    class Status(models.TextChoices):
        VALID = "valid", "Válido"
        REJECTED = "rejected", "Rejeitado pelo validador"

    class Rating(models.TextChoices):
        USABLE = "usable", "Usável com edição leve"
        REWRITE = "rewrite", "Precisa reescrever"
        UNUSABLE = "unusable", "Inútil"

    organization = models.ForeignKey(
        Organization,
        verbose_name="organização",
        on_delete=models.CASCADE,
        related_name="outreach_drafts",
    )
    service = models.ForeignKey(
        ServiceOffering,
        verbose_name="serviço",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    mode = models.CharField("modo", max_length=14, choices=Mode.choices)
    subject = models.CharField("assunto", max_length=200, blank=True)
    body = models.TextField("texto")
    claims = models.JSONField(
        "afirmações e fatos",
        default=list,
        blank=True,
        help_text='Lista de {"text", "about", "facts": [ids]}.',
    )
    facts = models.JSONField("fatos enviados ao modelo", default=list, blank=True)
    status = models.CharField("situação", max_length=10, choices=Status.choices)
    validation_issues = models.JSONField("problemas do validador", default=list, blank=True)
    attempts = models.JSONField(
        "tentativas", default=list, blank=True, help_text="Estratégias tentadas e por que caíram."
    )
    strategy = models.CharField("estratégia", max_length=80, blank=True)
    prompt_version = models.CharField("versão do prompt", max_length=20, blank=True)
    cost_usd = models.DecimalField("custo (US$)", max_digits=10, decimal_places=6, default=0)
    rating = models.CharField("avaliação humana", max_length=10, choices=Rating.choices, blank=True)
    rating_note = models.CharField("nota da avaliação", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="gerado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "rascunho de abordagem"
        verbose_name_plural = "rascunhos de abordagem"

    def __str__(self):
        return f"{self.organization} · {self.get_channel_display()} · {self.created_at:%Y-%m-%d}"
