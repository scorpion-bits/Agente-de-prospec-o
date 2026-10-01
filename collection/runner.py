"""Runner genérico: `fetch → normalize → dedupe → upsert → Evidence → CollectionRun`.

- Erro em um item **não** interrompe os demais (cada item roda em um savepoint).
- Erro no conector termina só aquela fonte; `--all` segue para as outras.
- Fonte que bloqueia (robots.txt ou 401/403) é **desabilitada** e registrada para revisão humana:
  não se contorna bloqueio (connectors.md, regra 7).
- `dry_run`: o conector roda de verdade, mas nada além do registro da execução é gravado.
"""

from __future__ import annotations

from contextlib import nullcontext

from django.db import transaction
from django.utils import timezone

from collection import registry, upsert
from collection.base import RunContext
from collection.fetcher import FetchBlocked, PoliteFetcher, RobotsDisallowed
from collection.models import CollectionRun
from core.models import Source

DEFAULT_MAX_PAGES = 20
DATASET_MAX_BYTES = 200 * 1024 * 1024
MAX_LOGGED_ERRORS = 50
MAX_ERROR_CHARS = 200


def runnable_problem(source: Source, *, dry_run: bool = False) -> str | None:
    """Por que a fonte não pode rodar agora (`None` = pode)."""
    if not source.enabled and not dry_run:
        return "fonte desabilitada (habilite no admin depois de conferir termos e robots.txt)."
    if registry.needs_network(source) and not source.robots_ok:
        return "termos de uso e robots.txt ainda não conferidos (marque `coleta permitida`)."
    return None


def build_fetcher(source: Source, **overrides) -> PoliteFetcher:
    """Fetcher configurado pela fonte (`config`: min_interval_seconds, max_pages, max_bytes)."""
    config = source.config or {}
    kwargs = {"max_requests": int(config.get("max_pages", DEFAULT_MAX_PAGES))}
    if "min_interval_seconds" in config:
        kwargs["min_interval"] = float(config["min_interval_seconds"])
    if "max_bytes" in config:
        kwargs["max_bytes"] = int(config["max_bytes"])
    elif source.kind == Source.Kind.DATASET:
        kwargs["max_bytes"] = DATASET_MAX_BYTES
    return PoliteFetcher(**{**kwargs, **overrides})


def _short(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARS]


def run_source(
    source: Source, *, fetcher=None, limit=None, dry_run=False, connector=None
) -> CollectionRun:
    run = CollectionRun.objects.create(source=source, dry_run=dry_run, item_limit=limit)
    errors: list[str] = []
    blocked = False
    seen = new = updated = failed = 0
    own_fetcher = fetcher is None and registry.needs_network(source)
    if own_fetcher:
        fetcher = build_fetcher(source)

    try:
        with transaction.atomic() if dry_run else nullcontext():
            try:
                connector = connector or registry.for_source(source)
                ctx = RunContext(source=source, fetcher=fetcher, limit=limit, dry_run=dry_run)
                for item in connector.fetch(ctx):
                    if limit is not None and seen >= limit:
                        break
                    seen += 1
                    try:
                        with transaction.atomic():
                            candidate = connector.normalize(item)
                            if candidate is None:
                                continue
                            _, outcome = upsert.upsert(
                                candidate, source=source, raw_document=item.raw_document
                            )
                        new += outcome == upsert.CREATED
                        updated += outcome == upsert.UPDATED
                    except Exception as exc:  # um item ruim não derruba a fonte
                        failed += 1
                        if len(errors) < MAX_LOGGED_ERRORS:
                            errors.append(f"{item.label or f'item {seen}'}: {_short(exc)}")
            except (RobotsDisallowed, FetchBlocked) as exc:
                blocked = True
                errors.append(f"BLOQUEADA: {_short(exc)}")
            except Exception as exc:  # erro do conector: encerra só esta fonte
                errors.append(f"conector: {_short(exc)}")
            if dry_run:
                transaction.set_rollback(True)
    finally:
        if own_fetcher:
            fetcher.close()

    if blocked and not dry_run:
        Source.objects.filter(pk=source.pk).update(enabled=False)
        errors.append("Fonte desabilitada para revisão humana (não contornamos bloqueios).")
    connector_failed = any(e.startswith(("conector:", "BLOQUEADA")) for e in errors)
    if connector_failed and not seen:
        status = CollectionRun.Status.ERROR
    elif failed or connector_failed:
        status = CollectionRun.Status.PARTIAL
    else:
        status = CollectionRun.Status.OK
    run.status = status
    run.finished_at = timezone.now()
    run.items_seen, run.items_new, run.items_updated, run.items_failed = seen, new, updated, failed
    run.error_log = "\n".join(errors)
    run.save()
    return run
