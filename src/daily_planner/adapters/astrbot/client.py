from __future__ import annotations

import httpx


class AstrBotDailyPlannerClient:
    def __init__(self, api_base: str = "http://127.0.0.1:8000") -> None:
        self.api_base = api_base.rstrip("/")

    async def plan(self, text: str, user_id: str = "default") -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.api_base}/api/v1/plans", json={"input": text, "user_id": user_id, "source": "AstrBot"})
            response.raise_for_status()
            return response.json()

    async def today(self, user_id: str = "default") -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.api_base}/api/v1/tasks/today", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()

    async def done(self, task_id: str, user_id: str = "default") -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.api_base}/api/v1/tasks/{task_id}/done", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()
