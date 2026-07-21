# Daily Planner Agent Upgrade Plan

This document tracks post-MVP evolution. The MVP keeps the core path independent:

Natural language input -> parser -> deterministic scheduler -> task service -> repository -> CLI/API.

## Phase 1: Scheduler Improvements

- Support recurring tasks.
- Support cross-day planning and overdue carry-over.
- Add user-defined workday templates.
- Add hard/soft constraints such as "must be continuous", "can split", and "avoid late night".
- Import busy windows from calendar providers.
- Add conflict explanations for unscheduled tasks.

## Phase 2: Review and Personal Memory

- Improve daily review tasks with richer completion statistics.
- Track estimated vs actual duration.
- Learn default duration by task category.
- Detect repeatedly postponed work.
- Generate weekly planning suggestions.

## Phase 3: Persistence and Sync

- Improve Notion read/search pagination and remote-to-local reconciliation.
- Add scheduled/background retry execution for `sync_queue`.
- Move Notion matching fully to `sync_mappings`; keep `Calendar Event ID` available for real calendar ids.
- Add conflict detection when remote tasks are manually edited.
- Keep SQLite as the local durable source for offline mode.

## Phase 4: External Adapters

- Expand AstrBot adapter from HTTP client sample to packaged plugin.
- Add Feishu bot and Feishu calendar adapter.
- Add OpenClaw desktop operation adapter.
- Add MCP server wrapper for other agents.
- Keep all adapters thin: no scheduling or persistence logic inside adapters.

## Phase 5: UI and Operations

- Add a small web UI for today view, drag reschedule, and review.
- Add API key auth and request logging with secret redaction.
- Add Docker image and healthcheck.
- Add migration scripts for schema changes.
- Add observability for parser failures, unscheduled rates, and sync errors.
