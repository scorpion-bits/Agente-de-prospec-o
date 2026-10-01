"""Apaga o texto dos documentos brutos vencidos (retenção — ADR-010).

URL, hash e ETag ficam: as evidências continuam apontando para o documento e dá para saber que a
página foi vista.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from collection.models import RawDocument


class Command(BaseCommand):
    help = "Apaga o texto dos documentos brutos cujo prazo de retenção venceu."

    def handle(self, *args, **options):
        expired = RawDocument.objects.filter(expires_at__lte=timezone.now()).exclude(text_gz=b"")
        count = 0
        for document in expired.iterator():
            document.purge_text()
            document.save(update_fields=["text_gz", "size_bytes", "etag", "last_modified"])
            count += 1
        self.stdout.write(f"Documentos brutos: texto apagado em {count}.")
