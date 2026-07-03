"""Ponto de entrada do price-radar: coleta, persiste e reporta.

Uso::

    PYTHONPATH=src python -m price_radar

Fluxo: carrega os alvos do targets.yml, faz o scraping, salva os snapshots
no SQLite, imprime o resumo (últimos preços + mudanças) e gera o gráfico.
Retorna código de saída 1 se nenhum alvo foi coletado — para o CI falhar
alto em vez de commitar uma rodada vazia.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from price_radar.config import load_targets
from price_radar.report import generate_chart, print_summary
from price_radar.scraper import scrape_all
from price_radar.storage import PriceHistory

logger = logging.getLogger("price_radar")

TARGETS_PATH = Path("targets.yml")
DB_PATH = Path("data/prices.db")
CHART_PATH = Path("data/price_chart.png")


def main() -> int:
    """Executa o fluxo completo; devolve o código de saída do processo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    targets = load_targets(TARGETS_PATH)
    snapshots = scrape_all(targets)
    if not snapshots:
        logger.error("Nenhum snapshot coletado; nada foi salvo.")
        return 1

    with PriceHistory(DB_PATH) as history:
        history.save_snapshots(snapshots)
    logger.info("%d snapshots salvos em %s", len(snapshots), DB_PATH)

    print()
    print_summary(DB_PATH)
    print()
    generate_chart(DB_PATH, CHART_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
