import logging
from typing import Any, Dict, List

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import select

from nagatha_assistant.core.plugin import Plugin
from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Reminder

class RemindersPlugin(Plugin):
    @property
    def name(self) -> str:
        return "reminders"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def setup(self, config: Dict[str, Any]) -> None:
        # Ensure database schema is ready
        await ensure_schema()
        return None

    async def teardown(self) -> None:
        # No teardown actions needed
        return None

    def function_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "create_reminder",
                "description": "Create a reminder for a task at a given time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "remind_at": {"type": "string", "description": "ISO datetime"},
                        "recurrence": {"type": "string", "description": "daily, weekly, monthly, yearly"},
                    },
                    "required": ["task_id", "remind_at"],
                },
            },
            {
                "name": "list_reminders",
                "description": "List reminders, optionally filtered by task_id.",
                "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}}},
            },
            {
                "name": "deliver_reminder",
                "description": "Mark a reminder as delivered and schedule the next.",
                "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        logger = logging.getLogger(__name__)
        logger.debug("RemindersPlugin.call %s args=%s", name, arguments)
        await ensure_schema()
        async with SessionLocal() as session:
            # CREATE REMINDER
            if name == "create_reminder":
                task_id: int = arguments.get("task_id")
                remind_at_str: str = arguments.get("remind_at")
                remind_at = datetime.fromisoformat(remind_at_str)
                recurrence: Optional[str] = arguments.get("recurrence")
                reminder = Reminder(
                    task_id=task_id,
                    remind_at=remind_at,
                    recurrence=recurrence,
                )
                session.add(reminder)
                await session.commit()
                await session.refresh(reminder)
                return f"Created reminder {reminder.id} for task {task_id} at {remind_at.isoformat()}"

            # LIST REMINDERS
            if name == "list_reminders":
                stmt = select(Reminder)
                task_id = arguments.get("task_id")
                if task_id is not None:
                    stmt = stmt.where(Reminder.task_id == task_id)
                res = await session.execute(stmt)
                rems = res.scalars().all()
                if not rems:
                    return "No reminders found."
                lines: List[str] = []
                for r in rems:
                    delivered = 'yes' if r.delivered else 'no'
                    rec = r.recurrence or 'none'
                    lines.append(
                        f"- [{r.id}] task={r.task_id} at={r.remind_at.isoformat()} delivered={delivered} recurrence={rec}"
                    )
                return "\n".join(lines)

            # DELIVER REMINDER
            if name == "deliver_reminder":
                rid = arguments.get("id")
                stmt = select(Reminder).where(Reminder.id == rid)
                res = await session.execute(stmt)
                r = res.scalars().first()
                if not r:
                    return f"Reminder {rid} not found."
                r.delivered = True
                await session.commit()
                return f"Reminder {rid} delivered."

        raise ValueError(f"Unknown function: {name}")