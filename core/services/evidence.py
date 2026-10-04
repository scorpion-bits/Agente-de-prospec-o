"""Registro de evidências (ADR-004): toda afirmação relevante tem origem rastreável.

`record_evidence` é a porta de entrada para conectores, extratores e regras. Aplica as regras do
ADR-004 e é **idempotente**: registrar de novo a mesma afirmação (mesma entidade, campo, tipo,
método, fonte e valor) só renova `retrieved_at`, em vez de duplicar a linha a cada coleta.
Valor diferente na mesma fonte gera uma nova linha: o histórico de mudanças é preservado.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.utils import timezone

from core.models import ENTITY_MODELS, Evidence

EXCERPT_MAX_CHARS = 500
# Trechos muito curtos ("SP", "sim") aparecem em qualquer texto: encontrá-los não prova nada.
MIN_VERIFIABLE_CHARS = 8

_TYPOGRAPHIC = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


class EvidenceError(ValueError):
    """Pedido de evidência que viola uma regra do ADR-004."""


def _squash(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHIC)
    return " ".join(text.split()).casefold()


def quote_in_text(quote: str, text: str) -> bool:
    """A citação está no texto? Ignora espaços, caixa e aspas/travessões tipográficos."""
    needle = _squash(quote)
    return len(needle) >= MIN_VERIFIABLE_CHARS and needle in _squash(text)


def _content_type_of(entity: Model) -> ContentType:
    if entity.pk is None:
        raise EvidenceError("Salve a entidade antes de registrar evidências sobre ela.")
    content_type = ContentType.objects.get_for_model(entity)
    if content_type.app_label != "core" or content_type.model not in ENTITY_MODELS:
        raise EvidenceError(
            f"Evidência não se aplica a {content_type.model!r} "
            f"(permitidos: {', '.join(ENTITY_MODELS)})."
        )
    return content_type


def record_evidence(
    entity: Model,
    field: str,
    value: Any,
    *,
    kind: str,
    method: str,
    source_url: str = "",
    source_name: str = "",
    excerpt: str = "",
    retrieved_at: datetime | None = None,
    confidence: float | None = None,
    verified: bool = False,
    source_text: str | None = None,
    raw_document=None,
    known: list[Evidence] | None = None,
    pending: list[Evidence] | None = None,
) -> Evidence:
    """Registra (ou renova) a afirmação "`entity.field` vale `value`" com sua origem.

    - `kind`: `observed` (lido na fonte; exige `source_url`), `inferred` (deduzido por regra ou
      IA) ou `manual` (informado por humano; exige `method="human"`).
    - `method`: `connector:<fonte>`, `regex:<nome>`, `rule:<nome>`, `llm:<modelo>@<prompt>`
      ou `human`.
    - `excerpt`: trecho **literal** da fonte; espaços são normalizados e o que passar de 500
      caracteres é cortado (um prefixo continua sendo literal).
    - `source_text`: texto de onde veio o trecho. Se informado, `verified` é **calculado**
      (a citação está no texto?) e o argumento `verified` é ignorado.
    - `raw_document`: `collection.RawDocument` de onde o dado veio (opcional).
    - Saída de LLM (`llm:`) só vale como `observed` se a citação for encontrada em
      `source_text`; caso contrário é registrada como `inferred` (ADR-004), sem perder o dado.

    - `known` e `pending` (opcionais, para gravar muitas evidências da mesma entidade de uma vez):
      `known` são as evidências que ela já tem (evita uma consulta por afirmação); com `pending`,
      as novas não são salvas, só acrescentadas à lista para o chamador gravar com `bulk_create`.

    Levanta `EvidenceError` se o pedido violar uma regra; nunca grava dado inválido.
    """
    content_type = _content_type_of(entity)
    excerpt = " ".join((excerpt or "").split())[:EXCERPT_MAX_CHARS]

    if source_text is not None and excerpt:
        verified = quote_in_text(excerpt, source_text)
    if method.startswith("llm:"):
        if source_text is None or not excerpt:
            verified = False
        if kind == Evidence.Kind.OBSERVED and source_url and not verified:
            kind = Evidence.Kind.INFERRED

    candidate = Evidence(
        content_type=content_type,
        object_id=entity.pk,
        field=field,
        value=value,
        kind=kind,
        source_url=source_url or "",
        source_name=source_name or "",
        retrieved_at=retrieved_at or timezone.now(),
        excerpt=excerpt,
        method=method,
        confidence=confidence,
        verified=bool(verified),
        raw_document=raw_document,
    )
    try:
        # `content_type` acabou de vir do ORM e as restrições do banco repetem `clean()` e os
        # validadores do campo: pular essas duas consultas por evidência acelera coletas grandes.
        candidate.entity_checked = known is not None  # o chamador acabou de ler a entidade
        candidate.full_clean(exclude=["content_type"], validate_constraints=False)
    except ValidationError as exc:
        details = "; ".join(f"{name}: {' '.join(msgs)}" for name, msgs in exc.message_dict.items())
        raise EvidenceError(details) from exc

    if known is None:
        existing = Evidence.objects.filter(
            content_type=content_type,
            object_id=entity.pk,
            field=field,
            kind=candidate.kind,
            method=method,
            source_url=candidate.source_url,
            value=value,
        ).first()
    else:
        stored_value = json.loads(json.dumps(value, cls=DjangoJSONEncoder))
        existing = next(
            (
                row
                for row in known
                if (row.field, row.kind, row.method, row.source_url, row.value)
                == (field, candidate.kind, method, candidate.source_url, stored_value)
            ),
            None,
        )
    if existing is None:
        if pending is None:
            candidate.save()
        else:
            pending.append(candidate)
            if known is not None:
                known.append(candidate)
        return candidate

    if existing.pk is None:  # repetida na mesma rodada, ainda na fila de `pending`
        return existing

    existing.retrieved_at = candidate.retrieved_at
    update_fields = ["retrieved_at"]
    if candidate.excerpt:  # trecho e verificação andam juntos
        existing.excerpt, existing.verified = candidate.excerpt, candidate.verified
        update_fields += ["excerpt", "verified"]
    if candidate.source_name:
        existing.source_name = candidate.source_name
        update_fields.append("source_name")
    if candidate.confidence is not None:
        existing.confidence = candidate.confidence
        update_fields.append("confidence")
    if raw_document is not None:
        existing.raw_document = raw_document
        update_fields.append("raw_document")
    existing.save(update_fields=update_fields)
    return existing
