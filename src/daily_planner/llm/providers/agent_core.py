from __future__ import annotations

import json
from datetime import date

import httpx

from daily_planner.exceptions import ParserError
from daily_planner.llm.providers.openai_compatible import OpenAICompatibleParser
from daily_planner.models.plan import ParsedPlan


class AgentCoreParser(OpenAICompatibleParser):
    """Planner adapter for the platform LLM gateway, preserving parser normalization."""

    def __init__(self, base_url: str, model: str = "") -> None:
        super().__init__(api_key="platform", base_url=base_url, model=model)
        self.generate_url = base_url.rstrip("/") + "/v1/generate"

    async def parse(self, raw_input: str, target_date: date | None = None) -> ParsedPlan:
        prompt = self._prompt(raw_input, target_date)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.generate_url,
                    json={"messages": [{"role": "user", "content": prompt}], "model": self.model or None, "temperature": 0},
                )
                response.raise_for_status()
            return ParsedPlan.model_validate(self._normalize_payload(json.loads(response.json()["content"]), target_date))
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"Platform LLM parse failed: {exc}") from exc
