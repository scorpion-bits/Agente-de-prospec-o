"""Extração determinística de contatos públicos institucionais (E19) — sem IA, sem rede.

Entrada: o HTML de uma página do site da organização. Saída: contatos encontrados, cada um com o
trecho literal da página (ADR-004). Fontes: `mailto:`, `tel:`, `wa.me`, texto visível (e-mail e
telefone com DDD), JSON-LD do schema.org, links de redes da organização e formulário de contato.

Regras de privacidade (docs/research/legal-and-compliance.md): só e-mails do domínio da própria
organização (ou de webmail, com confiança menor); e-mail com cara de nome de pessoa fica
`is_personal=True`; nunca se gera nem se "adivinha" endereço; e-mail ofuscado é perda aceita.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from core.services.normalize import normalize_domain, normalize_phone
from extraction.website import html_text

MAX_PAGES = 5
EXCERPT_RADIUS = 80

# Ordem de prioridade das páginas a visitar além da inicial (primeiro casamento ganha).
PAGE_HINTS = (
    ("contato", "contatos", "fale-conosco", "faleconosco", "fale conosco", "contact"),
    ("atendimento", "secretaria", "matricula", "matriculas", "admissao"),
    ("sobre", "quem-somos", "quem somos", "institucional", "a-escola", "a escola", "unidade"),
)
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".mp3", ".mp4", ".avi", ".css", ".js", ".xml", ".ico",
)  # fmt: skip

WEBMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "yahoo.com", "live.com",
        "icloud.com", "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br",
    }
)  # fmt: skip
# Endereços que aparecem em sites sem serem contato da organização (modelos, ferramentas, imagens).
IGNORED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "domain.com",
        "email.com",
        "sentry.io",
        "wixpress.com",
        "wix.com",
    }
)
IGNORED_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css")

# Partes de endereço que indicam caixa institucional (contém, não só igual).
INSTITUTIONAL_HINTS = (
    "contato", "secretaria", "atendimento", "comercial", "direcao", "diretoria", "coordenacao",
    "coordenador", "financeiro", "matricula", "admissao", "faleconosco", "fale", "info", "sac",
    "recepcao", "administrativo", "administracao", "comunicacao", "marketing", "cultura",
    "relacionamento", "pedagogico", "pedagogica", "escola", "colegio", "unidade", "geral",
    "projetos", "eventos", "imprensa", "rh", "contact", "suporte", "vendas",
)  # fmt: skip

EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# Telefone com DDD em texto: exige parênteses, +55 ou separador entre DDD e número (evita CEP/CNPJ).
PHONE_RE = re.compile(
    r"(?<![\d/.,-])(?:\+?55[\s.-]*)?(?:\((\d{2})\)\s*|(\d{2})[\s.-]+)(9?\d{4})[\s.-]?(\d{4})(?![\d-])"
)
WHATSAPP_HOSTS = ("wa.me", "api.whatsapp.com", "web.whatsapp.com", "whatsapp.com")
CONTACT_PATH_RE = re.compile(r"contato|contact|fale[-_ ]?conosco", re.I)

SOCIAL_KINDS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "linkedin.com": "linkedin_company",
    "youtube.com": "youtube",
}
# Primeiro segmento do caminho que **não** é um perfil (compartilhar, postagem, login…).
NOT_A_PROFILE = frozenset(
    {
        "p", "reel", "reels", "explore", "accounts", "stories", "tv", "share", "sharer",
        "sharer.php", "share.php", "dialog", "tr", "plugins", "login", "watch", "embed", "results",
        "hashtag", "intent", "photo", "photo.php", "events", "groups", "policies", "privacy",
        "help", "legal", "about", "watch_popup", "v", "shorts", "playlist", "feed",
    }
)  # fmt: skip


@dataclass(frozen=True)
class FoundContact:
    kind: str
    value: str  # já normalizado (e-mail minúsculo, telefone E.164, URL limpa)
    excerpt: str  # trecho literal da página (pode ser o `href` quando o link não tem texto)
    label: str = ""
    is_personal: bool = False
    confidence: float = 0.9


@dataclass
class PageResult:
    url: str
    title: str
    text: str  # texto visível (para verificar os trechos)
    contacts: list[FoundContact] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)  # (href absoluto, texto) internos


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []  # (href, texto)
        self.json_ld: list[str] = []
        self.has_form_fields = False
        self._in_form = False
        self._href: str | None = None
        self._anchor_text: list[str] = []
        self._ld: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = {k: (v or "") for k, v in attrs}
        if tag == "a" and attrs.get("href"):
            self._finish_anchor()
            self._href, self._anchor_text = attrs["href"].strip(), []
        elif tag == "script" and "ld+json" in attrs.get("type", "").lower():
            self._ld = []
        elif tag == "form":
            self._in_form = True
        elif self._in_form and tag in ("textarea", "input", "select"):
            if tag != "input" or attrs.get("type", "text").lower() in ("text", "email", "tel"):
                self.has_form_fields = True

    def handle_endtag(self, tag):
        if tag == "a":
            self._finish_anchor()
        elif tag == "script" and self._ld is not None:
            self.json_ld.append("".join(self._ld))
            self._ld = None
        elif tag == "form":
            self._in_form = False

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        elif self._href is not None:
            self._anchor_text.append(data)

    def _finish_anchor(self):
        if self._href is not None:
            self.anchors.append((self._href, " ".join(" ".join(self._anchor_text).split())))
        self._href = None

    def close(self):
        super().close()
        self._finish_anchor()


# --- e-mail ---------------------------------------------------------------------------------
def classify_email(local_part: str) -> bool:
    """`True` se o endereço parece de uma pessoa (nome.sobrenome); caixas de função são `False`."""
    local = re.sub(r"\d+", "", local_part.lower())
    if any(hint in local for hint in INSTITUTIONAL_HINTS):
        return False
    return len([p for p in re.split(r"[._-]+", local) if len(p) > 1]) >= 2


def email_belongs(email: str, site_domain: str) -> tuple[bool, float]:
    """(aceito?, confiança): domínio da organização (ou subdomínio/pai) vale mais que webmail."""
    domain = normalize_domain(email)
    if not domain or domain in IGNORED_EMAIL_DOMAINS or email.endswith(IGNORED_EMAIL_SUFFIXES):
        return False, 0.0
    if site_domain and (
        domain == site_domain
        or domain.endswith(f".{site_domain}")
        or site_domain.endswith(f".{domain}")
    ):
        return True, 0.9
    if domain in WEBMAIL_DOMAINS:
        return True, 0.6
    return False, 0.0  # domínio alheio: agência, hospedagem, parceiro


# --- telefone -------------------------------------------------------------------------------
def valid_br_phone(value: str) -> str:
    """E.164 de um telefone brasileiro plausível (DDD 11–99; fixo 2–5; celular 9), senão ''."""
    phone = normalize_phone(value)
    digits = phone.removeprefix("+55")
    if not phone.startswith("+55") or len(digits) not in (10, 11):
        return ""
    ddd, number = digits[:2], digits[2:]
    if not "11" <= ddd <= "99" or ddd[1] == "0":
        return ""
    if len(number) == 9 and number[0] == "9":
        return phone
    if len(number) == 8 and number[0] in "2345":
        return phone
    return ""


def _snippet(text: str, needle: str) -> str:
    index = text.find(needle)
    if index < 0:
        return ""
    return text[max(0, index - EXCERPT_RADIUS) : index + len(needle) + EXCERPT_RADIUS].strip()


# --- redes sociais --------------------------------------------------------------------------
def social_profile(url: str) -> tuple[str, str] | None:
    """(kind, URL limpa) se `url` é o perfil/página de uma organização numa rede; senão `None`."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower().removeprefix("www.")
    kind = next((k for d, k in SOCIAL_KINDS.items() if host == d or host.endswith(f".{d}")), None)
    if kind is None:
        return None
    segments = [unquote(s) for s in parts.path.split("/") if s]
    if not segments:
        return None
    first = segments[0].lower()
    if kind == "linkedin_company":
        if first not in ("company", "school") or len(segments) < 2:
            return None
        return kind, f"https://www.linkedin.com/{first}/{segments[1]}"
    if kind == "youtube":
        if first.startswith("@"):
            return kind, f"https://www.youtube.com/{segments[0]}"
        if first in ("channel", "c", "user") and len(segments) >= 2:
            return kind, f"https://www.youtube.com/{first}/{segments[1]}"
        return None
    if kind == "facebook" and first == "profile.php":
        ident = parse_qs(parts.query).get("id", [""])[0]
        return (kind, f"https://www.facebook.com/profile.php?id={ident}") if ident else None
    if first in NOT_A_PROFILE or first.endswith(".php"):
        return None
    if kind == "facebook" and first == "pages" and len(segments) >= 3:
        return kind, "https://www.facebook.com/" + "/".join(segments[:3])
    host_name = "instagram.com" if kind == "instagram" else "facebook.com"
    return kind, f"https://www.{host_name}/{segments[0]}"


def whatsapp_number(url: str) -> str:
    """Telefone E.164 de um link `wa.me/55…` ou `…/send?phone=55…`; vazio se não houver número."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not any(host == h or host.endswith(f".{h}") for h in WHATSAPP_HOSTS):
        return ""
    phone = parse_qs(parts.query).get("phone", [""])[0]
    if not phone and host == "wa.me":
        phone = parts.path.strip("/")
    return valid_br_phone(phone) if phone.isdigit() else ""


# --- JSON-LD --------------------------------------------------------------------------------
def _walk_ld(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_ld(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_ld(item)


def _ld_values(blocks: list[str]) -> tuple[list[str], list[str], list[str]]:
    emails, phones, links = [], [], []
    for block in blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in _walk_ld(data):
            for key, bucket in (("email", emails), ("telephone", phones)):
                value = node.get(key)
                if isinstance(value, str):
                    bucket.append(value)
            same_as = node.get("sameAs")
            for link in [same_as] if isinstance(same_as, str) else (same_as or []):
                if isinstance(link, str):
                    links.append(link)
    return emails, phones, links


# --- página ---------------------------------------------------------------------------------
def same_site(url: str, site_domain: str) -> bool:
    domain = normalize_domain(url)
    return bool(domain) and (domain == site_domain or domain.endswith(f".{site_domain}"))


def parse_page(html: str, page_url: str, site_domain: str) -> PageResult:
    """Contatos e links internos de uma página. Puro: o mesmo HTML dá sempre o mesmo resultado."""
    title, text = html_text(html)
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    result = PageResult(page_url, title, text)
    seen: set[tuple[str, str]] = set()

    def add(kind, value, excerpt, *, label="", personal=False, confidence=0.9):
        if not value or (kind, value) in seen:
            return
        seen.add((kind, value))
        result.contacts.append(
            FoundContact(
                kind, value, " ".join(excerpt.split()) or value, label, personal, confidence
            )
        )

    def add_email(raw, excerpt):
        email = raw.strip().strip(".,;:<>()[]").lower()
        ok, confidence = email_belongs(email, site_domain)
        if ok:
            add(
                "email",
                email,
                excerpt,
                personal=classify_email(email.split("@")[0]),
                confidence=confidence,
            )

    def add_phone(kind, raw, excerpt):
        add(kind, valid_br_phone(raw), excerpt)

    def add_social(url, excerpt):
        if profile := social_profile(url):
            add(profile[0], profile[1], excerpt, confidence=0.7)

    for href, anchor_text in parser.anchors:
        lowered = href.lower()
        if lowered.startswith("mailto:"):
            add_email(unquote(href[7:].split("?")[0]), anchor_text or href)
        elif lowered.startswith("tel:"):
            add_phone("phone", unquote(href[4:]), anchor_text or href)
        elif lowered.startswith(("http", "//", "whatsapp:")) or "wa.me" in lowered:
            absolute = urljoin(page_url, href) if not lowered.startswith("whatsapp:") else href
            whatsapp = whatsapp_number(absolute) or whatsapp_number(
                absolute.replace("whatsapp://", "https://api.whatsapp.com/")
            )
            if whatsapp:
                add("whatsapp", whatsapp, anchor_text or href)
            elif social_profile(absolute):
                add_social(absolute, anchor_text or href)
            elif same_site(absolute, site_domain):
                result.links.append((absolute.split("#")[0], anchor_text))
        elif not lowered.startswith(("#", "javascript:", "data:", "sms:")):
            result.links.append((urljoin(page_url, href).split("#")[0], anchor_text))

    for match in EMAIL_RE.finditer(text):
        add_email(match.group(0), _snippet(text, match.group(0)) or match.group(0))
    for match in PHONE_RE.finditer(text):
        ddd = match.group(1) or match.group(2)
        add_phone("phone", f"{ddd}{match.group(3)}{match.group(4)}", _snippet(text, match.group(0)))

    ld_emails, ld_phones, ld_links = _ld_values(parser.json_ld)
    for value in ld_emails:
        add_email(value.removeprefix("mailto:"), value)
    for value in ld_phones:
        add_phone("phone", value, value)
    for link in ld_links:
        add_social(link, link)

    if parser.has_form_fields and (
        CONTACT_PATH_RE.search(urlsplit(page_url).path) or "contato" in title.lower()
    ):
        add("contact_form", page_url, title or page_url, label="Formulário de contato")
    return result


def pick_pages(home_url: str, links: list[tuple[str, str]], site_domain: str) -> list[str]:
    """Até `MAX_PAGES - 1` páginas internas além da inicial, as de contato primeiro."""
    ranked: dict[str, int] = {}
    for url, text in links:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not same_site(url, site_domain):
            continue
        if parts.path.lower().endswith(SKIP_EXTENSIONS):
            continue
        clean = parts._replace(query="", fragment="").geturl()
        if clean.rstrip("/") == home_url.rstrip("/"):
            continue
        haystack = f"{parts.path} {text}".lower().replace("_", "-")
        for rank, hints in enumerate(PAGE_HINTS):
            if any(hint in haystack for hint in hints):
                ranked[clean] = min(rank, ranked.get(clean, rank))
                break
    ordered = sorted(ranked, key=lambda u: (ranked[u], len(u)))
    return ordered[: MAX_PAGES - 1]


def drop_ambiguous_socials(contacts: list[FoundContact]) -> tuple[list[FoundContact], int]:
    """Mais de um perfil da mesma rede no site (organização + agência, ou páginas distintas):
    não dá para saber qual é o oficial, então nenhum é gravado. Devolve (restantes, descartadas)."""
    by_kind: dict[str, set[str]] = {}
    for contact in contacts:
        if contact.kind in SOCIAL_KINDS.values():
            by_kind.setdefault(contact.kind, set()).add(contact.value)
    ambiguous = {kind for kind, values in by_kind.items() if len(values) > 1}
    kept = [c for c in contacts if c.kind not in ambiguous]
    return kept, len(ambiguous)
