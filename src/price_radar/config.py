"""Carregamento e validação dos alvos de monitoramento (targets.yml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_CAMPOS_OBRIGATORIOS = ("name", "url", "slug")


class ConfigError(Exception):
    """Erro de configuração dos alvos, com mensagem amigável."""


@dataclass(frozen=True)
class Target:
    """Um produto a monitorar: nome legível, URL da página de detalhe e slug."""

    name: str
    url: str
    slug: str


def load_targets(path: str | Path) -> list[Target]:
    """Lê o arquivo YAML de alvos e devolve a lista de ``Target`` validada.

    Levanta ``ConfigError`` com mensagem clara se o arquivo não existir,
    estiver malformado ou algum alvo estiver com campo faltando/vazio.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(
            f"Arquivo de alvos não encontrado: {path}. "
            "Crie um targets.yml na raiz do projeto (veja o exemplo no repositório)."
        )

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {path}: {exc}") from exc

    if not isinstance(data, dict) or "targets" not in data:
        raise ConfigError(
            f"{path} deve conter uma chave de topo 'targets' com a lista de produtos."
        )
    entries = data["targets"]
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"'targets' em {path} deve ser uma lista com ao menos um produto.")

    targets: list[Target] = []
    slugs_vistos: set[str] = set()
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ConfigError(f"Alvo #{i} em {path} deve ser um mapeamento (name/url/slug).")
        faltando = [
            campo
            for campo in _CAMPOS_OBRIGATORIOS
            if not isinstance(entry.get(campo), str) or not entry.get(campo, "").strip()
        ]
        if faltando:
            nome = entry.get("name") or entry.get("slug") or f"#{i}"
            raise ConfigError(
                f"Alvo {nome} em {path} está sem os campos: {', '.join(faltando)}."
            )
        if not entry["url"].startswith(("http://", "https://")):
            raise ConfigError(f"Alvo {entry['name']}: url deve começar com http:// ou https://.")
        if entry["slug"] in slugs_vistos:
            raise ConfigError(f"Slug duplicado em {path}: {entry['slug']}.")
        slugs_vistos.add(entry["slug"])
        targets.append(Target(name=entry["name"], url=entry["url"], slug=entry["slug"]))

    return targets
