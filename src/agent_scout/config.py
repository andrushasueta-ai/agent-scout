"""Загрузка и валидация конфигурации из config.yaml."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class PlatformConfig(BaseModel):
    """Конфигурация отдельной площадки."""

    enabled: bool = False
    base_url: str
    rate_limit: int = 25
    cooldown_minutes: list[int] = Field(default_factory=lambda: [30, 120])


class NicheConfig(BaseModel):
    """Конфигурация ниши для мониторинга."""

    name: str
    queries: list[str]
    category: str
    locations: list[str]


class ProxyConfig(BaseModel):
    """Конфигурация прокси-сервера."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def url(self) -> str:
        """Полный URL прокси для Playwright."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


class MessagingConfig(BaseModel):
    """Конфигурация AI-переписки."""

    enabled: bool = True
    claude_model: str = "claude-sonnet-4-6"
    max_conversations_per_day: int = 12
    reply_delay_minutes: list[int] = Field(default_factory=lambda: [3, 20])


class BrowserConfig(BaseModel):
    """Конфигурация браузера."""

    headless: bool = True
    viewport_width: int = 1440
    viewport_height: int = 900
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"


class ScheduleConfig(BaseModel):
    """Конфигурация расписания активности."""

    work_hours: list[int] = Field(default_factory=lambda: [9, 22])
    session_duration_minutes: list[int] = Field(default_factory=lambda: [15, 40])
    break_duration_minutes: list[int] = Field(default_factory=lambda: [20, 90])
    weekend_activity_reduction: float = 0.4


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных."""

    path: str = "data/agent_scout.db"
    sessions_dir: str = "data/sessions"


class AppConfig(BaseModel):
    """Корневая конфигурация приложения."""

    platforms: dict[str, PlatformConfig] = Field(default_factory=dict)
    niches: list[NicheConfig] = Field(default_factory=list)
    proxies: list[ProxyConfig] = Field(default_factory=list)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    """Загрузить конфигурацию из YAML-файла."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig.model_validate(raw)
