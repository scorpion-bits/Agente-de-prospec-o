"""Camada de IA (E10): único ponto de contato com modelos (ADR-003, ADR-011).

Uso::

    from llm.router import AIService
    from llm.types import DataClass, LLMInput
    result = AIService().run("minha_tarefa", LLMInput(DataClass.PUBLIC, text=...))

Um ``AIService()`` por execução (o teto por execução soma as chamadas dele). Nenhum outro módulo
importa SDK ou chama API de modelo.
"""
