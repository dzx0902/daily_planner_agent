from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    timezone: str = "Asia/Shanghai"
    host: str = "127.0.0.1"
    port: int = 8000

    task_backend: Literal["sqlite", "notion", "hybrid", "postgres", "postgres_hybrid"] = "sqlite"
    sqlite_path: str = "data/daily_planner.db"
    planner_database_url: str = ""

    llm_provider: str = "rule"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    agent_core_url: str = ""

    notion_api_key: str = ""
    notion_data_source_id: str = "3978473f-2546-80cd-8b11-000b260bf205"
    notion_version: str = "2025-09-03"
    default_task_source: str = "Agent"

    default_day_start: str = "09:00"
    default_day_end: str = "23:00"
    default_blocked_times: str = "12:00-13:00,18:00-19:00"
    auto_add_daily_review: bool = True
    daily_review_duration: int = 30

    api_key_enabled: bool = False
    daily_planner_api_key: str = Field(default="", repr=False)

    daily_planner_api_base: str = "http://127.0.0.1:8000"

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def sqlite_file(self) -> Path:
        return Path(self.sqlite_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
