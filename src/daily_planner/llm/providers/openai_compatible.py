from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx

from daily_planner.exceptions import ParserError
from daily_planner.llm.base import LLMParser
from daily_planner.models.plan import ParsedPlan


class OpenAICompatibleParser(LLMParser):
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def parse(self, raw_input: str, target_date: date | None = None) -> ParsedPlan:
        if not self.api_key:
            raise ParserError("LLM API key is not configured.")
        prompt = self._prompt(raw_input, target_date)
        last_error: Exception | None = None
        for _ in range(2):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                payload = self._normalize_payload(self._decode_json_object(content), target_date)
                return ParsedPlan.model_validate(payload)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ParserError(f"LLM parse failed: {last_error}")

    def _prompt(self, raw_input: str, target_date: date | None) -> str:
        return (
            "Parse the Chinese daily planning input into JSON matching this schema: "
            "{date: YYYY-MM-DD, tasks:[{title,duration_minutes,priority,project,must_today,"
            "time_preference,earliest_start,latest_end,fixed_start,fixed_end,notes}],"
            "blocked_times:[], preferences:{}}. "
            "Use null for unknown optional fields. Never use empty strings for enum or time fields. "
            "time_preference must be one of any, morning, afternoon, evening. "
            "Times must be HH:MM:SS or null. "
            "Use P0/P1/P2. Unknown duration defaults to 90. "
            f"Target date: {target_date or date.today()}. Input: {raw_input}"
        )

    def _normalize_payload(self, payload: dict[str, Any], target_date: date | None) -> dict[str, Any]:
        payload = dict(payload)
        if not payload.get("date"):
            payload["date"] = (target_date or date.today()).isoformat()
        payload["tasks"] = [self._normalize_task(task) for task in payload.get("tasks", [])]
        payload.setdefault("blocked_times", [])
        payload.setdefault("preferences", {})
        return payload

    @staticmethod
    def _decode_json_object(content: str) -> dict[str, Any]:
        """Accept JSON returned bare or wrapped in a Markdown code fence."""
        text = content.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]

        decoder = json.JSONDecoder()
        start = text.find("{")
        if start == -1:
            raise ValueError("LLM response does not contain a JSON object")
        payload, _ = decoder.raw_decode(text[start:])
        if not isinstance(payload, dict):
            raise ValueError("LLM response JSON must be an object")
        return payload

    def _normalize_task(self, task: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(task)
        for key in ("project", "earliest_start", "latest_end", "fixed_start", "fixed_end", "notes"):
            if normalized.get(key) == "":
                normalized[key] = None
        if normalized.get("time_preference") in ("", None):
            normalized["time_preference"] = "any"
        if normalized.get("duration_minutes") in ("", None):
            normalized["duration_minutes"] = 90
        if normalized.get("priority") in ("", None):
            normalized["priority"] = "P1"
        if normalized.get("must_today") in ("", None):
            normalized["must_today"] = False
        normalized.setdefault("title", "未命名任务")
        return normalized
