from datetime import UTC, datetime

import pytest

from core.services.canonical import canonical_url, opportunity_canonical_key
from core.services.normalize import (
    is_valid_cnpj,
    name_key,
    normalize_cnpj,
    normalize_contact_value,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_suppression_value,
)
from tests.conftest import VALID_CNPJ, mask_cnpj

# Exemplo oficial do CNPJ alfanumérico da Receita Federal (12.ABC.345/01DE-35).
ALPHANUMERIC_CNPJ = "12ABC34501DE35"


class TestCnpj:
    def test_valid_numeric_cnpj(self):
        assert is_valid_cnpj(VALID_CNPJ)

    def test_accepts_the_mask_and_lowercase(self):
        assert is_valid_cnpj(mask_cnpj(VALID_CNPJ))
        assert normalize_cnpj(" 12.abc.345/01de-35 ") == ALPHANUMERIC_CNPJ

    def test_valid_alphanumeric_cnpj(self):
        assert is_valid_cnpj(ALPHANUMERIC_CNPJ)

    @pytest.mark.parametrize(
        "value",
        [
            "11222333000182",  # dígito verificador errado
            "12ABC34501DE36",  # alfanumérico com dígito errado
            "00000000000000",  # repetido
            "1122233300018",  # curto
            "112223330001811",  # longo
            "1122233300018A",  # letra nas posições verificadoras
            "",
            None,
        ],
    )
    def test_invalid_cnpj(self, value):
        assert not is_valid_cnpj(value)


class TestContacts:
    def test_email(self):
        assert normalize_email(" mailto:Contato@Escola.ORG ") == "contato@escola.org"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("(16) 0000-0000", "+551600000000"),
            ("16 90000-0000", "+5516900000000"),
            ("+55 (16) 90000-0000", "+5516900000000"),
            ("0800 123 4567", "08001234567"),  # sem +55 indevido
            ("0000-0000", "00000000"),  # sem DDD: não dá para completar
            ("", ""),
            (None, ""),
        ],
    )
    def test_phone_is_e164_when_recognizable(self, raw, expected):
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("https://www.Escola-X.com.br/contato?a=1", "escola-x.com.br"),
            ("Contato@Escola.ORG", "escola.org"),
            ("escola.org/path", "escola.org"),
            ("http://sub.escola.org:8080/", "sub.escola.org"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_domain(self, raw, expected):
        assert normalize_domain(raw) == expected

    def test_contact_value_depends_on_kind(self):
        assert normalize_contact_value("email", " A@B.org ") == "a@b.org"
        assert normalize_contact_value("whatsapp", "(16) 90000-0000") == "+5516900000000"
        assert normalize_contact_value("website", " https://Escola.org/Contato ") == (
            "https://Escola.org/Contato"
        )  # URL: só tira espaços (o caminho é sensível a maiúsculas)


class TestNames:
    def test_name_key_ignores_accents_case_and_punctuation(self):
        assert name_key("  SESC — Ribeirão Preto ") == "sesc ribeirao preto"
        assert name_key(None) == ""

    def test_suppression_value_by_kind(self):
        assert normalize_suppression_value("email", "X@Y.org") == "x@y.org"
        assert normalize_suppression_value("domain", "https://www.y.org/a") == "y.org"
        assert normalize_suppression_value("phone", "(16) 0000-0000") == "+551600000000"
        # Organização: CNPJ válido vale pelo CNPJ; qualquer outro texto, pelo nome comparável.
        assert normalize_suppression_value("organization", mask_cnpj(VALID_CNPJ)) == VALID_CNPJ
        assert normalize_suppression_value("organization", "Escola Exemplo!") == "escola exemplo"

    def test_unknown_suppression_kind_is_an_error(self):
        with pytest.raises(ValueError):
            normalize_suppression_value("fax", "x")


class TestCanonicalUrl:
    def test_drops_scheme_www_fragment_and_trailing_slash(self):
        assert canonical_url("HTTPS://www.Example.org/Jam/#inscricoes") == "example.org/Jam"

    def test_drops_tracking_but_keeps_content_params_sorted(self):
        url = "https://example.org/e?utm_source=x&id=7&fbclid=abc&a=1&UTM_Medium=m"
        assert canonical_url(url) == "example.org/e?a=1&id=7"

    def test_keeps_non_default_port_only(self):
        assert canonical_url("http://example.org:80/x") == "example.org/x"
        assert canonical_url("https://example.org:8443/x") == "example.org:8443/x"

    def test_same_page_written_differently_has_one_key(self):
        a = canonical_url("https://example.org/jam/?utm_campaign=z")
        b = canonical_url("http://www.example.org/jam")
        assert a == b


class TestOpportunityCanonicalKey:
    def test_url_wins(self):
        key = opportunity_canonical_key(
            official_url="https://www.example.org/jam/?utm_source=x", title="Qualquer"
        )
        assert key == "url:example.org/jam"

    def test_without_url_uses_organizer_title_and_local_deadline(self):
        # 02:30 UTC de 16/11 ainda é 23:30 de 15/11 em São Paulo: vale a data local.
        key = opportunity_canonical_key(
            organizer_name="Prefeitura de Araraquara",
            title="Edital de Cultura 2026 — Ação!",
            deadline_at=datetime(2026, 11, 16, 2, 30, tzinfo=UTC),
        )
        assert key == "slug:prefeitura-de-araraquara|edital-de-cultura-2026-acao|2026-11-15"

    def test_without_deadline(self):
        key = opportunity_canonical_key(organizer_name="X", title="Y")
        assert key == "slug:x|y|sem-prazo"

    def test_naive_datetime_is_accepted(self):
        key = opportunity_canonical_key(title="Y", deadline_at=datetime(2026, 11, 15, 23, 59))
        assert key.endswith("|2026-11-15")
