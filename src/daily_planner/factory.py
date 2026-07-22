from __future__ import annotations

from daily_planner.config import Settings, get_settings
from daily_planner.core.planner_service import PlannerService
from daily_planner.core.review_service import ReviewService
from daily_planner.core.scheduler import Scheduler
from daily_planner.core.sync_service import SyncService
from daily_planner.llm.base import LLMParser
from daily_planner.llm.parser import RuleBasedParser
from daily_planner.llm.providers.deepseek import DeepSeekParser
from daily_planner.llm.providers.agent_core import AgentCoreParser
from daily_planner.repositories.base import TaskRepository
from daily_planner.repositories.hybrid import HybridTaskRepository
from daily_planner.repositories.notion import NotionTaskRepository
from daily_planner.repositories.sqlite import SQLiteTaskRepository
from daily_planner.repositories.postgres import PostgresTaskRepository


def build_parser(settings: Settings) -> LLMParser:
    if settings.agent_core_url:
        return AgentCoreParser(settings.agent_core_url, settings.deepseek_model)
    if settings.llm_provider == "deepseek":
        return DeepSeekParser(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)
    return RuleBasedParser()


def build_repository(settings: Settings) -> TaskRepository:
    sqlite = SQLiteTaskRepository(settings.sqlite_file)
    if settings.task_backend == "sqlite":
        return sqlite
    if settings.task_backend in {"postgres", "postgres_hybrid"}:
        if not settings.planner_database_url:
            raise ValueError("PLANNER_DATABASE_URL is required for PostgreSQL backends.")
        primary = PostgresTaskRepository(settings.planner_database_url)
        if settings.task_backend == "postgres":
            return primary
        return HybridTaskRepository(primary, NotionTaskRepository(settings))
    notion = NotionTaskRepository(settings)
    if settings.task_backend == "notion":
        return notion
    return HybridTaskRepository(sqlite, notion)


def build_service(settings: Settings | None = None) -> PlannerService:
    settings = settings or get_settings()
    return PlannerService(build_parser(settings), build_repository(settings), Scheduler(settings))


def build_review_service(settings: Settings | None = None) -> ReviewService:
    settings = settings or get_settings()
    return ReviewService(build_repository(settings))


def build_sync_service(settings: Settings | None = None) -> SyncService:
    settings = settings or get_settings()
    return SyncService(build_repository(settings), NotionTaskRepository(settings))
