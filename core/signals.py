"""Mantém os campos de relacionamento da organização em dia (ADR-012)."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.models import Interaction
from core.services.relationship import refresh_relationship


@receiver(pre_save, sender=Interaction, dispatch_uid="core.interaction_remember_org")
def remember_previous_organization(sender, instance, **kwargs):
    """Se a interação mudar de organização, a antiga também precisa ser recalculada."""
    instance._previous_organization_id = None
    if instance.pk:
        instance._previous_organization_id = (
            sender.objects.filter(pk=instance.pk).values_list("organization_id", flat=True).first()
        )


@receiver(post_save, sender=Interaction, dispatch_uid="core.interaction_saved")
def interaction_saved(sender, instance, **kwargs):
    refresh_relationship(instance.organization_id)
    previous = getattr(instance, "_previous_organization_id", None)
    if previous and previous != instance.organization_id:
        refresh_relationship(previous)


@receiver(post_delete, sender=Interaction, dispatch_uid="core.interaction_deleted")
def interaction_deleted(sender, instance, **kwargs):
    refresh_relationship(instance.organization_id)
