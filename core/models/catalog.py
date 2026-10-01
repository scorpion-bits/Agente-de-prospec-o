"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from core.fields import ChoiceArrayField
from core.models.common import UNIT_INTERVAL, GeoProfile
from core.models.organization import Organization


class ServiceOfferingManager(models.Manager):
    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class ServiceOffering(models.Model):
    """Catálogo de serviços como dado (novos serviços = novas linhas, sem código).

    Tem chave natural (`slug`): `loaddata services` atualiza em vez de duplicar. Atenção: o
    `loaddata` sobrescreve edições do admin; para carregar só o que falta, use `load_services`.
    """

    class Category(models.TextChoices):
        GAMES = "games", "Jogos"
        EDUCATION = "education", "Educação"
        SOFTWARE = "software", "Software"
        WEB = "web", "Web"
        OTHER = "other", "Outro"

    class MeiCoverage(models.TextChoices):
        COVERED = "covered", "Coberto pelo MEI"
        VERIFY = "verify", "Verificar com o contador"
        NOT_COVERED = "not_covered", "Exigiria ME"

    slug = models.SlugField(
        "identificador",
        max_length=60,
        unique=True,
        help_text="Chave estável usada por importações e regras: não renomeie.",
    )
    name = models.CharField("nome", max_length=120)
    category = models.CharField("categoria", max_length=12, choices=Category.choices)
    description = models.TextField("descrição", blank=True)
    keywords = ArrayField(
        models.CharField(max_length=80),
        verbose_name="palavras-chave",
        default=list,
        blank=True,
        help_text="Separe por vírgula. Usadas pelas regras de matching (E20).",
    )
    target_org_kinds = ChoiceArrayField(
        models.CharField(max_length=20, choices=Organization.Kind.choices),
        verbose_name="tipos de organização-alvo",
        default=list,
        blank=True,
    )
    target_cnaes = ArrayField(
        models.CharField(max_length=12),
        verbose_name="CNAEs-alvo (prefixos)",
        default=list,
        blank=True,
        help_text="CNAEs das organizações que costumam comprar. Vazio = qualquer.",
    )
    geo_profile = models.CharField(
        "perfil geográfico",
        max_length=20,
        choices=[c for c in GeoProfile.choices if c[0] != GeoProfile.EDITAL_SCOPE],
        help_text="Presencial recorrente: cursos e oficinas. Presencial pontual: game jam e "
        "eventos. Online: distância irrelevante. Serviço remoto: software, web e jogos sob "
        "encomenda. Ver docs/architecture/geo-relevance.md.",
    )
    typical_ticket_min_brl = models.DecimalField(
        "ticket típico — mínimo (R$)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    typical_ticket_max_brl = models.DecimalField(
        "ticket típico — máximo (R$)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    active = models.BooleanField("ativo", default=True)
    mei_coverage = models.CharField(
        "cobertura pelo MEI",
        max_length=12,
        choices=MeiCoverage.choices,
        default=MeiCoverage.VERIFY,
        help_text="Se o enquadramento atual cobre vender este serviço (ADR-015).",
    )
    required_cnae_prefixes = ArrayField(
        models.CharField(max_length=12),
        verbose_name="CNAEs exigidos da empresa (prefixos)",
        default=list,
        blank=True,
        help_text="Qualquer um deles cobre o serviço. A comparação ignora a pontuação.",
    )

    objects = ServiceOfferingManager()

    class Meta:
        ordering = ["name"]
        verbose_name = "serviço do catálogo"
        verbose_name_plural = "serviços do catálogo"
        constraints = [
            models.CheckConstraint(
                condition=Q(typical_ticket_min_brl__isnull=True)
                | Q(typical_ticket_max_brl__isnull=True)
                | Q(typical_ticket_max_brl__gte=F("typical_ticket_min_brl")),
                name="service_ticket_max_gte_min",
            ),
        ]

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.slug,)


class Match(models.Model):
    """Hipótese "a organização X provavelmente compraria o serviço Y" (E20).

    `portfolio_refs` aponta os trabalhos do portfólio que provam a capacidade (ADR-012).
    """

    organization = models.ForeignKey(
        Organization,
        verbose_name="organização",
        on_delete=models.CASCADE,
        related_name="matches",
    )
    service = models.ForeignKey(
        ServiceOffering, verbose_name="serviço", on_delete=models.CASCADE, related_name="matches"
    )
    reasons = models.JSONField(
        "motivos",
        default=list,
        blank=True,
        help_text='Lista de {"text": ..., "evidence_id": ..., "kind": "observed|inferred"}.',
    )
    strength = models.FloatField("força", validators=UNIT_INTERVAL, help_text="De 0 a 1.")
    method = models.CharField(
        "método", max_length=30, default="rules_v1", help_text="Ex.: rules_v1, llm_v1."
    )
    portfolio_refs = models.ManyToManyField(
        "core.PortfolioItem",
        verbose_name="portfólio como prova",
        blank=True,
        related_name="matches",
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-strength", "-created_at"]
        verbose_name = "match"
        verbose_name_plural = "matches"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "service", "method"], name="uniq_match_org_service_method"
            ),
            models.CheckConstraint(
                condition=Q(strength__gte=0, strength__lte=1), name="match_strength_in_0_1"
            ),
        ]

    def __str__(self):
        return f"{self.organization} → {self.service}"
