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
- `storage.py` — (planejado) persistência do histórico de preços em `data/`.
- `report.py` — (planejado) gráficos de evolução de preço com matplotlib.

`data/` é versionada **de propósito**: o histórico de preços commitado faz
parte do projeto (o workflow agendado commita novas leituras).

Testes em `tests/`, com HTML real salvo em `tests/fixtures/`. Nenhum teste
acessa a rede.

## Convenções

- Docstrings em português; type hints em todo o código.
- Toda lógica de parsing tem teste contra fixtures HTML (sem rede).
- Logging com o módulo `logging` (nível INFO); nunca `print` em código de
  biblioteca.

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
