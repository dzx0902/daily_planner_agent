from datetime import date

from daily_planner.config import Settings
from daily_planner.exceptions import IntegrationError
from daily_planner.models.task import Priority, Task, TaskStatus
from daily_planner.repositories.notion import NotionTaskRepository
import httpx
import pytest


def test_notion_payload_uses_data_source_parent_and_properties():
    settings = Settings(notion_api_key="secret", default_task_source="Agent")
    repo = NotionTaskRepository(settings)
    task = Task(title="测试任务", plan_date=date(2026, 7, 12), priority=Priority.P0, source="Agent", raw_input="raw")

    payload = repo.build_create_payload(task)

    assert payload["parent"]["type"] == "data_source_id"
    assert payload["parent"]["data_source_id"] == settings.notion_data_source_id
    assert payload["properties"]["任务"]["title"][0]["text"]["content"] == "测试任务"
    assert payload["properties"]["优先级"]["select"]["name"] == "P0"
    assert payload["properties"]["Calendar Event ID"]["rich_text"][0]["text"]["content"] == task.id
    assert "项目" not in payload["properties"]
    assert "结果记录" not in payload["properties"]
    assert "secret" not in str(payload)


def test_notion_page_to_task_maps_properties():
    repo = NotionTaskRepository(Settings(notion_api_key="secret"))
    task = repo._page_to_task(
        {
            "id": "notion-page-id",
            "properties": {
                "任务": {"title": [{"plain_text": "口语练习"}]},
                "计划时间": {"date": {"start": "2026-07-12T09:00:00+08:00", "end": "2026-07-12T09:30:00+08:00"}},
                "Plan Date": {"date": {"start": "2026-07-12"}},
                "状态": {"status": {"name": "Done"}},
                "优先级": {"select": {"name": "P0"}},
                "项目": {"select": {"name": "英语"}},
                "预计时长": {"number": 30},
                "必须今天": {"checkbox": True},
                "来源": {"select": {"name": "Agent"}},
                "Calendar Event ID": {"rich_text": [{"plain_text": "local-task-id"}]},
                "原始输入": {"rich_text": [{"plain_text": "raw"}]},
                "结果记录": {"rich_text": [{"plain_text": "done"}]},
            },
        }
    )

    assert task.id == "local-task-id"
    assert task.title == "口语练习"
    assert task.status == TaskStatus.DONE
    assert task.priority == Priority.P0
    assert task.start.hour == 9
    assert task.end.minute == 30


def test_notion_http_error_is_readable():
    repo = NotionTaskRepository(Settings(notion_api_key="secret"))
    response = httpx.Response(
        400,
        json={"object": "error", "code": "validation_error", "message": "来源 is expected to be select"},
        request=httpx.Request("POST", "https://api.notion.com/v1/pages"),
    )

    try:
        repo._raise_for_status(response, "create Notion page")
    except IntegrationError as exc:
        assert "HTTP 400" in str(exc)
        assert "来源 is expected" in str(exc)
    else:
        raise AssertionError("Expected IntegrationError")


@pytest.mark.asyncio
async def test_notion_request_error_is_wrapped(monkeypatch):
    repo = NotionTaskRepository(Settings(notion_api_key="secret"))

    async def fail_request(self, method, url, **kwargs):
        raise httpx.ConnectError("connect failed", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", fail_request)

    with pytest.raises(IntegrationError, match="network error"):
        await repo._request("POST", "https://api.notion.com/v1/pages", "create Notion page")


@pytest.mark.asyncio
async def test_notion_update_status_queries_by_local_task_id(monkeypatch):
    repo = NotionTaskRepository(Settings(notion_api_key="secret"))
    calls = []

    async def fake_request(method, url, action, **kwargs):
        calls.append((method, url, action, kwargs))
        if action == "find Notion task page":
            return httpx.Response(
                200,
                json={"results": [{"id": "notion-page-id"}]},
                request=httpx.Request(method, url),
            )
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    monkeypatch.setattr(repo, "_request", fake_request)

    result = await repo.update_status("local-task-id", TaskStatus.DONE)

    assert result is None
    assert calls[0][3]["json"]["filter"]["rich_text"]["equals"] == "local-task-id"
    assert calls[1][0] == "PATCH"
    assert calls[1][3]["json"]["properties"]["状态"]["status"]["name"] == "Done"


@pytest.mark.asyncio
async def test_notion_list_tasks_by_date_builds_query(monkeypatch):
    repo = NotionTaskRepository(Settings(notion_api_key="secret"))
    calls = []

    async def fake_request(method, url, action, **kwargs):
        calls.append((method, url, action, kwargs))
        return httpx.Response(200, json={"results": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(repo, "_request", fake_request)

    tasks = await repo.list_tasks_by_date(date(2026, 7, 12), TaskStatus.PLANNED)

    assert tasks == []
    query_filter = calls[0][3]["json"]["filter"]
    assert query_filter["and"][0]["date"]["equals"] == "2026-07-12"
    assert query_filter["and"][1]["status"]["equals"] == "Planned"
