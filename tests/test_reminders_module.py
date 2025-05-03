import pytest
from datetime import datetime, timedelta, timezone

from nagatha_assistant.modules.tasks import create_task
from nagatha_assistant.modules.reminders import (
    create_reminder,
    list_reminders,
    get_due_reminders,
    deliver_reminder,
)


@pytest.mark.asyncio
async def test_create_and_list_reminders():
    # Create a task
    task_id = await create_task("Task for Reminder", "Desc", None)
    now = datetime.now(timezone.utc)
    # Create reminder
    rem_id = await create_reminder(task_id, now, None)
    assert isinstance(rem_id, int)
    # List reminders
    items = await list_reminders(task_id=task_id)
    ids = [i['id'] for i in items]
    assert rem_id in ids


@pytest.mark.asyncio
async def test_due_and_deliver_reminders():
    # Create a task
    task_id = await create_task("Task for Due", "Desc", None)
    # Past reminder without recurrence
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    rem_id = await create_reminder(task_id, past, None)
    # Should be due
    due = await get_due_reminders()
    assert any(r.id == rem_id for r in due)
    # Deliver it
    await deliver_reminder(rem_id)
    # After delivery, should not appear in due
    due2 = await get_due_reminders()
    assert all(r.id != rem_id for r in due2)
    # Verify delivered flag
    items = await list_reminders(task_id=task_id)
    delivered_flags = [i['delivered'] for i in items if i['id'] == rem_id]
    assert delivered_flags == [True]


@pytest.mark.asyncio
async def test_recurring_reminder_schedules_next():
    # Create a task
    task_id = await create_task("Recurring Task", "Desc", None)
    # Reminder with daily recurrence
    base_time = datetime(2020, 1, 1, 8, 0, tzinfo=timezone.utc) - timedelta(days=1)
    rem_id = await create_reminder(task_id, base_time, 'daily')
    # Deliver it
    await deliver_reminder(rem_id)
    # After delivery, list reminders
    items = await list_reminders(task_id=task_id)
    # Should have original (delivered) and new (undelivered)
    assert len(items) >= 2
    # Find new reminder with remind_at = base_time + 1 day
    expected = base_time + timedelta(days=1)
    new_ones = [i for i in items if not i['delivered']]
    assert any(
        datetime.fromisoformat(i['remind_at']) == expected
        for i in new_ones
    )