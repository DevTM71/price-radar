"""Testes de parse_product contra HTML real salvo em fixture (sem rede)."""

from datetime import timezone
from decimal import Decimal
from pathlib import Path

import pytest

from price_radar.scraper import ParseError, parse_product

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def html_produto() -> str:
    return (FIXTURES / "a_light_in_the_attic.html").read_text(encoding="utf-8")


def test_extrai_titulo(html_produto: str) -> None:
    snapshot = parse_product(html_produto, slug="a-light-in-the-attic")
    assert snapshot.title == "A Light in the Attic"


def test_extrai_preco_como_decimal(html_produto: str) -> None:
    snapshot = parse_product(html_produto)
    assert snapshot.price == Decimal("51.77")
    assert isinstance(snapshot.price, Decimal)


def test_extrai_disponibilidade(html_produto: str) -> None:
    snapshot = parse_product(html_produto)
    assert snapshot.available is True


def test_propaga_slug_e_marca_horario_utc(html_produto: str) -> None:
    snapshot = parse_product(html_produto, slug="a-light-in-the-attic")
    assert snapshot.slug == "a-light-in-the-attic"
    assert snapshot.scraped_at.tzinfo == timezone.utc


def test_html_vazio_gera_erro_claro() -> None:
    with pytest.raises(ParseError, match="HTML vazio"):
        parse_product("")


def test_html_sem_produto_gera_erro_claro() -> None:
    html = "<html><body><p>Página qualquer, sem produto.</p></body></html>"
    with pytest.raises(ParseError, match="página de produto"):
        parse_product(html)
