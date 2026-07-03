"""Testes de PriceHistory: round-trip, últimos preços e detecção de mudança."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from price_radar.scraper import ProductSnapshot
from price_radar.storage import PriceHistory


def _snap(
    slug: str,
    price: str,
    dia: int,
    title: str | None = None,
    available: bool = True,
) -> ProductSnapshot:
    return ProductSnapshot(
        slug=slug,
        title=title or f"Livro {slug}",
        price=Decimal(price),
        available=available,
        scraped_at=datetime(2026, 7, dia, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def history():
    with PriceHistory(":memory:") as h:
        yield h


def test_save_e_history_redondo(history: PriceHistory) -> None:
    original = _snap("dune", "51.77", dia=1, available=False)
    history.save_snapshots([original])

    recuperados = history.history("dune")

    assert recuperados == [original]
    assert isinstance(recuperados[0].price, Decimal)
    assert recuperados[0].scraped_at.tzinfo is not None


def test_history_em_ordem_cronologica(history: PriceHistory) -> None:
    history.save_snapshots([_snap("dune", "12.00", dia=3), _snap("dune", "10.00", dia=1)])

    precos = [s.price for s in history.history("dune")]

    assert precos == [Decimal("10.00"), Decimal("12.00")]


def test_latest_prices_pega_o_mais_recente_de_cada_slug(history: PriceHistory) -> None:
    history.save_snapshots(
        [
            _snap("dune", "10.00", dia=1),
            _snap("dune", "12.50", dia=2),
            _snap("emma", "8.00", dia=1),
        ]
    )

    latest = {s.slug: s.price for s in history.latest_prices()}

    assert latest == {"dune": Decimal("12.50"), "emma": Decimal("8.00")}


def test_price_changes_detecta_mudanca(history: PriceHistory) -> None:
    history.save_snapshots([_snap("dune", "10.00", dia=1), _snap("dune", "12.50", dia=2)])

    (change,) = history.price_changes()

    assert change.slug == "dune"
    assert change.old_price == Decimal("10.00")
    assert change.new_price == Decimal("12.50")
    assert change.delta == Decimal("2.50")


def test_price_changes_ignora_preco_estavel(history: PriceHistory) -> None:
    history.save_snapshots([_snap("dune", "10.00", dia=1), _snap("dune", "10.00", dia=2)])

    assert history.price_changes() == []


def test_price_changes_ignora_slug_com_um_snapshot(history: PriceHistory) -> None:
    history.save_snapshots([_snap("dune", "10.00", dia=1)])

    assert history.price_changes() == []


def test_price_changes_compara_apenas_os_dois_mais_recentes(history: PriceHistory) -> None:
    history.save_snapshots(
        [
            _snap("dune", "10.00", dia=1),
            _snap("dune", "12.00", dia=2),
            _snap("dune", "12.00", dia=3),
        ]
    )

    assert history.price_changes() == []
