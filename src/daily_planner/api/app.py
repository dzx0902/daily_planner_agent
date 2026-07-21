from __future__ import annotations

from fastapi import FastAPI

from daily_planner.api.routes import health, integrations, plans, sync, tasks

app = FastAPI(title="Daily Planner Agent", version="0.1.0")
app.include_router(health.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
