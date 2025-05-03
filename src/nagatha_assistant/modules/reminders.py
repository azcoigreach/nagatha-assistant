"""
Reminder management: schedule and notify reminders tied to tasks, with support for recurrence.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Callable

from sqlalchemy import select, and_

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Reminder, Task


async def create_reminder(
    task_id: int,
    remind_at: datetime,
    recurrence: Optional[str] = None,
) -> int:
    """
    Create a reminder for a task. Returns reminder ID.
    Recurrence can be 'daily', 'weekly', 'monthly', or 'yearly'.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        rem = Reminder(
            task_id=task_id,
            remind_at=remind_at,
            recurrence=recurrence,
        )
        session.add(rem)
        await session.commit()
        await session.refresh(rem)
        return rem.id  # type: ignore


async def list_reminders(
    task_id: Optional[int] = None,
    delivered: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    List reminders, optionally filtering by task_id or delivered status.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(Reminder)
        filters = []
        if task_id is not None:
            filters.append(Reminder.task_id == task_id)
        if delivered is not None:
            filters.append(Reminder.delivered == delivered)
        if filters:
            stmt = stmt.where(and_(*filters))
        result = await session.execute(stmt)
        items = result.scalars().all()
        output: List[Dict[str, Any]] = []
        for rem in items:
            # Ensure remind_at is UTC-aware when formatting
            dt = rem.remind_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Ensure last_sent_at is UTC-aware if present
            ldt = rem.last_sent_at
            if ldt is not None and ldt.tzinfo is None:
                ldt = ldt.replace(tzinfo=timezone.utc)
            output.append({
                "id": rem.id,
                "task_id": rem.task_id,
                "remind_at": dt.isoformat(),
                "delivered": bool(rem.delivered),
                "recurrence": rem.recurrence,
                "last_sent_at": ldt.isoformat() if ldt else None,
            })
        return output


async def get_due_reminders() -> List[Reminder]:
    """
    Return Reminder objects that are due (remind_at <= now), not delivered, and whose task is still pending.
    """
    # Use UTC-aware current time
    now = datetime.now(timezone.utc)
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = (
            select(Reminder)
            .join(Task)
            .where(
                and_(
                    Reminder.remind_at <= now,
                    Reminder.delivered == False,  # noqa: E712
                    Task.status == 'pending',
                )
            )
        )
        result = await session.execute(stmt)
        return result.scalars().all()


async def deliver_reminder(reminder_id: int) -> None:
    """
    Mark a reminder as delivered and update last_sent_at.
    If recurrence is set, schedule the next reminder.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        rem = (await session.execute(select(Reminder).where(Reminder.id == reminder_id))).scalars().first()
        if not rem:
            return
        rem.delivered = True
        rem.last_sent_at = datetime.now()
        # Schedule next occurrence
        if rem.recurrence:
            delta = None
            if rem.recurrence == 'daily':
                delta = timedelta(days=1)
            elif rem.recurrence == 'weekly':
                delta = timedelta(weeks=1)
            elif rem.recurrence == 'monthly':
                delta = timedelta(days=30)
            elif rem.recurrence == 'yearly':
                delta = timedelta(days=365)
            if delta:
                next_time = rem.remind_at + delta
                new_rem = Reminder(
                    task_id=rem.task_id,
                    remind_at=next_time,
                    recurrence=rem.recurrence,
                )
                session.add(new_rem)
        await session.commit()


async def start_scheduler(
    notify: Callable[[Reminder], Any],
    interval: int = 60,
) -> None:
    """
    Background scheduler: every <interval> seconds, deliver due reminders by calling notify(reminder).
    """
    while True:
        due = await get_due_reminders()
        for rem in due:
            try:
                notify(rem)
                await deliver_reminder(rem.id)
            except Exception:
                # Log or ignore failures in notification
                pass
        await asyncio.sleep(interval)
        
# Alias for import compatibility
schedule_reminder = start_scheduler