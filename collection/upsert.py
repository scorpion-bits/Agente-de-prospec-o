"""Upsert de candidatos: dedupe, consulta à memória comercial e evidências.

- Organização: `get_or_create_organization` (CNPJ > INEP > domínio > nome+município+rede). Uma
  organização já conhecida — inclusive as já contatadas (ADR-012) — **nunca** vira nova: só tem
  campos em branco completados.
- Oportunidade: por `canonical_key`. Revisitar atualiza `last_seen_at` e os campos que mudaram.
- Cada afirmação vira `Evidence` por `record_evidence` (idempotente; valor novo = linha nova).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, OrganizationCandidate
from core.models import Evidence, Opportunity, Organization
from core.services.canonical import opportunity_canonical_key
from core.services.evidence import record_evidence
from core.services.organizations import find_existing_organization, get_or_create_organization

CREATED, UPDATED, UNCHANGED = "created", "updated", "unchanged"
ORGANIZATION_LOOKUP_FIELDS = (
    "municipality_name",
    "uf",
    "network",
    "cnpj",
    "inep_code",
    "website",
)


def _record(entity, drafts: list[EvidenceDraft], source, raw_document) -> bool:
    """Registra as evidências; devolve se alguma é nova (não só renovada)."""
    before = Evidence.objects.filter(
        content_type__model=entity._meta.model_name, object_id=entity.pk
    ).count()
    for draft in drafts:
        record_evidence(
            entity,
            draft.field,
            draft.value,
            kind=draft.kind,
            method=draft.method or f"connector:{source.slug}",
            source_url=draft.source_url,
            source_name=draft.source_name or source.name,
            excerpt=draft.excerpt,
            raw_document=raw_document,
        )
    after = Evidence.objects.filter(
        content_type__model=entity._meta.model_name, object_id=entity.pk
    ).count()
    return after > before


def _columns(organization_id):
    """Colunas da organização sem `updated_at`, para saber se algo foi completado."""
    row = Organization.objects.filter(pk=organization_id).values().get()
    row.pop("updated_at")
    return row


@transaction.atomic
def upsert_organization(candidate: OrganizationCandidate, *, source, raw_document=None):
    """`(organização, CREATED|UPDATED|UNCHANGED)`."""
    fields = dict(candidate.fields)
    lookup = {k: fields.pop(k) for k in ORGANIZATION_LOOKUP_FIELDS if k in fields}
    existing = find_existing_organization(candidate.name, **lookup)
    before = _columns(existing.pk) if existing is not None else None
    organization, created = get_or_create_organization(
        candidate.name, defaults={**fields, "first_seen_source": source}, **lookup
    )
    new_evidence = _record(organization, candidate.evidence, source, raw_document)
    if created:
        return organization, CREATED
    filled = before != _columns(organization.pk)
    return organization, UPDATED if filled or new_evidence else UNCHANGED


@transaction.atomic
def upsert_opportunity(candidate: OpportunityCandidate, *, source, raw_document=None):
    """`(oportunidade, CREATED|UPDATED|UNCHANGED)`."""
    fields = dict(candidate.fields)
    now = timezone.now()
    key = candidate.canonical_key or opportunity_canonical_key(
        official_url=fields.get("official_url", ""),
        organizer_name=fields.get("organizer_name", ""),
        title=candidate.title,
        deadline_at=fields.get("deadline_at"),
    )
    opportunity = Opportunity.objects.filter(canonical_key=key).first()
    if opportunity is None:
        organizer = None
        if fields.get("organizer_name") and "organizer" not in fields:
            # Memória comercial: se o organizador já é conhecido, liga a ele (nunca cria aqui).
            organizer = find_existing_organization(fields["organizer_name"])
        opportunity = Opportunity(
            title=candidate.title, canonical_key=key, organizer=organizer, **fields
        )
        opportunity.first_seen_at = opportunity.last_seen_at = now
        opportunity.full_clean()
        opportunity.save()
        _record(opportunity, candidate.evidence, source, raw_document)
        return opportunity, CREATED

    changed = []
    for name, value in {"title": candidate.title, **fields}.items():
        if getattr(opportunity, name) != value:
            setattr(opportunity, name, value)
            changed.append(name)
    opportunity.last_seen_at = now
    if changed:
        opportunity.full_clean()
    opportunity.save()
    new_evidence = _record(opportunity, candidate.evidence, source, raw_document)
    return opportunity, UPDATED if changed or new_evidence else UNCHANGED


def upsert(candidate, *, source, raw_document=None):
    if isinstance(candidate, OrganizationCandidate):
        return upsert_organization(candidate, source=source, raw_document=raw_document)
    if isinstance(candidate, OpportunityCandidate):
        return upsert_opportunity(candidate, source=source, raw_document=raw_document)
    raise TypeError(f"Candidato desconhecido: {type(candidate).__name__}")
