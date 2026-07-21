from datetime import date, time

import pytest

from daily_planner.llm.parser import RuleBasedParser
from daily_planner.llm.providers.openai_compatible import OpenAICompatibleParser
from daily_planner.models.plan import ParsedPlan
from daily_planner.models.task import Priority


@pytest.mark.asyncio
async def test_rule_parser_validates_common_rules():
    parsed = await RuleBasedParser().parse("今天口语练习半小时，必须完成；晚上8点以后提交报名", date(2026, 7, 12))

    assert parsed.date == date(2026, 7, 12)
    assert parsed.tasks[0].duration_minutes == 30
    assert parsed.tasks[0].priority == Priority.P0
    assert parsed.tasks[0].must_today is True
    assert parsed.tasks[1].earliest_start == time(20, 0)


def test_openai_compatible_parser_normalizes_empty_llm_fields():
    parser = OpenAICompatibleParser("key", "https://example.com", "model")
    payload = parser._normalize_payload(
        {
            "date": "2026-07-12",
            "tasks": [
                {
                    "title": "口语练习",
                    "duration_minutes": 30,
                    "priority": "P0",
                    "must_today": True,
                    "time_preference": "",
                    "earliest_start": "",
                    "latest_end": "",
                    "fixed_start": "",
                    "fixed_end": "",
                    "project": "",
                    "notes": "",
                }
            ],
        },
        date(2026, 7, 12),
    )

    validated = ParsedPlan.model_validate(payload)
    assert validated.tasks[0].time_preference == "any"
    assert validated.tasks[0].earliest_start is None
