# price-radar

Monitor de preços em Python: coleta preços de produtos com web scraping via
Selenium, guarda o histórico em arquivos versionados e roda de forma agendada
via GitHub Actions. Projeto de portfólio; o alvo é o
[books.toscrape.com](https://books.toscrape.com) — site público mantido
justamente para prática de scraping.

## Arquitetura

Pacote em `src/price_radar/`:

- `config.py` — dataclass `Target` e `load_targets()`: lê e valida o
  `targets.yml` da raiz (lista de produtos monitorados).
- `scraper.py` — Selenium (Chrome headless). `parse_product(html)` é uma
  função **pura** que extrai título, preço (`Decimal`) e disponibilidade do
  HTML; é ela que os testes cobrem, sem rede. `scrape_target()` navega e
  espera com `WebDriverWait`; `scrape_all()` itera os alvos com rate limiting.
- `storage.py` — histórico de preços em SQLite (`data/prices.db`), stdlib sem
  ORM. Preço gravado como TEXT (`Decimal` serializado) — nunca float para
  dinheiro. `price_changes()` compara os dois snapshots mais recentes por slug.
- `report.py` — gráfico de evolução de preço (matplotlib, backend Agg para
  CI) e `print_summary()` com o resumo de console; a paleta categórica do
  gráfico tem ordem fixa validada para daltonismo — não reordenar.

`data/` é versionada **de propósito**: o histórico de preços commitado faz
parte do projeto (o workflow agendado commita novas leituras).

CLI (`__main__.py`, argparse): `run` (pipeline completo), `report` (só o
resumo, sem rede) e `chart` (só o gráfico, sem rede), com flags globais
`--targets` e `--db`. Roda como `PYTHONPATH=src python -m price_radar <cmd>`.

## Automação (GitHub Actions)

- `.github/workflows/ci.yml` — roda o pytest em todo push na `main` e em
  todo pull request. Os testes não usam rede nem navegador.
- `.github/workflows/scrape.yml` ("Daily scrape") — roda o pipeline completo
  todo dia às **07:23 UTC** (horário quebrado de propósito: cargas em hora
  cheia entram em fila no Actions) e commita `data/` como
  `github-actions[bot]` com a mensagem `chore: daily price snapshot [skip ci]`
  — o `[skip ci]` evita disparar o workflow de testes no push do bot. Só
  commita se `data/` mudou; `concurrency` garante que nunca há duas execuções
  simultâneas.
- **Disparo manual**: aba Actions → "Daily scrape" → "Run workflow", ou
  `gh workflow run "Daily scrape"`.

Testes em `tests/`, com HTML real salvo em `tests/fixtures/`. Nenhum teste
acessa a rede.

## Desenvolvimento local

- Dependências no `.venv` da raiz: `.venv/bin/python -m pytest` roda a suíte;
  `PYTHONPATH=src .venv/bin/python -m price_radar <cmd>` roda a CLI.
- O workflow diário commita `data/` na `main` — faça `git pull` antes de
  começar a trabalhar.

## Convenções

- Docstrings em português; type hints em todo o código.
- Toda lógica de parsing tem teste contra fixtures HTML (sem rede).
- Logging com o módulo `logging` (nível INFO); nunca `print` em código de
  biblioteca. Exceção: `print_summary()` imprime de propósito — é o
  relatório de console que o CI exibe.
- `parse_product` usa `html.parser` da stdlib de propósito — não adicionar
  BeautifulSoup.
- O badge de contagem de testes do README é estático — atualize o número ao
  adicionar testes.

## Versionamento

- Commits pequenos e coesos: um assunto por commit, nunca misturar mudanças
  não relacionadas.
- Conventional Commits: `feat`, `fix`, `test`, `docs`, `chore`, `ci`.
- Mensagens em inglês, no modo imperativo ("add X", não "added X").

## Scraping ético

Regras do projeto — valem para qualquer código novo:

- **Apenas alvos apropriados**: somente o books.toscrape.com, site mantido
  para prática de scraping. Não apontar o scraper para sites reais sem
  permissão explícita.
- **Rate limiting**: pausa educada entre requisições (1,5 s entre alvos).
- **User-agent identificado**: o bot se apresenta como
  `price-radar/1.0 (+github.com/DevTM71/price-radar)`.
- **Proibido** burlar bloqueios, CAPTCHAs ou limites de acesso, e proibido
  coletar dados pessoais.
