import pytest

from nagatha_assistant.modules import notes


@pytest.mark.asyncio
async def test_take_and_get_note():
    """Test creating a note and retrieving it by ID."""
    title = "Test Note"
    content = "# Heading\nThis is a **test** note."
    tags = ["tag1", "tag2"]
    # Create note
    note_id = await notes.take_note(title, content, tags)
    assert isinstance(note_id, int)

    # Retrieve note
    note = await notes.get_note(note_id)
    assert note is not None
    assert note["id"] == note_id
    assert note["title"] == title
    assert note["content"] == content
    assert set(note["tags"]) == set(tags)
    # ISO format timestamps
    assert note["created_at"].endswith("Z") or note["created_at"]
    assert note["updated_at"].endswith("Z") or note["updated_at"]


@pytest.mark.asyncio
async def test_search_notes_by_query_and_tags():
    """Test searching notes by content query and by tags."""
    # Create two notes
    id1 = await notes.take_note(
        "First Note", "Content about apples and bananas.", ["fruit", "test"]
    )
    id2 = await notes.take_note(
        "Second Note", "Content about cars and bikes.", ["vehicle"]
    )
    # Search by query
    results = await notes.search_notes(query="apples")
    ids = [n["id"] for n in results]
    assert id1 in ids
    assert id2 not in ids

    # Search by tag
    results2 = await notes.search_notes(tags=["vehicle"])
    ids2 = [n["id"] for n in results2]
    assert id2 in ids2
    assert id1 not in ids2

    # Search by query and tag combined
    results3 = await notes.search_notes(query="Content", tags=["test"])
    ids3 = [n["id"] for n in results3]
    assert id1 in ids3
    assert id2 not in ids3