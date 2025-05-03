import pytest
from datetime import datetime, timedelta, timezone

from nagatha_assistant.modules.tasks import (
    create_task,
    get_task,
    list_tasks,
    update_task,
    complete_task,
    close_task,
    search_tasks,
)


@pytest.mark.asyncio
async def test_create_get_update_complete_close_task():
    title = "Test Task"
    description = "This is a test task."
    due = datetime.now(timezone.utc) + timedelta(hours=1)
    tags = ["home", "urgent"]
    # Create
    task_id = await create_task(title, description, due, "high", tags)
    assert isinstance(task_id, int)

    # Get
    task = await get_task(task_id)
    assert task is not None
    assert task["title"] == title
    assert task["description"] == description
    assert task["priority"] == "high"
    assert set(task["tags"]) == set(tags)

    # Update
    new_desc = "Updated description"
    updated = await update_task(task_id, description=new_desc, priority="low", tags=["work"])
    assert updated
    task2 = await get_task(task_id)
    assert task2["description"] == new_desc
    assert task2["priority"] == "low"
    assert task2["tags"] == ["work"]

    # Complete
    assert await complete_task(task_id)
    comp = await get_task(task_id)
    assert comp["status"] == "completed"

    # Close
    # reset status to pending for close test
    await update_task(task_id, status="pending")
    assert await close_task(task_id)
    closed = await get_task(task_id)
    assert closed["status"] == "closed"


@pytest.mark.asyncio
async def test_list_and_search_tasks():
    # Create multiple tasks
    t1 = await create_task("Task One", "Foo bar", None, "med", ["a"])
    t2 = await create_task("Task Two", "Baz qux", None, "low", ["b"])
    # List all
    all_tasks = await list_tasks()
    ids = {t["id"] for t in all_tasks}
    assert t1 in ids and t2 in ids

    # Filter by priority
    high = await list_tasks(priority="low")
    assert all(task["priority"] == "low" for task in high)

    # Search by query
    res = await search_tasks(query="Foo")
    assert len(res) == 1 and res[0]["id"] == t1

    # Search by tags
    res2 = await search_tasks(tags=["b"])
    assert len(res2) == 1 and res2[0]["id"] == t2