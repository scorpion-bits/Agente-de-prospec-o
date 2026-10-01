"""Consulta ao opt-out (`Suppression`) — LGPD, docs/research/legal-and-compliance.md.

Regra do modelo de dados: contatos em `Suppression` **nunca aparecem**. Todo código que exibe ou
usa contatos (digest, abordagem, exportação) deve passar por `ContactPoint.objects.usable()`,
que usa este módulo. A tabela é pequena: é lida inteira, uma vez por consulta.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.services.normalize import name_key, normalize_cnpj, normalize_domain


@dataclass(frozen=True)
class SuppressionIndex:
    emails: frozenset[str] = frozenset()
    phones: frozenset[str] = frozenset()
    domains: frozenset[str] = frozenset()
    organizations: frozenset[str] = frozenset()

    @classmethod
    def load(cls) -> SuppressionIndex:
        from core.models import Suppression

        by_kind: dict[str, set[str]] = {kind: set() for kind in Suppression.Kind.values}
        for kind, value in Suppression.objects.values_list("kind", "value"):
            by_kind[kind].add(value)
        return cls(
            emails=frozenset(by_kind["email"]),
            phones=frozenset(by_kind["phone"]),
            domains=frozenset(by_kind["domain"]),
            organizations=frozenset(by_kind["organization"]),
        )

    def domain_blocked(self, domain: str) -> bool:
        """O domínio (ou o domínio-pai) está suprimido? `escola.org` bloqueia `mail.escola.org`."""
        return bool(domain) and any(domain == d or domain.endswith(f".{d}") for d in self.domains)

    def organization_blocked(self, organization) -> bool:
        if organization.relationship_status == "do_not_contact":
            return True
        keys = {
            normalize_cnpj(organization.cnpj),
            name_key(organization.name),
            name_key(organization.legal_name),
        }
        keys.discard("")
        return bool(keys & self.organizations) or self.domain_blocked(
            normalize_domain(organization.website)
        )

    def contact_blocked(self, contact) -> bool:
        if self.organization_blocked(contact.organization):
            return True
        if contact.kind == "email":
            return contact.value in self.emails or self.domain_blocked(
                normalize_domain(contact.value)
            )
        if contact.kind in ("phone", "whatsapp"):
            return contact.value in self.phones
        return self.domain_blocked(normalize_domain(contact.value))


def is_suppressed(contact) -> bool:
    """O contato (ou sua organização) está no opt-out?"""
    return SuppressionIndex.load().contact_blocked(contact)


def exclude_suppressed(queryset):
    """Tira do queryset os contatos barrados pelo opt-out (não use com queryset fatiado)."""
    index = SuppressionIndex.load()
    blocked = [c.pk for c in queryset.select_related("organization") if index.contact_blocked(c)]
    return queryset.exclude(pk__in=blocked)
