import pytest

from nagatha_assistant.modules import transcription


@pytest.mark.asyncio
async def test_transcribe_importable():
    assert hasattr(transcription, "transcribe")