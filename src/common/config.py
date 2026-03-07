from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml


class Config:
    def __init__(self, data: dict[str, Any], source_files: list[str] | None = None) -> None:
        self._data = data
        self.source_files = source_files or []

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with path.open("r", encoding="utf-8") as file:
            parsed = yaml.safe_load(file) or {}
        if not isinstance(parsed, dict):
            raise ValueError(f"Top-level YAML content must be a mapping: {path}")
        return parsed

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = Config._deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    @classmethod
    def load(
        cls,
        config_dir: str | Path | None = None,
        base_file: str = "base.yaml",
        env_file: str | None = None,
        env_name: str | None = None,
    ) -> "Config":
        root_dir = Path(__file__).resolve().parents[2]
        resolved_config_dir = Path(config_dir) if config_dir else root_dir / "configs"

        selected_env = env_name or os.getenv("BDA_ENV", "dev")
        selected_env_file = env_file or f"{selected_env}.yaml"

        base_path = resolved_config_dir / base_file
        env_path = resolved_config_dir / selected_env_file

        base_cfg = cls._read_yaml(base_path)
        env_cfg = cls._read_yaml(env_path)
        merged = cls._deep_merge(base_cfg, env_cfg)

        merged.setdefault("app", {})
        merged["app"]["env"] = selected_env

        return cls(merged, source_files=[str(base_path), str(env_path)])

    def get(self, path: str, default: Any = None, required: bool = False) -> Any:
        current: Any = self._data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                if required:
                    raise KeyError(f"Missing configuration key: {path}")
                return default
        return current

    def section(self, path: str, required: bool = True) -> "Config":
        section_data = self.get(path, required=required)
        if not isinstance(section_data, dict):
            raise TypeError(f"Configuration section '{path}' is not a mapping")
        return Config(section_data, source_files=self.source_files)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getattr__(self, key: str) -> Any:
        try:
            value = self._data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

        if isinstance(value, dict):
            return Config(value, source_files=self.source_files)
        return value

    def __repr__(self) -> str:
        return f"Config(keys={list(self._data.keys())}, source_files={self.source_files})"


_cached_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    global _cached_config
    if _cached_config is None or reload:
        _cached_config = Config.load()
    return _cached_config
