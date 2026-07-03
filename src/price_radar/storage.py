"""Persistência do histórico de preços em SQLite (stdlib, sem ORM).

Decisão de modelagem: o preço é ``Decimal`` no domínio e fica gravado como
**TEXT** (ex.: ``"51.77"``), nunca como REAL. Float não representa dinheiro
com exatidão (``0.1 + 0.2 != 0.3``), enquanto a ida e volta
``Decimal -> str -> Decimal`` é exata. Comparações e deltas de preço são
sempre calculados em ``Decimal`` no lado Python; o SQL só ordena e agrupa.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from price_radar.scraper import ProductSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    slug       TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    price      TEXT    NOT NULL,  -- Decimal serializado como string
    available  INTEGER NOT NULL,  -- 0/1
    scraped_at TEXT    NOT NULL   -- ISO 8601, UTC
);

CREATE INDEX IF NOT EXISTS idx_snapshots_slug_scraped_at
    ON snapshots (slug, scraped_at);
"""


@dataclass(frozen=True)
class PriceChange:
    """Mudança de preço entre os dois snapshots mais recentes de um produto."""

    slug: str
    title: str
    old_price: Decimal
    new_price: Decimal
    delta: Decimal


class PriceHistory:
    """Histórico de preços em um banco SQLite.

    Uso típico::

        with PriceHistory() as history:
            history.save_snapshots(snapshots)
            mudancas = history.price_changes()
    """

    def __init__(self, db_path: str | Path = "data/prices.db") -> None:
        self.db_path = db_path
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        """Fecha a conexão com o banco."""
        self._conn.close()

    def __enter__(self) -> "PriceHistory":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def save_snapshots(self, snapshots: Sequence[ProductSnapshot]) -> None:
        """Insere os snapshots em lote, numa única transação."""
        with self._conn:  # commit no sucesso, rollback se algo falhar
            self._conn.executemany(
                """
                INSERT INTO snapshots (slug, title, price, available, scraped_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (s.slug, s.title, str(s.price), int(s.available), s.scraped_at.isoformat())
                    for s in snapshots
                ],
            )

    def history(self, slug: str) -> list[ProductSnapshot]:
        """Todos os snapshots de um produto, em ordem cronológica."""
        rows = self._conn.execute(
            """
            SELECT slug, title, price, available, scraped_at
            FROM snapshots
            WHERE slug = ?
            ORDER BY scraped_at, id
            """,
            (slug,),
        ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def latest_prices(self) -> list[ProductSnapshot]:
        """O snapshot mais recente de cada produto, ordenado por slug."""
        rows = self._conn.execute(
            """
            SELECT slug, title, price, available, scraped_at
            FROM (
                SELECT slug, title, price, available, scraped_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY slug
                           ORDER BY scraped_at DESC, id DESC
                       ) AS rn
                FROM snapshots
            )
            WHERE rn = 1
            ORDER BY slug
            """
        ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def price_changes(self) -> list[PriceChange]:
        """Produtos cujo preço mudou entre os dois snapshots mais recentes.

        Slugs com um único snapshot não têm comparação possível e ficam de
        fora. A comparação é feita em ``Decimal``, nunca em float.
        """
        rows = self._conn.execute(
            """
            SELECT slug, title, price, rn
            FROM (
                SELECT slug, title, price,
                       ROW_NUMBER() OVER (
                           PARTITION BY slug
                           ORDER BY scraped_at DESC, id DESC
                       ) AS rn
                FROM snapshots
            )
            WHERE rn <= 2
            ORDER BY slug, rn
            """
        ).fetchall()

        por_slug: dict[str, dict[int, tuple[str, Decimal]]] = {}
        for slug, title, price, rn in rows:
            por_slug.setdefault(slug, {})[rn] = (title, Decimal(price))

        changes: list[PriceChange] = []
        for slug, pares in por_slug.items():
            if 2 not in pares:
                continue  # só um snapshot: sem comparação possível
            title, new_price = pares[1]
            _, old_price = pares[2]
            if new_price != old_price:
                changes.append(
                    PriceChange(
                        slug=slug,
                        title=title,
                        old_price=old_price,
                        new_price=new_price,
                        delta=new_price - old_price,
                    )
                )
        return changes


def _row_to_snapshot(row: tuple[str, str, str, int, str]) -> ProductSnapshot:
    """Reconstrói um ``ProductSnapshot`` a partir de uma linha do banco."""
    slug, title, price, available, scraped_at = row
    return ProductSnapshot(
        slug=slug,
        title=title,
        price=Decimal(price),
        available=bool(available),
        scraped_at=datetime.fromisoformat(scraped_at),
    )
