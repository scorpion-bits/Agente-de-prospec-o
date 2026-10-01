"""Registro de cada chamada à camada de IA: custo, tokens e cache (E10).

Guarda **hash** da entrada (nunca o texto enviado). O texto da *resposta* fica em ``response_text``
só para servir de cache; é dado do banco, nunca vai para log (ADR-014).
"""

from django.db import models
from django.utils import timezone


class LLMCall(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "Concluída"
        CACHED = "cached", "Do cache (custo 0)"
        INVALID = "invalid", "Resposta fora do schema"
        RATE_LIMITED = "rate_limited", "Cota esgotada (429)"
        ERROR = "error", "Erro do provedor"

    created_at = models.DateTimeField("quando", default=timezone.now, db_index=True)
    task = models.CharField("tarefa", max_length=60, db_index=True)
    strategy = models.CharField("estratégia", max_length=120, help_text="provedor:modelo")
    provider = models.CharField("provedor", max_length=30)
    model = models.CharField("modelo", max_length=80)
    billing = models.CharField(
        "cobrança", max_length=10, help_text="free · credits (AI Pro) · money (dinheiro novo)"
    )
    data_class = models.CharField("classe do dado", max_length=10)
    status = models.CharField("situação", max_length=14, choices=Status.choices)
    prompt_version = models.CharField("versão do prompt", max_length=30, blank=True)
    cache_key = models.CharField("chave de cache", max_length=64, blank=True, db_index=True)
    input_tokens = models.PositiveIntegerField("tokens de entrada", default=0)
    output_tokens = models.PositiveIntegerField("tokens de saída", default=0)
    cost_usd = models.DecimalField("custo (US$)", max_digits=10, decimal_places=6, default=0)
    duration_ms = models.PositiveIntegerField("duração (ms)", default=0)
    error = models.CharField("erro", max_length=200, blank=True, help_text="Sem conteúdo.")
    response_text = models.TextField("resposta (cache)", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "chamada de IA"
        verbose_name_plural = "chamadas de IA"
        indexes = [models.Index(fields=["cache_key", "status"])]

    def __str__(self):
        return f"{self.task} · {self.strategy} · {self.status}"
