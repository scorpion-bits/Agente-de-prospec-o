"""Dedupe de organizações: base do "nunca redescobrir" (ADR-012).

Toda criação de organização (importação, conectores a partir da E04) passa por
`get_or_create_organization`, que procura uma existente antes de criar. Critérios, do mais ao
menos forte: CNPJ, código INEP, domínio do site e, por fim, **nome normalizado + município +
rede**. Não achou nada → cria. Achou → devolve a existente **sem sobrescrever** o que já está lá
(só completa campos vazios).
"""

from django.db import transaction

from core.models import Organization
from core.services.normalize import (
    is_valid_cnpj,
    name_key,
    normalize_cnpj,
    normalize_domain,
)

# Campos que uma descoberta pode completar quando a organização já os tem em branco.
FILLABLE_FIELDS = (
    "legal_name",
    "segment",
    "cnae_main",
    "address",
    "website",
    "network",
    "municipality_name",
    "uf",
)


def find_existing_organization(
    name,
    *,
    municipality_name="",
    uf="",
    network="",
    cnpj=None,
    inep_code=None,
    website="",
):
    """A organização já conhecida que corresponde aos dados, ou `None`."""
    cnpj = normalize_cnpj(cnpj)
    if cnpj and is_valid_cnpj(cnpj):
        found = Organization.objects.filter(cnpj=cnpj).first()
        if found:
            return found
    inep_code = (inep_code or "").strip()
    if inep_code:
        found = Organization.objects.filter(inep_code=inep_code).first()
        if found:
            return found
    domain = normalize_domain(website)
    if domain:
        for candidate in Organization.objects.exclude(website="").only("pk", "website"):
            if normalize_domain(candidate.website) == domain:
                return Organization.objects.get(pk=candidate.pk)

    wanted = (name_key(name), name_key(municipality_name), name_key(network))
    if not wanted[0]:
        return None
    candidates = Organization.objects.all()
    if uf:
        candidates = candidates.filter(uf__in=[uf.strip().upper(), ""])
    for candidate in candidates:
        key = (
            name_key(candidate.name),
            name_key(candidate.municipality_name),
            name_key(candidate.network),
        )
        if key == wanted:
            return candidate
    return None


@transaction.atomic
def get_or_create_organization(name, *, defaults=None, **lookup):
    """`(organização, criada)`. `lookup` são os critérios de `find_existing_organization`.

    `defaults` (outros campos do modelo) só são usados na criação; numa existente apenas
    preenchem campos em branco de `FILLABLE_FIELDS`.
    """
    defaults = dict(defaults or {})
    existing = find_existing_organization(name, **lookup)
    if existing is not None:
        changed = []
        values = {**{k: v for k, v in lookup.items() if k in FILLABLE_FIELDS}, **defaults}
        for field in FILLABLE_FIELDS:
            if values.get(field) and not getattr(existing, field):
                setattr(existing, field, values[field])
                changed.append(field)
        if changed:
            existing.save(update_fields=[*changed, "updated_at"])
        return existing, False
    fields = {k: v for k, v in lookup.items() if v not in (None, "")}
    organization = Organization(name=name, **fields, **defaults)
    organization.full_clean()
    organization.save()
    return organization, True
