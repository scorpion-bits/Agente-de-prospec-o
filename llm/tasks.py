"""Registro de tarefas: a aplicação conhece **tarefas**, não fornecedores (llm-strategy.md).

Cada tarefa declara schema, prompt (versionado) e uma lista ordenada de estratégias. Trocar
``Claude → Gemini``, ``API → local`` ou ``LLM → regras`` é mudar a lista, sem tocar em código:
``LLM_TASK_STRATEGIES`` (settings/.env, JSON) sobrescreve o padrão de cada tarefa.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from django.conf import settings
from pydantic import BaseModel

from llm.types import LLMError, LLMInput


@dataclass
class Task:
    name: str
    schema: type[BaseModel]
    system: str  # instruções fixas (cacheáveis); o schema é anexado pelo router
    strategies: list[str]  # ordem de tentativa; "rules" = função Python sem LLM
    prompt_version: str = "v1"  # mudou o prompt → mude aqui: invalida o cache
    rules: Callable[[LLMInput], dict | None] | None = None  # None = «não sei», passa à seguinte
    build_prompt: Callable[[LLMInput], str] | None = None
    max_input_chars: int = 48_000  # ≈ 12k tokens: limite duro por documento
    max_output_tokens: int = 1500
    extra: dict = field(default_factory=dict)

    def configured_strategies(self) -> list[str]:
        override = settings.LLM_TASK_STRATEGIES.get(self.name)
        return list(override if override is not None else self.strategies)

    def prompt_for(self, data: LLMInput) -> str:
        text = self.build_prompt(data) if self.build_prompt else data.text
        return text[: self.max_input_chars]


_REGISTRY: dict[str, Task] = {}


def register_task(task: Task) -> Task:
    _REGISTRY[task.name] = task
    return task


def get_task(name: str) -> Task:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise LLMError(f"tarefa desconhecida «{name}»") from None


def task_names() -> list[str]:
    return sorted(_REGISTRY)


class SmokePing(BaseModel):
    ok: bool
    echo: str


# Tarefa de fumaça (`manage.py llm_smoke`): confere chave, rede, schema e custo com ~100 tokens.
SMOKE = register_task(
    Task(
        name="smoke_ping",
        schema=SmokePing,
        system="Verificador de conexão: responda ok=true e repita em echo o texto recebido.",
        strategies=["gemini-free:gemini-3.1-flash-lite"],
    )
)
