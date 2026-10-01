"""Modelo de dados núcleo — ver docs/architecture/data-model.md.

Decisões desta etapa (E03):
- `Evidence` e `Triage` apontam para a entidade por `GenericForeignKey` (ADR-017).
- Listas de strings são `ArrayField` do PostgreSQL; JSON só para estruturas aninhadas (ADR-018).
- Município é provisório (`municipality_name` + `uf`) até a E12 trazer a tabela do IBGE.
- Os campos derivados de relacionamento de `Organization` ficam nos valores padrão até a E03b.
- `Evidence.raw_document` entra na E04, junto com `RawDocument`.
- Identificadores externos únicos e opcionais ficam NULL (nunca "") quando ausentes.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from core.fields import ChoiceArrayField
from core.services.canonical import opportunity_canonical_key
from core.services.normalize import (
    is_valid_cnpj,
    normalize_cnpj,
    normalize_contact_value,
    normalize_suppression_value,
)

# Entidades que recebem Evidence e Triage (ADR-017). `Score` (E13) seguirá a mesma regra.
ENTITY_MODELS = ("organization", "opportunity")
ENTITY_CHOICES = Q(app_label="core", model__in=ENTITY_MODELS)

UF_VALIDATOR = RegexValidator(r"^[A-Z]{2}$", "Use a sigla da UF com duas letras maiúsculas.")
UNIT_INTERVAL = [MinValueValidator(0), MaxValueValidator(1)]

# Métodos: `connector:devpost`, `regex:email`, `rule:cnae_map`,
# `llm:gemini-2.5-flash-lite@prompt_v3` ou `human`.
EVIDENCE_METHOD_PATTERN = r"^(?:(?:connector|regex|rule|llm):\S+|human)$"
EVIDENCE_FIELD_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$"


def missing_entity_error(content_type_id, object_id):
    """Erro de validação se o ID não existe para o tipo escolhido; `None` se existe.

    `Evidence` e `Triage` apontam para a entidade por ID genérico (sem chave estrangeira): quem
    digita o ID à mão no admin poderia criar um registro órfão.
    """
    if not content_type_id or object_id is None:
        return None
    model = ContentType.objects.get_for_id(content_type_id).model_class()
    if model is None or model._default_manager.filter(pk=object_id).exists():
        return None
    return f"Não existe {model._meta.verbose_name} com o ID {object_id}."


class GeoProfile(models.TextChoices):
    """Perfis de relevância geográfica (docs/architecture/geo-relevance.md)."""

    ONSITE_RECURRING = "onsite_recurring", "Presencial recorrente"
    ONSITE_EVENT = "onsite_event", "Presencial pontual"
    ONLINE = "online", "Online"
    EDITAL_SCOPE = "edital_scope", "Abrangência de edital"
    REMOTE_SERVICE = "remote_service", "Serviço remoto"


class LegalForm(models.TextChoices):
    """Natureza jurídica do proponente (`Opportunity.eligible_legal_forms`, ADR-013)."""

    PF = "PF", "Pessoa física"
    MEI = "MEI", "MEI"
    ME = "ME", "Microempresa (ME)"
    EPP = "EPP", "Empresa de pequeno porte (EPP)"
    OTHER_COMPANY = "OTHER_COMPANY", "Demais empresas (médio e grande porte)"
    OSC = "OSC", "Associação, ONG, cooperativa ou instituto (OSC)"


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

    # Derivados das interações (memória comercial, ADR-012): calculados na E03b, não editáveis.
    relationship_status = models.CharField(
        "relacionamento",
        max_length=20,
        choices=RelationshipStatus.choices,
        default=RelationshipStatus.NEVER_CONTACTED,
    )
    last_interaction_at = models.DateTimeField("última interação", null=True, blank=True)
    next_action_at = models.DateTimeField("próxima ação em", null=True, blank=True)

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


class Evidence(models.Model):
    """Uma afirmação sobre um campo de uma entidade, com sua origem (ADR-004).

    Use `core.services.evidence.record_evidence` para criar: ele aplica as regras do ADR-004.
    """

    class Kind(models.TextChoices):
        OBSERVED = "observed", "Observado"
        INFERRED = "inferred", "Inferido"
        MANUAL = "manual", "Manual"

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo da entidade",
        on_delete=models.CASCADE,
        limit_choices_to=ENTITY_CHOICES,
    )
    object_id = models.PositiveBigIntegerField("ID da entidade")
    entity = GenericForeignKey("content_type", "object_id")

    field = models.CharField(
        "campo",
        max_length=80,
        validators=[
            RegexValidator(
                EVIDENCE_FIELD_PATTERN,
                "Use minúsculas, números e _ (ex.: deadline_at, contact.email).",
            )
        ],
        help_text="Afirmação sobre a entidade. Ex.: deadline_at, offers_high_school.",
    )
    value = models.JSONField(
        "valor",
        encoder=DjangoJSONEncoder,
        blank=True,
        help_text='Em JSON: "2026-11-15" (texto entre aspas), 120, true ou ["a", "b"].',
    )
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    source_url = models.URLField("URL da fonte", max_length=1000, blank=True)
    source_name = models.CharField("nome da fonte", max_length=120, blank=True)
    retrieved_at = models.DateTimeField("coletado em", default=timezone.now)
    excerpt = models.CharField(
        "trecho literal",
        max_length=500,
        blank=True,
        help_text="Trecho copiado da fonte, sem alterações (até 500 caracteres).",
    )
    method = models.CharField(
        "método",
        max_length=120,
        validators=[
            RegexValidator(
                EVIDENCE_METHOD_PATTERN,
                "Use connector:<fonte>, regex:<nome>, rule:<nome>, llm:<modelo>@<prompt> ou human.",
            )
        ],
        help_text="Como o valor foi obtido. Ex.: connector:devpost, rule:cnae_map, human.",
    )
    confidence = models.FloatField(
        "confiança", null=True, blank=True, validators=UNIT_INTERVAL, help_text="De 0 a 1."
    )
    verified = models.BooleanField(
        "citação verificada",
        default=False,
        help_text="O trecho foi encontrado no texto da fonte?",
    )

    class Meta:
        ordering = ["-retrieved_at", "-id"]
        verbose_name = "evidência"
        verbose_name_plural = "evidências"
        indexes = [
            models.Index(fields=["content_type", "object_id", "field"], name="evidence_entity_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1),
                name="evidence_confidence_in_0_1",
            ),
            # ADR-004: todo fato observado tem fonte.
            models.CheckConstraint(
                condition=~Q(kind="observed") | ~Q(source_url=""),
                name="evidence_observed_has_source_url",
            ),
        ]

    def __str__(self):
        reference = self.source_url or self.excerpt[:60] or self.method
        return f"{self.field} · {self.get_kind_display()} · {reference}"

    def clean(self):
        errors = {}
        if self.value is None:
            errors["value"] = "Informe o valor afirmado."
        if self.kind == self.Kind.OBSERVED and not self.source_url:
            errors["source_url"] = "Fato observado exige a URL da fonte (ADR-004)."
        if self.kind == self.Kind.MANUAL and self.method != "human":
            errors["method"] = "Evidência manual usa o método 'human'."
        elif self.kind in (self.Kind.OBSERVED, self.Kind.INFERRED) and self.method == "human":
            errors["method"] = "O método 'human' só vale para evidência manual."
        if missing := missing_entity_error(self.content_type_id, self.object_id):
            errors["object_id"] = missing
        if errors:
            raise ValidationError(errors)


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


class Match(models.Model):
    """Hipótese "a organização X provavelmente compraria o serviço Y" (E20).

    `portfolio_refs` (trabalhos que provam a capacidade) entra na E03b, com `PortfolioItem`.
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


class Triage(models.Model):
    """Decisão humana sobre uma entidade; fonte das métricas de qualidade (E14)."""

    class Status(models.TextChoices):
        NEW = "new", "Nova"
        INTERESTING = "interesting", "Interessante"
        DISCARDED = "discarded", "Descartada"
        ACTING = "acting", "Em andamento"
        DONE = "done", "Concluída"

    class DiscardReason(models.TextChoices):
        NOT_RELEVANT = "not_relevant", "Não relevante"
        TOO_FAR = "too_far", "Longe demais"
        INELIGIBLE = "ineligible", "Inelegível"
        TOO_MUCH_EFFORT = "too_much_effort", "Esforço demais"
        LOW_VALUE = "low_value", "Pouco valor"
        DUPLICATE = "duplicate", "Duplicada"
        BAD_DATA = "bad_data", "Dados ruins"
        OTHER = "other", "Outro"

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="tipo da entidade",
        on_delete=models.CASCADE,
        limit_choices_to=ENTITY_CHOICES,
    )
    object_id = models.PositiveBigIntegerField("ID da entidade")
    entity = GenericForeignKey("content_type", "object_id")

    status = models.CharField("situação", max_length=12, choices=Status.choices, default=Status.NEW)
    discard_reason = models.CharField(
        "motivo do descarte", max_length=20, choices=DiscardReason.choices, blank=True
    )
    note = models.TextField("nota", blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="decidido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField("decidido em", null=True, blank=True)

    class Meta:
        ordering = ["-decided_at", "-id"]
        verbose_name = "triagem"
        verbose_name_plural = "triagens"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"], name="uniq_triage_entity"
            ),
            models.CheckConstraint(
                condition=~Q(status="discarded") | ~Q(discard_reason=""),
                name="triage_discard_needs_reason",
            ),
        ]

    def __str__(self):
        return f"{self.entity} — {self.get_status_display()}"

    def clean(self):
        errors = {}
        if self.status == self.Status.DISCARDED and not self.discard_reason:
            errors["discard_reason"] = "Informe o motivo do descarte."
        if missing := missing_entity_error(self.content_type_id, self.object_id):
            errors["object_id"] = missing
        if errors:
            raise ValidationError(errors)


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
