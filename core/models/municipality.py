"""Municípios do IBGE: base da relevância geográfica (docs/architecture/geo-relevance.md)."""

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.services.normalize import name_key

UF_BY_IBGE_CODE = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}  # fmt: skip


class MunicipalityManager(models.Manager):
    def get_by_natural_key(self, ibge_code):
        return self.get(ibge_code=ibge_code)


class Municipality(models.Model):
    """Município brasileiro (código IBGE de 7 dígitos) com a coordenada da sede."""

    class Region(models.TextChoices):
        NORTH = "N", "Norte"
        NORTHEAST = "NE", "Nordeste"
        SOUTHEAST = "SE", "Sudeste"
        SOUTH = "S", "Sul"
        CENTER_WEST = "CO", "Centro-Oeste"

    # O primeiro dígito do código IBGE é a região.
    REGION_BY_DIGIT = {
        "1": Region.NORTH,
        "2": Region.NORTHEAST,
        "3": Region.SOUTHEAST,
        "4": Region.SOUTH,
        "5": Region.CENTER_WEST,
    }

    ibge_code = models.PositiveIntegerField(
        "código IBGE",
        unique=True,
        validators=[MinValueValidator(1_000_000), MaxValueValidator(9_999_999)],
    )
    name = models.CharField("nome", max_length=120)
    name_key = models.CharField("nome normalizado", max_length=120, editable=False)
    uf = models.CharField(
        "UF", max_length=2, validators=[RegexValidator(r"^[A-Z]{2}$", "Sigla da UF em maiúsculas.")]
    )
    region = models.CharField("região", max_length=2, choices=Region.choices)
    lat = models.FloatField("latitude", validators=[MinValueValidator(-90), MaxValueValidator(90)])
    lon = models.FloatField(
        "longitude", validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    is_capital = models.BooleanField("capital", default=False)

    objects = MunicipalityManager()

    class Meta:
        ordering = ["uf", "name"]
        verbose_name = "município"
        verbose_name_plural = "municípios"
        constraints = [
            models.UniqueConstraint(fields=["name_key", "uf"], name="uniq_municipality_name_uf"),
        ]
        indexes = [models.Index(fields=["name_key"], name="municipality_name_key_idx")]

    def __str__(self):
        return f"{self.name}/{self.uf}"

    def save(self, *args, **kwargs):
        self.name_key = name_key(self.name)
        self.uf = (self.uf or "").strip().upper()
        if not self.region and self.ibge_code:
            self.region = self.REGION_BY_DIGIT[str(self.ibge_code)[0]]
        super().save(*args, **kwargs)

    def natural_key(self):
        return (self.ibge_code,)
