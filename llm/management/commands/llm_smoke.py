"""Chamada real de fumaça (E10): confere chave, rede, schema e custo com ~100 tokens.

Roda a tarefa ``smoke_ping`` com texto público fixo. Saída só com estratégia, tokens e custo.
"""

from django.core.management.base import BaseCommand, CommandError

from llm.router import AIService
from llm.tasks import SMOKE
from llm.types import DataClass, LLMError, LLMInput


class Command(BaseCommand):
    help = "Uma chamada real e barata à IA, registrada em LLMCall (precisa da chave no .env)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strategy",
            help="provedor:modelo (padrão: o da tarefa, gemini-free:gemini-3.1-flash-lite).",
        )

    def handle(self, *args, strategy, **options):
        service = AIService()
        try:
            result = service.run(
                SMOKE,
                LLMInput(DataClass.PUBLIC, text="radar"),
                strategies=[strategy] if strategy else None,
            )
        except LLMError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"OK · {result.strategy} · {result.input_tokens}+{result.output_tokens} tokens · "
            f"US$ {result.cost_usd:.6f} · cache={result.cached} · ok={result.data.ok}"
        )
