"""E03b — memória comercial: status derivado, dedupe, importações, perfil e admin."""

import json
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from core.models import (
    CompanyProfile,
    Interaction,
    Match,
    Organization,
    PortfolioItem,
    ServiceOffering,
)
from core.services.organizations import find_existing_organization, get_or_create_organization
from core.services.relationship import refresh_relationship
from tests.conftest import VALID_CNPJ, mask_cnpj

K = Interaction.Kind
O = Interaction.Outcome  # noqa: E741
S = Organization.RelationshipStatus


def interact(organization, kind, outcome=O.PENDING, **extra):
    return Interaction.objects.create(
        organization=organization, kind=kind, outcome=outcome, **extra
    )


def status_of(organization):
    organization.refresh_from_db()
    return organization.relationship_status


class TestDerivedRelationship:
    def test_without_interactions_the_organization_was_never_contacted(self, organization):
        assert status_of(organization) == S.NEVER_CONTACTED
        assert organization.last_interaction_at is None

    @pytest.mark.parametrize(
        ("kind", "outcome", "expected"),
        [
            (K.MESSAGE, O.NO_RESPONSE, S.CONTACTED),
            (K.EVENT_PARTICIPATION, O.PENDING, S.CONTACTED),
            (K.CALL, O.NO_RESPONSE, S.CONTACTED),
            (K.CALL, O.POSITIVE, S.IN_CONVERSATION),
            (K.MEETING, O.PENDING, S.IN_CONVERSATION),
            (K.RESPONSE_RECEIVED, O.PENDING, S.IN_CONVERSATION),
            (K.PROPOSAL_SENT, O.PENDING, S.PROPOSAL_SENT),
            (K.PROPOSAL_SENT, O.NO_RESPONSE, S.PROPOSAL_SENT),
            (K.PROPOSAL_SENT, O.NEGATIVE, S.LOST),
            (K.MEETING, O.LOST, S.LOST),
            (K.PROPOSAL_SENT, O.WON, S.CLIENT),
            (K.COURSE_DELIVERED, O.POSITIVE, S.CLIENT),
            (K.COURSE_DELIVERED, O.PENDING, S.CLIENT),
        ],
    )
    def test_status_for_a_single_interaction(self, organization, kind, outcome, expected):
        interact(organization, kind, outcome)
        assert status_of(organization) == expected

    def test_a_course_that_ended_badly_is_not_a_client(self, organization):
        interact(organization, K.COURSE_DELIVERED, O.NEGATIVE)
        assert status_of(organization) == S.LOST

    def test_highest_stage_reached_wins_over_later_softer_contacts(self, organization):
        interact(organization, K.PROPOSAL_SENT, occurred_at=date(2026, 9, 1))
        interact(organization, K.MESSAGE, occurred_at=date(2026, 9, 20))
        assert status_of(organization) == S.PROPOSAL_SENT

    def test_the_most_recent_negative_outcome_marks_the_organization_lost(self, organization):
        interact(organization, K.PROPOSAL_SENT, occurred_at=date(2026, 9, 1))
        interact(organization, K.CALL, O.NEGATIVE, occurred_at=date(2026, 9, 20))
        assert status_of(organization) == S.LOST

    def test_a_client_stays_a_client_after_a_later_refusal(self, organization):
        interact(organization, K.COURSE_DELIVERED, O.POSITIVE, occurred_at=date(2026, 5, 1))
        interact(organization, K.PROPOSAL_SENT, O.NEGATIVE, occurred_at=date(2026, 9, 1))
        assert status_of(organization) == S.CLIENT

    def test_do_not_contact_is_never_overwritten(self, organization):
        Organization.objects.filter(pk=organization.pk).update(relationship_status=S.DO_NOT_CONTACT)
        interact(organization, K.PROPOSAL_SENT)
        assert status_of(organization) == S.DO_NOT_CONTACT

    def test_dates_come_from_the_known_interactions_only(self, organization):
        interact(organization, K.PROPOSAL_SENT)  # pendente: sem data
        assert organization.last_interaction_at is None
        interact(organization, K.MESSAGE, occurred_at=date(2026, 8, 1))
        interact(organization, K.CALL, occurred_at=date(2026, 9, 5))
        organization.refresh_from_db()
        assert organization.last_interaction_at == date(2026, 9, 5)

    def test_next_action_lives_in_the_latest_interaction(self, organization):
        interact(
            organization,
            K.PROPOSAL_SENT,
            occurred_at=date(2026, 9, 1),
            next_action="Ligar",
            next_action_at=date(2026, 9, 15),
        )
        organization.refresh_from_db()
        assert organization.next_action_at == date(2026, 9, 15)
        interact(organization, K.CALL, O.POSITIVE, occurred_at=date(2026, 9, 10))
        organization.refresh_from_db()
        assert organization.next_action_at is None

    def test_deleting_an_interaction_recalculates(self, organization):
        interaction = interact(organization, K.PROPOSAL_SENT)
        assert status_of(organization) == S.PROPOSAL_SENT
        interaction.delete()
        assert status_of(organization) == S.NEVER_CONTACTED

    def test_moving_an_interaction_recalculates_both_organizations(self, organization):
        other = Organization.objects.create(name="Outra Escola")
        interaction = interact(organization, K.PROPOSAL_SENT)
        interaction.organization = other
        interaction.save()
        assert status_of(organization) == S.NEVER_CONTACTED
        assert status_of(other) == S.PROPOSAL_SENT

    def test_refresh_is_idempotent_and_ignores_unknown_organizations(self, organization):
        interact(organization, K.MEETING)
        assert refresh_relationship(organization.pk) == S.IN_CONVERSATION
        assert refresh_relationship(organization.pk) == S.IN_CONVERSATION
        assert refresh_relationship(0) is None


class TestInteractionValidation:
    def test_contact_must_belong_to_the_same_organization(self, organization, make_contact):
        other = Organization.objects.create(name="Outra Escola")
        contact = make_contact(other, "email", "contato@example.org")
        interaction = Interaction(organization=organization, kind=K.MESSAGE, contact_point=contact)
        with pytest.raises(ValidationError) as error:
            interaction.full_clean()
        assert "contact_point" in error.value.message_dict

    def test_a_dated_next_action_needs_a_description(self, organization):
        interaction = Interaction(
            organization=organization, kind=K.MESSAGE, next_action_at=date(2026, 10, 1)
        )
        with pytest.raises(ValidationError) as error:
            interaction.full_clean()
        assert "next_action" in error.value.message_dict


class TestOrganizationDedupe:
    def test_same_name_ignoring_accents_case_and_punctuation(self, organization):
        found = find_existing_organization(
            "ESCOLA  exemplo", municipality_name="araraquara", uf="sp"
        )
        assert found == organization

    def test_same_name_in_another_municipality_is_a_different_organization(self, organization):
        assert find_existing_organization("Escola Exemplo", municipality_name="Bauru") is None

    def test_same_name_in_another_network_is_different(self, organization):
        assert (
            find_existing_organization(
                "Escola Exemplo", municipality_name="Araraquara", network="SENAC-SP"
            )
            is None
        )

    def test_cnpj_wins_over_the_name(self, organization):
        organization.cnpj = VALID_CNPJ
        organization.save()
        found = find_existing_organization("Outro nome", cnpj=mask_cnpj(VALID_CNPJ))
        assert found == organization

    def test_website_domain_matches_regardless_of_scheme_and_www(self, organization):
        organization.website = "https://www.escola.example.org/contato"
        organization.save()
        assert find_existing_organization("Nome diferente", website="http://escola.example.org")

    def test_get_or_create_never_duplicates_and_only_fills_blanks(self, organization):
        again, created = get_or_create_organization(
            "Escola Exemplo",
            municipality_name="Araraquara",
            uf="SP",
            defaults={"segment": "ensino médio", "kind": Organization.Kind.COMPANY},
        )
        assert not created
        assert again == organization
        again.refresh_from_db()
        assert again.segment == "ensino médio"  # estava em branco
        assert again.kind == Organization.Kind.SCHOOL  # já tinha valor: não muda
        assert Organization.objects.count() == 1

    def test_get_or_create_creates_when_unknown(self, db):
        organization, created = get_or_create_organization("Escola Nova", municipality_name="Bauru")
        assert created
        assert organization.municipality_name == "Bauru"


@pytest.fixture
def catalog(db):
    call_command("load_services", stdout=StringIO())


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


INTERACTION_HEADER = (
    "organization_name,network,municipality,uf,occurred_at,kind,channel,service_slug,"
    "contact_role,summary,outcome,next_action,next_action_at,data_status,notes\n"
)


class TestImportInteractions:
    def run(self, path, *args):
        out = StringIO()
        call_command("import_interactions", str(path), *args, stdout=out)
        return out.getvalue()

    def test_the_real_template_imports_sesc_units_with_their_status(self, catalog, tmp_path):
        template = "data/seeds/interactions.template.csv"
        self.run(template)
        assert Organization.objects.filter(network="SESC-SP").count() == 5  # 4 unidades + rede
        network = Organization.objects.get(name="SESC-SP", parent__isnull=True)
        for city, status in [
            ("Bauru", S.PROPOSAL_SENT),
            ("Ribeirao Preto", S.PROPOSAL_SENT),
            ("Sao Carlos", S.PROPOSAL_SENT),
            ("Araraquara", S.CLIENT),
        ]:
            unit = Organization.objects.get(name=f"SESC {city}")
            assert unit.parent == network
            assert unit.kind == Organization.Kind.SESC
            assert unit.relationship_status == status
            assert unit.last_interaction_at is None  # sem data inventada
        game_lab = Interaction.objects.get(organization__name="SESC Araraquara")
        assert game_lab.kind == K.COURSE_DELIVERED
        assert game_lab.data_status == Interaction.DataStatus.PENDING
        assert game_lab.service.slug == "course_gamedev"

    def test_importing_twice_changes_nothing(self, catalog, tmp_path):
        path = write(
            tmp_path / "i.csv",
            INTERACTION_HEADER
            + "SESC Bauru,SESC-SP,Bauru,SP,2026-09-01,proposal_sent,email,,Gerente,Proposta,"
            "pending,Ligar,2026-10-10,confirmado,\n",
        )
        assert "1 criada" in self.run(path)
        second = self.run(path)
        assert "0 criada" in second
        assert "1 mantida" in second
        assert Interaction.objects.count() == 1
        assert Organization.objects.count() == 2

    def test_filling_in_a_pending_row_completes_it_without_duplicating(self, catalog, tmp_path):
        row = "SESC Bauru,SESC-SP,Bauru,SP,{date},proposal_sent,{ch},,,Proposta,pending,,,{st},\n"
        self.run(
            write(
                tmp_path / "i.csv",
                INTERACTION_HEADER + row.format(date="", ch="", st="pendente"),
            )
        )
        pending = Interaction.objects.get()
        assert pending.occurred_at is None
        self.run(
            write(
                tmp_path / "i.csv",
                INTERACTION_HEADER + row.format(date="2026-09-01", ch="email", st="confirmado"),
            )
        )
        done = Interaction.objects.get()
        assert done.pk == pending.pk
        assert done.occurred_at == date(2026, 9, 1)
        assert done.channel == "email"
        assert done.data_status == Interaction.DataStatus.CONFIRMED
        assert Organization.objects.get(name="SESC Bauru").last_interaction_at == date(2026, 9, 1)

    def test_confirmed_records_are_not_overwritten_without_update(self, catalog, tmp_path):
        row = "SESC Bauru,,Bauru,SP,2026-09-01,proposal_sent,,,,Proposta,{o},,,confirmado,\n"
        self.run(write(tmp_path / "i.csv", INTERACTION_HEADER + row.format(o="pending")))
        path = write(tmp_path / "i.csv", INTERACTION_HEADER + row.format(o="negative"))
        self.run(path)
        assert Interaction.objects.get().outcome == O.PENDING
        self.run(path, "--update")
        assert Interaction.objects.get().outcome == O.NEGATIVE

    def test_a_known_organization_is_reused_not_rediscovered(self, catalog, tmp_path):
        existing = Organization.objects.create(
            name="SESC Bauru", municipality_name="Bauru", uf="SP", network="SESC-SP"
        )
        path = write(
            tmp_path / "i.csv",
            INTERACTION_HEADER + "SESC Bauru,SESC-SP,Bauru,SP,,message,,,,Oi,,,,pendente,\n",
        )
        self.run(path)
        assert Organization.objects.filter(name="SESC Bauru").get() == existing
        assert existing.interactions.count() == 1

    def test_dry_run_validates_without_saving(self, catalog, tmp_path):
        path = write(
            tmp_path / "i.csv",
            INTERACTION_HEADER + "SESC Bauru,,Bauru,SP,,message,,,,Oi,,,,pendente,\n",
        )
        assert "[dry-run]" in self.run(path, "--dry-run")
        assert Interaction.objects.count() == 0
        assert Organization.objects.count() == 0

    @pytest.mark.parametrize(
        ("row", "message"),
        [
            (",,Bauru,SP,,message,,,,,,,,,\n", "organization_name"),
            ("X,,,,,voar,,,,,,,,,\n", "kind"),
            ("X,,,,31/12/2026,message,,,,,,,,,\n", "AAAA-MM-DD"),
            ("X,,,,,message,,nao_existe,,,,,,,\n", "fora do catálogo"),
            ("X,,,,,message,,,,,talvez,,,,\n", "outcome"),
            ("X,,,,,message,,,,,,,2026-10-01,,\n", "próxima ação"),
        ],
    )
    def test_invalid_rows_name_the_line_and_save_nothing(self, catalog, tmp_path, row, message):
        path = write(tmp_path / "i.csv", INTERACTION_HEADER + row)
        with pytest.raises(CommandError, match=message):
            self.run(path)
        assert Interaction.objects.count() == 0

    def test_missing_file_and_columns_are_friendly_errors(self, catalog, tmp_path):
        with pytest.raises(CommandError, match="Não foi possível ler"):
            self.run(tmp_path / "nao-existe.csv")
        with pytest.raises(CommandError, match="faltam as colunas"):
            self.run(write(tmp_path / "i.csv", "a,b\n1,2\n"))

    def test_output_has_counts_only(self, catalog, tmp_path):
        path = write(
            tmp_path / "i.csv",
            INTERACTION_HEADER + "SESC Bauru,,Bauru,SP,,message,,,Diretora X,Oi,,,,pendente,\n",
        )
        assert "Bauru" not in self.run(path)  # logs do Actions são públicos


class TestImportPortfolio:
    def run(self, *args):
        out = StringIO()
        call_command("import_portfolio", *args, stdout=out)
        return out.getvalue()

    def test_the_real_seed_imports_with_services_and_game_lab(self, catalog):
        self.run()
        assert PortfolioItem.objects.count() == 5
        game_lab = PortfolioItem.objects.get(slug="game-lab-sesc-araraquara")
        assert game_lab.kind == PortfolioItem.Kind.COURSE
        assert game_lab.year is None
        assert game_lab.status == PortfolioItem.DataStatus.PENDING
        assert game_lab.public
        assert {s.slug for s in game_lab.services.all()} == {
            "course_gamedev",
            "workshop_gamedev",
            "extracurricular_school",
        }
        assert game_lab.capability_tags == ["jogos", "ensino_presencial", "educacao"]
        prototype = PortfolioItem.objects.get(slug="prototipo-jogo")
        assert not prototype.public
        site = PortfolioItem.objects.get(slug="site-scorpionbits")
        assert site.status == PortfolioItem.DataStatus.TO_CONFIRM

    def test_idempotent_and_keeps_admin_edits_unless_update(self, catalog):
        self.run()
        PortfolioItem.objects.filter(slug="tirania").update(description="Editado no admin")
        assert "5 mantido(s)" in self.run()
        assert PortfolioItem.objects.get(slug="tirania").description == "Editado no admin"
        assert "5 atualizado(s)" in self.run("--update")
        assert PortfolioItem.objects.get(slug="tirania").description == ""
        assert PortfolioItem.objects.count() == 5

    def test_unknown_service_fails_and_rolls_back(self, db, tmp_path):
        path = write(
            tmp_path / "p.csv",
            "slug,title,kind,services\na,A,game,\nb,B,game,servico_fantasma\n",
        )
        with pytest.raises(CommandError, match="fora do catálogo"):
            call_command("import_portfolio", str(path), stdout=StringIO())
        assert PortfolioItem.objects.count() == 0

    def test_match_can_cite_portfolio_items_as_proof(self, catalog, organization):
        self.run()
        service = ServiceOffering.objects.get(slug="course_gamedev")
        match = Match.objects.create(organization=organization, service=service, strength=0.8)
        match.portfolio_refs.add(PortfolioItem.objects.get(slug="game-lab-sesc-araraquara"))
        assert match.portfolio_refs.count() == 1


class TestCompanyProfile:
    def run(self, *args):
        out = StringIO()
        call_command("load_company_profile", *args, stdout=out)
        return out.getvalue()

    def test_seed_loads_the_mei_profile_without_cnpj(self, db, settings):
        settings.COMPANY_CNPJ = ""
        settings.CONTACT_EMAIL = ""
        assert "criado" in self.run()
        profile = CompanyProfile.get()
        assert profile.legal_form == "MEI"
        assert profile.opened_at == date(2025, 4, 10)
        assert profile.annual_revenue_cap_brl == 81000
        assert profile.primary_cnae == "85.92-9/99"
        assert len(profile.cnaes) == 10
        assert profile.cnpj is None

    def test_cnpj_and_email_come_from_the_environment(self, db, settings):
        settings.COMPANY_CNPJ = mask_cnpj(VALID_CNPJ)
        settings.CONTACT_EMAIL = "contato@example.org"
        out = self.run()
        profile = CompanyProfile.get()
        assert profile.cnpj == VALID_CNPJ
        assert profile.contact_email == "contato@example.org"
        assert VALID_CNPJ not in out

    def test_an_invalid_cnpj_in_the_environment_is_rejected(self, db, settings):
        settings.COMPANY_CNPJ = "11222333000182"
        with pytest.raises(CommandError, match="inválido"):
            self.run()
        assert CompanyProfile.get() is None

    def test_reloading_keeps_admin_edits_unless_update(self, db, settings):
        settings.COMPANY_CNPJ = ""
        self.run()
        CompanyProfile.objects.update(legal_form="ME")
        assert "mantido" in self.run()
        assert CompanyProfile.get().legal_form == "ME"
        assert "atualizado" in self.run("--update")
        assert CompanyProfile.get().legal_form == "MEI"
        assert CompanyProfile.objects.count() == 1

    def test_unknown_fields_are_rejected(self, db, tmp_path):
        path = write(tmp_path / "c.json", json.dumps({"legal_form": "MEI", "cor": "azul"}))
        with pytest.raises(CommandError, match="cor"):
            self.run(str(path))

    def test_there_is_only_one_row(self, db):
        CompanyProfile().save()
        CompanyProfile(legal_form="ME").save()
        assert CompanyProfile.objects.count() == 1
        assert CompanyProfile.get().legal_form == "ME"


class TestCommercialAdmin:
    def test_organization_page_shows_the_history_most_recent_first(
        self, admin_client, organization
    ):
        interact(organization, K.MESSAGE, occurred_at=date(2026, 8, 1), summary="primeiro contato")
        interact(organization, K.PROPOSAL_SENT, occurred_at=date(2026, 9, 1), summary="proposta")
        response = admin_client.get(
            reverse("admin:core_organization_change", args=[organization.pk])
        )
        assert response.status_code == 200
        inline = next(
            i for i in response.context["inline_admin_formsets"] if i.formset.model is Interaction
        )
        assert [f.instance.kind for f in inline.formset.forms[:2]] == [
            K.PROPOSAL_SENT,
            K.MESSAGE,
        ]

    def test_an_interaction_can_be_added_in_the_organization_page(self, admin_client, organization):
        url = reverse("admin:core_organization_change", args=[organization.pk])
        page = admin_client.get(url)
        data = {
            "name": organization.name,
            "kind": "school",
            "size_hint": "unknown",
            "website_status": "unknown",
            "municipality_name": "Araraquara",
            "uf": "SP",
        }
        for inline in page.context["inline_admin_formsets"]:
            data |= {
                f"{inline.formset.prefix}-{key}": value
                for key, value in {
                    "TOTAL_FORMS": "1" if inline.formset.model is Interaction else "0",
                    "INITIAL_FORMS": "0",
                    "MIN_NUM_FORMS": "0",
                    "MAX_NUM_FORMS": "1000",
                }.items()
            }
            if inline.formset.model is Interaction:
                prefix = inline.formset.prefix
                data |= {
                    f"{prefix}-0-kind": K.PROPOSAL_SENT,
                    f"{prefix}-0-outcome": O.PENDING,
                    f"{prefix}-0-occurred_at": "2026-09-01",
                    f"{prefix}-0-data_status": "confirmed",
                }
        response = admin_client.post(url, data)
        assert response.status_code == 302
        assert status_of(organization) == S.PROPOSAL_SENT
        assert Interaction.objects.get().organization == organization

    def test_relationship_filter_and_columns_on_the_organization_list(
        self, admin_client, organization
    ):
        interact(organization, K.PROPOSAL_SENT, occurred_at=date(2026, 9, 1))
        url = reverse("admin:core_organization_changelist")
        response = admin_client.get(url, {"relationship_status__exact": "proposal_sent"})
        assert response.status_code == 200
        assert organization.name in response.content.decode()
        response = admin_client.get(url, {"relationship_status__exact": "client"})
        assert organization.name not in response.content.decode()

    def test_follow_ups_are_ordered_by_date_and_flag_overdue(self, admin_client):
        today = timezone.localdate()
        urgent = Organization.objects.create(name="Urgente")
        later = Organization.objects.create(name="Depois")
        Organization.objects.create(name="Sem lembrete")
        interact(urgent, K.PROPOSAL_SENT, next_action="Ligar hoje", next_action_at=today)
        interact(
            later,
            K.PROPOSAL_SENT,
            next_action="Mandar proposta",
            next_action_at=today - timedelta(days=3),
        )
        response = admin_client.get(reverse("admin:core_followup_changelist"))
        content = response.content.decode()
        assert response.status_code == 200
        assert "Sem lembrete" not in content
        assert content.index("Depois") < content.index("Urgente")  # a mais antiga primeiro
        assert "vencida" in content
        assert "Mandar proposta" in content

    def test_follow_ups_are_read_only(self, admin_client):
        assert admin_client.get(reverse("admin:core_followup_add")).status_code == 403

    def test_interaction_records_who_created_it(self, admin_client, organization, admin_user):
        response = admin_client.post(
            reverse("admin:core_interaction_add"),
            {
                "organization": organization.pk,
                "kind": K.MESSAGE,
                "outcome": O.PENDING,
                "data_status": "confirmed",
            },
        )
        assert response.status_code == 302
        assert Interaction.objects.get().created_by == admin_user

    def test_company_profile_is_a_singleton_in_the_admin(self, admin_client, db):
        add = reverse("admin:core_companyprofile_add")
        assert admin_client.get(add).status_code == 200
        profile = CompanyProfile.objects.create(legal_form="MEI")
        assert admin_client.get(add).status_code == 403
        listing = admin_client.get(reverse("admin:core_companyprofile_changelist"))
        assert listing.status_code == 302
        assert listing["Location"] == reverse("admin:core_companyprofile_change", args=[profile.pk])
        delete = reverse("admin:core_companyprofile_delete", args=[profile.pk])
        assert admin_client.get(delete).status_code == 403

    def test_portfolio_item_is_editable_and_slug_is_locked(self, admin_client, catalog):
        call_command("import_portfolio", stdout=StringIO())
        item = PortfolioItem.objects.get(slug="tirania")
        response = admin_client.get(reverse("admin:core_portfolioitem_change", args=[item.pk]))
        assert response.status_code == 200
        assert "slug" in response.context["adminform"].readonly_fields
