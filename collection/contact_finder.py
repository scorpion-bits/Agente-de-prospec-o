"""Contatos públicos institucionais (E19): site da organização → páginas → contatos com evidência.

A extração é do `extraction/contacts.py` (pura). Aqui ficam a rede (`PoliteFetcher`: robots, rate
limit, cache) e os efeitos: `ContactPoint` + `Evidence` observada (URL + trecho, ADR-004) e o
respeito ao opt-out (`Suppression`). Sem IA.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from collection.fetcher import FetchError, PageBudgetExceeded, PoliteFetcher
from core.models import ContactPoint, Organization
from core.services.evidence import record_evidence
from core.services.normalize import normalize_contact_value, normalize_domain
from core.services.suppression import SuppressionIndex
from extraction.contacts import (
    FoundContact,
    drop_ambiguous_socials,
    parse_page,
    pick_pages,
)
from extraction.website import is_blocked_domain

METHOD = "regex:contacts"
SOURCE_NAME = "site oficial"
# Tipos que contam como «forma de abordar a organização» na métrica da etapa.
REACHABLE_KINDS = ("email", "phone", "whatsapp", "contact_form")


@dataclass
class Scanned:
    contact: FoundContact
    page_url: str
    page_text: str


@dataclass
class Scan:
    status: str  # ok | unreachable | suppressed
    contacts: list[Scanned] = field(default_factory=list)
    pages: int = 0
    skipped_suppressed: int = 0
    dropped_social_kinds: int = 0


def scan_organization(
    organization: Organization, fetcher: PoliteFetcher, index: SuppressionIndex
) -> Scan:
    """Lê até 5 páginas do site e devolve os contatos achados, sem gravar nada.

    Levanta `PageBudgetExceeded` se o teto de páginas da execução acabar (a organização fica para
    a próxima). Falhas de uma página (robots, 404, bloqueio) só a descartam.
    """
    if index.organization_blocked(organization):
        return Scan("suppressed")
    site_domain = normalize_domain(organization.website)
    try:
        home = fetcher.fetch(organization.website)
    except PageBudgetExceeded:
        raise
    except FetchError:
        return Scan("unreachable")
    if not is_blocked_domain(home.url):  # redirecionou para o domínio novo da organização
        site_domain = normalize_domain(home.url) or site_domain
    pages = [parse_page(home.text, home.url, site_domain)]
    scan = Scan("ok", pages=1)
    for url in pick_pages(home.url, pages[0].links, site_domain):
        try:
            fetched = fetcher.fetch(url)
        except PageBudgetExceeded:
            raise
        except FetchError:
            continue
        scan.pages += 1
        pages.append(parse_page(fetched.text, fetched.url, site_domain))

    seen: set[tuple[str, str]] = set()
    scanned: list[Scanned] = []
    for page in pages:  # a página inicial vem primeiro: o trecho mais "oficial" ganha
        for contact in page.contacts:
            key = (contact.kind, contact.value)
            if key not in seen:
                seen.add(key)
                scanned.append(Scanned(contact, page.url, page.text))
    kept, scan.dropped_social_kinds = drop_ambiguous_socials([s.contact for s in scanned])
    kept_keys = {(c.kind, c.value) for c in kept}
    for item in scanned:
        if (item.contact.kind, item.contact.value) not in kept_keys:
            continue
        probe = ContactPoint(
            organization=organization,
            kind=item.contact.kind,
            value=normalize_contact_value(item.contact.kind, item.contact.value),
        )
        if index.contact_blocked(probe):
            scan.skipped_suppressed += 1
        else:
            scan.contacts.append(item)
    return scan


def apply_scan(organization: Organization, scan: Scan) -> dict[str, int]:
    """Grava os contatos (com evidência observada) e marca a organização como verificada.

    Contato já existente (inclusive editado ou invalidado à mão) não é alterado: só renova a
    evidência e, se estiver ativo, `last_verified_at`. Devolve `{kind: criados}`.
    """
    now = timezone.now()
    created: dict[str, int] = {}
    for item in scan.contacts:
        contact = item.contact
        value = normalize_contact_value(contact.kind, contact.value)
        evidence = record_evidence(
            organization,
            f"contact.{contact.kind}",
            value,
            kind="observed",
            method=METHOD,
            source_url=item.page_url,
            source_name=SOURCE_NAME,
            excerpt=contact.excerpt,
            source_text=item.page_text,
            confidence=contact.confidence,
        )
        point, was_created = ContactPoint.objects.get_or_create(
            organization=organization,
            kind=contact.kind,
            value=value,
            defaults={
                "label": contact.label,
                "is_personal": contact.is_personal,
                "evidence": evidence,
                "last_verified_at": now,
            },
        )
        if was_created:
            created[contact.kind] = created.get(contact.kind, 0) + 1
        elif point.status == ContactPoint.Status.ACTIVE:
            point.last_verified_at = now
            point.save(update_fields=["last_verified_at"])
    mark_checked(organization, now)
    return created


def mark_checked(organization: Organization, when=None):
    organization.contacts_checked_at = when or timezone.now()
    organization.save(update_fields=["contacts_checked_at", "updated_at"])
