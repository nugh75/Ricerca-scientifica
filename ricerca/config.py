"""Configurazione locale in ~/.ricerca/config.toml, con permessi 600.

Niente keyring, niente variabili d'ambiente obbligatorie: l'app parte
anche senza file di configurazione, con le fonti a chiave disattivate.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("RICERCA_HOME", Path.home() / ".ricerca"))
CONFIG_FILE = CONFIG_DIR / "config.toml"

PRESETS = {
    "ollama": "http://localhost:11434/v1",
    "llama-swap": "http://localhost:8080/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
}


@dataclass
class Config:
    lang: str = "it"
    mailto: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    core_api_key: str = ""
    s2_api_key: str = ""
    ncbi_api_key: str = ""

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


def load(path: Path | None = None) -> Config:
    path = path or CONFIG_FILE
    if not path.exists():
        return Config()
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    fields = {f for f in Config.__dataclass_fields__}
    return Config(**{k: str(v) for k, v in data.items() if k in fields})


def save(config: Config, path: Path | None = None) -> Path:
    path = path or CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{key} = "{_escape(value)}"' for key, value in asdict(config).items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
