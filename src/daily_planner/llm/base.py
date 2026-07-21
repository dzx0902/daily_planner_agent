from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from daily_planner.models.plan import ParsedPlan


class LLMParser(ABC):
    @abstractmethod
    async def parse(self, raw_input: str, target_date: date | None = None) -> ParsedPlan:
        raise NotImplementedError
