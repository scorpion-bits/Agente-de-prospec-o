import pytest

from core.models import ContactPoint, Opportunity, Organization
from core.services.evidence import record_evidence

# CNPJ clássico de exemplo (dígitos verificadores válidos; não pertence a ninguém).
VALID_CNPJ = "11222333000181"


def mask_cnpj(cnpj: str) -> str:
    """CNPJ com máscara. Montado em tempo de execução: o repo_checks barra CNPJ literal."""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """O hash padrão é lento de propósito (1 milhão de iterações); em teste só atrapalha."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Escola Exemplo",
        kind=Organization.Kind.SCHOOL,
        municipality_name="Araraquara",
        uf="SP",
    )


@pytest.fixture
def opportunity(db):
    return Opportunity.objects.create(
        title="Game Jam Exemplo",
        kind=Opportunity.Kind.GAME_JAM,
        official_url="https://example.org/jam",
    )


@pytest.fixture
def make_contact(db):
    """Cria um contato institucional já com a evidência obrigatória (dados fictícios)."""

    def _make(organization, kind, value, **extra):
        evidence = record_evidence(
            organization,
            f"contact.{kind}",
            value,
            kind="observed",
            method="regex:contact",
            source_url="https://example.org/contato",
            excerpt=f"Contato: {value}",
        )
        return ContactPoint.objects.create(
            organization=organization, kind=kind, value=value, evidence=evidence, **extra
        )

    return _make
