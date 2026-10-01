"""Relacionamento derivado das interações (ADR-012).

`relationship_status`, `last_interaction_at` e `next_action_at` da `Organization` nunca são
digitados: saem das `Interaction`s e são recalculados a cada interação salva ou apagada
(`core.signals`).

Regras do status, em ordem:

1. `do_not_contact` é decisão humana e **nunca** é sobrescrito (reverter exige edição consciente).
2. `client`: alguma interação `won`, ou `course_delivered` que não terminou negativa.
3. `lost`: a interação **mais recente** terminou `lost` ou `negative`.
4. Caso contrário vale o maior estágio já alcançado: `proposal_sent` > `in_conversation`
   (reunião, ligação, visita ou resposta que tiveram retorno) > `contacted` (qualquer outra).
5. Sem interações: `never_contacted`.

`last_interaction_at` é a data mais recente **conhecida**; `next_action_at` vem só da interação
mais recente (o próximo passo vive nela): registrar uma nova interação sem próxima ação limpa o
lembrete anterior.
"""

from core.models import Interaction, Organization

_Status = Organization.RelationshipStatus
_Kind = Interaction.Kind
_Outcome = Interaction.Outcome

_CONVERSATION_KINDS = {_Kind.MEETING, _Kind.CALL, _Kind.VISIT, _Kind.RESPONSE_RECEIVED}
_BAD_OUTCOMES = {_Outcome.LOST, _Outcome.NEGATIVE}
_RANK = {_Status.CONTACTED: 1, _Status.IN_CONVERSATION: 2, _Status.PROPOSAL_SENT: 3}


def _stage(interaction):
    if interaction.kind == _Kind.PROPOSAL_SENT:
        return _Status.PROPOSAL_SENT
    if interaction.kind in _CONVERSATION_KINDS and interaction.outcome != _Outcome.NO_RESPONSE:
        return _Status.IN_CONVERSATION
    return _Status.CONTACTED


def _is_client(interaction):
    if interaction.outcome == _Outcome.WON:
        return True
    return interaction.kind == _Kind.COURSE_DELIVERED and interaction.outcome not in _BAD_OUTCOMES


def derive_relationship(interactions):
    """`(status, última data, próxima ação em)` para uma lista de interações (mais recente 1ª)."""
    if not interactions:
        return _Status.NEVER_CONTACTED, None, None
    latest = interactions[0]
    dates = [i.occurred_at for i in interactions if i.occurred_at]
    last = max(dates) if dates else None
    if any(_is_client(i) for i in interactions):
        status = _Status.CLIENT
    elif latest.outcome in _BAD_OUTCOMES:
        status = _Status.LOST
    else:
        status = max((_stage(i) for i in interactions), key=_RANK.__getitem__)
    return status, last, latest.next_action_at


def refresh_relationship(organization_id):
    """Recalcula e grava os campos derivados da organização. Idempotente."""
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        return None
    # Data conhecida mais recente primeiro; sem data (pendente) vem antes: é o registro mais novo.
    interactions = list(Interaction.objects.filter(organization=organization))
    status, last, next_at = derive_relationship(interactions)
    if organization.relationship_status == _Status.DO_NOT_CONTACT:
        status = _Status.DO_NOT_CONTACT
    Organization.objects.filter(pk=organization.pk).update(
        relationship_status=status, last_interaction_at=last, next_action_at=next_at
    )
    return status
