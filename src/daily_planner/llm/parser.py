from __future__ import annotations

import re
from datetime import date, time

from daily_planner.llm.base import LLMParser
from daily_planner.models.plan import ParsedPlan
from daily_planner.models.task import ParsedTask, Priority, TimePreference


class RuleBasedParser(LLMParser):
    async def parse(self, raw_input: str, target_date: date | None = None) -> ParsedPlan:
        plan_date = target_date or date.today()
        chunks = [chunk.strip() for chunk in re.split(r"[;；。]\s*", raw_input) if chunk.strip()]
        tasks = [self._parse_task(chunk) for chunk in chunks] or [self._parse_task(raw_input)]
        return ParsedPlan(date=plan_date, tasks=tasks)

    def _parse_task(self, text: str) -> ParsedTask:
        duration = self._duration(text)
        priority = Priority.P1
        must_today = False
        if any(word in text for word in ("必须", "一定", "务必", "必须完成", "今天一定要做")):
            priority = Priority.P0
            must_today = True
        elif any(word in text for word in ("能做就做", "有空再做", "有空")):
            priority = Priority.P2
        elif "重点推进" in text:
            priority = Priority.P1

        earliest_start = self._after_time(text)
        fixed_start = self._fixed_time(text)
        preference = TimePreference.ANY
        if "上午" in text or "早上" in text:
            preference = TimePreference.MORNING
        elif "下午" in text:
            preference = TimePreference.AFTERNOON
        elif "晚上" in text or "夜里" in text:
            preference = TimePreference.EVENING

        title = self._clean_title(text)
        return ParsedTask(
            title=title,
            duration_minutes=duration,
            priority=priority,
            must_today=must_today,
            time_preference=preference,
            earliest_start=earliest_start,
            fixed_start=fixed_start,
            notes=text,
        )

    def _duration(self, text: str) -> int:
        if "半小时" in text or "半个小时" in text:
            return 30
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:个)?小时", text)
        if match:
            return int(float(match.group(1)) * 60)
        match = re.search(r"(\d+)\s*分钟", text)
        if match:
            return int(match.group(1))
        return 90

    def _after_time(self, text: str) -> time | None:
        if "以后" not in text and "之后" not in text:
            return None
        return self._extract_time(text)

    def _fixed_time(self, text: str) -> time | None:
        if not any(word in text for word in ("固定", "定在", "就在")):
            return None
        return self._extract_time(text)

    def _extract_time(self, text: str) -> time | None:
        match = re.search(r"(上午|早上|下午|晚上)?\s*(\d{1,2})(?:[:：点](\d{1,2})?)?", text)
        if not match:
            return None
        period, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        return time(hour=hour, minute=minute)

    def _clean_title(self, text: str) -> str:
        title = re.sub(r"\d+(?:\.\d+)?\s*(?:个)?小时", "", text)
        title = re.sub(r"\d+\s*分钟", "", title)
        title = re.sub(r"(上午|早上|下午|晚上)?\s*\d{1,2}(?:[:：点]\d{0,2})?", "", title)
        title = title.replace("半小时", "").replace("半个小时", "")
        for word in ("今天", "必须完成", "必须", "一定要做", "务必", "晚上", "以后", "之后", "固定"):
            title = title.replace(word, "")
        title = re.sub(r"\s+", "", title)
        return title.strip("，,：:；;。") or text
