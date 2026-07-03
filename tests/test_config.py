"""Testes de load_targets: YAML válido e falhas com mensagens amigáveis."""

from pathlib import Path

import pytest

from price_radar.config import ConfigError, Target, load_targets

RAIZ_DO_PROJETO = Path(__file__).parents[1]

YAML_VALIDO = """
targets:
  - name: "Livro Exemplo"
    url: "https://books.toscrape.com/catalogue/exemplo_1/index.html"
    slug: "livro-exemplo"
  - name: "Outro Livro"
    url: "https://books.toscrape.com/catalogue/outro_2/index.html"
    slug: "outro-livro"
"""


def test_carrega_yaml_valido(tmp_path: Path) -> None:
    arquivo = tmp_path / "targets.yml"
    arquivo.write_text(YAML_VALIDO, encoding="utf-8")

    targets = load_targets(arquivo)

    assert targets == [
        Target(
            name="Livro Exemplo",
            url="https://books.toscrape.com/catalogue/exemplo_1/index.html",
            slug="livro-exemplo",
        ),
        Target(
            name="Outro Livro",
            url="https://books.toscrape.com/catalogue/outro_2/index.html",
            slug="outro-livro",
        ),
    ]


def test_arquivo_ausente_gera_erro_amigavel(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="não encontrado"):
        load_targets(tmp_path / "nao-existe.yml")


def test_campo_faltando_gera_erro_amigavel(tmp_path: Path) -> None:
    arquivo = tmp_path / "targets.yml"
    arquivo.write_text(
        """
targets:
  - name: "Sem URL"
    slug: "sem-url"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="sem os campos: url"):
        load_targets(arquivo)


def test_sem_chave_targets_gera_erro_amigavel(tmp_path: Path) -> None:
    arquivo = tmp_path / "targets.yml"
    arquivo.write_text("produtos: []", encoding="utf-8")
    with pytest.raises(ConfigError, match="'targets'"):
        load_targets(arquivo)


def test_targets_yml_do_projeto_e_valido() -> None:
    targets = load_targets(RAIZ_DO_PROJETO / "targets.yml")
    assert len(targets) == 5
    assert all(t.url.startswith("https://books.toscrape.com/") for t in targets)
