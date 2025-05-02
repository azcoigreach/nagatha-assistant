import pytest

from nagatha_assistant.modules import tasks


@pytest.mark.asyncio
async def test_add_task_importable():
    assert hasattr(tasks, "add_task")