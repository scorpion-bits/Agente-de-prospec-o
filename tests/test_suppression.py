"""Opt-out (LGPD): contatos em `Suppression` nunca aparecem (data-model.md, ContactPoint)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.models import ContactPoint, Organization, Suppression
from core.services.suppression import is_suppressed
from tests.conftest import VALID_CNPJ, mask_cnpj

pytestmark = pytest.mark.django_db


def suppress(kind, value):
    return Suppression.objects.create(kind=kind, value=value)


def usable_values():
    return set(ContactPoint.objects.usable().values_list("value", flat=True))


@pytest.fixture
def school(make_contact):
    org = Organization.objects.create(
        name="Escola A", legal_name="Colégio A Ltda", website="https://www.escola-a.org"
    )
    make_contact(org, "email", "secretaria@escola-a.org")
    make_contact(org, "phone", "(16) 0000-0000")
    make_contact(org, "website", "https://escola-a.org/contato")
    return org


class TestSuppressionModel:
    def test_value_is_normalized_per_kind(self):
        assert suppress("email", " Contato@Escola.ORG ").value == "contato@escola.org"
        assert suppress("domain", "https://www.Escola.org/x").value == "escola.org"
        assert suppress("phone", "(16) 0000-0000").value == "+551600000000"
        assert suppress("organization", mask_cnpj(VALID_CNPJ)).value == VALID_CNPJ
        assert suppress("organization", "Escola Exemplo!").value == "escola exemplo"

    def test_uniqueness_applies_to_the_normalized_value(self):
        suppress("email", "a@escola.org")
        with pytest.raises(IntegrityError), transaction.atomic():
            suppress("email", " A@Escola.org ")
        suppress("domain", "escola.org")  # outro tipo, mesmo texto: permitido

    def test_values_that_normalize_to_nothing_are_rejected(self):
        with pytest.raises(ValidationError) as error:
            Suppression(kind="domain", value="///").full_clean()
        assert "value" in error.value.message_dict


class TestUsableContacts:
    def test_without_suppressions_all_active_contacts_are_usable(self, school):
        assert usable_values() == {
            "secretaria@escola-a.org",
            "+551600000000",
            "https://escola-a.org/contato",
        }

    def test_suppressed_email_disappears_only_that_contact(self, school):
        suppress("email", "Secretaria@Escola-A.org")
        assert usable_values() == {"+551600000000", "https://escola-a.org/contato"}

    def test_suppressed_phone_disappears_only_that_contact(self, school):
        suppress("phone", "16 0000 0000")
        assert usable_values() == {"secretaria@escola-a.org", "https://escola-a.org/contato"}

    def test_suppressed_domain_blocks_the_organization_and_its_subdomains(
        self, school, make_contact
    ):
        suppress("domain", "escola-a.org")
        assert usable_values() == set()  # o site da organização está no domínio suprimido
        other = Organization.objects.create(name="Escola B")
        make_contact(other, "email", "info@mail.escola-a.org")
        make_contact(other, "email", "info@notescola-a.org")  # não é subdomínio
        assert usable_values() == {"info@notescola-a.org"}

    def test_suppressed_organization_by_name_blocks_all_its_contacts(self, school):
        suppress("organization", "ESCOLA A")
        assert usable_values() == set()

    def test_suppressed_organization_by_legal_name_or_cnpj(self, school):
        suppress("organization", "Colégio A Ltda")
        assert usable_values() == set()
        Suppression.objects.all().delete()
        school.cnpj = VALID_CNPJ
        school.save()
        suppress("organization", mask_cnpj(VALID_CNPJ))
        assert usable_values() == set()

    def test_do_not_contact_organizations_are_blocked_too(self, school):
        Organization.objects.filter(pk=school.pk).update(
            relationship_status=Organization.RelationshipStatus.DO_NOT_CONTACT
        )
        assert usable_values() == set()

    def test_other_organizations_are_not_affected(self, school, make_contact):
        other = Organization.objects.create(name="Escola B")
        make_contact(other, "email", "contato@escola-b.org")
        suppress("organization", "Escola A")
        assert usable_values() == {"contato@escola-b.org"}

    def test_bounced_and_invalid_contacts_are_not_usable(self, school, make_contact):
        make_contact(school, "email", "velho@escola-a.org", status=ContactPoint.Status.BOUNCED)
        make_contact(school, "email", "errado@escola-a.org", status=ContactPoint.Status.INVALID)
        assert "velho@escola-a.org" not in usable_values()
        assert "errado@escola-a.org" not in usable_values()
        assert len(usable_values()) == 3

    def test_usable_is_a_chainable_queryset(self, school):
        emails = ContactPoint.objects.usable().filter(kind="email")
        assert [c.value for c in emails] == ["secretaria@escola-a.org"]
        assert ContactPoint.objects.filter(organization=school).usable().count() == 3

    def test_is_suppressed_agrees_with_usable(self, school):
        contact = ContactPoint.objects.get(kind="phone")
        assert is_suppressed(contact) is False
        suppress("phone", "(16) 0000-0000")
        assert is_suppressed(ContactPoint.objects.get(pk=contact.pk)) is True
