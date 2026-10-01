from django import forms
from django.contrib.postgres.fields import ArrayField


class ChoiceArrayField(ArrayField):
    """`ArrayField` de vocabulário controlado: no admin vira uma seleção múltipla.

    As escolhas vêm do `base_field` (um `CharField` com `choices`). Sem isto, o admin mostraria
    um campo de texto "a,b,c" e o usuário teria de saber os códigos de cor.
    """

    def formfield(self, **kwargs):
        defaults = {"form_class": forms.MultipleChoiceField, "choices": self.base_field.choices}
        defaults.update(kwargs)
        # Pula `ArrayField.formfield` (devolveria um `SimpleArrayField`) e usa o de `Field`.
        return super(ArrayField, self).formfield(**defaults)
