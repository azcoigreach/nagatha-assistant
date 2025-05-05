import logging
from typing import Any, Dict, List

import logging
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import Note, Tag
from nagatha_assistant.core.plugin import Plugin

class NotesPlugin(Plugin):
    @property
    def name(self) -> str:
        return "notes"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def setup(self, config: Dict[str, Any]) -> None:
        # No initial setup required
        return None

    async def teardown(self) -> None:
        # No teardown required
        return None

    def function_specs(self) -> List[Dict[str, Any]]:
        # Define functions for note management
        return [
            {
                "name": "create_note",
                "description": "Create a note with a title, content, and optional tags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "list_notes",
                "description": "List all notes.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_note",
                "description": "Get a note by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                },
            },
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        logger = logging.getLogger(__name__)
        logger.debug("NotesPlugin.call %s args=%s", name, arguments)
        await ensure_schema()
        async with SessionLocal() as session:
            # Create a new note
            if name == "create_note":
                title = arguments.get("title")
                content = arguments.get("content")
                tags = arguments.get("tags") or []
                tag_objs: List[Tag] = []
                for tag_name in tags:
                    res = await session.execute(select(Tag).where(Tag.name == tag_name))
                    tag = res.scalars().first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        session.add(tag)
                        await session.flush()
                    tag_objs.append(tag)
                note = Note(title=title, content=content, tags=tag_objs)
                session.add(note)
                await session.commit()
                await session.refresh(note)
                return f"Created note with ID {note.id}"

            # List all notes
            if name == "list_notes":
                stmt = select(Note).options(joinedload(Note.tags))
                res = await session.execute(stmt)
                notes = res.unique().scalars().all()
                if not notes:
                    return "No notes found."
                lines: List[str] = []
                for n in notes:
                    tags = ", ".join(t.name for t in n.tags) if n.tags else "no tags"
                    created = n.created_at.isoformat() if n.created_at else ""
                    updated = n.updated_at.isoformat() if n.updated_at else ""
                    lines.append(
                        f"- [{n.id}] {n.title} (tags: {tags}) created at {created} updated at {updated}"
                    )
                return "\n".join(lines)

            # Get a single note by ID
            if name == "get_note":
                note_id = arguments.get("id")
                stmt = select(Note).options(joinedload(Note.tags)).where(Note.id == note_id)
                res = await session.execute(stmt)
                n = res.scalars().first()
                if not n:
                    return f"Note {note_id} not found."
                tags = ", ".join(t.name for t in n.tags) if n.tags else "no tags"
                created = n.created_at.isoformat() if n.created_at else ""
                updated = n.updated_at.isoformat() if n.updated_at else ""
                return (
                    f"Note {n.id}: {n.title}\n"
                    f"Tags: {tags}\n"
                    f"Created at: {created}\n"
                    f"Updated at: {updated}\n"
                    f"\n{n.content}"
                )

        raise ValueError(f"Unknown function: {name}")