"""Sinais de necessidade web (E26): site da organização → sinais determinísticos com evidência.

A análise é do `extraction/web_signals.py` (pura). Aqui ficam a rede (`PoliteFetcher`: robots,
rate limit, cache) e os efeitos: `Evidence` por sinal (campo `web.signal.<código>`) e a marca de
«checado» (`web.signals_checked`), que dispensa migration e vence em `FRESH_DAYS`. Sem IA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from collection.fetcher import (
    FetchBlocked,
    FetchError,
    PageBudgetExceeded,
    PoliteFetcher,
    RobotsDisallowed,
    UnsupportedContent,
)
from core.models import Evidence, Organization
from core.services.evidence import record_evidence
from core.services.suppression import SuppressionIndex
from extraction.web_signals import WebSignal, analyze_home, is_social_only
from extraction.website import html_text

OBSERVED_METHOD = "regex:web_signals"
INFERRED_METHOD = "rule:web_signals"
SOURCE_NAME = "site oficial"
CHECKED_FIELD = "web.signals_checked"
SIGNAL_PREFIX = "web.signal."
FRESH_DAYS = 30  # política de frescor: site lido há menos que isso não é relido (sem --refresh)


@dataclass
class SignalScan:
    status: str  # ok | skipped | suppressed | unreadable
    signals: list[WebSignal] = field(default_factory=list)
    url: str = ""
    page_text: str = ""


def pending_organizations(*, refresh: bool = False, kind: str | None = None):
    """Organizações com site, ou sem site já «não encontrado» na E18, ainda sem checagem fresca."""
    from django.db.models import Q

    queryset = Organization.objects.filter(
        ~Q(website="") | Q(website="", website_status=Organization.WebsiteStatus.NOT_FOUND)
    )
    if kind:
        queryset = queryset.filter(kind=kind)
    if not refresh:
        ctype = ContentType.objects.get_for_model(Organization)
        fresh = Evidence.objects.filter(
            content_type=ctype,
            field=CHECKED_FIELD,
            retrieved_at__gte=timezone.now() - timedelta(days=FRESH_DAYS),
        ).values("object_id")
        queryset = queryset.exclude(pk__in=fresh)
    return queryset.order_by("pk")


def scan_organization(
    organization: Organization, fetcher: PoliteFetcher, index: SuppressionIndex
) -> SignalScan:
    """Lê **só a página inicial** e devolve os sinais, sem gravar nada.

    Levanta `PageBudgetExceeded` se o teto de páginas da execução acabar. Robots/bloqueio/conteúdo
    não textual → `skipped` (nenhuma conclusão); falha de rede ou HTTP → sinal `site_down` inferido.
    """
    if index.organization_blocked(organization):
        return SignalScan("suppressed")
    if not organization.website:
        return SignalScan("ok", [WebSignal("no_site", True, False, "", 0.6)])
    if is_social_only(organization.website):
        return SignalScan(
            "ok", [WebSignal("social_only", True, True, organization.website)], organization.website
        )
    try:
        home = fetcher.fetch(organization.website)
    except PageBudgetExceeded:
        raise
    except (RobotsDisallowed, FetchBlocked, UnsupportedContent):
        return SignalScan("skipped")
    except FetchError as exc:
        return SignalScan("unreadable", [WebSignal("site_down", True, False, str(exc)[:200], 0.5)])
    signals = analyze_home(home.text, home.url, current_year=timezone.now().year)
    _, visible = html_text(home.text)
    return SignalScan("ok", signals, home.url, f"{home.text}\n{visible}")


def apply_scan(organization: Organization, scan: SignalScan) -> int:
    """Grava os sinais como evidência e marca a organização como checada. Devolve quantos."""
    for signal in scan.signals:
        observed = signal.observed and (scan.url or organization.website)
        record_evidence(
            organization,
            SIGNAL_PREFIX + signal.code,
            signal.value,
            kind="observed" if observed else "inferred",
            method=OBSERVED_METHOD if observed else INFERRED_METHOD,
            source_url=(scan.url or organization.website) if observed else "",
            source_name=SOURCE_NAME,
            excerpt=signal.excerpt,
            source_text=scan.page_text if scan.page_text and signal.excerpt else None,
            confidence=signal.confidence,
        )
    mark_checked(organization)
    return len(scan.signals)


def mark_checked(organization: Organization):
    record_evidence(
        organization,
        CHECKED_FIELD,
        True,
        kind="inferred",
        method=INFERRED_METHOD,
        source_name=SOURCE_NAME,
    )
