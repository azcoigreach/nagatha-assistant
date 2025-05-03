"""
Task management: create, update, list, and search tasks with tags, priorities, and statuses.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import joinedload

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Task, Tag
from sqlalchemy.orm import joinedload


async def create_task(
    title: str,
    description: Optional[str] = None,
    due_at: Optional[datetime] = None,
    priority: str = "med",
    tags: Optional[List[str]] = None,
) -> int:
    """
    Create a new task. Returns the task ID.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        # Prepare tag objects
        tag_objs = []
        if tags:
            for name in tags:
                result = await session.execute(select(Tag).where(Tag.name == name))
                tag = result.scalars().first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                    await session.flush()
                tag_objs.append(tag)
        # Create task with associated tags
        task = Task(
            title=title,
            description=description or "",
            due_at=due_at,
            priority=priority,
            tags=tag_objs
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task.id  # type: ignore


async def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a task by ID.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(Task).options(joinedload(Task.tags)).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalars().first()
        if not task:
            return None
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "tags": [t.name for t in task.tags],
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }


async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
    due_before: Optional[datetime] = None,
    due_after: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    List tasks filtered by status, priority, tags, and due date range.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(Task).options(joinedload(Task.tags))
        filters = []
        if status:
            filters.append(Task.status == status)
        if priority:
            filters.append(Task.priority == priority)
        if due_before:
            filters.append(Task.due_at <= due_before)
        if due_after:
            filters.append(Task.due_at >= due_after)
        if tags:
            stmt = stmt.join(Task.tags)
            filters.append(Tag.name.in_(tags))
        if filters:
            stmt = stmt.where(and_(*filters))
        result = await session.execute(stmt)
        tasks = result.unique().scalars().all()
        return [await get_task(t.id) for t in tasks]


async def update_task(task_id: int, **fields: Any) -> bool:
    """
    Update specified fields on a task. Returns True if updated, False if not found.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(Task).options(joinedload(Task.tags)).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalars().first()
        if not task:
            return False
        # Allowed fields
        for key in ('title', 'description', 'status', 'priority', 'due_at'):
            if key in fields and fields[key] is not None:
                setattr(task, key, fields[key])
        # Handle tags update
        if 'tags' in fields and fields['tags'] is not None:
            task.tags.clear()
            for name in fields['tags']:
                result2 = await session.execute(select(Tag).where(Tag.name == name))
                tag = result2.scalars().first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                    await session.flush()
                task.tags.append(tag)
        await session.commit()
        return True


async def complete_task(task_id: int) -> bool:
    """
    Mark a task as completed.
    """
    return await update_task(task_id, status='completed')


async def close_task(task_id: int) -> bool:
    """
    Mark a task as closed.
    """
    return await update_task(task_id, status='closed')


async def search_tasks(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search tasks by title/description substring and/or tags.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(Task).options(joinedload(Task.tags))
        conditions = []
        if query:
            pattern = f"%{query}%"
            conditions.append(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
        if tags:
            stmt = stmt.join(Task.tags)
            conditions.append(Tag.name.in_(tags))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await session.execute(stmt)
        tasks = result.unique().scalars().all()
        return [await get_task(t.id) for t in tasks]

# Alias for backward compatibility / CLI import
add_task = create_task