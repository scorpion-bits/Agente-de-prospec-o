"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.fields import ChoiceArrayField
from core.models.common import UF_VALIDATOR, LegalForm
from core.models.organization import Organization
from core.services.canonical import opportunity_canonical_key


class Opportunity(models.Model):
    """Edital, hackathon, game jam, evento, programa, concurso, chamada ou licitação."""

    class Kind(models.TextChoices):
        EDITAL = "edital", "Edital"
        HACKATHON = "hackathon", "Hackathon"
        GAME_JAM = "game_jam", "Game jam"
        EVENT = "event", "Evento"
        PROGRAM = "program", "Programa"
        CONTEST = "contest", "Concurso"
        PROCUREMENT = "procurement", "Licitação"
        CALL_FOR_PARTNERS = "call_for_partners", "Chamada para parceiros"
        OTHER = "other", "Outro"

    class Category(models.TextChoices):
        CULTURE = "culture", "Cultura"
        INNOVATION = "innovation", "Inovação"
        EDUCATION = "education", "Educação"
        GAMES = "games", "Jogos"
        TECHNOLOGY = "technology", "Tecnologia"
        ENTREPRENEURSHIP = "entrepreneurship", "Empreendedorismo"

    class Modality(models.TextChoices):
        ONLINE = "online", "Online"
        IN_PERSON = "in_person", "Presencial"
        HYBRID = "hybrid", "Híbrida"
        UNKNOWN = "unknown", "Não informada"

    class Scope(models.TextChoices):
        MUNICIPAL = "municipal", "Municipal"
        REGIONAL = "regional", "Regional"
        STATE = "state", "Estadual"
        NATIONAL = "national", "Nacional"
        INTERNATIONAL = "international", "Internacional"

    class LegalEntityRequirement(models.TextChoices):
        YES = "yes", "Sim"
        NO = "no", "Não"
        UNKNOWN = "unknown", "Não informado"

    class Benefit(models.TextChoices):
        MONEY = "money", "Dinheiro"
        CONTRACT = "contract", "Contrato"
        PRIZE = "prize", "Prêmio"
        VISIBILITY = "visibility", "Visibilidade"
        NETWORKING = "networking", "Networking"
        MENTORING = "mentoring", "Mentoria"
        INFRASTRUCTURE = "infrastructure", "Infraestrutura"
        ACCELERATION = "acceleration", "Aceleração"
        PARTNERSHIP = "partnership", "Parceria"
        CLIENTS = "clients", "Clientes"
        PORTFOLIO = "portfolio", "Portfólio"
        CERTIFICATION = "certification", "Certificação"
        INVESTORS = "investors", "Investidores"

    class Effort(models.TextChoices):
        LOW = "low", "Baixo"
        MEDIUM = "medium", "Médio"
        HIGH = "high", "Alto"
        UNKNOWN = "unknown", "Desconhecido"

    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        UPCOMING = "upcoming", "Em breve"
        CLOSED = "closed", "Encerrada"
        UNKNOWN = "unknown", "Desconhecida"

    kind = models.CharField("tipo", max_length=20, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField("título", max_length=300)
    organizer = models.ForeignKey(
        Organization,
        verbose_name="organizador",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    organizer_name = models.CharField("nome do organizador", max_length=200, blank=True)
    description = models.TextField("resumo", blank=True)
    categories = ChoiceArrayField(
        models.CharField(max_length=20, choices=Category.choices),
        verbose_name="categorias",
        default=list,
        blank=True,
    )
    modality = models.CharField(
        "modalidade", max_length=10, choices=Modality.choices, default=Modality.UNKNOWN
    )

    # Provisório até a E12 (tabela `Municipality` do IBGE).
    municipality_name = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True, validators=[UF_VALIDATOR])
    scope = models.CharField("abrangência", max_length=15, choices=Scope.choices, blank=True)

    # Datas. Quando a fonte traz só o dia: prazo = 23:59 local; início/abertura = 00:00 local.
    opens_at = models.DateTimeField("abertura das inscrições", null=True, blank=True)
    deadline_at = models.DateTimeField("prazo final", null=True, blank=True)
    starts_at = models.DateTimeField("início do evento/projeto", null=True, blank=True)
    ends_at = models.DateTimeField("fim do evento/projeto", null=True, blank=True)

    # Requisitos da empresa, comparados com o `CompanyProfile` no scoring (ADR-013).
    eligibility_text = models.TextField("texto de elegibilidade", blank=True)
    requires_legal_entity = models.CharField(
        "exige CNPJ",
        max_length=7,
        choices=LegalEntityRequirement.choices,
        default=LegalEntityRequirement.UNKNOWN,
    )
    eligible_legal_forms = ChoiceArrayField(
        models.CharField(max_length=20, choices=LegalForm.choices),
        verbose_name="naturezas jurídicas aceitas",
        default=list,
        blank=True,
        help_text="Vazio = nenhuma restrição conhecida.",
    )
    exclusive_small_business = models.BooleanField(
        "cota exclusiva ME/EPP/MEI",
        null=True,
        blank=True,
        help_text="Desconhecido quando não informado.",
    )
    min_company_age_months = models.PositiveIntegerField(
        "idade mínima da empresa (meses)", null=True, blank=True
    )
    required_cnaes = ArrayField(
        models.CharField(max_length=12),
        verbose_name="CNAEs exigidos (prefixos)",
        default=list,
        blank=True,
        help_text="Separe por vírgula. A comparação ignora a pontuação. Vazio = sem exigência.",
    )
    eligible_regions = ArrayField(
        models.CharField(max_length=80),
        verbose_name="regiões elegíveis",
        default=list,
        blank=True,
        help_text="UFs ou municípios, separados por vírgula. Vazio = sem restrição conhecida.",
    )

    requirements_text = models.TextField("requisitos", blank=True)
    prize_text = models.CharField("prêmio/valor (texto)", max_length=300, blank=True)
    prize_amount_brl = models.DecimalField(
        "valor numérico (R$)",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    benefits = ChoiceArrayField(
        models.CharField(max_length=20, choices=Benefit.choices),
        verbose_name="benefícios",
        default=list,
        blank=True,
    )
    participation_cost_text = models.CharField("custo de participação", max_length=300, blank=True)
    effort_estimate = models.CharField(
        "esforço estimado", max_length=10, choices=Effort.choices, default=Effort.UNKNOWN
    )

    official_url = models.URLField("URL oficial", max_length=500, blank=True)
    canonical_key = models.CharField(
        "chave canônica",
        max_length=600,
        unique=True,
        blank=True,
        help_text="Identifica a oportunidade para evitar duplicatas. Em branco = gerada "
        "(URL oficial, ou organizador + título + prazo).",
    )
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.UNKNOWN
    )
    extraction_version = models.CharField("versão da extração", max_length=60, blank=True)
    first_seen_at = models.DateTimeField("vista pela primeira vez em", default=timezone.now)
    last_seen_at = models.DateTimeField("vista pela última vez em", default=timezone.now)

    evidence_items = GenericRelation("core.Evidence")
    triage_items = GenericRelation("core.Triage")

    class Meta:
        ordering = ["-first_seen_at", "-id"]
        verbose_name = "oportunidade"
        verbose_name_plural = "oportunidades"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self._normalize()
        super().save(*args, **kwargs)

    def clean(self):
        self._normalize()

    def _normalize(self):
        self.uf = (self.uf or "").strip().upper()
        self.canonical_key = (self.canonical_key or "").strip()
        if not self.canonical_key:
            organizer = self.organizer_name or (self.organizer.name if self.organizer_id else "")
            self.canonical_key = opportunity_canonical_key(
                official_url=self.official_url,
                organizer_name=organizer,
                title=self.title,
                deadline_at=self.deadline_at,
            )
