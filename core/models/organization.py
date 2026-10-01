"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.models.common import UF_VALIDATOR
from core.models.source import Source
from core.services.normalize import (
    is_valid_cnpj,
    normalize_cnpj,
)


class Organization(models.Model):
    """Escola, SESC, empresa, instituição, órgão público ou organizador de evento."""

    class Kind(models.TextChoices):
        SCHOOL = "school", "Escola"
        SESC = "sesc", "SESC"
        COMPANY = "company", "Empresa"
        UNIVERSITY = "university", "Universidade"
        PUBLIC_BODY = "public_body", "Órgão público"
        NGO = "ngo", "ONG / associação"
        EVENT_ORGANIZER = "event_organizer", "Organizador de eventos"
        OTHER = "other", "Outro"

    class SizeHint(models.TextChoices):
        MICRO = "micro", "Micro"
        SMALL = "small", "Pequena"
        MEDIUM = "medium", "Média"
        LARGE = "large", "Grande"
        UNKNOWN = "unknown", "Desconhecido"

    class WebsiteStatus(models.TextChoices):
        UNKNOWN = "unknown", "Não pesquisado"
        FOUND = "found", "Encontrado"
        NOT_FOUND = "not_found", "Não encontrado"
        AMBIGUOUS = "ambiguous", "Ambíguo"

    class RelationshipStatus(models.TextChoices):
        NEVER_CONTACTED = "never_contacted", "Nunca contatada"
        CONTACTED = "contacted", "Contatada"
        IN_CONVERSATION = "in_conversation", "Em conversa"
        PROPOSAL_SENT = "proposal_sent", "Proposta enviada"
        CLIENT = "client", "Cliente"
        LOST = "lost", "Perdida"
        DO_NOT_CONTACT = "do_not_contact", "Não contatar"

    name = models.CharField("nome", max_length=255)
    legal_name = models.CharField("razão social", max_length=255, blank=True)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices, default=Kind.OTHER)

    # Identificadores externos: opcionais e únicos. NULL (nunca "") quando ausentes, senão duas
    # organizações sem o identificador colidiriam na restrição de unicidade.
    cnpj = models.CharField(  # noqa: DJ001
        "CNPJ",
        max_length=18,
        unique=True,
        null=True,
        blank=True,
        help_text="Aceita a máscara; é guardado só com letras e dígitos (14 posições).",
    )
    inep_code = models.CharField(  # noqa: DJ001
        "código INEP",
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\d{8}$", "O código INEP tem 8 dígitos.")],
    )
    osm_id = models.CharField(  # noqa: DJ001
        "ID no OpenStreetMap",
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text="Ex.: way/123456789.",
    )

    segment = models.CharField("segmento", max_length=120, blank=True)
    cnae_main = models.CharField(
        "CNAE principal",
        max_length=12,
        blank=True,
        help_text="A comparação de CNAE ignora a pontuação (85.99-6/03 = 8599603).",
    )
    size_hint = models.CharField(
        "porte (estimado)", max_length=10, choices=SizeHint.choices, default=SizeHint.UNKNOWN
    )

    # Provisório até a E12 (tabela `Municipality` do IBGE).
    municipality_name = models.CharField("município", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True, validators=[UF_VALIDATOR])
    address = models.TextField("endereço", blank=True)
    lat = models.FloatField(
        "latitude",
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    lon = models.FloatField(
        "longitude",
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    website = models.URLField("site", max_length=500, blank=True)
    website_status = models.CharField(
        "situação do site",
        max_length=10,
        choices=WebsiteStatus.choices,
        default=WebsiteStatus.UNKNOWN,
    )

    network = models.CharField(
        "rede",
        max_length=80,
        blank=True,
        db_index=True,
        help_text="Ex.: SESC-SP, SENAC-SP, Centro Paula Souza.",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="organização-mãe",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        help_text="Para redes com várias unidades (ex.: SESC-SP → SESC Bauru).",
    )
    similarity_tags = ArrayField(
        models.CharField(max_length=60),
        verbose_name="tags de similaridade",
        default=list,
        blank=True,
        help_text="Separe por vírgula. Ex.: sistema_s, cultural_publico, educacao_nao_formal.",
    )

    # Derivados das interações (memória comercial, ADR-012): recalculados por
    # `core.services.relationship.refresh_relationship`, não editáveis.
    relationship_status = models.CharField(
        "relacionamento",
        max_length=20,
        choices=RelationshipStatus.choices,
        default=RelationshipStatus.NEVER_CONTACTED,
    )
    last_interaction_at = models.DateField("última interação", null=True, blank=True)
    next_action_at = models.DateField("próxima ação em", null=True, blank=True)

    first_seen_source = models.ForeignKey(
        Source,
        verbose_name="fonte da primeira descoberta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations",
    )
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    # Apagar a organização apaga suas evidências e triagens (sem registros órfãos).
    evidence_items = GenericRelation("core.Evidence")
    triage_items = GenericRelation("core.Triage")

    class Meta:
        ordering = ["name"]
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self._normalize()
        super().save(*args, **kwargs)

    def clean(self):
        self._normalize()
        errors = {}
        if self.cnpj and not is_valid_cnpj(self.cnpj):
            errors["cnpj"] = "CNPJ inválido: confira os dígitos verificadores."
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "Uma organização não pode ser mãe de si mesma."
            elif self._ancestors_loop():
                errors["parent"] = "A hierarquia de organizações não pode formar um ciclo."
        if errors:
            raise ValidationError(errors)

    def _normalize(self):
        """Mantém os identificadores únicos na forma canônica (NULL quando ausentes)."""
        self.cnpj = normalize_cnpj(self.cnpj) or None
        self.inep_code = (self.inep_code or "").strip() or None
        self.osm_id = (self.osm_id or "").strip() or None
        self.uf = (self.uf or "").strip().upper()

    def _ancestors_loop(self):
        seen = {self.pk}
        parent = self.parent
        while parent is not None:
            if parent.pk in seen:
                return True
            seen.add(parent.pk)
            parent = parent.parent
        return False
