"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Source(models.Model):
    """Uma fonte/conector de dados."""

    class Kind(models.TextChoices):
        API = "api", "API"
        HTML_WATCH = "html_watch", "Página monitorada"
        DATASET = "dataset", "Conjunto de dados"
        SEED_CSV = "seed_csv", "CSV de sementes"
        SEARCH = "search", "Busca"

    class Schedule(models.TextChoices):
        DAILY = "daily", "Diária"
        WEEKLY = "weekly", "Semanal"
        MANUAL = "manual", "Manual (sob demanda)"

    slug = models.SlugField("identificador", max_length=60, unique=True)
    name = models.CharField("nome", max_length=120)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    base_url = models.URLField("URL base", max_length=500, blank=True)
    terms_url = models.URLField("URL dos termos de uso", max_length=500, blank=True)
    robots_ok = models.BooleanField(
        "coleta permitida",
        default=False,
        help_text="robots.txt e termos de uso conferidos e permitem a coleta.",
    )
    license = models.CharField("licença", max_length=60, blank=True, help_text="Ex.: ODbL, CC-BY.")
    reliability = models.PositiveSmallIntegerField(
        "confiabilidade",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 a 5, julgamento humano documentado em docs/research.",
    )
    enabled = models.BooleanField("habilitada", default=False)
    schedule = models.CharField(
        "agendamento", max_length=10, choices=Schedule.choices, default=Schedule.MANUAL
    )
    config = models.JSONField("configuração", default=dict, blank=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "fonte"
        verbose_name_plural = "fontes"

    def __str__(self):
        return self.name
