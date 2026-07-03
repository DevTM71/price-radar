"""Testes do relatório: PNG gerado de banco populado e resumo com banco vazio."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from price_radar.report import generate_chart, print_summary
from price_radar.scraper import ProductSnapshot
from price_radar.storage import PriceHistory

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _snap(slug: str, price: str, dia: int) -> ProductSnapshot:
    return ProductSnapshot(
        slug=slug,
        title=f"Livro {slug}",
        price=Decimal(price),
        available=True,
        scraped_at=datetime(2026, 7, dia, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def db_populado(tmp_path: Path) -> Path:
    db_path = tmp_path / "prices.db"
    with PriceHistory(db_path) as history:
        history.save_snapshots(
            [
                _snap("dune", "10.00", dia=1),
                _snap("dune", "12.50", dia=2),
                _snap("emma", "8.00", dia=1),
                _snap("emma", "8.00", dia=2),
            ]
        )
    return db_path


def test_generate_chart_cria_png_nao_vazio(db_populado: Path, tmp_path: Path) -> None:
    saida = tmp_path / "chart.png"

    resultado = generate_chart(db_populado, saida)

    assert resultado == saida
    assert saida.stat().st_size > 0
    assert saida.read_bytes().startswith(PNG_MAGIC)


def test_print_summary_nao_explode_com_banco_vazio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "vazio.db"
    PriceHistory(db_path).close()  # cria só o schema

    print_summary(db_path)

    assert "Nenhum snapshot" in capsys.readouterr().out


def test_print_summary_lista_precos_e_mudancas(
    db_populado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    print_summary(db_populado)

    saida = capsys.readouterr().out
    assert "Últimos preços" in saida
    assert "£12.50" in saida
    assert "£10.00 -> £12.50" in saida  # dune mudou; emma estável fica de fora
