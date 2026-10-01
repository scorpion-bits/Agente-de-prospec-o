"""Portfólio da Scorpion Bits: prova de capacidade usada no matching (ADR-012)."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from core.models.catalog import ServiceOffering


class PortfolioItem(models.Model):
    """Um trabalho realizado (jogo, curso, site…) que prova que sabemos entregar um serviço."""

    class Kind(models.TextChoices):
        GAME = "game", "Jogo"
        COURSE = "course", "Curso/oficina"
        PROTOTYPE = "prototype", "Protótipo"
        WEBSITE = "website", "Site"
        SYSTEM = "system", "Sistema"
        OTHER = "other", "Outro"

    class DataStatus(models.TextChoices):
        COMPLETE = "complete", "Completo"
        PENDING = "pending", "Dados pendentes"
        DESCRIPTION_PENDING = "description_pending", "Descrição pendente"
        TO_CONFIRM = "to_confirm", "A confirmar"

    slug = models.SlugField(
        "identificador",
        max_length=60,
        unique=True,
        help_text="Chave estável usada pela importação: não renomeie.",
    )
    title = models.CharField("título", max_length=160)
    kind = models.CharField("tipo", max_length=12, choices=Kind.choices)
    year = models.PositiveSmallIntegerField("ano", null=True, blank=True)
    description = models.TextField("descrição", blank=True)
    public_url = models.URLField("URL pública", max_length=500, blank=True)
    url_source = models.CharField(
        "origem da URL", max_length=120, blank=True, help_text="Ex.: informado pelo titular."
    )
    services = models.ManyToManyField(
        ServiceOffering,
        verbose_name="serviços comprovados",
        blank=True,
        related_name="portfolio_items",
    )
    capability_tags = ArrayField(
        models.CharField(max_length=60),
        verbose_name="capacidades",
        default=list,
        blank=True,
        help_text="Separe por vírgula. Ex.: jogos, ensino_presencial.",
    )
    public = models.BooleanField(
        "pode ser citado em propostas", default=False, help_text="Só marque se já é público."
    )
    status = models.CharField(
        "situação dos dados",
        max_length=20,
        choices=DataStatus.choices,
        default=DataStatus.PENDING,
    )
    notes = models.TextField("observações", blank=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "item de portfólio"
        verbose_name_plural = "itens de portfólio"

    def __str__(self):
        return self.title
