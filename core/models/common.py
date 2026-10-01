"""Modelos de `core` — ver docs/architecture/data-model.md."""

from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

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
