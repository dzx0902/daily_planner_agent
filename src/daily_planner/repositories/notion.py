from __future__ import annotations

from datetime import date, datetime
import asyncio
from typing import Any

import httpx

from daily_planner.config import Settings
from daily_planner.exceptions import ConfigurationError, IntegrationError
from daily_planner.models.task import Priority, Task, TaskStatus
from daily_planner.repositories.base import TaskRepository


REQUIRED_PROPERTIES = {
    "任务": "title",
    "计划时间": "date",
    "Plan Date": "date",
    "状态": "status",
    "优先级": "select",
    "项目": "select",
    "预计时长": "number",
    "必须今天": "checkbox",
    "来源": "select",
    "Calendar Event ID": "rich_text",
    "原始输入": "rich_text",
    "结果记录": "rich_text",
}


class NotionTaskRepository(TaskRepository):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = "https://api.notion.com"
        self.provider_name = "notion"

    def build_create_payload(self, task: Task) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "任务": {"title": [{"text": {"content": task.title}}]},
            "计划时间": {"date": self._date_range(task)},
            "Plan Date": {"date": {"start": task.plan_date.isoformat()}},
            "状态": {"status": {"name": task.status.value}},
            "优先级": {"select": {"name": task.priority.value}},
            "预计时长": {"number": task.duration_minutes},
            "必须今天": {"checkbox": task.must_today},
            "来源": {"select": {"name": task.source}},
        }
        if task.project:
            properties["项目"] = {"select": {"name": task.project}}
        properties["Calendar Event ID"] = {"rich_text": self._text(task.calendar_event_id or task.id)}
        if task.raw_input:
            properties["原始输入"] = {"rich_text": self._text(task.raw_input)}
        if task.result_note:
            properties["结果记录"] = {"rich_text": self._text(task.result_note)}
        return {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self.settings.notion_data_source_id,
            },
            "properties": properties,
        }

    async def check(self) -> dict[str, Any]:
        self._ensure_configured()
        response = await self._request(
            "GET",
            f"{self.base_url}/v1/data_sources/{self.settings.notion_data_source_id}",
            action="check Notion data source",
        )
        data = response.json()
        properties = data.get("properties", {})
        problems: list[str] = []
        for name, expected_type in REQUIRED_PROPERTIES.items():
            prop = properties.get(name)
            if not prop:
                problems.append(f"Missing property: {name}")
                continue
            if prop.get("type") != expected_type:
                problems.append(f"Property {name} type is {prop.get('type')}, expected {expected_type}")
        source_options = self._options(properties.get("来源", {}))
        if self.settings.default_task_source not in source_options:
            available = ", ".join(sorted(source_options)) or "<none>"
            problems.append(f"来源 select is missing option: {self.settings.default_task_source}. Available: {available}")
        return {
            "name": data.get("title", [{}])[0].get("plain_text", ""),
            "ok": not problems,
            "problems": problems,
            "source_options": sorted(source_options),
        }

    async def create_task(self, task: Task) -> Task:
        await self.create_task_with_remote_id(task)
        return task

    async def create_task_with_remote_id(self, task: Task) -> tuple[Task, str]:
        self._ensure_configured()
        response = await self._request(
            "POST",
            f"{self.base_url}/v1/pages",
            action="create Notion page",
            json=self.build_create_payload(task),
        )
        return task, response.json()["id"]

    async def get_task(self, task_id: str) -> Task | None:
        page_id = await self._find_page_id(task_id)
        if not page_id:
            return None
        response = await self._request("GET", f"{self.base_url}/v1/pages/{page_id}", action="get Notion task page")
        return self._page_to_task(response.json())

    async def list_tasks_by_date(self, plan_date: date, status: TaskStatus | None = None, user_id: str = "default") -> list[Task]:
        filters: list[dict[str, Any]] = [
            {"property": "Plan Date", "date": {"equals": plan_date.isoformat()}},
        ]
        if status:
            filters.append({"property": "状态", "status": {"equals": status.value}})
        return await self._query_tasks(filters)

    async def search_open_tasks(self, keyword: str, plan_date: date | None = None, user_id: str = "default") -> list[Task]:
        filters: list[dict[str, Any]] = [
            {"property": "任务", "title": {"contains": keyword}},
            {
                "or": [
                    {"property": "状态", "status": {"equals": TaskStatus.PLANNED.value}},
                    {"property": "状态", "status": {"equals": TaskStatus.DOING.value}},
                ]
            },
        ]
        if plan_date:
            filters.append({"property": "Plan Date", "date": {"equals": plan_date.isoformat()}})
        return await self._query_tasks(filters)

    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        page_id = await self._find_page_id(task_id)
        if not page_id:
            return None
        await self.update_status_by_remote_id(page_id, status)
        return None

    async def update_status_by_remote_id(self, remote_id: str, status: TaskStatus) -> None:
        await self._request(
            "PATCH",
            f"{self.base_url}/v1/pages/{remote_id}",
            action="update Notion task status",
            json={"properties": {"状态": {"status": {"name": status.value}}}},
        )

    async def update_schedule(self, task_id: str, start: datetime, end: datetime) -> Task | None:
        page_id = await self._find_page_id(task_id)
        if not page_id:
            return None
        await self.update_schedule_by_remote_id(page_id, start, end)
        return None

    async def update_schedule_by_remote_id(self, remote_id: str, start: datetime, end: datetime) -> None:
        await self._request(
            "PATCH",
            f"{self.base_url}/v1/pages/{remote_id}",
            action="update Notion task schedule",
            json={
                "properties": {
                    "计划时间": {"date": {"start": start.isoformat(), "end": end.isoformat()}},
                    "Plan Date": {"date": {"start": start.date().isoformat()}},
                }
            },
        )

    async def append_result_note(self, task_id: str, note: str) -> Task | None:
        page_id = await self._find_page_id(task_id)
        if not page_id:
            return None
        await self.append_result_note_by_remote_id(page_id, note)
        return None

    async def append_result_note_by_remote_id(self, remote_id: str, note: str) -> None:
        await self._request(
            "PATCH",
            f"{self.base_url}/v1/pages/{remote_id}",
            action="append Notion task result note",
            json={"properties": {"结果记录": {"rich_text": self._text(note)}}},
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.notion_api_key}",
            "Notion-Version": self.settings.notion_version,
            "Content-Type": "application/json",
        }

    def _ensure_configured(self) -> None:
        if not self.settings.notion_api_key:
            raise ConfigurationError("NOTION_API_KEY is required for Notion backend.")
        if not self.settings.notion_data_source_id:
            raise ConfigurationError("NOTION_DATA_SOURCE_ID is required for Notion backend.")

    def _date_range(self, task: Task) -> dict[str, str] | None:
        if not task.start:
            return {"start": task.plan_date.isoformat()}
        data = {"start": task.start.isoformat()}
        if task.end:
            data["end"] = task.end.isoformat()
        return data

    def _text(self, value: str | None) -> list[dict[str, Any]]:
        return [{"text": {"content": value}}] if value else []

    def _options(self, prop: dict[str, Any]) -> set[str]:
        body = prop.get(prop.get("type", ""), {})
        return {item.get("name", "") for item in body.get("options", [])}

    async def _request(self, method: str, url: str, action: str, **kwargs: Any) -> httpx.Response:
        last_error: httpx.RequestError | None = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.request(method, url, headers=self._headers(), **kwargs)
                self._raise_for_status(response, action)
                return response
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
        raise IntegrationError(f"Failed to {action}: network error. {last_error}") from last_error

    async def _find_page_id(self, task_id: str) -> str | None:
        response = await self._request(
            "POST",
            f"{self.base_url}/v1/data_sources/{self.settings.notion_data_source_id}/query",
            action="find Notion task page",
            json={
                "filter": {
                    "property": "Calendar Event ID",
                    "rich_text": {"equals": task_id},
                },
                "page_size": 1,
            },
        )
        results = response.json().get("results", [])
        if not results:
            return None
        return results[0].get("id")

    async def _query_tasks(self, filters: list[dict[str, Any]]) -> list[Task]:
        response = await self._request(
            "POST",
            f"{self.base_url}/v1/data_sources/{self.settings.notion_data_source_id}/query",
            action="query Notion tasks",
            json={
                "filter": {"and": filters} if len(filters) > 1 else filters[0],
                "page_size": 100,
            },
        )
        return [self._page_to_task(page) for page in response.json().get("results", [])]

    def _page_to_task(self, page: dict[str, Any]) -> Task:
        props = page.get("properties", {})
        task_id = self._rich_text(props.get("Calendar Event ID")) or page.get("id", "")
        date_range = props.get("计划时间", {}).get("date") or {}
        plan_date_value = props.get("Plan Date", {}).get("date", {}).get("start") or date_range.get("start")
        start = self._parse_datetime(date_range.get("start"))
        end = self._parse_datetime(date_range.get("end"))
        plan_date = date.fromisoformat(plan_date_value[:10]) if plan_date_value else date.today()
        return Task(
            id=task_id.replace("-", "") if task_id == page.get("id") else task_id,
            title=self._title(props.get("任务")) or "Untitled",
            plan_date=plan_date,
            start=start,
            end=end,
            duration_minutes=int(props.get("预计时长", {}).get("number") or 90),
            status=self._status(props.get("状态")),
            priority=self._priority(props.get("优先级")),
            project=self._select(props.get("项目")),
            must_today=bool(props.get("必须今天", {}).get("checkbox")),
            source=self._select(props.get("来源")) or self.settings.default_task_source,
            calendar_event_id=self._rich_text(props.get("Calendar Event ID")),
            raw_input=self._rich_text(props.get("原始输入")),
            result_note=self._rich_text(props.get("结果记录")),
        )

    def _title(self, prop: dict[str, Any] | None) -> str:
        return "".join(item.get("plain_text", "") for item in (prop or {}).get("title", []))

    def _rich_text(self, prop: dict[str, Any] | None) -> str | None:
        text = "".join(item.get("plain_text", "") for item in (prop or {}).get("rich_text", []))
        return text or None

    def _select(self, prop: dict[str, Any] | None) -> str | None:
        value = (prop or {}).get("select") or {}
        return value.get("name")

    def _status(self, prop: dict[str, Any] | None) -> TaskStatus:
        value = ((prop or {}).get("status") or {}).get("name")
        try:
            return TaskStatus(value)
        except (TypeError, ValueError):
            return TaskStatus.PLANNED

    def _priority(self, prop: dict[str, Any] | None) -> Priority:
        value = ((prop or {}).get("select") or {}).get("name")
        try:
            return Priority(value)
        except (TypeError, ValueError):
            return Priority.P1

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value or len(value) <= 10:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _raise_for_status(self, response: httpx.Response, action: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._error_detail(response)
            raise IntegrationError(f"Failed to {action}: HTTP {response.status_code}. {detail}") from exc

    def _error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[:500]
        message = data.get("message") or data.get("code") or str(data)
        return str(message)[:500]
