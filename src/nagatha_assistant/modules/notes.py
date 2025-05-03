"""
Notes module – functions to create, retrieve, and search notes with tags.
"""
from typing import List, Optional, Dict, Any

from sqlalchemy import select, or_, distinct
from sqlalchemy.orm import joinedload
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
        # Prepare tag objects
        tag_objs = []
        if tags:
            for tag_name in tags:
                result = await session.execute(
                    select(Tag).where(Tag.name == tag_name)
                )
                tag = result.scalars().first()
                if not tag:
                    tag = Tag(name=tag_name)
                    session.add(tag)
                    await session.flush()
                tag_objs.append(tag)
        # Create note with associated tags
        note = Note(title=title, content=content, tags=tag_objs)
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
        stmt = select(Note).options(joinedload(Note.tags)).where(Note.id == note_id)
        result = await session.execute(stmt)
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
        # Start from Note with distinct to avoid duplicates when joining tags
        stmt = select(Note).distinct().options(joinedload(Note.tags))
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
        # Deduplicate in case of multiple tag matches
        note_objs = result.unique().scalars().all()
        output: List[Dict[str, Any]] = []
        for note in note_objs:
            output.append({
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "tags": [t.name for t in note.tags],
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            })
        return output