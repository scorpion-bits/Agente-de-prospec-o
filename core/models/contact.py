"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from core.models.organization import Organization
from core.services.normalize import (
    normalize_contact_value,
    normalize_suppression_value,
)


class ContactPointQuerySet(models.QuerySet):
    def usable(self):
        """Contatos ativos e fora do opt-out: o único conjunto que pode ser exibido ou usado.

        Remove os contatos cujo e-mail, telefone, domínio ou organização consta em `Suppression`
        (e os de organizações marcadas como `do_not_contact`). Ver `core.services.suppression`.
        """
        from core.services.suppression import exclude_suppressed

        return exclude_suppressed(self.filter(status=ContactPoint.Status.ACTIVE))


class ContactPoint(models.Model):
    """Forma de contato **institucional** de uma organização.

    Sem evidência não entra (`evidence` é obrigatória). Para exibir ou usar contatos em
    qualquer fluxo, passe por `ContactPoint.objects.usable()`: ele respeita o opt-out.
    """

    class Kind(models.TextChoices):
        EMAIL = "email", "E-mail"
        PHONE = "phone", "Telefone"
        WHATSAPP = "whatsapp", "WhatsApp"
        CONTACT_FORM = "contact_form", "Formulário de contato"
        WEBSITE = "website", "Site"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        LINKEDIN_COMPANY = "linkedin_company", "LinkedIn da organização"
        YOUTUBE = "youtube", "YouTube"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        BOUNCED = "bounced", "Devolvido"
        INVALID = "invalid", "Inválido"

    organization = models.ForeignKey(
        Organization,
        verbose_name="organização",
        on_delete=models.CASCADE,
        related_name="contact_points",
    )
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    value = models.CharField("valor", max_length=500)
    label = models.CharField("rótulo", max_length=120, blank=True, help_text='Ex.: "Secretaria".')
    is_personal = models.BooleanField(
        "dado pessoal",
        default=False,
        help_text="E-mail/telefone de pessoa identificada (LGPD): prefira contatos institucionais.",
    )
    role_hint = models.CharField(
        "cargo/setor",
        max_length=120,
        blank=True,
        help_text="Só se publicado pela própria organização; nunca inventado.",
    )
    evidence = models.ForeignKey(
        "core.Evidence",
        verbose_name="evidência",
        # RESTRICT (e não PROTECT): apagar a organização apaga contato e evidência juntos.
        on_delete=models.RESTRICT,
        related_name="contact_points",
    )
    last_verified_at = models.DateTimeField("verificado em", null=True, blank=True)
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.ACTIVE
    )

    objects = ContactPointQuerySet.as_manager()

    class Meta:
        ordering = ["organization", "kind", "value"]
        verbose_name = "contato"
        verbose_name_plural = "contatos"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind", "value"], name="uniq_contact_org_kind_value"
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"

    def save(self, *args, **kwargs):
        self.value = normalize_contact_value(self.kind, self.value)
        super().save(*args, **kwargs)

    def clean(self):
        self.value = normalize_contact_value(self.kind, self.value)
        if self.evidence_id and self.organization_id:
            organization_type = ContentType.objects.get_for_model(Organization)
            about_this_organization = (
                self.evidence.content_type_id == organization_type.pk
                and self.evidence.object_id == self.organization_id
            )
            if not about_this_organization:
                raise ValidationError(
                    {"evidence": "A evidência precisa ser sobre esta organização."}
                )


class Suppression(models.Model):
    """Opt-out (LGPD): contatos, domínios e organizações que nunca devem ser abordados.

    Consultada antes de exibir qualquer contato e antes de qualquer abordagem
    (`core.services.suppression`). O valor é normalizado ao salvar.
    """

    class Kind(models.TextChoices):
        EMAIL = "email", "E-mail"
        PHONE = "phone", "Telefone"
        DOMAIN = "domain", "Domínio"
        ORGANIZATION = "organization", "Organização"

    kind = models.CharField("tipo", max_length=15, choices=Kind.choices)
    value = models.CharField(
        "valor",
        max_length=255,
        help_text="E-mail, telefone, domínio (vale também para subdomínios) ou CNPJ/nome da "
        "organização.",
    )
    reason = models.CharField("motivo", max_length=255, blank=True)
    created_at = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        ordering = ["kind", "value"]
        verbose_name = "supressão (opt-out)"
        verbose_name_plural = "supressões (opt-out)"
        constraints = [
            models.UniqueConstraint(fields=["kind", "value"], name="uniq_suppression_kind_value"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"

    def save(self, *args, **kwargs):
        self._normalize()
        super().save(*args, **kwargs)

    def clean(self):
        self._normalize()
        if self.kind in self.Kind.values and not self.value:
            raise ValidationError({"value": "Valor inválido para este tipo de supressão."})

    def _normalize(self):
        if self.kind in self.Kind.values:
            self.value = normalize_suppression_value(self.kind, self.value)
