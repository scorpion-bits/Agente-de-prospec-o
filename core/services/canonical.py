"""Chave canônica de oportunidades (`Opportunity.canonical_key`) — regras de
`docs/architecture/connectors.md`, seção "Deduplicação".

Usada pelo cadastro manual (admin) já na E03; os conectores (E04+) podem definir a própria chave
(ex. `devpost:12345`) e só caem aqui quando não há identificador melhor.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.utils import timezone
from django.utils.text import slugify

# Parâmetros que só rastreiam a origem do clique. Os demais ficam: muitos sites identificam o
# conteúdo por querystring (`?id=123`), e descartá-los juntaria páginas diferentes.
_TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src"}


def _is_tracking(name: str) -> bool:
    name = name.lower()
    return name.startswith("utm_") or name in _TRACKING_PARAMS


def canonical_url(url: str) -> str:
    """URL sem esquema, `www.`, fragmento, barra final e parâmetros de rastreio.

    O resultado serve de chave, não de link (por isso não leva `https://`).
    """
    text = (url or "").strip()
    if "//" not in text:
        text = "//" + text
    parts = urlsplit(text)
    host = (parts.hostname or "").removeprefix("www.")
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    query = urlencode(
        sorted(
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)
        )
    )
    return netloc + parts.path.rstrip("/") + (f"?{query}" if query else "")


def opportunity_canonical_key(
    *,
    official_url: str = "",
    organizer_name: str = "",
    title: str = "",
    deadline_at: datetime | None = None,
) -> str:
    """URL canônica quando há URL estável; senão `slug(organizador)|slug(título)|data-limite`."""
    if official_url.strip():
        return "url:" + canonical_url(official_url)
    deadline = "sem-prazo"
    if deadline_at:
        local = timezone.localtime(deadline_at) if timezone.is_aware(deadline_at) else deadline_at
        deadline = local.date().isoformat()
    return "slug:" + "|".join([slugify(organizer_name), slugify(title), deadline])
