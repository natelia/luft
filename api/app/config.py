"""Runtime settings, overridable via environment variables."""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite://"))
    gios_base_url: str = field(
        default_factory=lambda: _env("GIOS_BASE_URL", "https://api.gios.gov.pl/pjp-api/rest")
    )
    tz: str = field(default_factory=lambda: _env("TZ", "Europe/Warsaw"))
