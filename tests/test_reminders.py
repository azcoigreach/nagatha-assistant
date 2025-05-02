import pytest
from datetime import datetime

from nagatha_assistant.modules import reminders


@pytest.mark.asyncio
async def test_schedule_reminder_importable():
    assert hasattr(reminders, "schedule_reminder")