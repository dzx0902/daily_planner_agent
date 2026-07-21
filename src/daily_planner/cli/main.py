from __future__ import annotations

import asyncio
from datetime import date, datetime

import typer
import uvicorn

from daily_planner.config import get_settings
from daily_planner.exceptions import DailyPlannerError
from daily_planner.factory import build_parser, build_review_service, build_service, build_sync_service
from daily_planner.factory import build_repository
from daily_planner.models.sync import SyncStatus
from daily_planner.models.task import Task, TaskStatus
from daily_planner.repositories.notion import NotionTaskRepository

app = typer.Typer(help="Standalone Daily Planner Agent")


def _print_task(task: Task) -> None:
    start = task.start.strftime("%H:%M") if task.start else "unscheduled"
    end = task.end.strftime("%H:%M") if task.end else ""
    typer.echo(f"{task.id[:8]}  [{task.status}] {start}-{end} {task.priority} {task.title}")


def _run(coro) -> None:
    try:
        asyncio.run(coro)
    except DailyPlannerError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("check-config")
def check_config() -> None:
    settings = get_settings()
    typer.echo(f"APP_ENV={settings.app_env}")
    typer.echo(f"TIMEZONE={settings.timezone}")
    typer.echo(f"TASK_BACKEND={settings.task_backend}")
    typer.echo(f"LLM_PROVIDER={settings.llm_provider}")
    typer.echo(f"SQLITE_PATH={settings.sqlite_path}")


@app.command("parse")
def parse(input_text: str, target_date: str | None = None) -> None:
    async def run() -> None:
        parser = build_parser(get_settings())
        parsed = await parser.parse(input_text, date.fromisoformat(target_date) if target_date else None)
        typer.echo(parsed.model_dump_json(indent=2))

    _run(run())


@app.command("schedule")
def schedule(input_text: str, target_date: str | None = None) -> None:
    async def run() -> None:
        settings = get_settings()
        parser = build_parser(settings)
        parsed = await parser.parse(input_text, date.fromisoformat(target_date) if target_date else None)
        from daily_planner.core.scheduler import Scheduler

        scheduled, unscheduled = Scheduler(settings).schedule(parsed, input_text)
        typer.echo("Scheduled:")
        for task in scheduled:
            _print_task(task)
        typer.echo("Unscheduled:")
        for task in unscheduled:
            _print_task(task)

    _run(run())


@app.command("plan")
def plan(input_text: str, target_date: str | None = None, user_id: str = "default") -> None:
    async def run() -> None:
        result = await build_service().create_plan(input_text, date.fromisoformat(target_date) if target_date else None, user_id)
        typer.echo(result.message)
        for task in result.scheduled_tasks:
            _print_task(task)
        for task in result.unscheduled_tasks:
            _print_task(task)

    _run(run())


@app.command("today")
def today(user_id: str = "default") -> None:
    async def run() -> None:
        for task in await build_service().get_today_tasks(user_id):
            _print_task(task)

    _run(run())


@app.command("list")
def list_tasks(
    target_date: str | None = typer.Option(None, "--date"),
    status: str | None = typer.Option(None, "--status"),
    user_id: str = "default",
) -> None:
    async def run() -> None:
        parsed_status = TaskStatus(status) if status else None
        parsed_date = date.fromisoformat(target_date) if target_date else None
        for task in await build_service().list_tasks(parsed_date, parsed_status, user_id):
            _print_task(task)

    _run(run())


@app.command("done")
def done(keyword_or_id: str, user_id: str = "default") -> None:
    async def run() -> None:
        result = await build_service().mark_done(keyword_or_id, user_id)
        typer.echo(result.message)
        if result.task:
            _print_task(result.task)
        for task in result.candidates:
            _print_task(task)

    _run(run())


@app.command("cancel")
def cancel(keyword_or_id: str, user_id: str = "default") -> None:
    async def run() -> None:
        result = await build_service().cancel_task(keyword_or_id, user_id)
        typer.echo(result.message)
        if result.task:
            _print_task(result.task)
        for task in result.candidates:
            _print_task(task)

    _run(run())


@app.command("archive-done")
def archive_done(before: str | None = typer.Option(None, "--before"), user_id: str = "default") -> None:
    async def run() -> None:
        before_date = date.fromisoformat(before) if before else None
        result = await build_service().archive_done(before_date, user_id)
        typer.echo(result.message)

    _run(run())


@app.command("reschedule")
def reschedule(task_id: str, start: str = typer.Option(...), end: str = typer.Option(...)) -> None:
    async def run() -> None:
        result = await build_service().reschedule_task(task_id, datetime.fromisoformat(start), datetime.fromisoformat(end))
        typer.echo(result.message)
        if result.task:
            _print_task(result.task)

    _run(run())


@app.command("review")
def review(target_date: str | None = typer.Option(None, "--date"), user_id: str = "default") -> None:
    async def run() -> None:
        plan_date = date.fromisoformat(target_date) if target_date else date.today()
        typer.echo(await build_review_service().create_daily_review(plan_date, user_id))

    _run(run())


@app.command("check-notion")
def check_notion() -> None:
    async def run() -> None:
        result = await NotionTaskRepository(get_settings()).check()
        typer.echo(result)

    _run(run())


@app.command("clean-local")
def clean_local(yes: bool = typer.Option(False, "--yes", help="Confirm local SQLite database removal.")) -> None:
    settings = get_settings()
    if not yes:
        typer.echo("Refusing to remove local data without --yes.")
        raise typer.Exit(code=1)
    path = settings.sqlite_file
    removed = False
    for candidate in [path, *path.parent.glob(f"{path.name}-*")]:
        if candidate.exists():
            candidate.unlink()
            removed = True
    typer.echo(f"Removed local SQLite data at {path}." if removed else f"No local SQLite data found at {path}.")


@app.command("sync-queue")
def sync_queue(status: str | None = typer.Option(None, "--status")) -> None:
    async def run() -> None:
        repo = build_repository(get_settings())
        if not hasattr(repo, "list_sync_queue"):
            typer.echo("Current backend does not expose a sync queue.")
            return
        parsed_status = SyncStatus(status) if status else None
        items = await repo.list_sync_queue(parsed_status)
        for item in items:
            typer.echo(f"{item.id[:8]} [{item.status}] {item.operation} {item.local_task_id[:8]} attempts={item.attempts} error={item.last_error}")
        if not items:
            typer.echo("Sync queue is empty.")

    _run(run())


@app.command("sync-retry")
def sync_retry(limit: int = typer.Option(10, "--limit")) -> None:
    async def run() -> None:
        report = await build_sync_service().retry_failed(limit)
        typer.echo(f"attempted={report.attempted} succeeded={report.succeeded} failed={report.failed}")

    _run(run())


@app.command("test-notion-write")
def test_notion_write() -> None:
    async def run() -> None:
        settings = get_settings()
        repo = NotionTaskRepository(settings)
        task = Task(title="Daily Planner Agent test task", plan_date=date.today(), source=settings.default_task_source)
        await repo.create_task(task)
        typer.echo("Test task created in Notion.")

    _run(run())


@app.command("serve")
def serve() -> None:
    settings = get_settings()
    uvicorn.run("daily_planner.api.app:app", host=settings.host, port=settings.port, reload=settings.app_env == "development")


if __name__ == "__main__":
    app()
