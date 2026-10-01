"""E11 — extração de oportunidades: regras, janelas, conferência, gravação e comando (sem rede)."""

import json
from datetime import date
from decimal import Decimal
from io import StringIO

import httpx
import pytest
from django.core.management import call_command
from django.utils import timezone

from collection.fetcher import PoliteFetcher
from core.models import Evidence, LegalForm, Opportunity
from extraction import opportunity as extraction_module
from extraction import rules
from extraction.opportunity import apply_extraction, extract_opportunity
from extraction.text import page_text, select_windows
from llm.models import LLMCall
from llm.providers.fake import FakeProvider
from llm.router import AIService
from llm.types import DataClass, LLMInput, NoStrategyAvailable

URL = "https://edital.example.org/jam-2026"
PAGE = (
    "Chamada Pública de Jogos Educativos 2026. As inscrições vão até 30/09/2026 pelo formulário. "
    "Podem participar microempreendedores individuais (MEI), ME e EPP com CNPJ constituído há "
    "mais de 2 anos. Atividade principal CNAE 62.01-5/01 ou 8599-6/04. "
    "O prêmio total é de R$ 15.000,00 para os três primeiros colocados. A participação é gratuita. "
)
PAGE = PAGE.replace("62.01-5/01", "6201-5/01")
HTML = f"<html><head><title>Chamada Jogos</title></head><body><p>{PAGE}</p></body></html>"


def reply(**fields):
    base = {}
    for name, (value, quote) in fields.items():
        base[name] = {"value": value, "quote": quote}
    return json.dumps(base)


GOOD = reply(
    deadline=("2026-09-30", "As inscrições vão até 30/09/2026"),
    accepts_mei=("yes", "Podem participar microempreendedores individuais (MEI)"),
    min_company_age_months=(24, "CNPJ constituído há mais de 2 anos"),
    prize_amount_brl=("15000.00", "O prêmio total é de R$ 15.000,00"),
    required_cnaes=(["6201-5/01"], "CNAE 6201-5/01"),
    summary=("Chamada para jogos educativos.", "Chamada Pública de Jogos Educativos 2026"),
    effort=("low", "frase que não está na página"),
)


def service(*replies):
    fake = FakeProvider(list(replies), name="gemini-free")
    return AIService(providers={"gemini-free": fake}), fake


@pytest.fixture
def opp(db):
    return Opportunity.objects.create(
        title="Chamada Jogos", kind=Opportunity.Kind.EDITAL, official_url=URL
    )


# --- regras ---------------------------------------------------------------------------------------
def test_dates_numeric_and_written():
    found = rules.find_dates("até 5/1/2026 ou 30 de setembro de 2026; 31/02/2026 não existe")
    assert [d for d, _s, _e in found] == [date(2026, 1, 5), date(2026, 9, 30)]


def test_deadline_needs_a_single_date_near_a_deadline_word():
    assert rules.deadline(PAGE).value == date(2026, 9, 30)
    two = "Inscrições até 01/10/2026. Prazo de recurso até 05/10/2026."
    assert rules.deadline(two) is None
    assert rules.deadline("O evento acontece em 12/11/2026 na cidade.") is None


def test_mei_acceptance_and_exclusion():
    assert rules.mei_acceptance(PAGE).value == "yes"
    veda = "É vedada a participação de MEI neste edital. Outras regras seguem."
    assert rules.mei_acceptance(veda).value == "no"
    assert rules.mei_acceptance("O MEI deve ter conta no portal.") is None


def test_company_age_exclusive_and_cnae():
    assert rules.company_age_months(PAGE).value == 24
    assert (
        rules.company_age_months("Atuamos há mais de 5 anos no mercado") is None
    )  # sem CNPJ/empresa
    assert rules.exclusive_small_business("Cota exclusiva para microempresas e EPP").value == "yes"
    assert rules.cnaes(PAGE).value == ["6201-5/01", "8599-6/04"]


def test_prize_takes_largest_value_near_prize_word():
    found = rules.prize("Taxa de R$ 50,00. Prêmio total de R$ 1.500,50 e valor extra R$ 200,00.")
    assert found.value == Decimal("1500.50")


# --- texto ----------------------------------------------------------------------------------------
def test_page_text_strips_html_and_windows_keep_keywords():
    title, text = page_text(HTML, "text/html")
    assert title == "Chamada Jogos" and "30/09/2026" in text and "<p>" not in text
    long_text = "lorem ipsum " * 3000 + "As inscrições vão até 30/09/2026. " + "dolor sit " * 3000
    window = select_windows(long_text, 2000)
    assert len(window) <= 2000 + 20 and "30/09/2026" in window
    assert select_windows("curto", 2000) == "curto"


# --- conferência e gravação -----------------------------------------------------------------------
def test_review_trusts_verified_and_consistent_fields_only(opp):
    svc, _ = service(GOOD)
    extraction = extract_opportunity(opp, PAGE, svc)
    assert extraction.fields["deadline"].trusted
    assert extraction.fields["min_company_age_months"].trusted
    assert extraction.fields["required_cnaes"].trusted
    assert not extraction.fields["effort"].trusted  # citação inventada
    assert "effort" in extraction.unverified


def test_model_date_absent_from_text_is_not_trusted(opp):
    wrong = reply(deadline=("2026-10-31", "As inscrições vão até 30/09/2026"))
    svc, _ = service(wrong)
    extraction = extract_opportunity(opp, PAGE, svc)
    assert not extraction.fields["deadline"].trusted


def test_apply_fills_blanks_and_records_evidence(opp):
    svc, _ = service(GOOD)
    extraction = extract_opportunity(opp, PAGE, svc)
    counts = apply_extraction(opp, extraction, PAGE)
    opp.refresh_from_db()
    assert (
        timezone.localtime(opp.deadline_at).date() == date(2026, 9, 30)
        and timezone.localtime(opp.deadline_at).hour == 23
    )
    assert opp.min_company_age_months == 24 and opp.required_cnaes == ["6201-5/01"]
    assert opp.prize_amount_brl == Decimal("15000.00")
    assert opp.description.startswith("Chamada")
    assert opp.effort_estimate == "low"  # não crítico: entra, mas só com evidência inferida
    assert opp.extraction_version == extraction_module.EXTRACTION_VERSION
    deadline = Evidence.objects.get(field="deadline_at")
    assert deadline.kind == "observed" and deadline.verified and "30/09/2026" in deadline.excerpt
    assert Evidence.objects.get(field="effort_estimate").kind == "inferred"
    assert counts["observed"] >= 5 and counts["inferred"] == 1


def test_untrusted_critical_field_stays_out_of_the_column(opp):
    wrong = reply(
        deadline=("2026-10-31", "prazo final em 31/10/2026"),
        min_company_age_months=(36, "CNPJ há mais de 3 anos"),
    )
    svc, _ = service(wrong)
    apply_extraction(opp, extract_opportunity(opp, PAGE, svc), PAGE)
    opp.refresh_from_db()
    assert opp.deadline_at is None and opp.min_company_age_months is None
    assert Evidence.objects.filter(kind="inferred", field="deadline_at").exists()


def test_existing_columns_are_never_overwritten(opp):
    opp.min_company_age_months = 12
    opp.save()
    svc, _ = service(GOOD)
    apply_extraction(opp, extract_opportunity(opp, PAGE, svc), PAGE)
    opp.refresh_from_db()
    assert opp.min_company_age_months == 12


def test_mei_exclusion_derives_other_legal_forms(opp):
    text = "Edital de fomento a estúdios independentes. É vedada a participação de MEI. " * 3
    veda = reply(accepts_mei=("no", "É vedada a participação de MEI"))
    svc, _ = service(veda)
    apply_extraction(opp, extract_opportunity(opp, text, svc), text)
    opp.refresh_from_db()
    assert (
        LegalForm.MEI not in opp.eligible_legal_forms and LegalForm.ME in opp.eligible_legal_forms
    )


def test_rules_strategy_alone_when_no_model_is_available(opp, monkeypatch):
    svc = AIService(providers={"gemini-free": FakeProvider(is_available=False)})
    extraction = extract_opportunity(opp, PAGE, svc)
    assert extraction.strategy == "rules"
    apply_extraction(opp, extraction, PAGE)
    opp.refresh_from_db()
    assert timezone.localtime(opp.deadline_at).date() == date(2026, 9, 30) and opp.required_cnaes
    assert Evidence.objects.filter(field="deadline_at", method="regex:extract_opportunity").exists()


def test_nothing_found_by_rules_and_no_model_raises(opp):
    svc = AIService(providers={"gemini-free": FakeProvider(is_available=False)})
    with pytest.raises(NoStrategyAvailable):
        extract_opportunity(opp, "Texto qualquer sem nenhum dado útil. " * 10, svc)


def test_same_document_does_not_call_the_model_twice(opp):
    svc, fake = service(GOOD, GOOD)
    extract_opportunity(opp, PAGE, svc)
    again = extract_opportunity(opp, PAGE, svc)
    assert len(fake.requests) == 1 and again.cached
    assert LLMCall.objects.filter(task="extract_opportunity", status="cached").count() == 1


def test_prompt_is_public_data_only_and_marks_page_as_data(opp):
    svc, fake = service(GOOD)
    extract_opportunity(opp, PAGE, svc)
    model, request = fake.requests[0]
    assert "dado" in request.system and URL in request.prompt
    assert extraction_module.TASK.configured_strategies()[-1] == "rules"
    assert LLMInput(DataClass.PUBLIC).data_class == DataClass.PUBLIC


# --- comando --------------------------------------------------------------------------------------
class Web:
    def __init__(self, body=HTML, content_type="text/html; charset=utf-8", status=200):
        self.body, self.content_type, self.status = body, content_type, status

    def __call__(self, request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(
            self.status, text=self.body, headers={"content-type": self.content_type}
        )


@pytest.fixture
def run_command(monkeypatch):
    def _run(web, *replies, **options):
        client = httpx.Client(transport=httpx.MockTransport(web))
        fake = FakeProvider(list(replies), name="gemini-free")
        monkeypatch.setattr(
            "collection.management.commands.extract_opportunities.PoliteFetcher",
            lambda **kw: PoliteFetcher(client=client, min_interval=0, sleep=lambda s: None, **kw),
        )
        monkeypatch.setattr(
            "collection.management.commands.extract_opportunities.AIService",
            lambda: AIService(providers={"gemini-free": fake}),
        )
        out = StringIO()
        call_command("extract_opportunities", stdout=out, **options)
        return out.getvalue()

    return _run


def test_command_extracts_and_is_idempotent(opp, run_command):
    out = run_command(Web(), GOOD)
    assert "1 de 1 extraídas" in out and "US$" in out
    opp.refresh_from_db()
    assert opp.deadline_at is not None and opp.extraction_version
    again = run_command(Web(), GOOD)
    assert "0 de 0 extraídas" in again


def test_command_dry_run_writes_nothing(opp, run_command):
    out = run_command(Web(), GOOD, dry_run=True)
    assert out.startswith("[dry-run]")
    opp.refresh_from_db()
    assert opp.deadline_at is None and opp.extraction_version == ""
    assert not Evidence.objects.filter(field="deadline_at").exists()


def test_command_marks_pdf_and_empty_pages_without_text(opp, run_command):
    out = run_command(Web("%PDF-1.4", "application/pdf"))
    assert "1 sem texto" in out
    opp.refresh_from_db()
    assert opp.extraction_version == "sem-texto"
    other = Opportunity.objects.create(title="Só JS", official_url="https://js.example.org/x")
    out = run_command(Web("<html><script>app()</script></html>"))
    other.refresh_from_db()
    assert other.extraction_version == "sem-texto"
    forced = run_command(Web(), GOOD, force=True)
    assert "extraídas" in forced


def test_command_counts_http_failure_and_skips_candidates_without_url(opp, run_command, db):
    Opportunity.objects.create(title="Sem URL")
    out = run_command(Web(status=500))
    assert "1 com falha" in out and "0 extraídas" not in out.split("(")[0]
    opp.refresh_from_db()
    assert opp.extraction_version == ""  # tenta de novo na próxima
