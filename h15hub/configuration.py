from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_YAML = """# H15-Hub Konfiguration
# Passe die IPs und Token an deine Umgebung an.
# Dokumentation: https://github.com/hoktaar/H15-Hub/wiki

app:
  title: "H15-Hub"
  description: "Hebewerk e.V. Makerspace Integration Hub"
  poll_interval_seconds: 10

devices: {}

automations: []
"""


def get_config_path() -> Path:
    return Path(os.getenv("H15HUB_CONFIG", "config.yaml"))


def ensure_config_file() -> Path:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return config_path


def read_config_text() -> tuple[Path, str]:
    config_path = ensure_config_file()
    return config_path, config_path.read_text(encoding="utf-8")


def validate_config_text(content: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"Die Konfiguration enthält ungültiges YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            "Die Konfiguration muss ein YAML-Objekt mit Schlüsseln wie 'app', 'devices' und 'automations' sein"
        )

    return data


def save_config_text(content: str) -> Path:
    validate_config_text(content)
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content if content.endswith("\n") else f"{content}\n"
    config_path.write_text(normalized, encoding="utf-8")
    return config_path


def load_config() -> dict[str, Any]:
    config_path, content = read_config_text()
    try:
        return validate_config_text(content)
    except ValueError as exc:
        raise ValueError(f"Ungültige Konfiguration in {config_path}: {exc}") from exc