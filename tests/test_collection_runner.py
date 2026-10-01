"""E04 — runner, upsert, conector seed_csv, comando `collect`, retenção e admin."""

from datetime import timedelta
from io import StringIO

import httpx
import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from collection import registry
from collection.base import (
    EvidenceDraft,
    OpportunityCandidate,
    OrganizationCandidate,
    RawItem,
)
from collection.fetcher import PoliteFetcher
from collection.models import CollectionRun, RawDocument
from collection.runner import build_fetcher, run_source, runnable_problem
from collection.upsert import CREATED, UNCHANGED, UPDATED, upsert
from core.models import Evidence, Interaction, Opportunity, Organization, Source

pytestmark = pytest.mark.django_db

ORG_HEADER = "name,kind,network,municipality,uf,website,segment,cnpj,inep_code,source_url\n"
OPP_HEADER = (
    "title,kind,official_url,organizer_name,description,deadline,municipality,uf,source_url\n"
)


def seed_source(tmp_path, text, *, entity="organization", enabled=True, slug="seed-teste"):
    path = tmp_path / "seed.csv"
    path.write_text(text, encoding="utf-8")
    return Source.objects.create(
        slug=slug,
        name="CSV de teste",
        kind=Source.Kind.SEED_CSV,
        enabled=enabled,
        config={"path": str(path), "entity": entity},
    )


def run(source, **kwargs):
    return run_source(source, **kwargs)


class TestSeedCsvOrganizations:
    def test_creates_organizations_with_manual_evidence_when_there_is_no_url(self, tmp_path):
        source = seed_source(
            tmp_path,
            ORG_HEADER
            + "Escola Alfa,school,,Araraquara,SP,https://alfa.example.org,Ensino médio,,,\n"
            + "SESC Teste,sesc,SESC-SP,Bauru,SP,,,,,\n",
        )
        result = run(source)
        assert (result.status, result.items_seen, result.items_new) == ("ok", 2, 2)
        alfa = Organization.objects.get(name="Escola Alfa")
        assert alfa.kind == "school" and alfa.first_seen_source == source
        claims = {e.field: e for e in Evidence.objects.filter(object_id=alfa.pk)}
        assert claims["municipality_name"].kind == "manual"
        assert claims["municipality_name"].method == "human"
        assert claims["municipality_name"].source_name == "seed.csv"

    def test_a_row_with_a_source_url_is_observed_evidence_by_the_connector(self, tmp_path):
        source = seed_source(
            tmp_path,
            ORG_HEADER + "Escola Beta,school,,Bauru,SP,,,,,https://example.org/lista\n",
        )
        run(source)
        evidence = Evidence.objects.filter(field="municipality_name").get()
        assert evidence.kind == "observed"
        assert evidence.method == "connector:seed-teste"
        assert evidence.source_url == "https://example.org/lista"

    def test_second_run_changes_nothing(self, tmp_path):
        source = seed_source(tmp_path, ORG_HEADER + "Escola Alfa,school,,Araraquara,SP,,,,,\n")
        run(source)
        evidence_before = Evidence.objects.count()
        again = run(source)
        assert (again.items_new, again.items_updated, again.status) == (0, 0, "ok")
        assert Organization.objects.count() == 1
        assert Evidence.objects.count() == evidence_before

    def test_a_known_organization_is_not_rediscovered_and_keeps_its_history(self, tmp_path):
        known = Organization.objects.create(
            name="SESC Bauru", municipality_name="Bauru", uf="SP", network="SESC-SP"
        )
        Interaction.objects.create(
            organization=known, kind=Interaction.Kind.PROPOSAL_SENT, occurred_at="2026-09-01"
        )
        source = seed_source(
            tmp_path,
            ORG_HEADER + "sesc  bauru,sesc,SESC-SP,Bauru,SP,https://sescsp.example.org/bauru,,,,\n",
        )
        result = run(source)
        assert (result.items_new, result.items_updated) == (0, 1)
        known.refresh_from_db()
        assert Organization.objects.count() == 1
        assert known.website == "https://sescsp.example.org/bauru"  # completou o que faltava
        assert known.kind == "other"  # não sobrescreve
        assert known.relationship_status == "proposal_sent"

    def test_bad_rows_fail_alone_and_the_run_is_partial(self, tmp_path):
        source = seed_source(
            tmp_path,
            ORG_HEADER
            + "Boa,school,,Bauru,SP,,,,,\n"
            + ",school,,Bauru,SP,,,,,\n"
            + "Tipo ruim,planeta,,Bauru,SP,,,,,\n"
            + "Outra boa,school,,Jaú,SP,,,,,\n",
        )
        result = run(source)
        assert (result.status, result.items_new, result.items_failed) == ("partial", 2, 2)
        assert "linha 3" in result.error_log and "linha 4" in result.error_log
        assert Organization.objects.count() == 2

    def test_limit_stops_early(self, tmp_path):
        source = seed_source(
            tmp_path, ORG_HEADER + "A,school,,X,SP,,,,,\nB,school,,X,SP,,,,,\nC,school,,X,SP,,,,,\n"
        )
        result = run(source, limit=2)
        assert (result.items_seen, result.items_new, result.item_limit) == (2, 2, 2)

    def test_dry_run_records_the_run_but_saves_nothing_else(self, tmp_path):
        source = seed_source(tmp_path, ORG_HEADER + "Escola Alfa,school,,Bauru,SP,,,,,\n")
        result = run(source, dry_run=True)
        assert (result.status, result.items_new, result.dry_run) == ("ok", 1, True)
        assert Organization.objects.count() == 0
        assert Evidence.objects.count() == 0
        assert CollectionRun.objects.get() == result

    def test_missing_file_is_a_connector_error(self, tmp_path):
        source = seed_source(tmp_path, "")
        source.config["path"] = str(tmp_path / "nao-existe.csv")
        source.save()
        result = run(source)
        assert result.status == "error"
        assert "Não foi possível ler" in result.error_log

    def test_source_without_path_or_connector_is_an_error_not_a_crash(self, db):
        no_path = Source.objects.create(slug="sem-path", name="x", kind="seed_csv")
        assert run(no_path).status == "error"
        unknown = Source.objects.create(slug="sem-conector", name="y", kind="api")
        result = run(unknown)
        assert result.status == "error" and "Sem conector" in result.error_log


class TestSeedCsvOpportunities:
    def test_creates_and_revisits_opportunities(self, tmp_path):
        row = (
            "Game Jam Teste,game_jam,https://example.org/jam,Prefeitura X,Resumo,2026-12-31,"
            "Bauru,SP,\n"
        )
        source = seed_source(tmp_path, OPP_HEADER + row, entity="opportunity")
        first = run(source)
        assert (first.items_new, first.status) == (1, "ok")
        opportunity = Opportunity.objects.get()
        assert opportunity.canonical_key == "url:example.org/jam"
        assert timezone.localdate(opportunity.deadline_at).isoformat() == "2026-12-31"
        seen_first = opportunity.last_seen_at

        again = run(source)
        assert (again.items_new, again.items_updated) == (0, 0)
        opportunity.refresh_from_db()
        assert opportunity.last_seen_at > seen_first
        assert Opportunity.objects.count() == 1

        changed = row.replace("2026-12-31", "2027-01-15")
        source_path = source.config["path"]
        open(source_path, "w", encoding="utf-8").write(OPP_HEADER + changed)
        third = run(source)
        assert third.items_updated == 1
        opportunity.refresh_from_db()
        assert timezone.localdate(opportunity.deadline_at).isoformat() == "2027-01-15"
        # Histórico preservado: a evidência do prazo antigo continua, a nova é outra linha.
        assert Evidence.objects.filter(field="deadline_at").count() == 2

    def test_links_the_organizer_when_it_is_already_known(self, tmp_path):
        known = Organization.objects.create(name="Prefeitura X")
        source = seed_source(
            tmp_path,
            OPP_HEADER + "Edital,edital,https://example.org/e,Prefeitura X,,,,,\n",
            entity="opportunity",
        )
        run(source)
        assert Opportunity.objects.get().organizer == known
        assert Organization.objects.count() == 1  # não cria organização nova

    def test_invalid_deadline_fails_the_row(self, tmp_path):
        source = seed_source(
            tmp_path,
            OPP_HEADER + "Edital,edital,https://example.org/e,,,31/12/2026,,,\n",
            entity="opportunity",
        )
        result = run(source)
        assert (result.status, result.items_failed) == ("partial", 1)
        assert "AAAA-MM-DD" in result.error_log


class TestUpsert:
    def test_candidate_without_evidence_is_still_deduplicated(self, tmp_path):
        source = seed_source(tmp_path, "")
        candidate = OrganizationCandidate(
            name="Escola Z", fields={"municipality_name": "Jaú", "uf": "SP"}
        )
        organization, outcome = upsert(candidate, source=source)
        assert outcome == CREATED
        _, again = upsert(candidate, source=source)
        assert again == UNCHANGED

    def test_new_evidence_counts_as_an_update_and_links_the_raw_document(self, tmp_path):
        source = seed_source(tmp_path, "")
        document = RawDocument.objects.create(url="https://example.org/p", source=source)
        base = {"fields": {"municipality_name": "Jaú"}}
        upsert(OrganizationCandidate(name="Escola Z", **base), source=source)
        candidate = OrganizationCandidate(
            name="Escola Z",
            **base,
            evidence=[
                EvidenceDraft(field="segment", value="técnico", source_url="https://example.org/p")
            ],
        )
        organization, outcome = upsert(candidate, source=source, raw_document=document)
        assert outcome == UPDATED
        assert Evidence.objects.get(field="segment").raw_document == document

    def test_unknown_candidate_type_is_rejected(self, tmp_path):
        with pytest.raises(TypeError):
            upsert(object(), source=seed_source(tmp_path, ""))

    def test_opportunity_candidate_default_key_uses_the_organizer_and_title(self, tmp_path):
        source = seed_source(tmp_path, "")
        candidate = OpportunityCandidate(
            title="Chamada Aberta",
            fields={"organizer_name": "Instituto Y", "kind": "call_for_partners"},
        )
        opportunity, outcome = upsert(candidate, source=source)
        assert outcome == CREATED
        assert opportunity.canonical_key == "slug:instituto-y|chamada-aberta|sem-prazo"


class FakeConnector:
    """Conector de teste: devolve itens e simula bloqueio ou falha no meio do caminho."""

    kind = "api"

    def __init__(self, items, fail_with=None):
        self.items, self.fail_with = items, fail_with

    def fetch(self, ctx):
        yield from self.items
        if self.fail_with:
            raise self.fail_with

    def normalize(self, item):
        return OrganizationCandidate(name=item.data["name"])


class TestRunnerIsolation:
    def source(self, **kwargs):
        defaults = {"slug": "api-teste", "name": "API", "kind": "api", "enabled": True}
        return Source.objects.create(**{**defaults, "robots_ok": True, **kwargs})

    def test_a_connector_crash_keeps_what_was_already_saved(self):
        connector = FakeConnector([RawItem(data={"name": "Uma"})], fail_with=RuntimeError("caiu"))
        result = run(self.source(), connector=connector, fetcher=object())
        assert (result.status, result.items_new) == ("partial", 1)
        assert "conector: RuntimeError: caiu" in result.error_log
        assert Organization.objects.count() == 1

    def test_a_crash_before_any_item_is_an_error(self):
        result = run(
            self.source(), connector=FakeConnector([], RuntimeError("x")), fetcher=object()
        )
        assert result.status == "error"

    def test_a_robots_block_disables_the_source_for_human_review(self):
        from collection.fetcher import RobotsDisallowed

        source = self.source()
        result = run(source, connector=FakeConnector([], RobotsDisallowed("não")), fetcher=object())
        assert result.status == "error"
        assert "BLOQUEADA" in result.error_log and "revisão humana" in result.error_log
        source.refresh_from_db()
        assert not source.enabled

    def test_a_dry_run_block_does_not_change_the_source(self):
        from collection.fetcher import FetchBlocked

        source = self.source()
        run(
            source, connector=FakeConnector([], FetchBlocked("403")), fetcher=object(), dry_run=True
        )
        source.refresh_from_db()
        assert source.enabled

    def test_errors_do_not_leak_item_content(self, tmp_path):
        source = seed_source(tmp_path, ORG_HEADER + "Pessoa Secreta,planeta,,X,SP,,,,,\n")
        result = run(source)
        assert result.items_failed == 1
        assert "linha 2" in result.error_log

    def test_a_run_uses_a_fetcher_configured_from_the_source(self):
        source = self.source(config={"min_interval_seconds": 9, "max_pages": 3, "max_bytes": 1000})
        fetcher = build_fetcher(source)
        assert (fetcher.min_interval, fetcher.max_requests, fetcher.max_bytes) == (9, 3, 1000)
        dataset = self.source(slug="dados", kind="dataset")
        assert build_fetcher(dataset).max_bytes > 20 * 1024 * 1024


class TestConnectorOverNetwork:
    """Um conector `html_watch` mínimo, para provar o fluxo fetcher → runner → evidência."""

    def test_end_to_end_with_a_mock_site(self):
        class Listing:
            kind = "html_watch"

            def __init__(self, source):
                self.source = source

            def fetch(self, ctx):
                result = ctx.fetcher.fetch("https://example.org/lista", source=ctx.source)
                for line in result.text.splitlines():
                    yield RawItem(
                        data={"name": line},
                        source_url=result.url,
                        raw_document=result.document,
                    )

            def normalize(self, item):
                return OrganizationCandidate(
                    name=item.data["name"],
                    evidence=[
                        EvidenceDraft(
                            field="name",
                            value=item.data["name"],
                            source_url=item.source_url,
                            excerpt=item.data["name"],
                        )
                    ],
                )

        def site(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(
                200, text="Escola Um\nEscola Dois", headers={"content-type": "text/plain"}
            )

        fetcher = PoliteFetcher(
            client=httpx.Client(transport=httpx.MockTransport(site)),
            sleep=lambda s: None,
        )
        source = Source.objects.create(
            slug="listagem", name="Listagem", kind="html_watch", enabled=True, robots_ok=True
        )
        result = run(source, connector=Listing(source), fetcher=fetcher)
        assert (result.status, result.items_new) == ("ok", 2)
        evidence = Evidence.objects.filter(field="name").first()
        assert evidence.raw_document.url == "https://example.org/lista"
        assert evidence.method == "connector:listagem"
        assert RawDocument.objects.get().source == source


class TestCollectCommand:
    def collect(self, *args):
        out = StringIO()
        call_command("collect", *args, stdout=out)
        return out.getvalue()

    def test_collect_one_source_prints_counts_only(self, tmp_path):
        seed_source(tmp_path, ORG_HEADER + "Pessoa Secreta,school,,Bauru,SP,,,,,\n")
        out = self.collect("seed-teste")
        assert "1 novos" in out and "concluída" in out
        assert "Secreta" not in out and "Bauru" not in out
        assert CollectionRun.objects.count() == 1

    def test_dry_run_flag(self, tmp_path):
        seed_source(tmp_path, ORG_HEADER + "A,school,,Bauru,SP,,,,,\n")
        assert "[dry-run]" in self.collect("seed-teste", "--dry-run")
        assert Organization.objects.count() == 0
        assert CollectionRun.objects.get().dry_run

    def test_all_runs_only_enabled_sources(self, tmp_path):
        seed_source(tmp_path, ORG_HEADER + "A,school,,Bauru,SP,,,,,\n")
        Source.objects.create(slug="desligada", name="D", kind="seed_csv", enabled=False)
        out = self.collect("--all")
        assert "seed-teste: concluída" in out
        assert "desligada" not in out

    def test_all_skips_network_sources_whose_robots_were_not_checked(self, tmp_path):
        Source.objects.create(slug="api-x", name="X", kind="api", enabled=True)
        assert "ignorada" in self.collect("--all")
        assert CollectionRun.objects.count() == 0

    def test_argument_errors(self, tmp_path):
        with pytest.raises(CommandError, match="Informe uma fonte"):
            self.collect()
        with pytest.raises(CommandError, match="Informe uma fonte"):
            self.collect("a", "--all")
        with pytest.raises(CommandError, match="não existe"):
            self.collect("fantasma")
        with pytest.raises(CommandError, match="--limit"):
            self.collect("--all", "--limit", "0")

    def test_a_disabled_source_needs_the_admin_first_but_dry_run_is_allowed(self, tmp_path):
        seed_source(tmp_path, ORG_HEADER + "A,school,,Bauru,SP,,,,,\n", enabled=False)
        with pytest.raises(CommandError, match="desabilitada"):
            self.collect("seed-teste")
        assert "[dry-run]" in self.collect("seed-teste", "--dry-run")

    def test_network_source_requires_robots_ok_even_in_dry_run(self):
        source = Source.objects.create(slug="api-x", name="X", kind="api", enabled=True)
        assert "robots.txt" in runnable_problem(source, dry_run=True)
        with pytest.raises(CommandError, match="robots.txt"):
            self.collect("api-x", "--dry-run")

    def test_exits_with_error_when_a_source_fails_completely(self, tmp_path):
        source = seed_source(tmp_path, "")
        source.config["path"] = str(tmp_path / "nada.csv")
        source.save()
        with pytest.raises(CommandError, match="falharam"):
            self.collect("seed-teste")

    def test_limit_flag(self, tmp_path):
        seed_source(tmp_path, ORG_HEADER + "A,school,,X,SP,,,,,\nB,school,,X,SP,,,,,\n")
        assert "1 vistos" in self.collect("seed-teste", "--limit", "1")


class TestRegistry:
    def test_slug_connector_wins_over_the_generic_kind(self):
        class Special:
            def __init__(self, source):
                self.source = source

        registry.register(slug="especial-teste")(Special)
        try:
            source = Source(slug="especial-teste", kind="seed_csv")
            assert isinstance(registry.for_source(source), Special)
        finally:
            registry._BY_SLUG.pop("especial-teste")

    def test_register_needs_exactly_one_selector(self):
        with pytest.raises(ValueError):
            registry.register()
        with pytest.raises(ValueError):
            registry.register(slug="a", kind="b")


class TestRetention:
    def test_purge_clears_expired_text_but_keeps_url_hash_and_evidence_link(self, tmp_path):
        source = seed_source(tmp_path, "")
        old = RawDocument(url="https://example.org/velho", source=source, content_hash="abc")
        old.set_text("conteúdo antigo")
        old.expires_at = timezone.now() - timedelta(days=1)
        old.etag = '"v"'
        old.save()
        fresh = RawDocument(url="https://example.org/novo", source=source)
        fresh.set_text("conteúdo novo")
        fresh.save()
        out = StringIO()
        call_command("purge_raw_documents", stdout=out)
        assert "apagado em 1" in out.getvalue()
        old.refresh_from_db()
        assert not old.has_text and old.size_bytes == 0 and old.content_hash == "abc"
        assert old.etag == ""  # sem texto não dá para responder a um 304
        fresh.refresh_from_db()
        assert fresh.text == "conteúdo novo"

    def test_default_expiry_follows_the_setting(self, settings):
        settings.RAW_DOCUMENT_RETENTION_DAYS = 10
        document = RawDocument.objects.create(url="https://example.org/x")
        delta = document.expires_at - timezone.now()
        assert timedelta(days=9) < delta <= timedelta(days=10)


class TestAdmin:
    def test_runs_and_documents_are_visible_and_read_only(self, admin_client, tmp_path):
        source = seed_source(tmp_path, ORG_HEADER + "A,school,,Bauru,SP,,,,,\n")
        run_source(source)
        RawDocument.objects.create(url="https://example.org/x", source=source)
        for name in ("collectionrun", "rawdocument"):
            assert (
                admin_client.get(reverse(f"admin:collection_{name}_changelist")).status_code == 200
            )
            assert admin_client.get(reverse(f"admin:collection_{name}_add")).status_code == 403
        document = RawDocument.objects.get()
        response = admin_client.get(
            reverse("admin:collection_rawdocument_change", args=[document.pk])
        )
        assert response.status_code == 200
        assert "text_gz" not in response.content.decode()
