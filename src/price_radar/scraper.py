"""Scraper Selenium para páginas de produto do books.toscrape.com.

A extração de dados fica em ``parse_product``, função pura que recebe o HTML
e não depende de rede nem de driver — é ela que os testes cobrem.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Sequence

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from price_radar.config import Target

logger = logging.getLogger(__name__)

#: User-agent identificado do bot (ver CLAUDE.md, "Scraping ético").
USER_AGENT = "price-radar/1.0 (+github.com/DevTM71/price-radar)"

#: Pausa educada entre alvos, em segundos.
RATE_LIMIT_SECONDS = 1.5

#: Tempo máximo de espera pelo carregamento da página de produto.
PAGE_TIMEOUT_SECONDS = 15


class ParseError(ValueError):
    """O HTML recebido não é uma página de produto reconhecível."""


@dataclass(frozen=True)
class ProductSnapshot:
    """Uma leitura pontual de um produto: preço e disponibilidade no momento."""

    slug: str
    title: str
    price: Decimal
    available: bool
    scraped_at: datetime


class _ProductPageParser(HTMLParser):
    """Extrai título, preço e disponibilidade do bloco ``.product_main``."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.price_text: str | None = None
        self.availability_text: str | None = None
        self._in_main = False
        self._capturing: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        if tag == "div" and "product_main" in classes:
            self._in_main = True
            return
        if not self._in_main or self._capturing:
            return
        if tag == "h1" and self.title is None:
            self._capturing, self._buffer = "title", []
        elif tag == "p" and "price_color" in classes and self.price_text is None:
            self._capturing, self._buffer = "price", []
        elif tag == "p" and "availability" in classes and self.availability_text is None:
            self._capturing, self._buffer = "availability", []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capturing == "title" and tag == "h1":
            self.title = "".join(self._buffer).strip()
        elif self._capturing == "price" and tag == "p":
            self.price_text = "".join(self._buffer).strip()
        elif self._capturing == "availability" and tag == "p":
            self.availability_text = " ".join("".join(self._buffer).split())
        else:
            return
        self._capturing = None


def _parse_price(text: str) -> Decimal:
    """Converte um texto de preço como ``£51.77`` em ``Decimal('51.77')``."""
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        raise ParseError(f"Não foi possível extrair um preço de: {text!r}")
    try:
        return Decimal(match.group())
    except InvalidOperation as exc:  # defensivo; o regex já restringe o formato
        raise ParseError(f"Preço inválido: {text!r}") from exc


def parse_product(html: str, slug: str = "") -> ProductSnapshot:
    """Extrai um ``ProductSnapshot`` do HTML de uma página de produto.

    Função pura em relação à rede: recebe o HTML como string, sem driver.
    O ``slug`` identifica o alvo (não está presente no HTML) e ``scraped_at``
    é preenchido com o horário UTC atual.
    """
    if not html or not html.strip():
        raise ParseError("HTML vazio: nada para extrair.")

    parser = _ProductPageParser()
    parser.feed(html)

    if parser.title is None or parser.price_text is None:
        raise ParseError(
            "HTML não parece uma página de produto do books.toscrape.com "
            "(bloco .product_main com título e preço não encontrado)."
        )

    available = "in stock" in (parser.availability_text or "").lower()
    return ProductSnapshot(
        slug=slug,
        title=parser.title,
        price=_parse_price(parser.price_text),
        available=available,
        scraped_at=datetime.now(timezone.utc),
    )


def create_driver() -> webdriver.Chrome:
    """Cria um Chrome headless com o user-agent identificado do projeto."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--window-size=1280,1024")
    return webdriver.Chrome(options=options)


def scrape_target(driver: webdriver.Chrome, target: Target) -> ProductSnapshot:
    """Navega até a página do alvo, espera o produto carregar e faz o parse."""
    logger.info("Coletando %s (%s)", target.slug, target.url)
    driver.get(target.url)
    WebDriverWait(driver, PAGE_TIMEOUT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.product_main"))
    )
    snapshot = parse_product(driver.page_source, slug=target.slug)
    logger.info(
        "%s: £%s (%s)",
        snapshot.slug,
        snapshot.price,
        "em estoque" if snapshot.available else "indisponível",
    )
    return snapshot


def scrape_all(targets: Sequence[Target]) -> list[ProductSnapshot]:
    """Coleta todos os alvos com rate limiting; falha de um não derruba os demais."""
    snapshots: list[ProductSnapshot] = []
    driver = create_driver()
    try:
        for i, target in enumerate(targets):
            if i > 0:
                time.sleep(RATE_LIMIT_SECONDS)
            try:
                snapshots.append(scrape_target(driver, target))
            except Exception:
                logger.exception("Falha ao coletar %s; seguindo para o próximo alvo", target.slug)
    finally:
        driver.quit()
    logger.info("Coleta concluída: %d de %d alvos com sucesso", len(snapshots), len(targets))
    return snapshots
