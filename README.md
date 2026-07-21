# Daily Planner Agent

Standalone Daily Planner Agent. It can run without AstrBot, OpenClaw, Feishu, or MCP.

Core flow:

```text
natural language -> parser -> deterministic scheduler -> task repository -> CLI / REST API
```

## Setup

```bash
cd /home/dzx0902/daily_planner_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env
```

SQLite mode is the default MVP mode:

```env
TASK_BACKEND=sqlite
SQLITE_PATH=data/daily_planner.db
LLM_PROVIDER=rule
```

## CLI

```bash
daily-planner check-config
daily-planner parse "今天口语练习30分钟，必须完成；晚上8点以后提交报名"
daily-planner schedule "今天口语练习30分钟，必须完成；晚上8点以后提交报名"
daily-planner plan "今天口语练习30分钟，必须完成；晚上8点以后提交报名"
daily-planner today
daily-planner list --date 2026-07-12
daily-planner done "口语练习"
daily-planner cancel "提交报名"
daily-planner reschedule TASK_ID --start "2026-07-12T20:00:00+08:00" --end "2026-07-12T20:30:00+08:00"
daily-planner review --date 2026-07-12
daily-planner archive-done --before 2026-07-12
daily-planner sync-queue --status failed
daily-planner sync-retry --limit 10
daily-planner clean-local --yes
```

## REST API

Start the service:

```bash
daily-planner serve
```

Development equivalent:

```bash
uvicorn daily_planner.api.app:app --reload
```

Endpoints:

```text
GET    /api/v1/health
POST   /api/v1/plans
GET    /api/v1/tasks/today
GET    /api/v1/tasks
POST   /api/v1/tasks/{task_id}/done
POST   /api/v1/tasks/{task_id}/cancel
POST   /api/v1/tasks/archive-done
PATCH  /api/v1/tasks/{task_id}/schedule
POST   /api/v1/review
GET    /api/v1/sync/queue
POST   /api/v1/sync/retry
GET    /api/v1/integrations/notion/check
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/plans \
  -H 'Content-Type: application/json' \
  -d '{"input":"今天口语练习30分钟，必须完成","user_id":"default"}'
```

## Notion

Configure:

```env
TASK_BACKEND=hybrid
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=3978473f-2546-80cd-8b11-000b260bf205
NOTION_VERSION=2025-09-03
DEFAULT_TASK_SOURCE=Agent
```

Commands:

```bash
daily-planner check-notion
daily-planner test-notion-write
```

`hybrid` mode stores tasks locally in SQLite and mirrors creates, done updates, result notes, and reschedules to Notion.

Hybrid mode keeps local sync tables:

```text
sync_mappings  # local task id -> remote provider/page id
sync_queue     # failed remote operations for inspection/retry work
```

New Notion pages also store the local task id in `Calendar Event ID`, which gives a backwards-compatible lookup key for later updates.

Use this command to inspect failed sync work:

```bash
daily-planner sync-queue --status failed
```

Retry failed sync work:

```bash
daily-planner sync-retry --limit 10
```

Pages created before sync mappings existed may not be updated automatically by `done` or `reschedule`; create new tasks after this version for full hybrid sync.

Pure `notion` mode can read tasks by date and search open tasks using Notion queries, but `hybrid` remains the recommended daily-use mode because SQLite is the local durable source.

`clean-local --yes` removes only the local SQLite database. It does not delete Notion pages.

## Review

Create a daily review summary and append it to the `今日复盘` task when it exists:

```bash
daily-planner review --date 2026-07-12
```

The review includes total tasks, completed tasks, planned tasks, canceled/archived tasks, completion rate, and unfinished P0 tasks.

## Adapters

Adapters are optional. The core package does not import AstrBot, Feishu, OpenClaw, or MCP SDKs.

The AstrBot sample is a thin HTTP client in:

```text
src/daily_planner/adapters/astrbot/client.py
```

It maps:

```text
/plan  -> POST /api/v1/plans
/today -> GET /api/v1/tasks/today
/done  -> POST /api/v1/tasks/{task_id}/done
```

Feishu, OpenClaw, and MCP directories are reserved for later adapters.

## Tests

```bash
pytest
```

The test suite covers SQLite mode, parser schema, scheduler priority and blocked windows, Notion payload/read mapping, sync retry, planner service behavior, and API health/plans.

## Upgrade Plan

See `docs/upgrade-plan.md`.
