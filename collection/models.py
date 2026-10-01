"""Execuções de coleta e documentos brutos (cache e prova) — ver docs/architecture/connectors.md.

Sem binários (ADR-010): guardamos URL, hash, ETag e o **texto** comprimido, com retenção.
"""

import gzip
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Source


def default_expiry():
    return timezone.now() + timedelta(days=settings.RAW_DOCUMENT_RETENTION_DAYS)


class CollectionRun(models.Model):
    """Uma execução de um conector sobre uma fonte."""

    class Status(models.TextChoices):
        RUNNING = "running", "Em andamento"
        OK = "ok", "Concluída"
        PARTIAL = "partial", "Parcial (houve falhas)"
        ERROR = "error", "Falhou"

    source = models.ForeignKey(
        Source, verbose_name="fonte", on_delete=models.CASCADE, related_name="runs"
    )
    started_at = models.DateTimeField("início", default=timezone.now)
    finished_at = models.DateTimeField("fim", null=True, blank=True)
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.RUNNING
    )
    dry_run = models.BooleanField(
        "simulação", default=False, help_text="Nada foi gravado além deste registro."
    )
    item_limit = models.PositiveIntegerField("limite de itens", null=True, blank=True)
    items_seen = models.PositiveIntegerField("itens vistos", default=0)
    items_new = models.PositiveIntegerField("novos", default=0)
    items_updated = models.PositiveIntegerField("atualizados", default=0)
    items_failed = models.PositiveIntegerField("com falha", default=0)
    error_log = models.TextField(
        "erros",
        blank=True,
        help_text="Só o tipo e a mensagem do erro, sem o conteúdo dos itens (logs públicos).",
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "execução de coleta"
        verbose_name_plural = "execuções de coleta"

    def __str__(self):
        mode = " (simulação)" if self.dry_run else ""
        return f"{self.source.slug} · {self.started_at:%d/%m/%Y %H:%M}{mode}"


class RawDocument(models.Model):
    """Página ou arquivo de texto baixado: cache condicional e prova de onde veio o dado."""

    source = models.ForeignKey(
        Source,
        verbose_name="fonte",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="raw_documents",
    )
    url = models.URLField("URL", max_length=1000, unique=True)
    status_code = models.PositiveSmallIntegerField("status HTTP", default=200)
    content_type = models.CharField("tipo de conteúdo", max_length=120, blank=True)
    etag = models.CharField("ETag", max_length=255, blank=True)
    last_modified = models.CharField("Last-Modified", max_length=120, blank=True)
    content_hash = models.CharField("hash do conteúdo (SHA-256)", max_length=64, blank=True)
    text_gz = models.BinaryField("texto comprimido", default=bytes, blank=True, editable=False)
    size_bytes = models.PositiveIntegerField("tamanho do texto (bytes)", default=0)
    fetched_at = models.DateTimeField("baixado em", default=timezone.now)
    expires_at = models.DateTimeField(
        "expira em",
        null=True,
        blank=True,
        default=default_expiry,
        help_text="Depois disso `purge_raw_documents` apaga o texto e mantém URL e hash.",
    )

    class Meta:
        ordering = ["-fetched_at"]
        verbose_name = "documento bruto"
        verbose_name_plural = "documentos brutos"

    def __str__(self):
        return self.url

    @property
    def has_text(self):
        return bool(self.text_gz)

    @property
    def text(self):
        return gzip.decompress(bytes(self.text_gz)).decode("utf-8") if self.text_gz else ""

    def set_text(self, text):
        encoded = text.encode("utf-8")
        self.text_gz = gzip.compress(encoded)
        self.size_bytes = len(encoded)

    def purge_text(self):
        """Apaga o texto e mantém URL, hash e ETag (as evidências continuam apontando para cá)."""
        self.text_gz = b""
        self.size_bytes = 0
        self.etag = self.last_modified = ""  # sem texto, não há como responder a um 304


class SearchQuery(models.Model):
    """Resultado de uma busca web, guardado **para sempre**: nenhuma consulta é paga duas vezes."""

    provider = models.CharField("provedor", max_length=20)
    query_key = models.CharField(
        "consulta normalizada", max_length=300, help_text="Sem acentos, caixa e pontuação."
    )
    query = models.CharField("consulta", max_length=300)
    results = models.JSONField("resultados", default=list)
    searched_at = models.DateTimeField("feita em", default=timezone.now)

    class Meta:
        ordering = ["-searched_at"]
        verbose_name = "busca web"
        verbose_name_plural = "buscas web"
        constraints = [
            models.UniqueConstraint(fields=["provider", "query_key"], name="uniq_search_query")
        ]

    def __str__(self):
        return f"{self.provider}: {self.query}"
