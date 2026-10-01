"""E10 — camada de IA: roteamento, cache, teto, classe de dados e adapters (sem rede)."""

import base64
import json
import re
from decimal import Decimal
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.core.management import call_command
from pydantic import BaseModel

from llm.models import LLMCall
from llm.pricing import cost_usd
from llm.providers.anthropic import AnthropicProvider
from llm.providers.fake import FakeProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.ollama import OllamaProvider
from llm.quotes import Quoted, verify_quotes
from llm.router import AIService, parse_response
from llm.tasks import Task, get_task, task_names
from llm.types import (
    DataClass,
    LLMInput,
    NoStrategyAvailable,
    PricingError,
    ProviderError,
    RateLimited,
    SchemaValidationFailed,
)

PUBLIC = LLMInput(DataClass.PUBLIC, text="Edital de jogos educativos")
INTERNAL = LLMInput(DataClass.INTERNAL, text="Contato interno da escola")
GOOD = json.dumps({"answer": "ok"})


class Out(BaseModel):
    answer: str


def make_task(strategies, **kwargs):
    return Task(name="t", schema=Out, system="Responda.", strategies=strategies, **kwargs)


def service(**providers):
    return AIService(providers=providers)


def paid(replies=(), **kwargs):
    """Provedor pago falso com nome/modelo que existem na tabela de preços."""
    return FakeProvider(replies, name="anthropic", billing="money", **kwargs)


# --- parsing e custo -----------------------------------------------------------------------------


def test_parse_accepts_code_fence_and_text_around():
    assert parse_response(f"```json\n{GOOD}\n```", Out).answer == "ok"
    assert parse_response(f"Claro! {GOOD} Pronto.", Out).answer == "ok"


@pytest.mark.parametrize("text", ["sem json", "{quebrado", '{"outra": 1}'])
def test_parse_rejects_without_echoing_content(text):
    with pytest.raises(SchemaValidationFailed) as exc:
        parse_response(text, Out)
    assert "quebrado" not in str(exc.value)


def test_cost_is_computed_from_price_table():
    # Haiku 4.5: US$ 1 / US$ 5 por 1M -> 1.000 entrada + 500 saída
    assert cost_usd("anthropic", "claude-haiku-4-5", "money", 1000, 500) == Decimal("0.0035")
    assert cost_usd("gemini-free", "qualquer", "free", 10**6, 10**6) == 0
    with pytest.raises(PricingError):
        cost_usd("anthropic", "modelo-inexistente", "money", 1, 1)


# --- roteamento, cache, retry --------------------------------------------------------------------


@pytest.mark.django_db
def test_second_identical_call_is_served_from_cache():
    fake = FakeProvider([GOOD])
    ai = service(fake=fake)
    task = make_task(["fake:m"])
    first = ai.run(task, PUBLIC)
    second = ai.run(task, PUBLIC)
    assert (first.cached, second.cached) == (False, True)
    assert second.cost_usd == 0 and second.data.answer == "ok"
    assert len(fake.requests) == 1
    assert list(LLMCall.objects.order_by("id").values_list("status", flat=True)) == ["ok", "cached"]


@pytest.mark.django_db
def test_new_prompt_version_invalidates_cache():
    fake = FakeProvider([GOOD, GOOD])
    ai = service(fake=fake)
    ai.run(make_task(["fake:m"], prompt_version="v1"), PUBLIC)
    ai.run(make_task(["fake:m"], prompt_version="v2"), PUBLIC)
    assert len(fake.requests) == 2


@pytest.mark.django_db
def test_schema_failure_retries_once_then_succeeds():
    fake = FakeProvider(["lixo", GOOD])
    result = service(fake=fake).run(make_task(["fake:m"]), PUBLIC)
    assert result.data.answer == "ok" and len(fake.requests) == 2
    assert "recusada" in fake.requests[1][1].prompt
    assert list(LLMCall.objects.order_by("id").values_list("status", flat=True)) == [
        "invalid",
        "ok",
    ]


@pytest.mark.django_db
def test_schema_failure_twice_falls_back_to_next_strategy():
    bad = FakeProvider(["lixo", "lixo"], name="bad")
    good = FakeProvider([GOOD], name="good")
    result = service(bad=bad, good=good).run(make_task(["bad:m", "good:m"]), PUBLIC)
    assert result.strategy == "good:m" and len(bad.requests) == 2


@pytest.mark.django_db
def test_rate_limit_and_provider_error_pass_to_next_provider():
    a = FakeProvider([RateLimited("429")], name="a")
    b = FakeProvider([ProviderError("HTTP 500")], name="b")
    c = FakeProvider([GOOD], name="c")
    result = service(a=a, b=b, c=c).run(make_task(["a:m", "b:m", "c:m"]), PUBLIC)
    assert result.strategy == "c:m"
    assert list(LLMCall.objects.order_by("id").values_list("status", flat=True))[:2] == [
        "rate_limited",
        "error",
    ]


@pytest.mark.django_db
def test_all_strategies_failing_raises_with_reasons_and_no_content():
    fake = FakeProvider([ProviderError("HTTP 500")])
    with pytest.raises(NoStrategyAvailable) as exc:
        service(fake=fake).run(make_task(["fake:m", "inexistente:m"]), PUBLIC)
    assert "HTTP 500" in str(exc.value) and "Edital" not in str(exc.value)


@pytest.mark.django_db
def test_strategy_is_changed_by_configuration_only(settings):
    a, b = FakeProvider([GOOD], name="a"), FakeProvider([GOOD], name="b")
    ai = service(a=a, b=b)
    task = make_task(["a:m"])
    assert ai.run(task, PUBLIC).strategy == "a:m"
    settings.LLM_TASK_STRATEGIES = {"t": ["b:m"]}
    assert ai.run(task, LLMInput(DataClass.PUBLIC, text="outro texto")).strategy == "b:m"


@pytest.mark.django_db
def test_rules_strategy_answers_without_llm_and_falls_through_on_none():
    fake = FakeProvider([GOOD])
    ai = service(fake=fake)
    task = make_task(
        ["rules", "fake:m"],
        rules=lambda i: {"answer": "regra"} if "jogos" in i.text else None,
    )
    hit = ai.run(task, PUBLIC)
    assert (hit.strategy, hit.cost_usd, hit.data.answer) == ("rules", 0, "regra")
    assert not fake.requests and LLMCall.objects.count() == 0
    miss = ai.run(task, LLMInput(DataClass.PUBLIC, text="sem pista"))
    assert miss.strategy == "fake:m"


@pytest.mark.django_db
def test_input_is_truncated_to_hard_limit():
    fake = FakeProvider([GOOD])
    service(fake=fake).run(
        make_task(["fake:m"], max_input_chars=10), LLMInput(DataClass.PUBLIC, text="x" * 500)
    )
    assert fake.requests[0][1].prompt == "x" * 10


# --- orçamento -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_budget_blocks_paid_but_allows_free(settings):
    settings.LLM_MONTHLY_BUDGET_USD = 0.0
    pago = paid([GOOD])
    gratis = FakeProvider([GOOD], name="free")
    result = service(anthropic=pago, free=gratis).run(
        make_task(["anthropic:claude-haiku-4-5", "free:m"]), PUBLIC
    )
    assert result.strategy == "free:m" and not pago.requests


@pytest.mark.django_db
def test_paid_call_is_logged_with_cost_and_counts_toward_month(settings):
    settings.LLM_MONTHLY_BUDGET_USD = 5.0
    pago = paid([GOOD], input_tokens=1000, output_tokens=500)
    result = service(anthropic=pago).run(make_task(["anthropic:claude-haiku-4-5"]), PUBLIC)
    assert result.cost_usd == Decimal("0.0035")
    call = LLMCall.objects.get()
    assert (call.billing, call.cost_usd, call.input_tokens) == ("money", Decimal("0.0035"), 1000)

    from llm import budget

    assert budget.month_spent("money") == Decimal("0.0035")
    assert budget.month_spent("credits") == 0


@pytest.mark.django_db
def test_run_budget_stops_second_paid_call(settings):
    settings.LLM_RUN_BUDGET_USD = 0.01  # estimativa ≈ 0,0076 por chamada; real 0,0035
    pago = paid([GOOD, GOOD], input_tokens=1000, output_tokens=500)  # 0,0035 cada
    ai = service(anthropic=pago)
    ai.run(make_task(["anthropic:claude-haiku-4-5"]), PUBLIC)
    with pytest.raises(NoStrategyAvailable, match="execução"):
        ai.run(make_task(["anthropic:claude-haiku-4-5"]), LLMInput(DataClass.PUBLIC, text="b"))


@pytest.mark.django_db
def test_paid_model_without_price_is_never_called():
    pago = paid([GOOD])
    with pytest.raises(NoStrategyAvailable, match="sem preço"):
        service(anthropic=pago).run(make_task(["anthropic:modelo-sem-preco"]), PUBLIC)
    assert not pago.requests


# --- classe de dados -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_internal_data_never_reaches_free_tier(settings):
    settings.GEMINI_API_KEY_FREE = "chave-de-teste"

    def refuse(request):
        raise AssertionError("nada deveria sair para o free tier")

    free = GeminiProvider(paid=False, client=httpx.Client(transport=httpx.MockTransport(refuse)))
    ai = service(**{"gemini-free": free, "anthropic": paid([GOOD])})
    result = ai.run(
        make_task(["gemini-free:gemini-2.5-flash-lite", "anthropic:claude-haiku-4-5"]), INTERNAL
    )
    assert result.strategy == "anthropic:claude-haiku-4-5"
    with pytest.raises(NoStrategyAvailable, match="não pode ir"):
        ai.run(make_task(["gemini-free:gemini-2.5-flash-lite"]), INTERNAL)


def test_data_class_policy_per_provider(settings):
    settings.OLLAMA_BASE_URL = "http://localhost:11434"
    assert OllamaProvider().accepts(DataClass.INTERNAL)
    settings.OLLAMA_BASE_URL = "https://ollama.example.org"  # remoto = terceiro (LGPD)
    assert not OllamaProvider().accepts(DataClass.INTERNAL)
    assert OllamaProvider().accepts(DataClass.PUBLIC)
    assert not GeminiProvider(paid=False).accepts(DataClass.INTERNAL)
    assert GeminiProvider(paid=True).accepts(DataClass.INTERNAL)
    assert AnthropicProvider().accepts(DataClass.INTERNAL)


@pytest.mark.django_db
def test_provider_without_key_is_skipped(settings):
    settings.GEMINI_API_KEY_FREE = ""
    with pytest.raises(NoStrategyAvailable, match="sem chave"):
        AIService().run(make_task(["gemini-free:gemini-2.5-flash-lite"]), PUBLIC)


# --- adapters (HTTP simulado) --------------------------------------------------------------------


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_request_and_usage(settings):
    settings.GEMINI_API_KEY_PAID = "chave-de-teste"
    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": GOOD}]}}],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 30,
                    "thoughtsTokenCount": 10,
                },
            },
        )

    from llm.types import ProviderRequest

    provider = GeminiProvider(paid=True, client=mock_client(handler))
    response = provider.complete(
        "gemini-2.5-flash", ProviderRequest("sistema", "pergunta", pdf_bytes=b"%PDF-x")
    )
    assert (response.text, response.input_tokens, response.output_tokens) == (GOOD, 120, 40)
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert "chave-de-teste" not in seen["url"] and seen["key"] == "chave-de-teste"
    parts = seen["body"]["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "application/pdf"
    assert base64.b64decode(parts[0]["inline_data"]["data"]) == b"%PDF-x"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_blocked_response_and_429():
    from llm.types import ProviderRequest

    blocked = GeminiProvider(paid=True, client=mock_client(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ProviderError):
        blocked.complete("m", ProviderRequest("s", "p"))
    limited = GeminiProvider(paid=False, client=mock_client(lambda r: httpx.Response(429)))
    with pytest.raises(RateLimited):
        limited.complete("m", ProviderRequest("s", "p"))


def test_anthropic_request_and_usage(settings):
    settings.ANTHROPIC_API_KEY = "chave-de-teste"
    seen = {}

    def handler(request):
        seen["headers"], seen["body"] = request.headers, json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": GOOD}],
                "usage": {"input_tokens": 80, "output_tokens": 20},
            },
        )

    from llm.types import ProviderRequest

    response = AnthropicProvider(client=mock_client(handler)).complete(
        "claude-haiku-4-5", ProviderRequest("sistema", "pergunta", max_output_tokens=500)
    )
    assert (response.text, response.input_tokens, response.output_tokens) == (GOOD, 80, 20)
    assert seen["headers"]["x-api-key"] == "chave-de-teste"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["max_tokens"] == 500 and seen["body"]["system"] == "sistema"


def test_ollama_request_and_custom_base_url(settings):
    settings.OLLAMA_BASE_URL = "https://ollama.example.org/"
    settings.OLLAMA_API_KEY = "chave-de-teste"
    seen = {}

    def handler(request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        return httpx.Response(
            200, json={"message": {"content": GOOD}, "prompt_eval_count": 7, "eval_count": 3}
        )

    from llm.types import ProviderRequest

    response = OllamaProvider(client=mock_client(handler)).complete(
        "qwen2.5:7b", ProviderRequest("s", "p")
    )
    assert (response.input_tokens, response.output_tokens) == (7, 3)
    assert seen["url"] == "https://ollama.example.org/api/chat"
    assert seen["auth"] == "Bearer chave-de-teste"


# --- citações ------------------------------------------------------------------------------------


class Edital(BaseModel):
    prazo: Quoted
    premio: Quoted


def test_quotes_are_verified_against_source_ignoring_accents_and_spacing():
    source = "Inscrições   até 30/11/2026.\nPrêmio de R$ 5.000"
    data = Edital(
        prazo=Quoted(value="2026-11-30", quote="inscricoes ate 30/11/2026"),
        premio=Quoted(value="R$ 10.000", quote="Prêmio de R$ 10.000"),  # citação inventada
    )
    assert verify_quotes(data, source) == ["premio"]
    assert data.prazo.verified and not data.premio.verified


def test_unknown_value_is_not_a_failure():
    data = Edital(prazo=Quoted(), premio=Quoted(value="unknown"))
    assert verify_quotes(data, "texto") == []


@pytest.mark.django_db
def test_router_reports_unverified_quotes():
    reply = json.dumps(
        {"prazo": {"value": "x", "quote": "não está no texto"}, "premio": {"value": "unknown"}}
    )
    task = Task(name="e", schema=Edital, system="s", strategies=["fake:m"])
    result = service(fake=FakeProvider([reply])).run(task, PUBLIC)
    assert result.unverified == ["prazo"]


# --- comandos, registro e regra de isolamento -----------------------------------------------------


@pytest.mark.django_db
def test_llm_usage_reports_month_without_content(settings):
    settings.LLM_MONTHLY_BUDGET_USD = 5.0
    ai = service(anthropic=paid([GOOD], input_tokens=1000, output_tokens=500))
    ai.run(make_task(["anthropic:claude-haiku-4-5"]), PUBLIC)
    out = StringIO()
    call_command("llm_usage", stdout=out)
    text = out.getvalue()
    assert "dinheiro novo: US$ 0.0035 de US$ 5.00" in text
    assert "t · anthropic:claude-haiku-4-5 · ok: 1x" in text
    assert "Edital" not in text


@pytest.mark.django_db
def test_llm_smoke_logs_a_call(monkeypatch):
    reply = json.dumps({"ok": True, "echo": "radar"})
    fake = FakeProvider([reply], name="gemini-free")
    monkeypatch.setattr(
        "llm.management.commands.llm_smoke.AIService",
        lambda: AIService(providers={"gemini-free": fake}),
    )
    out = StringIO()
    call_command("llm_smoke", stdout=out)
    assert "OK · gemini-free:gemini-2.5-flash-lite" in out.getvalue()
    assert LLMCall.objects.filter(task="smoke_ping", status="ok").count() == 1


def test_smoke_task_is_registered():
    assert "smoke_ping" in task_names() and get_task("smoke_ping").schema.__name__ == "SmokePing"


def test_only_llm_providers_talk_to_model_apis_or_import_sdks():
    root = Path(__file__).resolve().parent.parent
    forbidden = re.compile(
        r"(?:^|\n)\s*(?:import|from)\s+(?:anthropic|google\.genai|google\.generativeai|openai|ollama)\b"
        r"|generativelanguage\.googleapis\.com|api\.anthropic\.com|api/chat",
    )
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts[0] in {"tests", ".venv", "docs"} or rel.parts[:2] == ("llm", "providers"):
            continue
        if forbidden.search(path.read_text(encoding="utf-8")):
            offenders.append(str(rel))
    assert not offenders, f"fora de llm/providers: {offenders}"
