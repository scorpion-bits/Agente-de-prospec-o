"""Triagem humana (E14): grava a decisão com autor e data, uma linha por entidade (ADR-017).

«Não triada» é a entidade sem linha de `Triage` ou com a situação `new`.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import Triage

DECIDED = (
    Triage.Status.INTERESTING,
    Triage.Status.DISCARDED,
    Triage.Status.ACTING,
    Triage.Status.DONE,
)


@transaction.atomic
def triage_entities(entities, status, user, *, reason="", note=""):
    """Aplica `status` às entidades; devolve quantas foram alteradas.

    Descartar exige motivo. Voltar para `new` limpa a decisão. A nota existente só muda quando
    uma nova é informada.
    """
    if status == Triage.Status.DISCARDED and not reason:
        raise ValueError("Descartar exige um motivo.")
    if status != Triage.Status.DISCARDED:
        reason = ""
    entities = list(entities)
    for entity in entities:
        triage, _ = Triage.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(entity), object_id=entity.pk
        )
        triage.status = status
        triage.discard_reason = reason
        if note:
            triage.note = note
        if status == Triage.Status.NEW:
            triage.decided_by, triage.decided_at = None, None
        else:
            triage.decided_by = user if getattr(user, "pk", None) else None
            triage.decided_at = timezone.now()
        triage.save()
    return len(entities)
