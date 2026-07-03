"""CLI do price-radar: coleta, persiste e reporta.

Uso::

    PYTHONPATH=src python -m price_radar run     # pipeline completo
    PYTHONPATH=src python -m price_radar report  # só o resumo do banco
    PYTHONPATH=src python -m price_radar chart   # só regenera o gráfico

``run`` retorna código de saída 1 se nenhum alvo foi coletado — para o CI
falhar alto em vez de commitar uma rodada vazia. Erros de configuração
(targets.yml ausente ou inválido) retornam código 2.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from price_radar.config import ConfigError, load_targets
from price_radar.report import generate_chart, print_summary
from price_radar.scraper import scrape_all
from price_radar.storage import PriceHistory

logger = logging.getLogger("price_radar")

DEFAULT_TARGETS = "targets.yml"
DEFAULT_DB = "data/prices.db"
DEFAULT_CHART = "data/price_chart.png"


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser da CLI com os subcomandos run, report e chart."""
    parser = argparse.ArgumentParser(
        prog="price-radar",
        description="Monitor de preços do books.toscrape.com: "
        "coleta com Selenium, histórico em SQLite e relatório visual.",
    )
    parser.add_argument(
        "--targets",
        default=DEFAULT_TARGETS,
        help="caminho do YAML de alvos (padrão: %(default)s)",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="caminho do banco SQLite de histórico (padrão: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="comando")

    p_run = sub.add_parser(
        "run",
        help="pipeline completo: scraping + salvar + resumo + gráfico",
        description="Coleta todos os alvos, salva os snapshots no banco, "
        "imprime o resumo e regenera o gráfico.",
    )
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser(
        "report",
        help="imprime o resumo do banco existente (sem scraping)",
        description="Imprime os últimos preços por produto e as mudanças "
        "detectadas, a partir do banco existente. Não acessa a rede.",
    )
    p_report.set_defaults(func=cmd_report)

    p_chart = sub.add_parser(
        "chart",
        help="regenera o gráfico a partir do banco existente (sem scraping)",
        description="Regenera o PNG de evolução de preços a partir do banco "
        "existente. Não acessa a rede.",
    )
    p_chart.add_argument(
        "--output",
        default=DEFAULT_CHART,
        help="caminho do PNG gerado (padrão: %(default)s)",
    )
    p_chart.set_defaults(func=cmd_chart)

    return parser


def _exigir_banco(db_path: str) -> bool:
    """Confere que o banco já existe; orienta o usuário se não existir."""
    if Path(db_path).is_file():
        return True
    logger.error(
        "Banco não encontrado: %s. Rode 'price-radar run' primeiro para coletar dados.",
        db_path,
    )
    return False


def cmd_run(args: argparse.Namespace) -> int:
    """Pipeline completo: scraping, persistência, resumo e gráfico."""
    targets = load_targets(args.targets)
    snapshots = scrape_all(targets)
    if not snapshots:
        logger.error("Nenhum snapshot coletado; nada foi salvo.")
        return 1

    with PriceHistory(args.db) as history:
        history.save_snapshots(snapshots)
    logger.info("%d snapshots salvos em %s", len(snapshots), args.db)

    print()
    print_summary(args.db)
    print()
    generate_chart(args.db, DEFAULT_CHART)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Só o resumo de console, a partir do banco existente."""
    if not _exigir_banco(args.db):
        return 1
    print_summary(args.db)
    return 0


def cmd_chart(args: argparse.Namespace) -> int:
    """Só o gráfico, a partir do banco existente."""
    if not _exigir_banco(args.db):
        return 1
    generate_chart(args.db, args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI; devolve o código de saída do processo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
