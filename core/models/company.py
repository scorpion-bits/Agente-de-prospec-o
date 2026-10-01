"""Perfil da própria empresa (linha única): base da elegibilidade em editais (ADR-013)."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models.common import UF_VALIDATOR, LegalForm
from core.services.normalize import is_valid_cnpj, normalize_cnpj


class CompanyProfile(models.Model):
    """Dados da Scorpion Bits usados para checar elegibilidade (MEI, CNAE, idade da empresa).

    Existe **uma** linha (`pk=1`). O CNPJ e a razão social do titular são dado pessoal e o
    repositório é público (ADR-014): só entram pelo `.env` (`COMPANY_CNPJ`) ou pelo admin.
    """

    class Status(models.TextChoices):
        ACTIVE = "ativa", "Ativa"
        OTHER = "outra", "Outra situação"

    SINGLETON_PK = 1

    legal_form = models.CharField(
        "natureza jurídica", max_length=14, choices=LegalForm.choices, default=LegalForm.MEI
    )
    status = models.CharField("situação", max_length=5, choices=Status.choices, default="ativa")
    opened_at = models.DateField("data de abertura", null=True, blank=True)
    cnpj = models.CharField(  # noqa: DJ001
        "CNPJ",
        max_length=18,
        null=True,
        blank=True,
        help_text="Só pelo .env/admin; nunca no git. Aceita a máscara.",
    )
    legal_name = models.CharField("razão social", max_length=255, blank=True)
    hq_municipality = models.CharField("município da sede", max_length=120, blank=True)
    hq_uf = models.CharField("UF da sede", max_length=2, blank=True, validators=[UF_VALIDATOR])
    annual_revenue_cap_brl = models.DecimalField(
        "teto de faturamento anual (R$)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    website = models.URLField("site", max_length=500, blank=True)
    contact_email = models.EmailField("e-mail de contato", blank=True)
    activity_mode = models.CharField("modalidade de atuação", max_length=40, blank=True)
    primary_cnae = models.CharField("CNAE principal", max_length=12, blank=True)
    cnaes = models.JSONField(
        "CNAEs",
        default=list,
        blank=True,
        help_text='Lista de {"code", "description", "role": "principal|secundario", "occupation"}.',
    )
    notes = models.TextField("observações", blank=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "perfil da empresa"
        verbose_name_plural = "perfil da empresa"
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="company_profile_singleton"),
        ]

    def __str__(self):
        return "Scorpion Bits"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        self.cnpj = normalize_cnpj(self.cnpj) or None
        self.hq_uf = (self.hq_uf or "").strip().upper()
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """A linha única, ou `None` se o perfil ainda não foi carregado."""
        return cls.objects.filter(pk=cls.SINGLETON_PK).first()

    @classmethod
    def get_or_new(cls):
        return cls.get() or cls(pk=cls.SINGLETON_PK)

    def clean(self):
        self.cnpj = normalize_cnpj(self.cnpj) or None
        if self.cnpj and not is_valid_cnpj(self.cnpj):
            raise ValidationError({"cnpj": "CNPJ inválido: confira os dígitos verificadores."})
        others = type(self).objects.exclude(pk=self.SINGLETON_PK)
        if others.exists():  # pragma: no cover - barrado também pela constraint
            raise ValidationError("O perfil da empresa tem uma única linha.")
