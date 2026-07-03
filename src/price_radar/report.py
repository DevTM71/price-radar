"""Relatórios do histórico de preços: gráfico de evolução e resumo de console.

O gráfico usa o backend "Agg" do matplotlib (renderiza direto para arquivo,
sem display) para rodar em CI. As cores das séries vêm de uma paleta
categórica fixa, validada para daltonismo — a ordem dos tons importa e não
deve ser embaralhada. Preços são ``Decimal`` e só viram float no momento de
desenhar; texto e rótulos ficam em cor de tinta, nunca na cor da série.

``print_summary`` usa ``print`` de propósito: ele é o relatório de console
(saída do CI), não log de diagnóstico.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem display: renderiza direto para arquivo (CI)

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from price_radar.storage import PriceHistory

logger = logging.getLogger(__name__)

#: Paleta categórica em ordem fixa (a ordem maximiza a separação entre tons
#: adjacentes para visão com daltonismo — não reordenar nem sortear).
_PALETTE = (
    "#2a78d6",  # azul
    "#1baf7a",  # verde-água
    "#eda100",  # amarelo
    "#008300",  # verde
    "#4a3aa7",  # violeta
    "#e34948",  # vermelho
    "#e87ba4",  # magenta
    "#eb6834",  # laranja
)

_SURFACE = "#fcfcfb"
_INK = "#1f1f1e"
_INK_MUTED = "#6f6e66"
_GRID = "#e4e3dd"

_TITULO_MAX = 28


def _titulo_curto(titulo: str) -> str:
    """Encurta o título para caber na legenda."""
    if len(titulo) <= _TITULO_MAX:
        return titulo
    return titulo[: _TITULO_MAX - 1].rstrip() + "…"


def generate_chart(
    db_path: str | Path, output_path: str | Path = "data/price_chart.png"
) -> Path:
    """Gera o PNG com a evolução de preço por produto (uma linha por slug)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with PriceHistory(db_path) as history:
        slugs = [snap.slug for snap in history.latest_prices()]
        series = {slug: history.history(slug) for slug in slugs}

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    fig.set_facecolor(_SURFACE)
    ax.set_facecolor(_SURFACE)

    if len(series) > len(_PALETTE):
        ignorados = sorted(series)[len(_PALETTE) :]
        logger.warning(
            "Mais produtos (%d) do que cores na paleta (%d); fora do gráfico: %s",
            len(series),
            len(_PALETTE),
            ", ".join(ignorados),
        )

    for cor, (slug, snaps) in zip(_PALETTE, sorted(series.items())):
        xs = [s.scraped_at for s in snaps]
        ys = [float(s.price) for s in snaps]  # float apenas para desenhar
        ax.plot(
            xs,
            ys,
            color=cor,
            linewidth=2,
            marker="o",
            markersize=5,
            label=_titulo_curto(snaps[-1].title),
        )
        # Preço no fim da linha, em cor de tinta (identidade fica na legenda).
        ax.annotate(
            f"£{snaps[-1].price}",
            (xs[-1], ys[-1]),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=_INK,
        )

    if series:
        # Folga à direita para os rótulos de preço não saírem do quadro.
        x0, x1 = ax.get_xlim()
        ax.set_xlim(x0, x1 + (x1 - x0) * 0.18)
        ax.legend(frameon=False, fontsize=9, loc="best", labelcolor=_INK)
    else:
        ax.text(
            0.5, 0.5, "Sem dados ainda", transform=ax.transAxes,
            ha="center", va="center", color=_INK_MUTED, fontsize=12,
        )

    ax.set_title(
        "Evolução de preços — books.toscrape.com",
        loc="left", fontsize=13, color=_INK, pad=14,
    )
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"£{y:.2f}"))
    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(_GRID)
    ax.tick_params(colors=_INK_MUTED, labelsize=8.5)
    fig.autofmt_xdate(rotation=30, ha="right")

    fig.tight_layout()
    fig.savefig(output_path, facecolor=_SURFACE)
    plt.close(fig)
    logger.info("Gráfico salvo em %s", output_path)
    return output_path


def print_summary(db_path: str | Path) -> None:
    """Imprime o resumo para o log do CI: últimos preços e mudanças detectadas."""
    with PriceHistory(db_path) as history:
        latest = history.latest_prices()
        changes = history.price_changes()

    if not latest:
        print("Nenhum snapshot no banco ainda.")
        return

    print("Últimos preços:")
    for snap in latest:
        estado = "em estoque" if snap.available else "indisponível"
        print(
            f"  £{snap.price!s:>6}  {snap.title}"
            f"  ({estado}, {snap.scraped_at:%Y-%m-%d %H:%M} UTC)"
        )

    print()
    if changes:
        print("Mudanças de preço detectadas:")
        for change in changes:
            sinal = "+" if change.delta > 0 else ""
            print(
                f"  {change.title}: £{change.old_price} -> £{change.new_price}"
                f" ({sinal}{change.delta})"
            )
    else:
        print("Nenhuma mudança de preço detectada.")
