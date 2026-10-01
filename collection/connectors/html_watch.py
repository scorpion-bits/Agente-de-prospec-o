"""Conector genérico `html_watch`: monitora uma página de listagem e acha links novos (E07).

Uma página = uma `Source` (`kind=html_watch`), **sem código por página** (ADR-030). Cada link da
área de listagem que passa nos filtros vira `Opportunity(status=unknown)` candidata (título = texto
do link, trecho = bloco que o cerca), pronta para a extração (E11) ler a página do link. «Novo» é
o que o upsert cria: a chave é a URL canônica do link, então rodar de novo sem mudança dá 0 novos,
e o diff é o próprio banco (nada de hash de página para manter). Sem IA, sem navegador (página só
em JavaScript → erro).

    {"url": "https://exemplo.gov.br/editais",   # em branco = `Source.base_url`
     "selector": "main .lista, #conteudo",      # área da listagem (subconjunto de CSS, abaixo)
     "link_patterns": ["/edital", "chamamento"],  # regex na URL do link (qualquer uma); [] = todos
     "keywords": ["edital", "chamada"],         # palavra no texto/URL (minúsculas); [] = todas
     "exclude_patterns": ["/noticias/"],        # regex na URL: descarta
     "same_host": false,                        # true = só links do domínio da página
     "max_links": 200, "min_title_chars": 8,
     "opportunity": {"kind": "edital", "organizer_name": "FAPESP", "scope": "state",
                     "categories": ["innovation"], "uf": "SP", "municipality_name": ""}}

Seletor (subconjunto): lista separada por vírgula de sequências descendentes de `tag`, `.classe`,
`#id` (ex.: `main ul.editais`). Sem seletor — ou se ele não achar nada (layout mudou) — vale o
«conteúdo principal»: a página sem `nav`, `header`, `footer` e `aside`. Página sem nenhum link é
erro explícito («provável JavaScript»), nunca coleta vazia silenciosa. Datas e valores **não** são
lidos aqui (ADR-004): isso é da E11, que lê a página do edital. Cada afirmação vira
`Evidence(observed)`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.registry import register
from core.models import Opportunity
from core.services.canonical import canonical_url

DEFAULT_MAX_LINKS = 200
DEFAULT_MIN_TITLE_CHARS = 8
EXCERPT_MAX_CHARS = 300
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
    "source", "track", "wbr",
}  # fmt: skip
SKIPPED_TAGS = {"script", "style", "noscript", "template", "head"}
CHROME_TAGS = {"nav", "header", "footer", "aside"}
# Itens que o HTML tolerante fecha sozinho ao abrir o próximo irmão (`<li>` sem `</li>`).
SELF_CLOSING = {"li", "p", "tr", "td", "th", "dt", "dd", "option"}
BOUNDARY_TAGS = {"ul", "ol", "table", "tbody", "dl", "select", "body"}
BLOCK_TAGS = {"li", "p", "tr", "article", "dd", "dt", "h1", "h2", "h3", "h4", "h5", "h6"}
IGNORED_SCHEMES = ("mailto:", "tel:", "javascript:", "whatsapp:", "data:")
OPPORTUNITY_KEYS = {"kind", "organizer_name", "scope", "categories", "uf", "municipality_name"}


class HtmlWatchError(ValueError):
    pass


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def text(self) -> str:
        parts = [c if isinstance(c, str) else c.text() for c in self.children]
        return " ".join(" ".join(parts).split())

    def ancestors(self) -> Iterable[Node]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def walk(self) -> Iterable[Node]:
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()


class _TreeBuilder(HTMLParser):
    """Árvore tolerante a HTML malformado (sem dependência externa)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("[document]")
        self.stack = [self.root]
        self.skipped = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self.skipped += 1  # nenhum filho nosso: só conta até o fechamento
            return
        if self.skipped:
            return
        if tag in SELF_CLOSING:
            self._close_open_sibling(tag)
        node = Node(tag, {k: v or "" for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag not in SKIPPED_TAGS and not self.skipped:
            self.handle_starttag(tag, attrs)
            if tag not in VOID_TAGS:
                self.stack.pop()

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            self.skipped = max(self.skipped - 1, 0)
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if not self.skipped:
            self.stack[-1].children.append(data)

    def _close_open_sibling(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            current = self.stack[index].tag
            if current == tag:
                del self.stack[index:]
                return
            if current in BOUNDARY_TAGS:
                return


def parse_html(page_html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(page_html or "")
    builder.close()
    return builder.root


_COMPOUND = re.compile(r"^([a-zA-Z][\w-]*)?((?:[.#][\w-]+)*)$")


def _compound(token: str):
    match = _COMPOUND.match(token)
    if not match or not token:
        raise HtmlWatchError(f"Seletor não suportado: {token!r} (use tag, .classe e #id).")
    tag = (match.group(1) or "").lower()
    classes, ident = set(), ""
    for part in re.findall(r"[.#][\w-]+", match.group(2) or ""):
        if part[0] == ".":
            classes.add(part[1:])
        else:
            ident = part[1:]
    return tag, classes, ident


def _matches(node: Node, compound) -> bool:
    tag, classes, ident = compound
    return (
        (not tag or node.tag == tag)
        and classes <= node.classes()
        and (not ident or node.attrs.get("id") == ident)
    )


def select(root: Node, selector: str) -> list[Node]:
    """Nós que casam com o seletor (subconjunto: vírgulas e descendentes de tag/.classe/#id)."""
    found: list[Node] = []
    for group in (g.strip() for g in selector.split(",")):
        chain = [_compound(t) for t in group.split()]
        if not chain:
            continue
        for node in root.walk():
            if not _matches(node, chain[-1]) or node in found:
                continue
            pending = chain[:-1]
            for ancestor in node.ancestors():
                if pending and _matches(ancestor, pending[-1]):
                    pending.pop()
            if not pending:
                found.append(node)
    return found


def _in_chrome(node: Node, scope: Node) -> bool:
    for ancestor in node.ancestors():
        if ancestor is scope:
            return False
        if ancestor.tag in CHROME_TAGS:
            return True
    return False


def extract_links(page_html: str, *, base_url: str, selector: str = "") -> list[dict]:
    """Links `<a href>` da área de listagem → dicts (`url`, `title`, `excerpt`), sem repetir URL."""
    root = parse_html(page_html)
    scopes = select(root, selector) if selector.strip() else []
    fallback = bool(selector.strip()) and not scopes
    anchors: list[Node] = []
    if scopes:
        for scope in scopes:
            anchors += [n for n in scope.walk() if n.tag == "a" and n not in anchors]
    else:
        anchors = [n for n in root.walk() if n.tag == "a" and not _in_chrome(n, root)]

    links, seen = [], set()
    for anchor in anchors:
        href = anchor.attrs.get("href", "").strip()
        if not href or href.startswith("#") or href.lower().startswith(IGNORED_SCHEMES):
            continue
        url = urljoin(base_url, href).split("#")[0]
        if urlsplit(url).scheme not in ("http", "https") or url in seen:
            continue
        seen.add(url)
        title = anchor.text() or " ".join(
            (anchor.attrs.get("title") or anchor.attrs.get("aria-label") or "").split()
        )
        block = next((a for a in anchor.ancestors() if a.tag in BLOCK_TAGS), anchor.parent)
        excerpt = (block or anchor).text()[:EXCERPT_MAX_CHARS]
        links.append({"url": url, "title": title, "excerpt": excerpt, "fallback": fallback})
    return links


def _regexes(values, name):
    try:
        return [re.compile(v, re.I) for v in values or []]
    except re.error as exc:
        raise HtmlWatchError(f"Regex inválida em `{name}`: {exc}") from exc


@register(kind="html_watch")
class HtmlWatchConnector:
    kind = "html_watch"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        config = source.config or {}
        self.url = str(config.get("url") or source.base_url or "").strip()
        self.selector = str(config.get("selector") or "")
        self.patterns = _regexes(config.get("link_patterns"), "link_patterns")
        self.excludes = _regexes(config.get("exclude_patterns"), "exclude_patterns")
        self.keywords = tuple(str(k).lower() for k in config.get("keywords") or [])
        self.same_host = bool(config.get("same_host", False))
        self.max_links = int(config.get("max_links", DEFAULT_MAX_LINKS))
        self.min_title = int(config.get("min_title_chars", DEFAULT_MIN_TITLE_CHARS))
        defaults = dict(config.get("opportunity") or {})
        unknown = set(defaults) - OPPORTUNITY_KEYS
        if unknown:
            raise HtmlWatchError(f"Chaves desconhecidas em `opportunity`: {sorted(unknown)}.")
        self.defaults = {"kind": Opportunity.Kind.EDITAL, **defaults}

    def accepts(self, link: dict, page_url: str) -> bool:
        url, title = link["url"], link["title"]
        if len(title) < self.min_title:
            return False
        if self.same_host and urlsplit(url).hostname != urlsplit(page_url).hostname:
            return False
        if self.patterns and not any(p.search(url) for p in self.patterns):
            return False
        if any(p.search(url) for p in self.excludes):
            return False
        haystack = f"{title} {url}".lower()
        return not self.keywords or any(k in haystack for k in self.keywords)

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        if not self.url:
            raise HtmlWatchError("Fonte sem `config.url` (nem `base_url`).")
        result = ctx.fetcher.fetch(self.url, source=ctx.source)
        links = extract_links(result.text, base_url=result.url, selector=self.selector)
        if not links:
            raise HtmlWatchError(
                "Resposta inesperada: nenhum link na página (layout mudou ou a página exige "
                "JavaScript, que não executamos)."
            )
        accepted = [link for link in links if self.accepts(link, result.url)]
        for position, link in enumerate(accepted[: self.max_links], 1):
            yield RawItem(
                data={**link, "page_url": result.url},
                source_url=link["url"],
                raw_document=result.document,
                label=f"link {position}",
            )

    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        title = " ".join(str(data.get("title", "")).split())
        url = str(data.get("url", "")).strip()
        if not title or not url or not canonical_url(url):
            return None
        fields = {
            **self.defaults,
            "official_url": url,
            "status": Opportunity.Status.UNKNOWN,
        }
        page = data.get("page_url") or self.url
        evidence = [
            EvidenceDraft(
                field="title",
                value=title,
                source_url=url,
                source_name=self.source.name,
                excerpt=str(data.get("excerpt", "")),
            ),
            EvidenceDraft(
                field="official_url",
                value=url,
                source_url=page,
                source_name=self.source.name,
                excerpt=title,
            ),
        ]
        return OpportunityCandidate(title=title[:300], fields=fields, evidence=evidence)
