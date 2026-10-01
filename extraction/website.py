"""Validação determinística de candidatos a site oficial (E18) — sem IA, sem rede.

Entrada: resultados de busca + o texto da página de cada candidato (baixado por quem chama).
Saída: `found` (exatamente um domínio confere), `ambiguous` (conferência parcial, vários
domínios ou página não verificável) ou `not_found`. **Errar para `ambiguous`, nunca para
`found`**: um site errado vira prospecção errada (docs/plan/fase-3-leads-institucionais.md, E18).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from collection.search.base import SearchResult
from core.services.normalize import name_key, normalize_domain

# Redes sociais, diretórios, buscadores e agregadores: nunca são o site oficial (sufixo de domínio).
BLOCKED_DOMAINS = frozenset(
    {
        # redes sociais e mensageiros
        "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
        "tiktok.com", "pinterest.com", "threads.net", "wa.me", "whatsapp.com", "t.me",
        "linktr.ee", "kwai.com",
        # buscadores, mapas e enciclopédias
        "google.com", "google.com.br", "bing.com", "maps.app.goo.gl", "waze.com",
        "wikipedia.org", "wikimedia.org", "wikidata.org",
        # diretórios de escolas, empresas e telefones
        "escolas.com.br", "escolasbrasil.com.br", "escolas.net.br", "qedu.org.br",
        "melhoresescolas.com.br", "mundoeducacao.uol.com.br", "guiamais.com.br",
        "telelistas.net", "apontador.com.br", "yelp.com", "tripadvisor.com.br",
        "tripadvisor.com", "foursquare.com", "cylex.com.br", "listamais.com.br",
        "cnpj.biz", "cnpja.com", "casadosdados.com.br", "econodata.com.br", "cnpj.info",
        "empresascnpj.com", "consultasocio.com", "cnpjs.rocks",
        # reclamações, vagas e classificados
        "reclameaqui.com.br", "glassdoor.com.br", "indeed.com", "olx.com.br",
        "mercadolivre.com.br", "infojobs.com.br", "catho.com.br",
        # hospedagem de documentos e jurisprudência
        "scribd.com", "slideshare.net", "issuu.com", "jusbrasil.com.br",
    }
)  # fmt: skip

STOPWORDS = frozenset(
    {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "na", "no", "para", "com"}
)
# Palavras que qualquer escola/instituição tem: não distinguem uma da outra.
GENERIC_TOKENS = frozenset(
    {
        "escola", "colegio", "centro", "educacional", "educacao", "instituto", "municipal",
        "estadual", "federal", "particular", "emef", "emei", "emeief", "eefm", "eef", "ceu",
        "creche", "unidade", "prof", "profa", "professor", "professora", "dr", "dra", "sao",
        "santa", "santo", "ensino", "curso", "cursos", "faculdade", "universidade",
    }
)  # fmt: skip

HEAD_CHARS = 3000  # os tokens do nome têm de aparecer no começo da página (título/cabeçalho)
EXCERPT_RADIUS = 120
MAX_CANDIDATES = 3


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)
        elif not self._skip:
            self.parts.append(data)


def html_text(html: str) -> tuple[str, str]:
    """(título, texto visível) de um HTML, com espaços normalizados."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return " ".join(" ".join(parser.title).split()), " ".join(" ".join(parser.parts).split())


def is_blocked_domain(url: str) -> bool:
    domain = normalize_domain(url)
    return not domain or any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


def name_tokens(name: str) -> list[str]:
    """Tokens que distinguem a organização (sem artigos nem palavras genéricas como «escola»)."""
    tokens = [t for t in name_key(name).split() if t not in STOPWORDS and len(t) > 1]
    distinctive = [t for t in tokens if t not in GENERIC_TOKENS]
    return distinctive or tokens


def required_tokens(count: int) -> int:
    return count if count <= 2 else max(2, math.ceil(0.75 * count))


def canonical_site_url(url: str) -> str:
    """Raiz do site quando o resultado é a página inicial; senão a URL sem query."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if not segments or (len(segments) == 1 and segments[0].lower().startswith(("index", "home"))):
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


@dataclass
class CandidateVerdict:
    url: str
    verdict: str  # match | weak | reject
    reason: str
    excerpt: str = ""
    page_text: str = ""

    @property
    def domain(self) -> str:
        return normalize_domain(self.url)


def evaluate_candidate(
    result: SearchResult, *, name: str, municipality: str, page_html: str | None
) -> CandidateVerdict:
    """`match`: nome e município conferem **na página**; `weak`: só nos metadados da busca ou só
    o nome; `reject`: domínio bloqueado ou nada confere."""
    url = result.url
    if urlsplit(url).scheme not in ("http", "https") or is_blocked_domain(url):
        return CandidateVerdict(url, "reject", "domínio bloqueado (rede social, diretório…)")
    tokens = name_tokens(name)
    if not tokens:
        return CandidateVerdict(url, "reject", "nome sem tokens distintivos")
    need = required_tokens(len(tokens))
    city = f" {name_key(municipality)} "

    if page_html is None:  # página não verificável: só título/trecho da busca → no máximo «fraco»
        text = f"{result.title} {result.snippet}"
        words = set(name_key(text).split())
        if sum(t in words for t in tokens) >= need and city in f" {name_key(text)} ":
            return CandidateVerdict(
                url, "weak", "conferiu só no resultado da busca (página não lida)"
            )
        return CandidateVerdict(url, "reject", "página não lida e o resultado não confere")

    title, body = html_text(page_html)
    full = f"{title} {body}".strip()
    head_words = set(name_key(f"{title} {body[:HEAD_CHARS]}").split())
    hits = sum(t in head_words for t in tokens)
    if hits < need:
        return CandidateVerdict(
            url, "reject", f"nome não aparece no começo da página ({hits}/{len(tokens)})"
        )
    if city not in f" {name_key(full)} ":
        return CandidateVerdict(
            url, "weak", "o nome confere, mas o município não aparece na página"
        )
    return CandidateVerdict(
        url, "match", "nome e município conferem na página", _excerpt(full, tokens), full
    )


def _excerpt(text: str, tokens: list[str]) -> str:
    """Trecho literal da página em volta da primeira ocorrência de um token do nome."""
    lowered = text.casefold()
    positions = [i for t in tokens if (i := lowered.find(t)) >= 0]
    start = max(min(positions, default=0) - EXCERPT_RADIUS // 2, 0)
    return text[start : start + EXCERPT_RADIUS * 2].strip()


@dataclass
class Decision:
    status: str  # found | ambiguous | not_found
    url: str = ""
    chosen: CandidateVerdict | None = None
    candidates: list[CandidateVerdict] | None = None
    reason: str = ""


def decide(verdicts: list[CandidateVerdict]) -> Decision:
    """`found` só com **um** domínio em `match` e nenhum outro domínio plausível."""
    matches = {v.domain: v for v in verdicts if v.verdict == "match"}
    weak = [v for v in verdicts if v.verdict == "weak"]
    if len(matches) == 1 and not weak:
        chosen = next(iter(matches.values()))
        return Decision("found", canonical_site_url(chosen.url), chosen, verdicts, chosen.reason)
    if matches or weak:
        plausible = list(matches.values()) + weak
        why = "mais de um domínio plausível" if len(plausible) > 1 else plausible[0].reason
        return Decision("ambiguous", "", None, plausible, why)
    return Decision("not_found", "", None, verdicts, "nenhum resultado confere")
