"""Sinais de necessidade web (E26) — determinísticos, sem IA, sem rede.

Entrada: a página inicial já baixada (HTML + URL final). Saída: sinais de que o site é antigo ou
inexistente, **fatores de Fit, não verdade** (site simples pode ser adequado). Regra do ADR-004:
só vira sinal o que a página mostra; texto curto demais (site montado por JavaScript) não permite
concluir nada sobre `viewport`, então fica sem sinal (`unknown`), nunca `False` por ausência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

from core.services.normalize import normalize_domain
from extraction.website import html_text

# Redes e agregadores de links: ter só isso como «site» é o sinal mais forte de falta de site.
SOCIAL_ONLY_DOMAINS = frozenset(
    {
        "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
        "tiktok.com", "linktr.ee", "wa.me", "whatsapp.com", "kwai.com", "threads.net",
    }
)  # fmt: skip

OLD_COPYRIGHT_YEARS = 4  # © de 4 anos atrás ou mais (ex.: 2022 em 2026) conta como antigo
MIN_TEXT_FOR_LAYOUT = 200  # abaixo disso a página é «casca» de JS: não dá para julgar viewport
EXCERPT_RADIUS = 60

COPYRIGHT_RE = re.compile(
    r"(?:©|&copy;|\(c\)|copyright)\s*(?:\d{4}\s*[-–/]\s*)?(\d{4})\b", re.IGNORECASE
)
FLASH_RE = re.compile(
    r"""<(?:embed|object|param)\b[^>]*(?:\.swf\b|x-shockwave-flash|shockwave)""", re.IGNORECASE
)
JQUERY_RE = re.compile(
    r"""jquery[-.]?(?:min[-.])?v?(?P<ver>[12])\.\d+(?:\.\d+)?(?:\.min)?\.js""", re.IGNORECASE
)
JQUERY_VER_RE = re.compile(r"""jquery[^"'<>]*?[?&]ver=(?P<ver>[12])\.\d+""", re.IGNORECASE)
FRAMESET_RE = re.compile(r"<frameset\b", re.IGNORECASE)


@dataclass(frozen=True)
class WebSignal:
    # no_site | social_only | site_down | no_https | no_viewport | old_copyright | obsolete_tech
    code: str
    value: object
    observed: bool  # True: a página/URL mostra o fato; False: inferido de ausência
    excerpt: str = ""
    confidence: float = 0.9


class _HeadFacts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_viewport = False
        self.has_head = False

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.has_head = True
        elif tag == "meta" and (dict(attrs).get("name") or "").lower() == "viewport":
            self.has_viewport = True


def is_social_only(url: str) -> bool:
    domain = normalize_domain(url)
    return bool(domain) and any(
        domain == d or domain.endswith("." + d) for d in SOCIAL_ONLY_DOMAINS
    )


def _around(text: str, start: int, end: int) -> str:
    return " ".join(text[max(start - EXCERPT_RADIUS, 0) : end + EXCERPT_RADIUS].split())


def analyze_home(html: str, final_url: str, *, current_year: int) -> list[WebSignal]:
    """Sinais de uma página inicial baixada. `final_url` é a URL depois dos redirecionamentos."""
    signals: list[WebSignal] = []
    if urlsplit(final_url).scheme == "http":
        signals.append(WebSignal("no_https", True, True))

    _, visible = html_text(html)
    facts = _HeadFacts()
    facts.feed(html)
    facts.close()
    if facts.has_head and len(visible) >= MIN_TEXT_FOR_LAYOUT and not facts.has_viewport:
        signals.append(
            WebSignal("no_viewport", True, False, "meta viewport ausente na página inicial", 0.7)
        )

    best: tuple[int, re.Match] | None = None
    for match in COPYRIGHT_RE.finditer(visible):
        year = int(match.group(1))
        if 1990 <= year <= current_year and (best is None or year > best[0]):
            best = (year, match)
    if best and current_year - best[0] >= OLD_COPYRIGHT_YEARS:
        year, match = best
        signals.append(
            WebSignal("old_copyright", year, True, _around(visible, match.start(), match.end()))
        )

    tech: list[tuple[str, str]] = []
    if m := FLASH_RE.search(html):
        tech.append(("flash", m.group(0)))
    if m := FRAMESET_RE.search(html):
        tech.append(("frameset", m.group(0)))
    if m := JQUERY_RE.search(html) or JQUERY_VER_RE.search(html):
        tech.append((f"jquery_{m.group('ver')}", m.group(0)))
    if tech:
        signals.append(
            WebSignal("obsolete_tech", [name for name, _ in tech], True, tech[0][1][:200])
        )
    return signals
