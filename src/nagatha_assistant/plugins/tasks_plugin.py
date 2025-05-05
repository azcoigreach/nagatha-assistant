import logging
from typing import Any, Dict, List

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from nagatha_assistant.core.plugin import Plugin
from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Task, Tag

class TasksPlugin(Plugin):
    @property
    def name(self) -> str:
        return "tasks"

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
                "name": "create_task",
                "description": "Create a task with title, description, optional due date, priority, and tags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "due_at": {"type": "string", "description": "ISO datetime, optional"},
                        "priority": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "list_tasks",
                "description": "List tasks with optional filters.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_task",
                "description": "Get a task by ID.",
                "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed.",
                "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
            {
                "name": "close_task",
                "description": "Mark a task as closed.",
                "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        logger = logging.getLogger(__name__)
        logger.debug("TasksPlugin.call %s args=%s", name, arguments)
        await ensure_schema()
        async with SessionLocal() as session:
            # CREATE TASK
            if name == "create_task":
                title: str = arguments.get("title")
                description: Optional[str] = arguments.get("description")
                due_at_str: Optional[str] = arguments.get("due_at")
                due_at = datetime.fromisoformat(due_at_str) if due_at_str else None
                priority: Optional[str] = arguments.get("priority")
                tags_list: List[str] = arguments.get("tags") or []
                tag_objs: List[Tag] = []
                for tag_name in tags_list:
                    res = await session.execute(select(Tag).where(Tag.name == tag_name))
                    tag = res.scalars().first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        session.add(tag)
                        await session.flush()
                    tag_objs.append(tag)
                task = Task(
                    title=title,
                    description=description,
                    due_at=due_at,
                    priority=priority,
                    tags=tag_objs,
                )
                session.add(task)
                await session.commit()
                await session.refresh(task)
                return f"Created task with ID {task.id}"

            # LIST TASKS
            if name == "list_tasks":
                stmt = select(Task).options(joinedload(Task.tags))
                res = await session.execute(stmt)
                tasks = res.unique().scalars().all()
                if not tasks:
                    return "No tasks found."
                lines: List[str] = []
                for t in tasks:
                    tags = f" [{', '.join(tag.name for tag in t.tags)}]" if t.tags else ''
                    due = f" due at {t.due_at.isoformat()}" if t.due_at else ''
                    lines.append(f"- [{t.id}] {t.title} (status={t.status}, priority={t.priority}{due}){tags}")
                return "\n".join(lines)

            # GET TASK
            if name == "get_task":
                tid = arguments.get("id")
                stmt = select(Task).options(joinedload(Task.tags)).where(Task.id == tid)
                res = await session.execute(stmt)
                t = res.scalars().first()
                if not t:
                    return f"Task {tid} not found."
                tags = f"Tags: {', '.join(tag.name for tag in t.tags)}" if t.tags else 'No tags.'
                due = t.due_at.isoformat() if t.due_at else 'No due date.'
                return (
                    f"Task {t.id}: {t.title}\n"
                    f"Description: {t.description or ''}\n"
                    f"Status: {t.status}, Priority: {t.priority}\n"
                    f"Due at: {due}\n"
                    f"{tags}"
                )

            # COMPLETE TASK
            if name == "complete_task":
                tid = arguments.get("id")
                stmt = select(Task).where(Task.id == tid)
                res = await session.execute(stmt)
                t = res.scalars().first()
                if not t:
                    return f"Task {tid} not found."
                t.status = "completed"
                await session.commit()
                return f"Task {tid} marked completed."

            # CLOSE TASK
            if name == "close_task":
                tid = arguments.get("id")
                stmt = select(Task).where(Task.id == tid)
                res = await session.execute(stmt)
                t = res.scalars().first()
                if not t:
                    return f"Task {tid} not found."
                t.status = "closed"
                await session.commit()
                return f"Task {tid} marked closed."

        raise ValueError(f"Unknown function: {name}")