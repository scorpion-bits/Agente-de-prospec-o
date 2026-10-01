"""``ai.run(task, input)``: roteia a tarefa pelas estratégias, em ordem, até uma dar certo.

Por estratégia: classe do dado → chave/PDF → cache → teto → chamada → schema (1 retry) → citações.
Rate limit, erro, schema inválido, teto ou dado interno em free tier ⇒ passa à seguinte.
Nenhuma mensagem de erro ou log leva o conteúdo enviado ou recebido (ADR-014).
"""

from __future__ import annotations

import json
import re
import time
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from llm import budget, cache
from llm.models import LLMCall
from llm.pricing import cost_usd
from llm.providers import RULES, default_providers, split_strategy
from llm.quotes import verify_quotes
from llm.tasks import Task, get_task
from llm.types import (
    BudgetExceeded,
    LLMError,
    LLMInput,
    LLMResult,
    NoStrategyAvailable,
    PricingError,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    RateLimited,
    SchemaValidationFailed,
)

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
MAX_ATTEMPTS = 2  # chamada + 1 retry de schema (ADR-003)

SCHEMA_RULES = (
    "Responda SOMENTE com um objeto JSON válido que siga este JSON Schema, sem texto extra. "
    'Se algo não está no texto, use "unknown" (nunca invente) e, em campos com citação, copie '
    "o trecho literal do texto em «quote».\nSchema:\n"
)


def parse_response(text: str, schema: type[BaseModel]) -> BaseModel:
    """JSON (com ou sem cerca de código) -> instância do schema. Erro sem eco do conteúdo."""
    cleaned = FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise SchemaValidationFailed("resposta sem objeto JSON")
    try:
        return schema.model_validate(json.loads(cleaned[start : end + 1]))
    except json.JSONDecodeError:
        raise SchemaValidationFailed("JSON malformado") from None
    except ValidationError as exc:
        # Só caminho e tipo do erro: a mensagem do pydantic repete o valor recebido.
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors())
        raise SchemaValidationFailed(f"fora do schema ({problems[:150]})") from None


class AIService:
    """Uma instância = uma execução (o teto por execução soma as chamadas dela)."""

    def __init__(self, *, providers=None, client=None):
        self.providers = providers if providers is not None else default_providers(client)
        self.run_spent = Decimal("0")

    def reset_run(self) -> None:
        self.run_spent = Decimal("0")

    # -- API pública ---------------------------------------------------------------------------
    def run(
        self,
        task: str | Task,
        input: LLMInput,  # noqa: A002 — nome da API documentada em llm-strategy.md
        schema: type[BaseModel] | None = None,
        *,
        strategies: list[str] | None = None,
    ) -> LLMResult:
        task = get_task(task) if isinstance(task, str) else task
        schema = schema or task.schema
        specs = strategies if strategies is not None else task.configured_strategies()
        system = task.system + "\n\n" + SCHEMA_RULES + json.dumps(schema.model_json_schema())
        prompt = task.prompt_for(input)
        reasons: list[str] = []

        for spec in specs:
            try:
                result = self._try(spec, task, schema, input, system, prompt)
            except LLMError as exc:
                reasons.append(f"{spec}: {exc}")
                continue
            if result is not None:
                return result
            reasons.append(f"{spec}: sem resultado")
        raise NoStrategyAvailable(f"{task.name}: " + ("; ".join(reasons) or "sem estratégias"))

    # -- internos ------------------------------------------------------------------------------
    def _try(self, spec, task, schema, input, system, prompt) -> LLMResult | None:
        provider_name, model = split_strategy(spec)
        if provider_name == RULES:
            return self._rules(task, schema, input)
        provider = self.providers.get(provider_name)
        if provider is None:
            raise LLMError(f"provedor desconhecido «{provider_name}»")  # erro de configuração
        if not provider.available():
            raise LLMError("sem chave/endereço configurado")
        if not provider.accepts(input.data_class):
            raise LLMError(f"dado «{input.data_class}» não pode ir a este provedor")
        pdf = input.pdf_bytes if provider.supports_pdf else None
        if input.pdf_bytes and not pdf and not prompt:
            raise LLMError("provedor sem suporte a PDF")

        key = cache.make_key(spec, task.prompt_version, system, prompt, pdf)
        hit = cache.lookup(key)
        if hit is not None:
            try:
                data = parse_response(hit.response_text, schema)
            except SchemaValidationFailed:
                pass  # schema mudou desde a gravação: refaz a chamada
            else:
                self._log(task, spec, provider, model, input, LLMCall.Status.CACHED, key)
                return self._result(data, spec, input, Decimal("0"), 0, 0, cached=True)

        estimate = cost_usd(
            provider_name,
            model,
            provider.billing,
            budget.estimate_input_tokens(prompt, system, pdf),
            task.max_output_tokens,
        )
        budget.check(provider.billing, estimate, self.run_spent)
        return self._call(task, schema, input, spec, provider, model, system, prompt, pdf, key)

    def _call(self, task, schema, input, spec, provider, model, system, prompt, pdf, key):
        current_prompt, last_error = prompt, "sem tentativa"
        for _attempt in range(MAX_ATTEMPTS):
            request = ProviderRequest(system, current_prompt, pdf, task.max_output_tokens)
            started = time.monotonic()
            try:
                response = provider.complete(model, request)
            except RateLimited as exc:
                self._log(
                    task, spec, provider, model, input, LLMCall.Status.RATE_LIMITED, key, error=exc
                )
                raise
            except ProviderError as exc:
                self._log(task, spec, provider, model, input, LLMCall.Status.ERROR, key, error=exc)
                raise
            elapsed = int((time.monotonic() - started) * 1000)
            cost = self._cost(provider, model, response)
            self.run_spent += cost
            try:
                data = parse_response(response.text, schema)
            except SchemaValidationFailed as exc:
                last_error = str(exc)
                self._log(
                    task, spec, provider, model, input, LLMCall.Status.INVALID, key,
                    response=response, cost=cost, elapsed=elapsed, error=exc,
                )  # fmt: skip
                current_prompt = f"{prompt}\n\nResposta recusada ({last_error}). Só o JSON."
                continue
            self._log(
                task, spec, provider, model, input, LLMCall.Status.OK, key,
                response=response, cost=cost, elapsed=elapsed, store=True,
            )  # fmt: skip
            return self._result(
                data, spec, input, cost, response.input_tokens, response.output_tokens
            )
        raise SchemaValidationFailed(last_error)

    def _rules(self, task, schema, input) -> LLMResult | None:
        if task.rules is None:
            raise LLMError("tarefa sem função de regras")
        raw = task.rules(input)
        if raw is None:
            return None
        try:
            data = schema.model_validate(raw)
        except ValidationError:
            raise SchemaValidationFailed("regras devolveram dado fora do schema") from None
        return self._result(data, RULES, input, Decimal("0"), 0, 0)

    @staticmethod
    def _cost(provider, model, response: ProviderResponse) -> Decimal:
        try:
            return cost_usd(
                provider.name,
                model,
                provider.billing,
                response.input_tokens,
                response.output_tokens,
            )
        except PricingError:
            raise BudgetExceeded("modelo pago sem preço na tabela") from None

    @staticmethod
    def _result(data, spec, input, cost, tokens_in, tokens_out, cached=False) -> LLMResult:
        unverified = verify_quotes(data, input.text) if input.text else []
        return LLMResult(
            data=data,
            strategy=spec,
            cost_usd=cost,
            cached=cached,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            unverified=unverified,
        )

    @staticmethod
    def _log(
        task, spec, provider, model, input, status, key, *, response=None, cost=Decimal("0"),
        elapsed=0, error=None, store=False,
    ):  # fmt: skip
        LLMCall.objects.create(
            task=task.name,
            strategy=spec,
            provider=provider.name,
            model=model,
            billing=provider.billing,
            data_class=str(input.data_class),
            status=status,
            prompt_version=task.prompt_version,
            cache_key=key,
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            cost_usd=cost,
            duration_ms=elapsed,
            error=str(error)[:200] if error else "",
            response_text=response.text if (store and response) else "",
        )
