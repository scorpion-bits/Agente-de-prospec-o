"""Cache por hash (llm-strategy.md, item 2): conteúdo e prompt iguais ⇒ não paga duas vezes.

A chave é ``sha256(estratégia + versão do prompt + instruções + entrada + PDF)``; a estratégia já
inclui o modelo. Fica guardada a **resposta** (``LLMCall.response_text``), nunca a entrada.
"""

from __future__ import annotations

import hashlib

from llm.models import LLMCall

SEP = "\x1f"


def make_key(
    strategy: str, prompt_version: str, system: str, prompt: str, pdf_bytes: bytes | None
) -> str:
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest() if pdf_bytes else ""
    material = SEP.join([strategy, prompt_version, system, prompt, pdf_hash])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def lookup(key: str) -> LLMCall | None:
    return LLMCall.objects.filter(cache_key=key, status=LLMCall.Status.OK).first()
