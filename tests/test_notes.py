import pytest

from nagatha_assistant.modules import notes


@pytest.mark.asyncio
async def test_take_note_importable():
    assert hasattr(notes, "take_note")