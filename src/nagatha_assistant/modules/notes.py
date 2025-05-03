"""
Notes module – functions to create, retrieve, and search notes with tags.
"""
from typing import List, Optional, Dict, Any

from sqlalchemy import select, or_, distinct
from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Note, Tag


async def take_note(
    title: str, content: str, tags: Optional[List[str]] = None
) -> int:
    """
    Create a new note with title, markdown content, and optional list of tag names.
    Returns the new note's ID.
    """
    # Ensure DB schema is up-to-date
    await ensure_schema()
    async with SessionLocal() as session:
        note = Note(title=title, content=content)
        # Handle tags
        if tags:
            for tag_name in tags:
                # find existing tag or create new
                result = await session.execute(
                    select(Tag).where(Tag.name == tag_name)
                )
                tag = result.scalars().first()
                if not tag:
                    tag = Tag(name=tag_name)
                    session.add(tag)
                    await session.flush()
                note.tags.append(tag)
        session.add(note)
        await session.commit()
        await session.refresh(note)
        return note.id  # type: ignore


async def get_note(note_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a note by its ID. Returns a dict with keys id, title, content, tags, created_at, updated_at.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        result = await session.execute(select(Note).where(Note.id == note_id))
        note = result.scalars().first()
        if not note:
            return None
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "tags": [t.name for t in note.tags],
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        }


async def search_notes(
    query: Optional[str] = None, tags: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search notes by title/content substring and/or tags.
    Returns list of dicts with note metadata and content.
    """
    await ensure_schema()
    async with SessionLocal() as session:
        stmt = select(distinct(Note)).select_from(Note)
        # Join tags if filtering by tags
        if tags:
            stmt = stmt.join(Note.tags).where(Tag.name.in_(tags))
        # Filter by query on title or content
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(Note.title.ilike(pattern), Note.content.ilike(pattern))
            )
        result = await session.execute(stmt)
        notes = result.scalars().all()
        output: List[Dict[str, Any]] = []
        for note in notes:
            output.append({
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "tags": [t.name for t in note.tags],
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            })
        return output